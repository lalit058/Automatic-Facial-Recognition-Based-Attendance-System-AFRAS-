from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import Student, SystemLog, StaffProfile
from .models import AttendanceSession, AttendanceLog


class SemesterAttendanceService:
    """Service for managing semester-based attendance with strict validation"""
    
    @staticmethod
    def create_session(data, user):
        """Create a new attendance session with semester validation"""
        
        semester = data.get('semester')
        year = data.get('year')
        department = data.get('department')
        section = data.get('section')
        subject_name = data.get('subject_name')
        
        # Validate semester
        if semester and not 1 <= semester <= 8:
            raise ValidationError("Semester must be between 1 and 8")
        
        # Validate year
        if year and not 1 <= year <= 4:
            raise ValidationError("Year must be between 1 and 4")
        
        # Check if any students exist for this semester/year/department
        students_qs = Student.objects.all()
        if semester:
            students_qs = students_qs.filter(semester=semester)
        if year:
            students_qs = students_qs.filter(year=year)
        if department:
            students_qs = students_qs.filter(department=department)
        if section:
            students_qs = students_qs.filter(section=section)
        
        if not students_qs.exists():
            raise ValidationError(
                f"No students found for Semester {semester}, Year {year}, Department {department}. "
                "Please register students first or check the filters."
            )
        
        # Check for active sessions
        active_sessions = AttendanceSession.objects.filter(
            semester=semester,
            year=year,
            is_active=True
        )
        if department:
            active_sessions = active_sessions.filter(department=department)
        if section:
            active_sessions = active_sessions.filter(section=section)
        
        if active_sessions.count() >= 3:
            raise ValidationError(
                f"There are already {active_sessions.count()} active sessions for "
                f"Semester {semester}, Year {year}. Please end existing sessions first."
            )
        
        # Create session
        with transaction.atomic():
            session = AttendanceSession.objects.create(
                subject_name=subject_name,
                department=department,
                year=year,
                semester=semester,
                section=section,
                start_time=timezone.now(),
                date=timezone.now().date(),
                expected_duration=data.get('expected_duration', 60),
                created_by=user,
                is_active=True
            )
            
            # Get staff user for logging
            staff_user = user.user if hasattr(user, 'user') else user
            
            # Log session creation
            SystemLog.objects.create(
                user=staff_user,
                action='create',
                details=f"Created attendance session {session.session_id} for Semester {semester}, Year {year}, Dept {department}",
                ip_address=data.get('ip_address')
            )
            
            # Create initial attendance logs for all enrolled students
            enrolled_students = session.get_enrolled_students()
            for student in enrolled_students:
                AttendanceLog.objects.get_or_create(
                    session=session,
                    student=student,
                    defaults={
                        'status': 'ABSENT',
                        'confidence': 0,
                        'first_seen': timezone.now(),
                        'last_seen': timezone.now(),
                        'minute_presence': [0] * session.expected_duration,
                        'minute_count': session.expected_duration,
                        'attended_minutes': 0,
                    }
                )
            
            return session
    
    @staticmethod
    def record_attendance(session_id, roll_number, status, confidence, user, **kwargs):
        """Record attendance with strict semester validation"""
        
        try:
            session = AttendanceSession.objects.get(session_id=session_id, is_active=True)
        except AttendanceSession.DoesNotExist:
            raise ValidationError("Invalid or inactive session. Please start a new session.")
        
        try:
            student = Student.objects.get(roll_number=roll_number)
        except Student.DoesNotExist:
            raise ValidationError(f"Student with roll number {roll_number} not found")
        
        # CRITICAL VALIDATION: Check if student is enrolled in this session
        if not session.is_student_enrolled(student.id):
            error_message = (
                f"❌ Student {student.full_name} (Roll: {student.roll_number}) "
                f"is from Semester {student.semester}, Year {student.year}, "
                f"Dept {student.department} but current session is for "
                f"Semester {session.semester}, Year {session.year}, "
                f"Dept {session.department}"
            )
            
            # Get staff user for logging
            staff_user = user.user if hasattr(user, 'user') else user
            
            # Log the failed attempt
            SystemLog.objects.create(
                user=staff_user,
                action='login_failed',
                details=error_message,
                ip_address=kwargs.get('ip_address')
            )
            
            # Create or update a failed attendance log with validation error
            log, created = AttendanceLog.objects.get_or_create(
                session=session,
                student=student,
                defaults={
                    'status': 'ABSENT',
                    'confidence': 0.0,
                    'is_manual': True,
                    'is_validated': False,
                    'validation_error': error_message,
                    'student_semester': student.semester,
                    'student_year': student.year,
                    'session_semester': session.semester,
                    'session_year': session.year,
                    'first_seen': timezone.now(),
                    'last_seen': timezone.now(),
                }
            )
            
            if not created:
                log.validation_error = error_message
                log.is_validated = False
                log.status = 'ABSENT'
                log.save()
            
            raise ValidationError(error_message)
        
        # Check for duplicate attendance
        with transaction.atomic():
            existing_log = AttendanceLog.objects.filter(
                session=session,
                student=student
            ).first()
            
            # Get staff user for logging
            staff_user = user.user if hasattr(user, 'user') else user
            
            if existing_log:
                # Update existing log
                existing_log.status = status
                existing_log.confidence = confidence
                existing_log.last_seen = timezone.now()
                existing_log.last_detected = timezone.now()
                existing_log.detection_count += 1
                existing_log.is_validated = True
                existing_log.validation_error = None
                existing_log.student_semester = student.semester
                existing_log.student_year = student.year
                existing_log.session_semester = session.semester
                existing_log.session_year = session.year
                existing_log.save()
                
                return existing_log
            
            # Create new attendance log
            attendance_log = AttendanceLog.objects.create(
                session=session,
                student=student,
                status=status,
                confidence=confidence,
                first_seen=timezone.now(),
                last_seen=timezone.now(),
                is_manual=kwargs.get('is_manual', False),
                student_semester=student.semester,
                student_year=student.year,
                session_semester=session.semester,
                session_year=session.year,
                is_validated=True,
                validation_error=None,
            )
            
            # Initialize minute tracking
            attendance_log.reset_minute_tracking(session.expected_duration)
            
            # Log the attendance
            SystemLog.objects.create(
                user=staff_user,
                action='create',
                details=f"Marked {status} for {student.full_name} (Roll: {student.roll_number}) in session {session.session_id}",
                ip_address=kwargs.get('ip_address')
            )
            
            return attendance_log
    
    @staticmethod
    def get_session_students(session_id):
        """Get all students enrolled in the session's semester/year/department"""
        try:
            session = AttendanceSession.objects.get(session_id=session_id)
            return session.get_enrolled_students()
        except AttendanceSession.DoesNotExist:
            return Student.objects.none()
    
    @staticmethod
    def get_student_attendance_summary(student_id, semester=None, year=None):
        """Get attendance summary for a student with filtering"""
        queryset = AttendanceLog.objects.filter(student_id=student_id)
        
        if semester:
            queryset = queryset.filter(session_semester=semester)
        if year:
            queryset = queryset.filter(session_year=year)
        
        total_sessions = queryset.count()
        present_count = queryset.filter(status='PRESENT').count()
        partial_count = queryset.filter(status='PARTIAL').count()
        absent_count = queryset.filter(status='ABSENT').count()
        validated_count = queryset.filter(is_validated=True).count()
        validation_failed = queryset.filter(is_validated=False).count()
        
        return {
            'total_sessions': total_sessions,
            'present': present_count,
            'partial': partial_count,
            'absent': absent_count,
            'validated': validated_count,
            'validation_failed': validation_failed,
            'attendance_percentage': ((present_count + partial_count) / total_sessions * 100) if total_sessions > 0 else 0
        }
    
    @staticmethod
    def end_session(session_id, user):
        """End an active session"""
        try:
            session = AttendanceSession.objects.get(session_id=session_id, is_active=True)
        except AttendanceSession.DoesNotExist:
            raise ValidationError("No active session found with this ID")
        
        session.is_active = False
        session.end_time = timezone.now()
        session.save()
        
        # Get staff user for logging
        staff_user = user.user if hasattr(user, 'user') else user
        
        # Log session end
        SystemLog.objects.create(
            user=staff_user,
            action='update',
            details=f"Ended session {session.session_id}",
            ip_address=getattr(user, 'ip_address', None)
        )
        
        return session
    
    @staticmethod
    def get_semester_stats(semester, year=None, department=None):
        """Get attendance statistics for a specific semester"""
        sessions = AttendanceSession.objects.filter(semester=semester)
        if year:
            sessions = sessions.filter(year=year)
        if department:
            sessions = sessions.filter(department=department)
        
        total_sessions = sessions.count()
        total_students = Student.objects.filter(semester=semester)
        if year:
            total_students = total_students.filter(year=year)
        if department:
            total_students = total_students.filter(department=department)
        
        # Get attendance logs for these sessions
        logs = AttendanceLog.objects.filter(session__in=sessions)
        
        return {
            'total_sessions': total_sessions,
            'total_students': total_students.count(),
            'total_attendance_records': logs.count(),
            'present_count': logs.filter(status='PRESENT').count(),
            'partial_count': logs.filter(status='PARTIAL').count(),
            'absent_count': logs.filter(status='ABSENT').count(),
            'validation_failed': logs.filter(is_validated=False).count(),
        }