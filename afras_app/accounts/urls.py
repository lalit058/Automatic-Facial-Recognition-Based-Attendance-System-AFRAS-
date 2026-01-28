from django.urls import path
from . import views
from django.contrib.auth import authenticate, login, logout


urlpatterns = [
    path('register-student/', views.register_student, name='register-student'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('register-staff/', views.register_staff, name='register-staff'),
]
