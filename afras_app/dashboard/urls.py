from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("staff-directory/", views.staff_directory, name="staff-directory"),
    path(
        "api/student/<int:student_id>/face-encoding/",
        views.get_student_face_encoding,
        name="get-face-encoding",
    ),
    path(
        "attendance/api/session-stats/",
        views.api_session_stats,
        name="api-session-stats",
    ),
    path(
        "attendance/api/recent-sessions/",
        views.api_recent_sessions,
        name="api-recent-sessions",
    ),
    path("student-directory/", views.student_directory, name="student-directory"),
    path(
        "student-profile/<int:student_id>/",
        views.student_profile,
        name="student-profile",
    ),
    path('staff-profile/<int:staff_id>/', views.staff_profile, name='staff-profile'),
    path(
        "student/<int:student_id>/details/",
        views.get_student_details,
        name="student-details",
    ),
    path("student/<int:student_id>/edit/", views.edit_student, name="edit-student"),
    path(
        "student/<int:student_id>/delete/", views.delete_student, name="delete-student"
    ),
    path("staff/<int:staff_id>/edit/", views.edit_staff, name="edit-staff"),
    path("staff/<int:staff_id>/delete/", views.delete_staff, name="delete-staff"),
    
    # System Logs
    path('system-logs/', views.system_logs_view, name='system-logs'),
    
    # Single Log Actions
    path('api/soft-delete-log/<int:log_id>/', views.soft_delete_log, name='soft_delete_log'),
    path('api/restore-log/<int:log_id>/', views.restore_log, name='restore_log'),
    path('api/permanent-delete-log/<int:log_id>/', views.permanent_delete_log, name='permanent_delete_log'),
    
    path('api/delete-log/<int:log_id>/', views.delete_single_log, name='delete_single_log'),
    
    # Bulk Actions
    path('api/bulk-soft-delete-logs/', views.bulk_soft_delete_logs, name='bulk_soft_delete_logs'),
    path('api/bulk-restore-logs/', views.bulk_restore_logs, name='bulk_restore_logs'),
    
    # Export
    path('api/export-logs/', views.export_logs, name='export_logs'),
    path('api/notifications/export/', views.export_notifications, name='export_notifications'),
    
    # Log Details
    path('api/log-details/<int:log_id>/', views.api_get_log_details, name='log_details'),
    
    path('api/active-routines/', views.active_routines_api, name='active_routines_api'),
    
    path('configuration/', views.system_configuration_view, name='system_configuration'),
    path("api/test-config/", views.test_configuration_api, name="test_configuration"),
    path("api/generate-key/", views.generate_api_key_api, name="generate_api_key"),
    path("api/system-status/", views.system_status_api, name="system_status"),
    path('routine-start-manual/', views.start_manual_session, name='start_manual_session'),
    path("routine-extract-ai/", views.extract_routine_ai, name="extract_routine_ai"),
    path('api/clear-extracted-routines/', views.clear_extracted_routines, name='clear_extracted_routines'),
    path('api/apply-extracted-routines/', views.apply_extracted_routines, name='apply_extracted_routines'),
    
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api-dashboard-stats'),
    path('api/recent-attendance/', views.api_recent_attendance, name='api-recent-attendance'),
    path('api/attendance-summary/', views.api_attendance_summary, name='api-attendance-summary'),
    path('api/export-attendance/', views.api_export_attendance, name='api-export-attendance'),
    path('api/filter-attendance/', views.api_filter_attendance, name='api-filter-attendance'),
    
    path('api/notifications/', views.api_get_notifications, name='api_notifications'),
    path('api/notifications/mark-read/<int:notification_id>/', views.api_mark_notification_read, name='api_mark_notification_read'),
    path('api/notifications/mark-all-read/', views.api_mark_all_notifications_read, name='api_mark_all_read'),
    path('api/notifications/delete/<int:notification_id>/', views.api_delete_notification, name='api_delete_notification'),
    path('api/notifications/create/', views.api_create_notification, name='api_create_notification'),
    

    # Add these to your urlpatterns

    path('notifications/', views.notifications_list, name='notifications_list'),
    path('api/notifications/all/', views.api_get_all_notifications, name='api_all_notifications'),
    path('api/notifications/test-real-time/', views.api_test_real_time_notification, name='api_test_real_time'),
    path('api/notifications/simulate-bulk/', views.api_simulate_bulk_notifications, name='api_simulate_bulk'),
    
    path('activity-logs/', views.activity_logs_view, name='activity_logs'),
    path('api/activity-logs/', views.api_activity_logs, name='api_activity_logs'),
]
