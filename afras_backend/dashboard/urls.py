from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='dashboard_home'),
    path('student-directory/', views.student_directory, name='student_directory'),
    path('routine-management/', views.routine_management, name='routine_management'),
]
