# attendance/apps.py

from django.apps import AppConfig
import os
import threading
import time


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'

    def ready(self):
        # Skip in test environment
        if os.environ.get('DJANGO_TEST') or 'test' in os.environ.get('DJANGO_SETTINGS_MODULE', ''):
            return
        
        # Skip in migrations
        if 'makemigrations' in os.environ.get('DJANGO_COMMAND', '') or 'migrate' in os.environ.get('DJANGO_COMMAND', ''):
            return
        
        # Only start in main process (not autoreload)
        if os.environ.get('DJANGO_AUTORELOAD') and os.environ.get('RUN_MAIN') != 'true':
            return
        
        # Start scheduler after a short delay to ensure everything is loaded
        def start_scheduler_with_delay():
            time.sleep(3)  # Wait for Django to fully initialize
            try:
                from attendance.scheduler import start_scheduler
                start_scheduler()
                print("✅ Attendance Scheduler auto-started from app")
            except Exception as e:
                print(f"⚠️ Failed to start scheduler: {e}")
        
        thread = threading.Thread(target=start_scheduler_with_delay, daemon=True)
        thread.start()