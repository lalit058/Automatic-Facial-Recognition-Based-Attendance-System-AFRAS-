# afras_app/attendance/urls.py

from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Session Management
    path('sessions/', views.unified_session_management, name='unified_sessions'),
    path('start/', views.start_session, name='start_session'),
    path('all/', views.all_sessions_view, name='all_sessions'),
    
    # Live Session
    path('live/<int:session_id>/', views.attendance_session_view, name='attendance_session'),
    path('mark/<int:session_id>/', views.mark_attendance, name='mark_attendance'),
    
    # Session Details & Summary
    path('details/<int:session_id>/', views.session_details, name='session_details'),
    path('summary/<int:session_id>/', views.session_summary, name='session_summary'),
    
    # Session Actions - FIXED: Removed duplicate 'attendance/' prefix
    path('delete-session/<int:session_id>/', views.delete_session, name='delete_session'),
    path('stop/<int:session_id>/', views.stop_session, name='stop_session'),
    path('end-session/<int:session_id>/', views.end_session, name='end_session'),
    path('sync-sessions/', views.sync_sessions, name='sync_sessions'),
    
    # Session Edit - FIXED: Removed duplicate 'attendance/' prefix
    path('edit-session/<int:session_id>/', views.edit_session, name='edit_session'),
    path('check-session/', views.check_session_exists, name='check_session_exists'),
    
    # Student Records
    path('student-attendance/<int:student_id>/', views.student_attendance_record, name='student_attendance_record'),
    path('records/', views.attendance_records, name='attendance_records'),
    path('attendance-report/', views.weekly_attendance_report, name='attendance_report'),
    path('attendance-report/export-csv/', views.export_attendance_report_csv, name='export_attendance_report_csv'),
    
    
    path('api/scheduler/status/', views.scheduler_status, name='scheduler_status'),
    path('api/scheduler/trigger/', views.trigger_scheduler, name='trigger_scheduler'),
    
    # Video Feeds
    path('video_feed/<int:session_id>/', views.video_feed, name='video_feed'),
    path('live/hybrid/<int:session_id>/', views.hybrid_video_feed, name='hybrid_video_feed'),
    path('video_feed_basic/', views.video_feed, name='video_feed_basic'),
    
    # APIs
    path('api/recent/', views.recent_sessions_api, name='recent_sessions_api'),
    path('api/stats/', views.session_stats_api, name='session_stats_api'),
    path('api/logs/<int:session_id>/', views.get_logs, name='get_logs'),
    path('api/student-status/<int:session_id>/', views.get_student_status, name='get_student_status'),
    path('api/attendance-stats/<int:session_id>/', views.get_attendance_stats, name='get_attendance_stats'),
    path('api/hybrid-status/', views.hybrid_status, name='hybrid_status'),
    
    # Recognition
    path('pattern/<int:log_id>/', views.attendance_pattern, name='attendance_pattern'),
    path('update-manual/', views.update_attendance_manual, name='update_attendance_manual'),
    path('manual-attendance/', views.manual_attendance, name='manual_attendance'),
    path('extract-routine/', views.extract_routine_ai, name='extract_routine_ai'),
    path('scan/', views.scan_face, name='scan_face'),
]