from django.db import models
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from accounts.models import StaffProfile, Student, SystemConfiguration
from dashboard.models import Routine


class AttendanceSession(models.Model):
    subject_name = models.CharField(max_length=100)
    start_time = models.DateTimeField(auto_now_add=True)
    expected_duration = models.PositiveIntegerField(default=60)
    routine = models.ForeignKey(Routine, on_delete=models.SET_NULL, null=True, related_name="sessions")
    subject_name = models.CharField(max_length=100) 
    date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.subject_name} ({self.date})"


class AttendanceLog(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("LATE", "Late"),  # Added missing comma
        ("LEAVE", "Authorized Leave"),
    ]

    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="logs"
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    first_seen = models.DateTimeField(default=timezone.now) 
    last_seen = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ABSENT")
    is_manual = models.BooleanField(default=False)
    confidence = models.FloatField(null=True, blank=True)  # ADD THIS FIELD

    @property
    def retention_percentage(self):
        if self.session.expected_duration <= 0:
            return 0
        # Ensure we use floating point for accurate percentage
        return (self.presence_duration_minutes / self.session.expected_duration) * 100

    def save(self, *args, **kwargs):
        # 1. Update last_seen if not manual
        if not self.is_manual:
            self.last_seen = timezone.now()

        # 2. Get the global config
        config = SystemConfiguration.load()
        
        # 3. Use the dynamic threshold from configuration
        if self.retention_percentage >= config.min_retention_required:
            self.status = "PRESENT"
        elif self.presence_duration_minutes > 5: # Small buffer for 'Late'
            self.status = "LATE"
        else:
            self.status = "ABSENT"

        super().save(*args, **kwargs)
        
        

    class Meta:
        unique_together = ("session", "student")

