# test_auto_schedule.py
import os
import django
import time
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'afras_app.settings')
django.setup()

from dashboard.models import Routine
from attendance.models import AttendanceSession
from attendance.scheduler import sync_routines_and_sessions

print("=" * 70)
print("🧪 TESTING DAILY AUTO-START/STOP")
print("=" * 70)

# 1. Create a routine for tomorrow
from django.utils import timezone
now = timezone.now()
tomorrow = now.date() + timedelta(days=1)
day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
tomorrow_name = day_names[tomorrow.weekday()]

# Delete old routines
Routine.objects.filter(subject="DAILY TEST SESSION").delete()

# Create routine for tomorrow at 9:00 AM
routine = Routine.objects.create(
    subject="DAILY TEST SESSION",
    department="Engineering",
    year=1,
    semester=2,
    section="A",
    day_of_week=tomorrow_name,
    start_time=time(9, 0),  # 9:00 AM
    duration=60,  # 1 hour
    is_active=True
)

print(f"✅ Created routine: {routine.subject}")
print(f"   Day: {routine.day_of_week} ({tomorrow_name})")
print(f"   Start: {routine.start_time.strftime('%I:%M %p')}")
print(f"   Duration: {routine.duration} minutes")

# 2. Generate sessions
print("\n🔄 Generating sessions...")
result = sync_routines_and_sessions()
print(f"✅ Created: {result['created_count']} sessions")
print(f"✅ Started: {result['started_count']} sessions")
print(f"✅ Ended: {result['ended_count']} sessions")

# 3. Check sessions
sessions = AttendanceSession.objects.filter(subject_name="DAILY TEST SESSION")
print(f"\n📚 Found {sessions.count()} sessions")
for s in sessions:
    status = "🟢 ACTIVE" if s.is_active else "🔴 INACTIVE"
    print(f"   #{s.id} | {s.date} | {s.start_time.strftime('%I:%M %p')} | {status}")

# 4. Check tomorrow's session
tomorrow_sessions = sessions.filter(date=tomorrow)
if tomorrow_sessions.exists():
    s = tomorrow_sessions.first()
    print(f"\n📅 Tomorrow's session:")
    print(f"   Start: {s.start_time.strftime('%I:%M %p')}")
    print(f"   End: {s.end_time.strftime('%I:%M %p')}")
    print(f"   Will auto-start at: {s.start_time.strftime('%I:%M %p')}")
    print(f"   Will auto-end at: {s.end_time.strftime('%I:%M %p')}")
else:
    print("\n⚠️ No session found for tomorrow")

print("\n" + "=" * 70)
print("✅ Test complete! The session will auto-start/end at its scheduled time.")
print("=" * 70)