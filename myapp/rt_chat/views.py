from django.shortcuts import render
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
# Create your views here.



def logout_view(request):
    logout(request)
    return redirect(reverse("rt_chat:login"))

def home(request):
    return render(request, 'rt_chat/landingpage.html')

def realtime_chat(request):
    return render(request, 'rt_chat/realtime_chat.html')