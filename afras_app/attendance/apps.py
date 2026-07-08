# attendance/apps.py
from django.apps import AppConfig
import os


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'

    def ready(self):
        # Only start scheduler in production, not in migrations or test
        if os.environ.get('RUN_MAIN') or os.environ.get('DJANGO_AUTORELOAD'):
            return
        
        # Don't start in test environment
        if os.environ.get('DJANGO_TEST') or 'test' in os.environ.get('DJANGO_SETTINGS_MODULE', ''):
            return
        
        try:
            from attendance.scheduler import start_scheduler
            import threading
            # Start in a separate thread to avoid blocking startup
            thread = threading.Thread(target=start_scheduler, daemon=True)
            thread.start()
            print("✅ Attendance Scheduler auto-started")
        except Exception as e:
            print(f"⚠️ Failed to start attendance scheduler: {e}")