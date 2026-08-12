# attendance/scheduler.py - Complete updated version with correct day order

from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from dashboard.models import Routine
from .models import AttendanceSession, AttendanceLog
from accounts.models import Student
import logging
import threading
import time
from .views import get_local_time

logger = logging.getLogger(__name__)


# ============================================================
# DAYS OF THE WEEK (Excluding Saturday)
# Order: Sunday, Monday, Tuesday, Wednesday, Thursday, Friday
# ============================================================
DAYS_IN_ORDER = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
DAY_MAP = {
    'Sunday': 0, 'Monday': 1, 'Tuesday': 2,
    'Wednesday': 3, 'Thursday': 4, 'Friday': 5, 'Saturday': 6
}
# Note: In Python's weekday(), Monday=0, Tuesday=1, ..., Sunday=6
# So Sunday maps to 6 in weekday(), but we want it first in display order


def get_day_display_order(day_name):
    """Get the display order for a day (0-6)"""
    order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    try:
        return order.index(day_name)
    except ValueError:
        return 999


def get_next_session_for_subject(subject, today, current_time):
    """
    Get the next session date for a subject based on its routines.
    Returns the next occurrence (today, tomorrow, or next week).
    """
    from datetime import datetime
    from dashboard.models import Routine
    from .models import AttendanceSession
    
    # Get ALL routines for this subject
    routines = Routine.objects.filter(subject=subject, is_active=True).order_by('day_of_week')
    
    if not routines.exists():
        # If no routines, find the next actual session
        future_sessions = AttendanceSession.objects.filter(
            subject_name=subject,
            start_time__gt=current_time
        ).order_by('start_time')
        
        if future_sessions.exists():
            next_future = future_sessions.first()
            next_future_local = get_local_time(next_future.start_time)
            next_date = next_future.date
            
            return {
                'date': next_date.strftime('%Y-%m-%d'),
                'day': next_date.strftime('%A'),
                'time': next_future_local.strftime('%I:%M %p').lstrip('0'),
                'is_today': (next_date == today),
                'is_tomorrow': (next_date == today + timedelta(days=1)),
                'is_current': (next_date == today and next_future.start_time <= current_time)
            }
        return None
    
    # Find the next session from routines
    next_session = None
    min_days_ahead = None
    
    for routine in routines:
        next_date = get_next_session_date(routine, today)
        
        if next_date:
            days_ahead = (next_date - today).days
            
            # Skip if days_ahead is None or negative
            if days_ahead is None or days_ahead < 0:
                continue
            
            # Choose the earliest session
            if min_days_ahead is None or days_ahead < min_days_ahead:
                min_days_ahead = days_ahead
                
                next_start = timezone.make_aware(
                    datetime.combine(next_date, routine.start_time)
                )
                next_local = get_local_time(next_start)
                
                is_current = (next_date == today and next_start <= current_time)
                
                next_session = {
                    'date': next_date.strftime('%Y-%m-%d'),
                    'day': next_date.strftime('%A'),
                    'time': next_local.strftime('%I:%M %p').lstrip('0'),
                    'is_today': (next_date == today),
                    'is_tomorrow': (next_date == today + timedelta(days=1)),
                    'is_current': is_current,
                    'days_ahead': days_ahead
                }
    
    return next_session

def get_next_session_date(routine, from_date=None):
    """
    Get the next session date for a routine after the given date
    Skips Saturday ONLY (Saturday is day 5 in weekday())
    """
    if from_date is None:
        from_date = timezone.now().date()
    
    # Get the target day
    day = routine.day_of_week
    
    # Map day name to weekday number (Monday=0, Sunday=6)
    if isinstance(day, str):
        day_map_to_weekday = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
            'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }
        target_day = day_map_to_weekday.get(day)
    else:
        target_day = day
    
    # If target is Saturday, skip to Sunday (or move to next week)
    if target_day == 5:  # Saturday
        current_weekday = from_date.weekday()
        days_ahead = (6 - current_weekday) % 7
        if days_ahead == 0:
            days_ahead = 7
        return from_date + timedelta(days=days_ahead)
    
    current_weekday = from_date.weekday()
    days_ahead = target_day - current_weekday
    
    if days_ahead < 0:
        days_ahead += 7
    elif days_ahead == 0:
        # ✅ FIX: Use timezone.localtime() correctly
        now = timezone.localtime(timezone.now())
        if now.time() >= routine.start_time:
            days_ahead = 7
    
    return from_date + timedelta(days=days_ahead)


def generate_sessions_from_routines():
    """
    Generate attendance sessions from active routines for LIFETIME
    All generated sessions have is_manual=False (hidden from template)
    """
    routines = Routine.objects.filter(is_active=True)
    
    created_count = 0
    existing_count = 0
    errors = []
    created_sessions = []
    
    today = timezone.now().date()
    day_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    print(f"📋 Found {routines.count()} active routines")
    print(f"📅 Generating sessions for days: {', '.join(day_order)}")
    print(f"⏭️ Saturday sessions will be skipped automatically")
    print(f"📌 All generated sessions will be hidden (is_manual=False)")
    
    for routine in routines:
        next_date = get_next_session_date(routine, today)
        max_date = today + timedelta(days=365)
        
        while next_date and next_date <= max_date:
            # Skip Saturday (weekday=5)
            if next_date.weekday() == 5:  # Saturday
                next_date = next_date + timedelta(days=1)
                continue
            
            start_datetime = datetime.combine(
                next_date,
                routine.start_time,
                tzinfo=timezone.get_current_timezone()
            )
            
            end_datetime = start_datetime + timedelta(minutes=routine.duration or 60)
            
            # Check if session already exists
            existing = AttendanceSession.objects.filter(
                subject_name=routine.subject,
                department=routine.department,
                semester=routine.semester,
                year=routine.year,
                date=next_date,
                start_time=start_datetime
            ).first()
            
            if existing:
                # Update existing session's end time if needed
                if existing.end_time != end_datetime:
                    existing.end_time = end_datetime
                    existing.save(update_fields=['end_time'])
                existing_count += 1
            else:
                try:
                    with transaction.atomic():
                        session = AttendanceSession.objects.create(
                            subject_name=routine.subject,
                            department=routine.department,
                            semester=routine.semester,
                            year=routine.year,
                            section=routine.section or '',
                            date=next_date,
                            start_time=start_datetime,
                            end_time=end_datetime,
                            expected_duration=routine.duration or 60,
                            routine=routine,
                            is_active=False,
                            created_by=None,
                            is_manual=False,  # ← All generated sessions are NOT manual (hidden)
                        )
                        
                        # Create attendance logs for enrolled students
                        enrolled_students = session.get_enrolled_students()
                        for student in enrolled_students:
                            AttendanceLog.objects.get_or_create(
                                session=session,
                                student=student,
                                defaults={
                                    'status': 'ABSENT',
                                    'is_validated': True,
                                    'student_semester': student.semester,
                                    'student_year': student.year,
                                    'session_semester': session.semester,
                                    'session_year': session.year,
                                    'minute_presence': [0] * session.expected_duration,
                                    'minute_count': session.expected_duration,
                                    'attended_minutes': 0,
                                    'detection_count': 0,
                                    'first_seen': timezone.now(),
                                    'last_seen': timezone.now(),
                                }
                            )
                        
                        created_count += 1
                        created_sessions.append({
                            'id': session.id,
                            'subject': session.subject_name,
                            'date': session.date.strftime('%Y-%m-%d'),
                            'day': session.date.strftime('%A'),
                            'time': session.start_time.strftime('%I:%M %p'),
                            'is_manual': False  # ← Hidden from template
                        })
                        
                        print(f"✅ Created hidden session: {session.subject_name} on {session.date.strftime('%A, %B %d, %Y')} at {session.start_time.strftime('%I:%M %p')} (is_manual=False)")
                        
                except Exception as e:
                    errors.append(f"Error creating session for {routine.subject} on {next_date}: {str(e)}")
            
            # Get next occurrence (weekly)
            next_date = next_date + timedelta(days=7)
    
    print(f"\n📊 Generation Complete:")
    print(f"   ✅ Created: {created_count} sessions (all hidden)")
    print(f"   📌 Existing: {existing_count} sessions")
    
    return {
        'created_count': created_count,
        'existing_count': existing_count,
        'errors': errors,
        'created_sessions': created_sessions,
        'total_routines': routines.count()
    }


def auto_start_scheduled_sessions():
    """
    Check and auto-start sessions that are scheduled but not yet active
    Runs every 30 seconds to start sessions at their exact scheduled time
    """
    current_time = timezone.now()
    
    # Find sessions that should be started (start_time <= now, not active)
    pending_sessions = AttendanceSession.objects.filter(
        is_active=False,
        start_time__lte=current_time
    )
    
    started_count = 0
    for session in pending_sessions:
        session.is_active = True
        session.save(update_fields=['is_active'])
        started_count += 1
        print(f"🚀 Auto-started session: {session.subject_name} (ID: {session.id}) at {current_time.strftime('%I:%M:%S %p')}")
    
    return {'started_count': started_count}


def auto_end_completed_sessions():
    """
    Check and auto-end sessions that have passed their end time
    Runs every 30 seconds to end sessions exactly when duration is complete
    """
    current_time = timezone.now()
    
    # Find sessions that should be ended (end_time <= now, still active)
    ending_sessions = AttendanceSession.objects.filter(
        is_active=True,
        end_time__lte=current_time
    )
    
    ended_count = 0
    for session in ending_sessions:
        session.is_active = False
        session.save(update_fields=['is_active'])
        ended_count += 1
        print(f"⏹️ Auto-ended session: {session.subject_name} (ID: {session.id}) at {current_time.strftime('%I:%M:%S %p')}")
    
    return {'ended_count': ended_count}


def sync_routines_and_sessions():
    """
    Synchronize routines with sessions - generate missing sessions
    and update status of existing ones
    """
    # Generate all missing sessions
    result = generate_sessions_from_routines()
    
    # Auto-start pending sessions
    start_result = auto_start_scheduled_sessions()
    
    # Auto-end completed sessions
    end_result = auto_end_completed_sessions()
    
    return {
        'created_count': result.get('created_count', 0),
        'existing_count': result.get('existing_count', 0),
        'started_count': start_result.get('started_count', 0),
        'ended_count': end_result.get('ended_count', 0),
        'errors': result.get('errors', []),
        'created_sessions': result.get('created_sessions', []),
        'total_routines': result.get('total_routines', 0)
    }


class SessionScheduler:
    """
    Background scheduler for automatic session management
    Runs every 30 seconds to check and update session status
    """
    def __init__(self):
        self.running = False
        self.thread = None
        self.interval = 30
        self.last_check = None
        self.status = 'stopped'
        self.last_full_sync = None
    
    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            return
        
        self.running = True
        self.status = 'starting'
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print(f"🔄 Session Scheduler started (checking every {self.interval} seconds)")
        self.status = 'running'
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        self.status = 'stopping'
        if self.thread:
            self.thread.join(timeout=2)
        self.status = 'stopped'
        print("⏹️ Session Scheduler stopped")
    
    def _run(self):
        """Main scheduler loop - runs every interval seconds"""
        self.last_full_sync = timezone.now()
        sync_interval = timedelta(hours=6)  # Full sync every 6 hours
        quick_sync_interval = timedelta(minutes=5)  # Quick check every 5 minutes
        
        while self.running:
            try:
                self.last_check = timezone.now()
                current_time = timezone.now()
                
                # 1. AUTO-START: Check for sessions to start (every 30 seconds)
                start_result = auto_start_scheduled_sessions()
                
                # 2. AUTO-END: Check for sessions to end (every 30 seconds)
                end_result = auto_end_completed_sessions()
                
                if start_result['started_count'] > 0 or end_result['ended_count'] > 0:
                    print(f"📊 Auto-updated: {start_result['started_count']} started, {end_result['ended_count']} ended")
                
                # 3. FULL SYNC: Generate missing sessions (every 6 hours)
                if current_time - self.last_full_sync > sync_interval:
                    print("🔄 Running full synchronization...")
                    result = sync_routines_and_sessions()
                    
                    if result['created_count'] > 0:
                        print(f"✅ Generated {result['created_count']} new sessions")
                    
                    # Show daily schedule summary
                    self._print_daily_summary()
                    self._print_weekly_summary()
                    
                    self.last_full_sync = current_time
                
                # 4. QUICK SYNC: Check for missing sessions (every 5 minutes)
                elif current_time - self.last_full_sync > quick_sync_interval:
                    self._quick_check()
                
            except Exception as e:
                print(f"❌ Scheduler error: {e}")
                import traceback
                traceback.print_exc()
            
            # Sleep for interval
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _quick_check(self):
        """Quick check for missing sessions"""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        for date in [today, tomorrow]:
            if date.weekday() == 5:  # Saturday
                continue
            
            sessions = AttendanceSession.objects.filter(date=date)
            if not sessions.exists():
                result = generate_sessions_from_routines()
                if result['created_count'] > 0:
                    print(f"✅ Generated {result['created_count']} missing sessions")
                break
    
    def _print_daily_summary(self):
        """Print a summary of today's sessions"""
        today = timezone.now().date()
        today_sessions = AttendanceSession.objects.filter(date=today)
        today_name = today.strftime('%A')
        
        if today_name == 'Saturday':
            print(f"📅 Today is Saturday - No sessions scheduled")
            return
        
        active = today_sessions.filter(is_active=True).count()
        total = today_sessions.count()
        
        if total > 0:
            print(f"\n📅 Today ({today_name}): {total} sessions ({active} active)")
            # Sort by time
            for s in today_sessions.order_by('start_time'):
                status = "🟢 ACTIVE" if s.is_active else "⏳ SCHEDULED"
                print(f"   #{s.id} | {s.subject_name} | {s.start_time.strftime('%I:%M %p')} | {status}")
        else:
            print(f"\n📅 Today ({today_name}): No sessions scheduled yet")
    
    def _print_weekly_summary(self):
        """Print a summary of next 7 days"""
        today = timezone.now().date()
        print("\n📅 Weekly Schedule (Next 7 Days):")
        print("-" * 60)
        
        # Days in display order: Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday
        display_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        for day_name in display_order:
            # Find the date for this day
            days_ahead = (list(display_order).index(day_name) - today.weekday()) % 7
            if days_ahead < 0:
                days_ahead += 7
            date = today + timedelta(days=days_ahead)
            
            sessions = AttendanceSession.objects.filter(date=date)
            
            if day_name == 'Saturday':
                print(f"   📅 {date.strftime('%a %b %d')} (Saturday): ❌ OFF - No sessions")
            else:
                total = sessions.count()
                active = sessions.filter(is_active=True).count()
                status_icon = "✅" if total > 0 else "⚠️"
                print(f"   {status_icon} 📅 {date.strftime('%a %b %d')}: {total} sessions ({active} active)")
        
        print("-" * 60)


def get_local_time(dt):
    """Convert UTC datetime to local time"""
    if dt is None:
        return None
    return timezone.localtime(dt)


# Global scheduler instance
_scheduler = None

def get_scheduler():
    """Get or create the global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = SessionScheduler()
    return _scheduler

def start_scheduler(interval=30):
    """Start the global scheduler"""
    scheduler = get_scheduler()
    scheduler.interval = interval
    scheduler.start()
    return scheduler

def stop_scheduler():
    """Stop the global scheduler"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None