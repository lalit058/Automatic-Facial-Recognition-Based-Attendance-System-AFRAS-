from django.urls import path
from . import views

app_name = 'attendance'
urlpatterns = [
    path('mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance-scan/', views.attendance_scan, name='attendance-scan'),
]
