# test_scheduler_order.py
import os
import django
from datetime import time, timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'afras_app.settings')
django.setup()

from dashboard.models import Routine
from attendance.models import AttendanceSession
from attendance.scheduler import generate_sessions_from_routines

print("=" * 70)
print("🧪 TESTING SCHEDULER WITH CORRECT DAY ORDER")
print("=" * 70)

# 1. Check existing routines
print("\n📋 1. Active Routines:")
routines = Routine.objects.filter(is_active=True)
print(f"   Total: {routines.count()}")

# Display routines by day
day_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
for day in day_order:
    day_routines = routines.filter(day_of_week=day)
    count = day_routines.count()
    print(f"   📅 {day}: {count} routines")

# 2. Generate all sessions
print("\n🔄 2. Generating ALL Sessions...")
result = generate_sessions_from_routines()

print(f"   ✅ Created: {result['created_count']} sessions")
print(f"   ⏳ Existing: {result['existing_count']} sessions")

# 3. Check session distribution by day
print("\n📊 3. Session Distribution:")
today = timezone.now().date()
day_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

for day_name in day_order:
    # Find the next occurrence of this day
    days_ahead = (list(day_order).index(day_name) - today.weekday()) % 7
    if days_ahead < 0:
        days_ahead += 7
    date = today + timedelta(days=days_ahead)
    
    count = AttendanceSession.objects.filter(date=date).count()
    
    if day_name == 'Saturday':
        print(f"   📅 {day_name}: ❌ OFF ({count} sessions - should be 0)")
    else:
        icon = "✅" if count > 0 else "⚠️"
        print(f"   {icon} 📅 {day_name}: {count} sessions")

# 4. Show next 7 days
print("\n📅 4. Next 7 Days Schedule:")
for i in range(7):
    date = today + timedelta(days=i)
    day_name = date.strftime('%A')
    count = AttendanceSession.objects.filter(date=date).count()
    
    if day_name == 'Saturday':
        print(f"   {date.strftime('%a %b %d')} ({day_name}): ❌ OFF")
    else:
        active = AttendanceSession.objects.filter(date=date, is_active=True).count()
        icon = "🟢" if active > 0 else "⏳"
        print(f"   {icon} {date.strftime('%a %b %d')} ({day_name}): {count} sessions ({active} active)")

print("\n" + "=" * 70)
print("✅ Test Complete!")
print("=" * 70)