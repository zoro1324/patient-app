
from django.urls import path
from .views import chat_with_ai_patient

urlpatterns = [
    path('chat/<int:patient_id>/task/<int:task_id>/',chat_with_ai_patient, name='chat_with_ai_patient'),    
]
