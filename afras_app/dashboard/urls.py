from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('staff-directory/', views.staff_directory, name='staff-directory'),
    path('student-directory/', views.student_directory, name='student-directory'),
    path('routine-management/', views.routine_management, name='routine_management'),
    path('routine-start-manual/', views.start_manual_session, name='start_manual_session'),
    path('routine-extract-ai/', views.extract_routine_ai, name='extract_routine_ai'),
]
