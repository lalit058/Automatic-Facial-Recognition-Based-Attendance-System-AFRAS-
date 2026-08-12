# afras_app/attendance/models.py

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import Student, StaffProfile
from dashboard.models import Routine
from datetime import timedelta
import random
import string


class AttendanceSession(models.Model):
    subject_name = models.CharField(max_length=100)
    department = models.CharField(max_length=100, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    semester = models.IntegerField(blank=True, null=True)
    section = models.CharField(max_length=10, blank=True, null=True)
    start_time = models.DateTimeField(default=timezone.now)
    expected_duration = models.PositiveIntegerField(default=60)
    routine = models.ForeignKey(Routine, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    # NEW FIELD: Track manual vs auto-generated sessions
    is_manual = models.BooleanField(
        default=False,
        help_text="True if session was manually created by user (shows in template)"
    )
    
    # Session identifier for tracking - FIXED to prevent duplicates
    session_id = models.CharField(max_length=50, unique=True, null=True, blank=True)

    def __str__(self):
        dept_info = f"{self.department} - " if self.department else ""
        sem_info = f"Sem {self.semester}" if self.semester else ""
        manual = " [Manual]" if self.is_manual else ""
        return f"{self.subject_name} ({self.date}) - {dept_info}{sem_info}{manual}"
    
    def save(self, *args, **kwargs):
        """Generate unique session_id with timestamp and random suffix"""
        if not self.session_id and not self.pk:
            # Generate unique session_id with timestamp and random component
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            random_suffix = ''.join(random.choices(string.digits, k=4))
            self.session_id = f"S{timestamp}{random_suffix}"
            
            # Check if this session_id already exists (very unlikely, but possible)
            while AttendanceSession.objects.filter(session_id=self.session_id).exists():
                random_suffix = ''.join(random.choices(string.digits, k=4))
                self.session_id = f"S{timestamp}{random_suffix}"
        
        super().save(*args, **kwargs)
    
    def get_enrolled_students(self):
        if self.semester and self.year:
            students = Student.objects.filter(
                semester=self.semester,
                year=self.year
            )
            if self.department:
                students = students.filter(department=self.department)
            if self.section:
                students = students.filter(section=self.section)
            return students
        return Student.objects.none()
    
    def is_student_enrolled(self, student_id):
        try:
            student = Student.objects.get(id=student_id)
            if self.semester and self.year:
                if student.semester != self.semester or student.year != self.year:
                    return False
                if self.department and student.department != self.department:
                    return False
                if self.section and student.section != self.section:
                    return False
                return True
            return False
        except Student.DoesNotExist:
            return False
    
    def get_attendance_summary(self):
        total_students = self.get_enrolled_students().count()
        present_count = self.logs.filter(status__in=['PRESENT', 'PARTIAL']).count()
        
        return {
            'total_students': total_students,
            'present': present_count,
            'absent': total_students - present_count,
            'percentage': (present_count / total_students * 100) if total_students > 0 else 0
        }
    
    def end_session(self):
        self.is_active = False
        self.end_time = timezone.now()
        self.save()
    
    class Meta:
        ordering = ['-date', '-start_time']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['semester', 'year']),
            models.Index(fields=['is_active']),
            models.Index(fields=['date']),
            models.Index(fields=['department', 'semester', 'year']),
            models.Index(fields=['is_manual']),  # NEW: Index for filtering manual sessions
        ]



class AttendanceLog(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("LATE", "Late"),
        ("LEAVE", "Authorized Leave"),
        ("PARTIAL", "Partial Presence"),
    ]

    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="logs"
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ABSENT")
    is_manual = models.BooleanField(default=False)
    confidence = models.FloatField(null=True, blank=True)
    
    # Add this field to store the reason for manual changes
    reason = models.TextField(
        blank=True, 
        null=True, 
        help_text="Reason for manual attendance change (e.g., Approved leave, Technical issue)"
    )
    
    # Minute-by-minute tracking fields
    minute_presence = models.JSONField(default=list, blank=True)
    minute_count = models.IntegerField(default=0)
    attended_minutes = models.IntegerField(default=0)
    
    # Legacy tracking fields
    total_presence_seconds = models.IntegerField(default=0)
    last_detected = models.DateTimeField(null=True, blank=True)
    detection_count = models.IntegerField(default=0)
    out_of_frame_count = models.IntegerField(default=0)
    
    # Semester validation fields
    student_semester = models.IntegerField(null=True, blank=True, help_text="Student's semester at time of attendance")
    student_year = models.IntegerField(null=True, blank=True, help_text="Student's year at time of attendance")
    session_semester = models.IntegerField(null=True, blank=True, help_text="Session semester")
    session_year = models.IntegerField(null=True, blank=True, help_text="Session year")
    is_validated = models.BooleanField(default=False, help_text="Whether student was validated for this semester")
    validation_error = models.TextField(blank=True, null=True, help_text="Validation error message if any")
    
    class Meta:
        unique_together = ("session", "student")
        indexes = [
            models.Index(fields=['session', 'student']),
            models.Index(fields=['status', 'session']),
            models.Index(fields=['is_validated']),
            models.Index(fields=['student_semester', 'session_semester']),
            models.Index(fields=['student', 'session_semester']),
        ]
    
    @property
    def presence_duration_minutes(self):
        return self.total_presence_seconds / 60 if self.total_presence_seconds else 0

    @property
    def retention_percentage(self):
        if self.session.expected_duration <= 0:
            return 0
        return (self.presence_duration_minutes / self.session.expected_duration) * 100
    
    def validate_student_semester(self):
        """Validate that student belongs to the session's semester and year"""
        if self.session and self.student:
            self.student_semester = self.student.semester
            self.student_year = self.student.year
            self.session_semester = self.session.semester
            self.session_year = self.session.year
            
            if self.student.semester != self.session.semester:
                self.is_validated = False
                self.validation_error = (
                    f"Student {self.student.full_name} (Roll: {self.student.roll_number}) "
                    f"is from Semester {self.student.semester} but session is for "
                    f"Semester {self.session.semester}"
                )
                return False
            
            if self.student.year != self.session.year:
                self.is_validated = False
                self.validation_error = (
                    f"Student {self.student.full_name} (Roll: {self.student.roll_number}) "
                    f"is from Year {self.student.year} but session is for "
                    f"Year {self.session.year}"
                )
                return False
            
            if self.session.department and self.student.department != self.session.department:
                self.is_validated = False
                self.validation_error = (
                    f"Student {self.student.full_name} (Roll: {self.student.roll_number}) "
                    f"is from {self.student.department} but session is for "
                    f"{self.session.department}"
                )
                return False
            
            if self.session.section and self.student.section != self.session.section:
                self.is_validated = False
                self.validation_error = (
                    f"Student {self.student.full_name} (Roll: {self.student.roll_number}) "
                    f"is from Section {self.student.section} but session is for "
                    f"Section {self.session.section}"
                )
                return False
            
            self.is_validated = True
            self.validation_error = None
            return True
        
        return False
    
    def reset_minute_tracking(self, session_duration):
        """Initialize minute tracking for the session"""
        self.minute_presence = [0] * session_duration
        self.minute_count = session_duration
        self.attended_minutes = 0
        self.save(update_fields=['minute_presence', 'minute_count', 'attended_minutes'])
    
    def mark_minute_present(self, minute_index):
        """Mark a specific minute as present"""
        if 0 <= minute_index < len(self.minute_presence):
            if self.minute_presence[minute_index] == 0:
                self.minute_presence[minute_index] = 1
                self.attended_minutes += 1
                self.save(update_fields=['minute_presence', 'attended_minutes'])
                return True
        return False
    
    def get_minute_attendance_percentage(self):
        if self.minute_count == 0:
            return 0
        return (self.attended_minutes / self.minute_count) * 100
    
    def get_attendance_pattern(self):
        if not self.minute_presence:
            return "No data"
        
        pattern = []
        for i, present in enumerate(self.minute_presence):
            if i > 0 and i % 5 == 0:
                pattern.append(" ")
            pattern.append("█" if present else "░")
        return "".join(pattern)
    
    def get_attendance_summary(self):
        total = self.minute_count or self.session.expected_duration
        attended = self.attended_minutes
        absent = total - attended
        percentage = self.get_minute_attendance_percentage() if self.minute_count > 0 else self.retention_percentage
        
        return {
            'total_minutes': total,
            'attended_minutes': attended,
            'absent_minutes': absent,
            'percentage': percentage,
            'pattern': self.get_attendance_pattern(),
            'status': self.status,
            'detection_count': self.detection_count,
            'confidence': self.confidence,
            'is_validated': self.is_validated,
            'validation_error': self.validation_error,
            'student_semester': self.student_semester,
            'session_semester': self.session_semester
        }

    def save(self, *args, **kwargs):
        """
        Modified save() with combined single-shot + minute-tracking logic
        REMOVED SystemConfiguration dependency
        """
        
        # ============================================================
        # STEP 1: Validate semester
        # ============================================================
        self.validate_student_semester()
        
        # ============================================================
        # STEP 2: Manual override check
        # ============================================================
        if self.is_manual:
            # Manual entries keep their status
            self.last_seen = timezone.now()
            super().save(*args, **kwargs)
            return
        
        # ============================================================
        # STEP 3: If validation failed, force ABSENT
        # ============================================================
        if not self.is_validated:
            self.status = "ABSENT"
            self.confidence = 0.0
            super().save(*args, **kwargs)
            return
        
        # ============================================================
        # STEP 4: Update tracking fields
        # ============================================================
        if not self.is_manual and self.is_validated:
            self.last_seen = timezone.now()
            self.last_detected = timezone.now()
            self.detection_count += 1
        
        # ============================================================
        # STEP 5: Get config - Use 80% as default
        # ============================================================
        min_retention = 80.0
        
        # ============================================================
        # STEP 6: Calculate actual session duration
        # ============================================================
        actual_duration = self.session.expected_duration or 60
        if self.session.start_time and self.session.end_time:
            time_diff = self.session.end_time - self.session.start_time
            actual_duration = int(time_diff.total_seconds() // 60)
            if actual_duration <= 0:
                actual_duration = self.session.expected_duration or 60
        
        # If session ended early, use actual duration
        if self.session.end_time and self.session.start_time:
            expected_end = self.session.start_time + timedelta(minutes=self.session.expected_duration or 60)
            if self.session.end_time < expected_end:
                actual_duration = int((self.session.end_time - self.session.start_time).total_seconds() // 60)
                if actual_duration <= 0:
                    actual_duration = self.session.expected_duration or 60
        
        # Ensure we have at least 1 minute
        if actual_duration < 1:
            actual_duration = 1
        
        # ============================================================
        # STEP 7: DETERMINE STATUS - Combined Logic
        # ============================================================
        
        # ----- CASE 1: SINGLE SHOT MODE -----
        # Student was detected at least once AND no minute tracking data
        if self.detection_count >= 1 and (self.minute_count == 0 or not self.minute_presence):
            self.status = "PRESENT"
            print(f"✅ SINGLE-SHOT: {self.student.full_name} marked PRESENT (detections={self.detection_count})")
        
        # ----- CASE 2: MINUTE-BASED TRACKING MODE -----
        elif self.minute_count > 0 and self.minute_presence:
            if len(self.minute_presence) != actual_duration:
                # Resize minute_presence to match actual duration
                if len(self.minute_presence) < actual_duration:
                    self.minute_presence.extend([0] * (actual_duration - len(self.minute_presence)))
                else:
                    self.minute_presence = self.minute_presence[:actual_duration]
                self.minute_count = actual_duration
                self.attended_minutes = sum(self.minute_presence)
            
            retention = self.attended_minutes / self.minute_count if self.minute_count > 0 else 0
            
            if retention >= (min_retention / 100):
                self.status = "PRESENT"
            elif retention >= 0.5:
                self.status = "PARTIAL"
            elif retention > 0:
                self.status = "LATE"
            else:
                self.status = "ABSENT"
            
            print(f"📊 MINUTE-TRACKING: {self.student.full_name} retention={retention:.1f}%, status={self.status}")
        
        # ----- CASE 3: MIXED MODE -----
        # Student was detected AND has some minute data (hybrid scenario)
        elif self.detection_count >= 1 and self.minute_count > 0:
            retention = self.attended_minutes / self.minute_count if self.minute_count > 0 else 0
            
            # Use the better of the two methods
            if retention >= (min_retention / 100):
                self.status = "PRESENT"
            elif retention >= 0.5:
                self.status = "PARTIAL"
            else:
                # If detected but retention is low, still mark as PRESENT
                # Because they were physically present at least once
                self.status = "PRESENT"
            
            print(f"🔄 MIXED MODE: {self.student.full_name} detection={self.detection_count}, retention={retention:.1f}%, status={self.status}")
        
        # ----- CASE 4: FALLBACK -----
        else:
            self.status = "ABSENT"
            print(f"❌ FALLBACK: {self.student.full_name} marked ABSENT")
        
        # ============================================================
        # STEP 8: Save to database
        # ============================================================
        super().save(*args, **kwargs)