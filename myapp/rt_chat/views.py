from django.shortcuts import render
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from .forms import SignUpForm
from django.contrib.auth import login
# Create your views here.

def register(request):
    form = SignUpForm()
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request,user)
            return redirect(reverse("rt_chat:home"))
    return render(request,'rt_chat/register.html',{'form':form})

def logout_view(request):
    logout(request)
    return redirect(reverse("rt_chat:login"))

def home(request):
    return render(request, 'rt_chat/landingpage.html')

def realtime_chat(request):
    return render(request, 'rt_chat/realtime_chat.html')