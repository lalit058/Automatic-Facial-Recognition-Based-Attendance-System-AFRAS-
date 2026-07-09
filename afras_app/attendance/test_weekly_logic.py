# test_weekly_logic.py
import os
import django
from datetime import datetime, timedelta
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'afras_app.settings')
django.setup()

from attendance.scheduler import get_next_session_date, generate_sessions_from_routines
from dashboard.models import Routine
from attendance.models import AttendanceSession
from django.utils import timezone

def test_weekly_logic():
    print("="*70)
    print("📅 TESTING WEEKLY ATTENDANCE LOGIC")
    print("="*70)
    
    # 1. Test get_next_session_date for each day
    print("\n🔍 Testing get_next_session_date()")
    print("-"*50)
    
    today = timezone.now().date()
    print(f"Today: {today} ({today.strftime('%A')})")
    
    day_map = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
        'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    
    # Mock routine class
    class MockRoutine:
        def __init__(self, day, start_time):
            self.day_of_week = day
            self.start_time = start_time
    
    for day_name in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Sunday']:
        # Mock routine with start time at 10:00 AM
        routine = MockRoutine(day_name, timezone.now().time().replace(hour=10, minute=0))
        next_date = get_next_session_date(routine, today)
        
        if next_date:
            days_delta = (next_date - today).days
            print(f"  {day_name}: Next on {next_date} ({next_date.strftime('%A')}) - in {days_delta} days")
        else:
            print(f"  {day_name}: No date found")
    
    # 2. Test with actual routines
    print("\n📋 Checking Active Routines")
    print("-"*50)
    
    routines = Routine.objects.filter(is_active=True)
    print(f"Active routines: {routines.count()}")
    
    for routine in routines:
        day = routine.day_of_week
        if isinstance(day, int):
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_name = day_names[day] if day < len(day_names) else 'Unknown'
        else:
            day_name = day
        
        next_date = get_next_session_date(routine, today)
        print(f"  {routine.subject}: {day_name} at {routine.start_time}")
        if next_date:
            print(f"    → Next session: {next_date} ({next_date.strftime('%A')})")
        else:
            print(f"    → No next session")
    
    # 3. Test weekly generation
    print("\n🔄 Testing Weekly Session Generation")
    print("-"*50)
    
    result = generate_sessions_from_routines()
    
    print(f"✅ Created: {result['created_count']} sessions")
    print(f"📌 Existing: {result['existing_count']} sessions")
    print(f"⚠️ Errors: {len(result.get('errors', []))}")
    
    # 4. Show generated sessions grouped by week
    print("\n📊 Generated Sessions by Week")
    print("-"*50)
    
    sessions = AttendanceSession.objects.filter(
        date__gte=today,
        date__lte=today + timedelta(days=30)
    ).order_by('date', 'start_time')
    
    # Group by week
    weeks = {}
    for session in sessions:
        week_num = session.date.isocalendar()[1]
        year = session.date.year
        week_key = f"{year}-W{week_num:02d}"
        
        if week_key not in weeks:
            weeks[week_key] = []
        weeks[week_key].append(session)
    
    for week_key, week_sessions in sorted(weeks.items()):
        print(f"\n  📅 Week: {week_key}")
        for session in week_sessions:
            day = session.date.strftime('%A')
            print(f"    {session.date} ({day}) - {session.subject_name} at {session.start_time.strftime('%I:%M %p')}")
    
    # 5. Check weekly pattern
    print("\n📈 Weekly Pattern Analysis")
    print("-"*50)
    
    # Get all sessions for next 30 days
    sessions_30 = AttendanceSession.objects.filter(
        date__gte=today,
        date__lte=today + timedelta(days=30)
    )
    
    # Count by day of week
    day_counts = {}
    for session in sessions_30:
        day_name = session.date.strftime('%A')
        day_counts[day_name] = day_counts.get(day_name, 0) + 1
    
    print("Sessions by day (next 30 days):")
    for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
        count = day_counts.get(day, 0)
        bar = "█" * (count // 2) if count > 0 else " "
        print(f"  {day:10} : {count:2} sessions {bar}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    test_weekly_logic()