# In your app's views.py (e.g., ai_therapy/views.py)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
import json
import os 
import logging 
from .models import AIPatientProfile, StudentAIPatientProgress, Messages, TaskPermission, Student, AIPatientTask 
import google.generativeai as genai
from django.db import models # <--- Add this line

logger = logging.getLogger(__name__)

# --- Updated _generate_content_with_gemini helper ---
def _generate_content_with_gemini(messages, mime_type='text/plain', temperature=0.7):
    """Helper function to encapsulate Gemini API call."""
    try:
        # It's highly recommended to store API keys in environment variables
        # or a secure configuration management system, NOT directly in code.
        api_key = "AIzaSyCFHFXcQk-m6sY4JsTcqz51YA63kld67Q8" # Your provided API key

        if not api_key:
            logger.error("GEMINI_API_KEY environment variable not set.")
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest') # Or 'gemini-1.5-pro-latest'

        response = model.generate_content(
            messages,
            generation_config=genai.types.GenerationConfig(
                response_mime_type=mime_type,
                temperature=temperature
            )
        )
        return response.text
    except Exception as e:
        logger.error(f"Error during Gemini content generation: {e}")
        raise # Re-raise to be caught by the calling view's try-except


# --- Django View for Chat ---

@login_required
def chat_with_ai_patient(request, patient_id, task_id):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        logger.error(f"User {request.user.username} is not registered as a student.")
        return HttpResponseBadRequest("You are not registered as a student.")

    ai_patient_profile = get_object_or_404(AIPatientProfile, id=patient_id)
    current_task = get_object_or_404(AIPatientTask, id=task_id, patient_profile=ai_patient_profile)

    # --- Retrieve/Create the SINGLE StudentAIPatientProgress record for this student, patient, task ---
    # This remains outside the if/else for GET/POST, as there's only one such record
    student_progress, created = StudentAIPatientProgress.objects.get_or_create(
        student=student,
        patient_profile=ai_patient_profile,
        current_task=current_task,
        # No 'is_completed' here as per your request
        # 'current_attempt_number' will be managed below for new attempts
        defaults={'current_doctor_score_for_task': 0} # Set default for initial creation if new
    )

    # --- Check Task Permissions (logic remains the same) ---
    if student.student_group:
        task_permission = TaskPermission.objects.filter(
            student_group=student.student_group,
            ai_patient_task=current_task
        ).first()

        if not task_permission or not task_permission.is_open:
            logger.warning(f"Task {current_task.title} (ID: {task_id}) for student group {student.student_group.name} is not open.")
            # If the progress record was just created for an inaccessible task, you might want to delete it.
            # However, if it's an existing one, just showing the message is fine.
            if created: # Only delete if it was just created (prevent clutter for blocked tasks)
                student_progress.delete()
            return render(request, 'ai_chat/task_not_open.html', {
                'patient_name': ai_patient_profile.name,
                'task_title': current_task.title,
                'message': "Your teacher has not yet enabled this task for your class."
            })
    else:
        logger.warning(f"Student {student.user.username} is not assigned to a student group for task permission check for task {current_task.title} (ID: {task_id}).")
        if created: # Only delete if it was just created
            student_progress.delete()
        return render(request, 'ai_chat/task_not_open.html', {
            'patient_name': ai_patient_profile.name,
            'task_title': current_task.title,
            'message': "You are not assigned to a student group that has access to this task."
        })


    # --- MAIN LOGIC FOR HANDLING ATTEMPTS AND REQUEST METHODS ---
    if request.method == 'GET':
        # On a GET request (page load or refresh), we want to start a new logical attempt.
        # Find the highest existing attempt number for this student, patient, and task from Messages.
        max_attempt_in_messages = Messages.objects.filter(
            student=student,
            bot=ai_patient_profile,
            task=current_task
        ).aggregate(max_attempt=models.Max('attempt_number'))['max_attempt']

        # Determine the new attempt number for the current session
        new_attempt_for_session = (max_attempt_in_messages or 0) + 1

        # Update the single student_progress record to reflect this new attempt
        student_progress.current_attempt_number = new_attempt_for_session
        student_progress.current_doctor_score_for_task = 0 # Reset score for new attempt
        student_progress.save() # Save the updated attempt number and reset score

        logger.info(f"Student {student.user.username} starting logical attempt {new_attempt_for_session} for task {current_task.title}.")

        # Initial mental state for the first render of a new attempt
        display_mental_state = {
            "happiness": current_task.task_happiness,
            "sadness": current_task.task_sadness,
            "anxiety": current_task.task_anxiety,
            "loneliness": current_task.task_loneliness,
            "hopefulness": current_task.task_hopefulness,
            "anger": current_task.task_anger,
            "motivation": current_task.task_motivation,
            "calmness": current_task.task_calmness,
            "fear": current_task.task_fear,
        }

        # For a new logical attempt, the chat history displayed starts empty
        current_chat_history = [] 

        context = {
            'student': student,
            'ai_patient': ai_patient_profile,
            'current_task': current_task,
            'student_progress': student_progress, # Pass the updated progress object
            'chat_history': current_chat_history, # This will be an empty list for a new attempt
            'current_mental_state': display_mental_state
        }
        return render(request, 'ai_chat/chat_interface.html', context)

    elif request.method == 'POST':
        # For a POST request, we continue with the current logical attempt
        # which is identified by student_progress.current_attempt_number that was set on GET.
        # If student_progress wasn't found (e.g., direct POST without GET first), handle error.
        if not student_progress: # This check is primarily for robustness, should not happen normally
            logger.error(f"No StudentAIPatientProgress found for POST request from {student.user.username}, patient {patient_id}, task {task_id}.")
            return JsonResponse({'error': 'No active session found. Please refresh the page to start.'}, status=404)

        user_message_content = request.POST.get('user_message', '').strip()
        if not user_message_content:
            logger.warning(f"Empty message received from student {student.user.username}.")
            return JsonResponse({'error': 'Message cannot be empty.'}, status=400)

        # --- Determine the current mental state for the LLM prompt ---
        # Get the very last AI message for THIS specific attempt
        last_ai_message = Messages.objects.filter(
            student=student,
            bot=ai_patient_profile,
            task=current_task,
            attempt_number=student_progress.current_attempt_number, # Filter by current attempt number
            ai_message__isnull=False # Ensure it's an AI message
        ).order_by('-timestamp').first()

        current_mental_state_values = {}
        if last_ai_message and last_ai_message.ai_response_metadata and 'current_mental_state' in last_ai_message.ai_response_metadata:
            # If there's a previous AI message for this attempt with mental state data, use it
            current_mental_state_values = last_ai_message.ai_response_metadata['current_mental_state']
        else:
            # Otherwise (first message in this specific attempt), use the initial mood from AIPatientTask
            current_mental_state_values = {
                "happiness": current_task.task_happiness,
                "sadness": current_task.task_sadness,
                "anxiety": current_task.task_anxiety,
                "loneliness": current_task.task_loneliness,
                "hopefulness": current_task.task_hopefulness,
                "anger": current_task.task_anger,
                "motivation": current_task.task_motivation,
                "calmness": current_task.task_calmness,
                "fear": current_task.task_fear,
            }

        message_record = Messages.objects.create(
            student=student,
            bot=ai_patient_profile,
            task=current_task,
            attempt_number=student_progress.current_attempt_number, # Associate with current attempt number
            user_message=user_message_content,
            ai_message=None,
            ai_review_feedback=None
        )

        # ... (AI Review of User Message - This part is largely independent of mood state) ...
        ai_review_feedback = None
        ai_review_raw_response_json = {}

        review_prompt = f"""
        You are an AI assistant designed to review a student's message in a therapy simulation.
        The student is interacting with a patient named {ai_patient_profile.name} who is currently experiencing:
        "{current_task.description}" (Task Goals: {current_task.student_goals})

        The patient's initial emotional state for this task was (on a scale of 0-100):
        Happiness: {current_task.task_happiness}, Sadness: {current_task.task_sadness}, Anxiety: {current_task.task_anxiety},
        Loneliness: {current_task.task_loneliness}, Hopefulness: {current_task.task_hopefulness}, Anger: {current_task.task_anger},
        Motivation: {current_task.task_motivation}, calmness: {current_task.task_calmness}, Fear: {current_task.task_fear}.

        Student's message to the patient: "{user_message_content}"

        Review the student's message based on its effectiveness in the context of a therapeutic conversation for this task.
        Consider aspects like empathy, relevance, open-endedness, and progression towards task goals.
        Provide constructive feedback and suggestions for improvement.

        Respond ONLY in JSON format, with keys: "feedback" (string), "score_suggestion" (integer, optional, e.g., 0-10 on message quality).
        Example: {{"feedback": "You've successfully validated the patient's feelings and offered support. Consider asking an open-ended question next to encourage more sharing.", "score_suggestion": 8}}
        """

        try:
            review_response_string = _generate_content_with_gemini(
                [{"role": "user", "parts": [{"text": review_prompt}]}],
                mime_type='application/json', temperature=0.2
            )
            ai_review_raw_response_json = json.loads(review_response_string)
            ai_review_feedback = ai_review_raw_response_json.get('feedback', 'No specific feedback generated.')

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error during AI message review for student '{student.user.username}' for task {task_id}: {e}. Raw response: {review_response_string if 'review_response_string' in locals() else 'N/A'}")
            ai_review_feedback = "Automatic review failed due to an internal error."
            ai_review_raw_response_json = {"error": str(e), "raw_response": review_response_string if 'review_response_string' in locals() else 'N/A'}


        # --- AI Patient's Reply (SECOND LLM CALL) ---
        ai_reply = 'I apologize, I am unable to respond at the moment.'
        new_doctor_score = student_progress.current_doctor_score_for_task # Start with current score
        task_completed_by_ai = False # From LLM, not saved to model
        llm_response_metadata = {} 

        chat_history_for_llm = []
        prior_messages = Messages.objects.filter(
            student=student,
            bot=ai_patient_profile,
            task=current_task,
            attempt_number=student_progress.current_attempt_number # Filter by current attempt number
        ).exclude(id=message_record.id).order_by('timestamp')

        for msg in prior_messages:
            if msg.user_message:
                chat_history_for_llm.append({"role": "user", "parts": [{"text": msg.user_message}]})
            if msg.ai_message:
                chat_history_for_llm.append({"role": "model", "parts": [{"text": msg.ai_message}]})
        
        chat_history_for_llm.append({"role": "user", "parts": [{"text": user_message_content}]})

        # --- Prepare mental_state for the prompt as a formatted string ---
        mental_state_str = (
            f"Happiness: {current_mental_state_values.get('happiness', 50)}\n"
            f"Sadness: {current_mental_state_values.get('sadness', 50)}\n"
            f"Anxiety: {current_mental_state_values.get('anxiety', 50)}\n"
            f"Loneliness: {current_mental_state_values.get('loneliness', 50)}\n"
            f"Hopefulness: {current_mental_state_values.get('hopefulness', 50)}\n"
            f"Anger: {current_mental_state_values.get('anger', 50)}\n"
            f"Motivation: {current_mental_state_values.get('motivation', 50)}\n"
            f"Calmness: {current_mental_state_values.get('calmness', 50)}\n"
            f"Fear: {current_mental_state_values.get('fear', 50)}"
        )

        # --- Build the patient_reply_prompt ---
        patient_reply_prompt = f"""
        You are a patient named {ai_patient_profile.name}. You are struggling with mental health issues.

        Your story:
        \"\"\"{ai_patient_profile.problem_story}\"\"\" 

        Family background:
        Father: \"\"\"{ai_patient_profile.father_story or 'Not specified'}\"\"\"
        Mother: \"\"\"{ai_patient_profile.mother_story or 'Not specified'}\"\"\"
        Sibling: \"\"\"{ai_patient_profile.sibling_story or 'Not specified'}\"\"\"
        Friends: \"\"\"{ai_patient_profile.friends_story or 'Not specified'}\"\"\"

        Your current mental state (out of 100):
        {mental_state_str}

        The doctor's current score is:
        {student_progress.current_doctor_score_for_task}

        The doctor is attempting the following task:
        Task Description: \"\"\"{current_task.description}\"\"\" 
        Task Goal: \"\"\"{current_task.student_goals}\"\"\"

        Instructions:
        - Reply emotionally as {ai_patient_profile.name}.
        - Evaluate the doctor’s message based on how well it matches the task goal and description.
        - Assign a doctor_score_change from [-5, -4, -3, -2, -1, 0, 1, 2, 3].
        - Adjust happiness, sadness, anxiety, loneliness, hopefulness, anger, motivation, calmness, fear using values from [-5 to 2], based on the doctor’s message.
        - If the total doctor_score reaches or exceeds 70, set "task_completed": true, else "task_completed": false.

        Respond ONLY in this JSON format:
        {{
        "patient_reply": "Your reply as {ai_patient_profile.name}",
        "current_mental_state": {{
            "happiness": new value,
            "sadness": new value,
            "anxiety": new value,
            "loneliness": new value,
            "hopefulness": new value,
            "anger": new value,
            "motivation": new value,
            "calmness": new value,
            "fear": new value
        }},
        "doctor_score": new value,
        "task_completed": true/false
        }}
        """

        try:
            patient_response_string = _generate_content_with_gemini(
                [{"role": "user", "parts": [{"text": patient_reply_prompt}]}, *chat_history_for_llm],
                mime_type='application/json', temperature=0.7
            )
            llm_response_metadata = json.loads(patient_response_string)
            ai_reply = llm_response_metadata.get('patient_reply', ai_reply)
            new_doctor_score = llm_response_metadata.get('doctor_score', new_doctor_score)
            task_completed_by_ai = llm_response_metadata.get('task_completed', task_completed_by_ai)
            
            # --- Update current_mental_state_values with new values from LLM for frontend and next prompt ---
            if 'current_mental_state' in llm_response_metadata:
                 for mood_key, mood_value in llm_response_metadata['current_mental_state'].items():
                     if mood_key in current_mental_state_values:
                         current_mental_state_values[mood_key] = mood_value

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error during AI patient response for student '{student.user.username}' for task {task_id}: {e}. Raw response: {patient_response_string if 'patient_response_string' in locals() else 'N/A'}")
            llm_response_metadata = {"error": str(e), "raw_response": patient_response_string if 'patient_response_string' in locals() else 'N/A'}


        # Update the Messages record created earlier with AI's reply and review data
        message_record.ai_message = ai_reply
        message_record.ai_response_metadata = llm_response_metadata # Save the full LLM JSON here!
        message_record.ai_review_feedback = ai_review_feedback
        message_record.ai_review_raw_response = ai_review_raw_response_json
        message_record.save()

        # Update student's doctor score for the current attempt
        student_progress.current_doctor_score_for_task = new_doctor_score
        student_progress.save()

        # Return a JSON response for AJAX-based chat
        return JsonResponse({
            'user_message': user_message_content,
            'ai_message': ai_reply,
            'ai_review_feedback': ai_review_feedback,
            'new_doctor_score': new_doctor_score,
            'task_completed_by_ai': task_completed_by_ai, # Still return this, but not stored on model
            'current_task_title': current_task.title,
            'current_attempt': student_progress.current_attempt_number,
            'patient_name': ai_patient_profile.name,
            'current_mental_state': current_mental_state_values
        })
    
print("hello world")