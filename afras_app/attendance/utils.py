# attendance/utils.py

from datetime import timedelta, datetime
from django.utils import timezone
from dashboard.models import Routine
from attendance.models import AttendanceSession, AttendanceLog

# Days of the week (excluding Saturday)
DAYS_IN_ORDER = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']


def auto_schedule_session(session):
    """
    Auto-schedule a session by creating routines for ALL days of the week.
    Only the original session is marked as manual (is_manual=True).
    All generated sessions are marked as is_manual=False (hidden from template).
    
    Args:
        session: AttendanceSession instance
        
    Returns:
        dict: Result with created routines and sessions
    """
    results = {
        'routines_created': 0,
        'sessions_created': 0,
        'routines': [],
        'sessions': [],
        'status': 'success'
    }
    
    # Skip if already has a routine
    if session.routine:
        results['routines'].append({
            'id': session.routine.id,
            'day': session.date.strftime('%A'),
            'status': 'existing'
        })
        results['status'] = 'already_linked'
        return results
    
    # Get the day of the week from the session
    original_day = session.date.strftime('%A')
    
    print(f"\n🔄 Auto-scheduling for: {session.subject_name}")
    print(f"   Original day: {original_day}")
    print(f"   Time: {session.start_time.strftime('%I:%M %p')}")
    print(f"   Duration: {session.expected_duration} minutes")
    print("-" * 50)
    
    # For each day of the week (Sunday to Friday)
    for day_name in DAYS_IN_ORDER:
        # Skip Saturday
        if day_name == 'Saturday':
            continue
        
        # Check if routine already exists
        existing_routine = Routine.objects.filter(
            subject=session.subject_name,
            department=session.department,
            year=session.year,
            semester=session.semester,
            section=session.section or '',
            day_of_week=day_name,
            start_time=session.start_time.time()
        ).first()
        
        if existing_routine:
            # Link session to existing routine if it's the same day
            if day_name == original_day:
                session.routine = existing_routine
                session.save(update_fields=['routine'])
                results['routines'].append({
                    'id': existing_routine.id,
                    'day': day_name,
                    'status': 'existing'
                })
                print(f"   📌 {day_name}: Using existing routine #{existing_routine.id}")
            continue
        
        # Create new routine for this day
        routine = Routine.objects.create(
            subject=session.subject_name,
            department=session.department,
            year=session.year,
            semester=session.semester,
            section=session.section or '',
            day_of_week=day_name,
            start_time=session.start_time.time(),
            duration=session.expected_duration or 60,
            is_active=True
        )
        
        results['routines_created'] += 1
        results['routines'].append({
            'id': routine.id,
            'day': day_name,
            'status': 'created'
        })
        
        print(f"   ✅ {day_name}: Created routine #{routine.id}")
        
        # Link original session to its day's routine
        if day_name == original_day:
            session.routine = routine
            session.save(update_fields=['routine'])
            print(f"   🔗 Linked session #{session.id} to routine #{routine.id}")
    
    print("-" * 50)
    
    # Now generate sessions from all routines
    # IMPORTANT: These sessions will have is_manual=False (hidden)
    from attendance.scheduler import generate_sessions_from_routines
    gen_result = generate_sessions_from_routines()
    
    results['sessions_created'] = gen_result.get('created_count', 0)
    results['sessions'] = gen_result.get('created_sessions', [])
    
    print(f"\n📊 Auto-schedule Results:")
    print(f"   ✅ Routines created: {results['routines_created']}")
    print(f"   ✅ Sessions generated: {results['sessions_created']}")
    print(f"   🎯 All generated sessions are hidden (is_manual=False)")
    print(f"   📌 Only the main session will show in template (is_manual=True)")
    
    return results


def get_manual_sessions():
    """Get all manual sessions (is_manual=True)"""
    return AttendanceSession.objects.filter(is_manual=True)


def get_auto_sessions():
    """Get all auto-generated sessions (is_manual=False)"""
    return AttendanceSession.objects.filter(is_manual=False)