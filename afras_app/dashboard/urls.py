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
    path("system-logs/", views.system_logs_view, name="system-logs"),
    path("routine-management/", views.routine_management, name="routine_management"),
    path('configuration/', views.system_configuration_view, name='system_configuration'),
    path("api/test-config/", views.test_configuration_api, name="test_configuration"),
    path("api/generate-key/", views.generate_api_key_api, name="generate_api_key"),
    path("api/system-status/", views.system_status_api, name="system_status"),
    path(
        "routine-start-manual/", views.start_manual_session, name="start_manual_session"
    ),
    path("routine-extract-ai/", views.extract_routine_ai, name="extract_routine_ai"),
]
