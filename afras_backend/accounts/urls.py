from django.urls import path
from . import views
from django.contrib.auth import authenticate, login, logout

urlpatterns = [
    path('register/', views.register_student, name='register_student'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('register_staff/', views.register_staff, name='register_staff'),
    path('directory-staff/', views.staff_directory, name='staff_directory'),
]
