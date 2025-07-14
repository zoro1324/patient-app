
from django.urls import path
from django.contrib.auth.views import LoginView
from . import views

app_name = 'rt_chat'

urlpatterns = [
    path('login/', LoginView.as_view(template_name='rt_chat/login.html'), name='login'),
    path('logout/',views.logout_view,name="logout"),
    path('', views.home, name='home'),
    PATH('register/', views.register, name='register'),
]
