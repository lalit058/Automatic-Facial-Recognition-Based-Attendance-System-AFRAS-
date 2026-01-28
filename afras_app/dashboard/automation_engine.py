import os
import django
import time
import subprocess
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'afras_backend.settings')
django.setup()

from dashboard.models import Routine

def check_and_trigger():
    now = datetime.now()
    current_day = now.strftime('%A') # e.g., 'Monday'
    current_time = now.strftime('%H:%M') # e.g., '14:30'

    print(f"[{now}] Scanning routine for {current_day} at {current_time}...")

    # Find a routine that matches the current day and time
    session = Routine.objects.filter(
        day_of_week=current_day, 
        start_time__strftime='%H:%M' = current_time,
        is_active=True
    ).first()

    if session:
        print(f"!!! MATCH FOUND: Starting {session.subject} biometric session.")
        # Trigger ResNet-101 script
        subprocess.Popen(['python', 'recognition/predict.py', '--subject', session.subject])
        # Optional: Deactivate to prevent double-triggering in the same minute
        time.sleep(61) 

if __name__ == "__main__":
    while True:
        check_and_trigger()
        time.sleep(30) # Check every 30 seconds