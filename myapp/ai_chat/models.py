# models.py

from django.db import models
from django.contrib.auth.models import User # Using Django's built-in User model
from django.core.validators import MinValueValidator, MaxValueValidator
import json # For JSONField default if needed, though usually not directly in model definition

# --- Core User and Organizational Models ---

class Institution(models.Model):
    """
    Represents an educational institution (e.g., a university, college).
    Institutions buy credentials from your platform.
    """
    name = models.CharField(max_length=200, unique=True,
                            help_text="The official name of the institution.")
    address = models.TextField(blank=True, null=True,
                               help_text="Physical address of the institution.")
    contact_person = models.CharField(max_length=100, blank=True, null=True,
                                     help_text="Main contact person at the institution.")
    license_key = models.CharField(max_length=255, unique=True, blank=True, null=True,
                                  help_text="Unique key provided to the institution for access.")
    is_active = models.BooleanField(default=True,
                                   help_text="Whether this institution's access is currently active.")

    class Meta:
        verbose_name = "Institution"
        verbose_name_plural = "Institutions"

    def __str__(self):
        return self.name

class Teacher(models.Model):
    """
    Represents a teacher associated with an institution.
    Teachers supervise student activities and manage task permissions.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile',
                                help_text="The associated Django User account for this teacher.")
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='teachers',
                                    help_text="The institution this teacher belongs to.")
    # Add any other teacher-specific fields like specialization, employee ID, etc.
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    specialization = models.CharField(max_length=100, blank=True, null=True)


    class Meta:
        verbose_name = "Teacher"
        verbose_name_plural = "Teachers"

    def __str__(self):
        return self.user.get_full_name() or self.user.username

class StudentGroup(models.Model):
    """
    Represents a class or a specific group of students within an institution.
    Teachers are assigned to these groups, and tasks can be opened/closed per group.
    """
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='student_groups',
                                    help_text="The institution this student group belongs to.")
    name = models.CharField(max_length=100,
                            help_text="Name of the class or student group (e.g., 'Psychology 101 - Fall 2024').")
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True,
                                help_text="The teacher primarily in charge of this student group.")
    # Add any other group-specific fields like semester, year, etc.
    
    class Meta:
        verbose_name = "Student Group (Class)"
        verbose_name_plural = "Student Groups (Classes)"
        unique_together = ('institution', 'name') # A group name should be unique within an institution

    def __str__(self):
        return f"{self.name} ({self.institution.name})"

class Student(models.Model):
    """
    Represents a student associated with an institution and a student group.
    Students are the primary users interacting with AI patients.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile',
                                help_text="The associated Django User account for this student.")
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='students',
                                    help_text="The institution this student belongs to.")
    student_group = models.ForeignKey(StudentGroup, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='students_in_group',
                                     help_text="The student group/class this student belongs to.")
    # Add any other student-specific fields like student ID, program, etc.
    student_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    program_of_study = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"

    def __str__(self):
        return self.user.get_full_name() or self.user.username

# --- AI Patient and Task Models ---

class AIPatientProfile(models.Model):
    """
    Defines the core, static profile of an AI patient (e.g., 'Alice', 'Bob').
    This acts as a template for different patient scenarios.
    """
    name = models.CharField(max_length=50, unique=True,
                            help_text="Unique name for this AI patient (e.g., 'Alice', 'Bob').")
    description = models.TextField(
        help_text="A brief overview or summary of the AI patient's background/situation."
    )
    problem_story = models.TextField(help_text="The core narrative or presenting problem of the AI patient.")
    
    # Background stories for context, used to enrich the AI's persona
    father_story = models.TextField(blank=True, null=True, help_text="Optional: Story related to the father.")
    mother_story = models.TextField(blank=True, null=True, help_text="Optional: Story related to the mother.")
    sibling_story = models.TextField(blank=True, null=True, help_text="Optional: Story related to siblings.")
    friends_story = models.TextField(blank=True, null=True, help_text="Optional: Story related to friends.")
    
    image = models.ImageField(upload_to='ai_images/', null=True, blank=True,
                              help_text="Optional: An image representing the AI patient.")

    class Meta:
        verbose_name = "AI Patient Profile"
        verbose_name_plural = "AI Patient Profiles"

    def __str__(self):
        return self.name

class AIPatientTask(models.Model):
    """
    Defines distinct "tasks" or progression stages for an AI patient.
    Each task has a fixed emotional state for the AI for that task.
    """
    patient_profile = models.ForeignKey(AIPatientProfile, on_delete=models.CASCADE, related_name='tasks',
                                        help_text="The AI patient this task belongs to.")
    task_number = models.PositiveIntegerField(
        help_text="Order of the task for this patient (e.g., 1, 2, 3...).")
    title = models.CharField(max_length=100,
                            help_text="Short title for this task (e.g., 'Build Rapport', 'Explore Trauma').")
    description = models.TextField(
        help_text="Detailed description of what the student needs to achieve in this task. Shown to the student.")
    student_goals = models.TextField(blank=True, null=True,
                                     help_text="JSON list of specific objectives for the student to fulfill for this task (for internal evaluation).")

    # These are the *fixed emotional values* for the AI patient *when they are in this specific task*.
    # These will be passed to the LLM for every message when this task is active.
    task_happiness = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=50)
    task_sadness = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=50)
    task_anxiety = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=50)
    task_loneliness = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=50)
    task_hopefulness = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=50)
    task_anger = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=50)
    task_motivation = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=50)
    task_calmness = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=50)
    task_fear = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=50)
    
    class Meta:
        ordering = ['task_number'] # Ensure tasks are ordered correctly
        unique_together = ('patient_profile', 'task_number') # Each patient has unique task numbers
        verbose_name = "AI Patient Task"
        verbose_name_plural = "AI Patient Tasks"

    def __str__(self):
        return f"{self.patient_profile.name} - Task {self.task_number}: {self.title}"

# --- Student Progress and Permissions ---

class StudentAIPatientProgress(models.Model):
    """
    Tracks a specific student's *active* progress through an AI patient's tasks.
    This holds the live state (current task, current attempt number, current session score).
    There should only be ONE such record for a given student-patient_profile pair at any time.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE,
                                help_text="The student who is progressing through this AI patient's tasks.")
    patient_profile = models.ForeignKey(AIPatientProfile, on_delete=models.CASCADE,
                                        help_text="The AI patient whose tasks the student is attempting.")
    
    current_task = models.ForeignKey(AIPatientTask, on_delete=models.SET_NULL, null=True, blank=True,
                                     help_text="The current task the student is on for this AI patient. Null if all tasks completed or no task started.")
    
    current_attempt_number = models.PositiveIntegerField(default=1,
                                                         help_text="The current attempt number for the active task. This corresponds to an entry in StudentTaskAttempt.")

    current_doctor_score_for_task = models.IntegerField(default=0,
                                                        validators=[MinValueValidator(0), MaxValueValidator(100)],
                                                        help_text="Student's performance score for the current attempt on the current task (0-100). Resets per task attempt.")

    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'patient_profile') # A student has one active progress record per AI patient
        verbose_name = "Student AI Patient Progress"
        verbose_name_plural = "Student AI Patient Progresses"

    def __str__(self):
        task_info = f"Task {self.current_task.task_number}" if self.current_task else "No current task"
        return f"{self.student.user.username}'s progress with {self.patient_profile.name} on {task_info} (Attempt {self.current_attempt_number})"

    def start_new_attempt_for_current_task(self):
        """
        Increments the attempt number for the current task and resets the score.
        Call this if a student explicitly wants to retry the current task.
        A new StudentTaskAttempt record should be created for this new attempt.
        """
        if self.current_task:
            self.current_attempt_number += 1
            self.current_doctor_score_for_task = 0 
            self.save()
            return True
        return False


class StudentTaskAttempt(models.Model):
    """
    Records each distinct attempt a student makes on a specific AI Patient Task,
    including its final state (score, completed/not completed, timestamps).
    This model provides a comprehensive history of all task attempts.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='task_attempts')
    patient_profile = models.ForeignKey(AIPatientProfile, on_delete=models.CASCADE, related_name='task_attempts_patient')
    task = models.ForeignKey(AIPatientTask, on_delete=models.CASCADE, related_name='attempts')
    
    attempt_number = models.PositiveIntegerField(
        help_text="The sequential number of this attempt for the given student and task."
    )
    
    final_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
        help_text="The final score achieved for this attempt (0-100)."
    )
    
    is_completed = models.BooleanField(
        default=False,
        help_text="True if the task completion criteria were met in this attempt."
    )
    
    start_time = models.DateTimeField(auto_now_add=True,
                                      help_text="Timestamp when this attempt started.")
    end_time = models.DateTimeField(null=True, blank=True,
                                    help_text="Timestamp when this attempt ended (e.g., task completed, or new attempt started).")

    class Meta:
        ordering = ['start_time'] # Order attempts chronologically
        unique_together = ('student', 'task', 'attempt_number') # Ensures a unique record for each specific attempt
        verbose_name = "Student Task Attempt"
        verbose_name_plural = "Student Task Attempts"

    def __str__(self):
        status = "Completed" if self.is_completed else "Not Completed"
        return (f"{self.student.user.username} - {self.patient_profile.name} "
                f"Task '{self.task.title}' Attempt {self.attempt_number}: {status} (Score: {self.final_score})")


class TaskPermission(models.Model):
    """
    Controls which AI Patient Tasks are currently accessible for students in a specific StudentGroup.
    Managed by teachers.
    """
    student_group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, related_name='task_permissions',
                                     help_text="The student group/class for which this permission applies.")
    ai_patient_task = models.ForeignKey(AIPatientTask, on_delete=models.CASCADE, related_name='permissions',
                                         help_text="The specific AI Patient Task being controlled.")
    
    is_open = models.BooleanField(default=False,
                                  help_text="True if this task is currently open for students in this group.")
    
    opened_at = models.DateTimeField(null=True, blank=True,
                                      help_text="Timestamp when the task was opened for this group.",auto_now_add=True)
    opened_by_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True,
                                          help_text="The teacher who opened this task for the group.")

    class Meta:
        unique_together = ('student_group', 'ai_patient_task') # A group can only have one permission setting for a task.
        verbose_name = "Task Permission"
        verbose_name_plural = "Task Permissions"

    def __str__(self):
        status = "Open" if self.is_open else "Closed"
        return f"{self.ai_patient_task.title} for {self.student_group.name}: {status}"

# --- Chat Log Model ---

class Messages(models.Model):
    """
    Stores each conversational turn (student message + AI reply).
    """
    bot = models.ForeignKey('AIPatientProfile', on_delete=models.CASCADE, related_name='messages_received',
                            help_text="The AI patient profile involved in this message turn.")
    
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='messages_sent',
                                help_text="The student who sent the message in this turn.")
    
    task = models.ForeignKey('AIPatientTask', on_delete=models.CASCADE, related_name='messages_logged',
                             help_text="The AI patient task active during this message turn.")
    
    attempt_number = models.PositiveIntegerField(
        help_text="The attempt number for this message within the given task.")

    user_message = models.TextField(null=True, blank=True, help_text="The message sent by the student.")
    ai_message = models.TextField(null=True, blank=True, help_text="The reply generated by the AI patient.")
    
    ai_review_feedback = models.TextField(null=True, blank=True,
                                          help_text="AI's automated textual review/feedback on the user's message.")
    ai_review_raw_response = models.JSONField(null=True, blank=True,
                                               help_text="Raw JSON response from the AI reviewer model (for debugging).")

    timestamp = models.DateTimeField(auto_now_add=True, help_text="Timestamp of this message turn.")

    ai_response_metadata = models.JSONField(
        null=True, blank=True, 
        help_text="Raw JSON metadata from the AI's response (e.g., score, task_completed flag). This contains what the LLM *suggested*."
    )

    class Meta:
        ordering = ['timestamp']
        verbose_name = "Message Turn"
        verbose_name_plural = "Message Turns"

    def __str__(self):
        return f"Turn {self.attempt_number} ({self.student.user.username} - {self.bot.name}, Task {self.task.task_number if self.task else 'N/A'}): {self.user_message[:30]}... / {self.ai_message[:30]}..."

# --- Reporting Model ---

class Report(models.Model):
    """
    Allows students or teachers to report issues with chat messages or sessions.
    Teachers can receive notifications for these reports.
    """
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_issues',
                                help_text="The user who filed this report.")
    
    reported_message = models.ForeignKey(Messages, on_delete=models.SET_NULL, null=True, blank=True,
                                         help_text="The specific message turn being reported (optional, if reporting a whole session).")
    
    reported_student_progress = models.ForeignKey(StudentAIPatientProgress, on_delete=models.SET_NULL, null=True, blank=True,
                                                  help_text="The student progress session being reported (e.g., if issue is with overall session behavior).")
    
    reason = models.TextField(help_text="Detailed reason for the report.")
    
    timestamp = models.DateTimeField(auto_now_add=True, help_text="When the report was filed.")
    
    is_resolved = models.BooleanField(default=False, help_text="Whether this report has been reviewed and resolved.")
    resolved_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text="The teacher who resolved this report.")
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="When the report was resolved.")

    class Meta:
        ordering = ['-timestamp'] # Latest reports first
        verbose_name = "Report"
        verbose_name_plural = "Reports"

    def __str__(self):
        return f"Report by {self.reporter.username} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"