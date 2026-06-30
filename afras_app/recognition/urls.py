# recognition/urls.py
from django.urls import path
from . import views

app_name = 'recognition'

urlpatterns = [
    # Scan face view with optional session_id
    path('scan/', views.scan_face, name='scan'),
    path('scan/<int:session_id>/', views.scan_face, name='scan_with_session'),
    
    # Video feed with optional session_id for filtering
    path('video_feed/', views.video_feed, name='video_feed'),
    path('video_feed/<int:session_id>/', views.video_feed, name='video_feed_filtered'),
    
    # API endpoints for attendance marking with semester filter
    path('mark-attendance/<int:session_id>/', 
         views.mark_attendance_with_semester_filter, 
         name='mark_attendance_filtered'),
    
    path('api/semester-students/', 
         views.get_semester_students_api, 
         name='get_semester_students'),
    
    path('api/semester-stats/', 
         views.get_semester_stats, 
         name='get_semester_stats'),
]