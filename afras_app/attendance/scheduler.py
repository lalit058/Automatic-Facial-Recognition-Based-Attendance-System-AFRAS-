# attendance/scheduler.py - Complete updated version

from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from dashboard.models import Routine
from .models import AttendanceSession, AttendanceLog
from accounts.models import Student
import logging
import threading
import time

logger = logging.getLogger(__name__)


def generate_sessions_from_routines(week_start_date=None, week_end_date=None):
    """
    Generate attendance sessions from active routines for a given week
    """
    if week_start_date is None:
        today = timezone.now().date()
        week_start_date = today - timedelta(days=today.weekday())
    
    if week_end_date is None:
        week_end_date = week_start_date + timedelta(days=13)  # 2 weeks ahead
    
    routines = Routine.objects.filter(is_active=True)
    
    created_count = 0
    existing_count = 0
    errors = []
    created_sessions = []
    
    # Day name to number mapping
    day_map = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
        'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    
    for routine in routines:
        # Get the day number (handle both string and int)
        day = routine.day_of_week
        if isinstance(day, str):
            target_day = day_map.get(day)
        else:
            target_day = day
        
        if target_day is None:
            errors.append(f"Invalid day for routine {routine.subject}: {routine.day_of_week}")
            continue
        
        # Calculate next occurrence
        current_weekday = week_start_date.weekday()
        days_ahead = target_day - current_weekday
        
        if days_ahead < 0:
            days_ahead += 7
        
        next_date = week_start_date + timedelta(days=days_ahead)
        
        # Continue generating sessions
        while next_date and next_date <= week_end_date:
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
                            is_active=False,  # Start inactive, will be auto-started
                            created_by=None
                        )
                        
                        # Create attendance logs
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
                        print(f"✅ Created session: {session.subject_name} on {session.date} at {session.start_time.strftime('%I:%M %p')}")
                        
                except Exception as e:
                    errors.append(f"Error creating session for {routine.subject}: {str(e)}")
            
            next_date = next_date + timedelta(days=7)
    
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
    Runs every minute to start sessions at their exact scheduled time
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
    Runs every minute to end sessions exactly when duration is complete
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
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=13)  # 2 weeks ahead
    
    result = generate_sessions_from_routines(week_start, week_end)
    
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
    """
    def __init__(self):
        self.running = False
        self.thread = None
        self.interval = 30
        self.last_check = None
        self.status = 'stopped'
    
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
        last_sync_time = timezone.now()
        sync_interval = timedelta(hours=1)
        
        while self.running:
            try:
                self.last_check = timezone.now()
                current_time = timezone.now()
                
                # Check for sessions to start/end
                start_result = auto_start_scheduled_sessions()
                end_result = auto_end_completed_sessions()
                
                if start_result['started_count'] > 0 or end_result['ended_count'] > 0:
                    print(f"📊 Auto-updated: {start_result['started_count']} started, {end_result['ended_count']} ended")
                
                # Sync routines once per hour
                if current_time - last_sync_time > sync_interval:
                    print("🔄 Syncing routines...")
                    result = sync_routines_and_sessions()
                    if result['created_count'] > 0:
                        print(f"✅ Generated {result['created_count']} new sessions")
                    last_sync_time = current_time
                
            except Exception as e:
                print(f"❌ Scheduler error: {e}")
                import traceback
                traceback.print_exc()
            
            # Sleep for interval
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)


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