# afras_app/attendance/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from accounts.models import StaffProfile, Student, SystemConfiguration
from dashboard.models import Routine


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

    def __str__(self):
        dept_info = f"{self.department} - " if self.department else ""
        sem_info = f"Sem {self.semester}" if self.semester else ""
        return f"{self.subject_name} ({self.date}) - {dept_info}{sem_info}"


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
    
    # Minute-by-minute tracking fields
    minute_presence = models.JSONField(default=list, blank=True)
    minute_count = models.IntegerField(default=0)
    attended_minutes = models.IntegerField(default=0)
    
    # Legacy tracking fields
    total_presence_seconds = models.IntegerField(default=0)
    last_detected = models.DateTimeField(null=True, blank=True)
    detection_count = models.IntegerField(default=0)
    out_of_frame_count = models.IntegerField(default=0)
    
    @property
    def presence_duration_minutes(self):
        """Calculate presence duration in minutes"""
        return self.total_presence_seconds / 60

    @property
    def retention_percentage(self):
        if self.session.expected_duration <= 0:
            return 0
        return (self.presence_duration_minutes / self.session.expected_duration) * 100
    
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
        """Calculate attendance percentage from minute tracking"""
        if self.minute_count == 0:
            return 0
        return (self.attended_minutes / self.minute_count) * 100
    
    def get_attendance_pattern(self):
        """Get attendance pattern as a string"""
        if not self.minute_presence:
            return "No data"
        
        pattern = []
        for i, present in enumerate(self.minute_presence):
            if i > 0 and i % 5 == 0:
                pattern.append(" ")
            pattern.append("█" if present else "░")
        return "".join(pattern)
    
    def get_attendance_summary(self):
        """Get a summary of attendance"""
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
            'confidence': self.confidence
        }

    def save(self, *args, **kwargs):
        # Update last_seen if not manual
        if not self.is_manual:
            self.last_seen = timezone.now()
            self.last_detected = timezone.now()
            self.detection_count += 1

        # Get the global config
        config = SystemConfiguration.load()
        
        # Get min_retention_required (80% default)
        min_retention = float(config.min_retention_required) if config.min_retention_required else 80.0
        
        # Calculate retention based on minute tracking (if available)
        if self.minute_count > 0:
            retention = self.get_minute_attendance_percentage()
        else:
            retention = self.retention_percentage  # Fallback to old method
        
        # Determine status based on retention percentage
        if retention >= min_retention:
            self.status = "PRESENT"
        elif retention >= 50:  # Between 50% and 80%
            self.status = "PARTIAL"
        elif self.presence_duration_minutes > 2:  # Less than 2 minutes
            self.status = "LATE"
        else:
            self.status = "ABSENT"

        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("session", "student")