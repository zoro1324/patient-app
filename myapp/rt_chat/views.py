from django.shortcuts import render
from django.contrib.auth import logout
# Create your views here.

def logout_view(request):
    logout(request)
    return render(request, 'rt_chat/logout.html')


def realtime_chat(request):

    return render(request, 'rt_chat/realtime_chat.html')