from django.urls import path
from . import views

urlpatterns = [
    # Session management
    path("start/", views.start_session, name="start_session"),
    path(
        "live/<int:session_id>/", views.attendance_session_view, name="live_monitoring"
    ),
    path("video-feed/<int:session_id>/", views.video_feed, name="video_feed"),
    path("session/<int:session_id>/stop/", views.stop_session, name="stop_session"),
    path("api/extract-routine/", views.extract_routine_ai, name="extract_routine_ai"),
    # Manual attendance updates
    path("manual-update/", views.update_attendance_manual, name="manual_update"),
    path("get-logs/<int:session_id>/", views.get_logs, name="get_logs"),
    path(
        "session-summary/<int:session_id>/",
        views.session_summary,
        name="session_summary",
    ),
    # API endpoints for dashboard - WITHOUT /attendance prefix
    path("api/recent-sessions/", views.recent_sessions_api, name="recent-sessions-api"),
    path("api/session-stats/", views.session_stats_api, name="session-stats-api"),
    # Dashboard routes
    path(
        "dashboard/routine-start-manual/",
        views.start_session,
        name="routine-start-manual",
    ),
]
