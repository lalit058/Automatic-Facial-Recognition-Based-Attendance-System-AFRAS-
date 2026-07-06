from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Session Management
    path('start/', views.start_session, name='start_session'),
    path('all/', views.all_sessions_view, name='all_sessions'),
    path('live/<int:session_id>/', views.attendance_session_view, name='attendance_session'),
    path('mark/<int:session_id>/', views.mark_attendance, name='mark_attendance'),
    path('details/<int:session_id>/', views.session_details, name='session_details'),
    path('summary/<int:session_id>/', views.session_summary, name='session_summary'),
    path('api/delete-session/<int:session_id>/', views.delete_session, name='delete_session'),
    path('stop/<int:session_id>/', views.stop_session, name='stop_session'),
    path('end-session/<int:session_id>/', views.end_session, name='end_session'),  # New endpoint
    
    # Attendance records
    path('student-attendance/<int:student_id>/', views.student_attendance_record, name='student_attendance_record'),
    path('records/', views.attendance_records, name='attendance_records'),
    
    # Update the URL patterns
    path('attendance-report/', views.weekly_attendance_report, name='attendance_report'),
    path('attendance-report/export-csv/', views.export_attendance_report_csv, name='export_attendance_report_csv'),
    
    # Video Feeds
    path('video_feed/<int:session_id>/', views.hybrid_video_feed, name='video_feed'),
    path('live/hybrid/<int:session_id>/', views.hybrid_video_feed, name='hybrid_video_feed'),
    path('video_feed_basic/', views.video_feed, name='video_feed_basic'),
    
    # API Endpoints
    path('api/recent/', views.recent_sessions_api, name='recent_sessions_api'),
    path('api/stats/', views.session_stats_api, name='session_stats_api'),
    path('api/logs/<int:session_id>/', views.get_logs, name='get_logs'),
    path('api/student-status/<int:session_id>/', views.get_student_status, name='get_student_status'),
    path('api/attendance-stats/<int:session_id>/', views.get_attendance_stats, name='get_attendance_stats'),
    path('api/hybrid-status/', views.hybrid_status, name='hybrid_status'),
    
    # Pattern View
    path('pattern/<int:log_id>/', views.attendance_pattern, name='attendance_pattern'),
    
    # Manual Update
    path('update-manual/', views.update_attendance_manual, name='update_attendance_manual'),
    path('manual-attendance/', views.manual_attendance, name='manual_attendance'),
    
    # File Extraction
    path('extract-routine/', views.extract_routine_ai, name='extract_routine_ai'),
    
    # Face Scan
    path('scan/', views.scan_face, name='scan_face'),
]