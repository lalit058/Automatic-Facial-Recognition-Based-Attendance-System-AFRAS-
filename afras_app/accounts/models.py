from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.conf import settings
import secrets
from django.utils import timezone
import string


class CustomUser(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_staff_member = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        Group,
        related_name="custom_user_groups",
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="custom_user_permissions",
        blank=True,
    )


class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    full_name = models.CharField(max_length=100)
    roll_number = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=10)
    email = models.EmailField(blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    year = models.IntegerField(default=1)
    semester = models.IntegerField(default=1)
    section = models.CharField(max_length=10, blank=True)
    address = models.CharField(max_length=50, blank=True)

    photo = models.ImageField(upload_to="student_photos/")
    id_proof = models.FileField(upload_to="student_docs/", blank=True, null=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    face_encoding = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.roll_number} - {self.full_name}"


class StaffProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile"
    )
    staff_id = models.CharField(max_length=50, unique=True, blank=True)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    degree = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    department = models.CharField(max_length=100)
    address = models.CharField(max_length=50, blank=True)
    photo = models.ImageField(upload_to="staff_photos/")

    def save(self, *args, **kwargs):
        if not self.staff_id and self.user:
            self.staff_id = self.user.username
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.staff_id} - {self.full_name} ({self.designation})"


class SystemLog(models.Model):
    """System audit log with soft delete capability"""
    
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('view', 'View'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('register', 'Register'),
        ('login_failed', 'Login Failed'),
    ]
    
    # Core fields
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='system_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Soft delete fields
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='deleted_logs'
    )
    deletion_reason = models.CharField(max_length=200, blank=True, null=True)
    
    # For deleted users
    deleted_username = models.CharField(max_length=150, blank=True, null=True)
    deleted_user_email = models.EmailField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', 'action']),
            models.Index(fields=['is_deleted']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        user_name = self.user.username if self.user else (self.deleted_username or 'Deleted User')
        return f"{self.action} by {user_name} at {self.timestamp}"
    
    def soft_delete(self, deleted_by=None, reason=None):
        """Soft delete the log entry"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.deletion_reason = reason
        
        # Store user info before deletion
        if self.user:
            self.deleted_username = self.user.username
            self.deleted_user_email = self.user.email
        
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'deletion_reason', 'deleted_username', 'deleted_user_email'])
    
    def restore(self):
        """Restore a soft-deleted log"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'deletion_reason'])
    
    @classmethod
    def archive_old_logs(cls, days=365):
        """Archive logs older than specified days"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        old_logs = cls.objects.filter(
            timestamp__lt=cutoff_date,
            is_deleted=False
        )
        count = old_logs.count()
        for log in old_logs:
            log.soft_delete(
                deleted_by=None,
                reason=f"Auto-archived after {days} days"
            )
        return count
    
    @classmethod
    def purge_old_archived(cls, days=730):
        """Permanently delete archived logs older than specified days"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return cls.objects.filter(
            is_deleted=True,
            deleted_at__lt=cutoff_date
        ).delete()
        

class SystemConfiguration(models.Model):
    # Basic Institution Settings
    institution_name = models.CharField(
        max_length=200, default="Far Western University"
    )
    timezone = models.CharField(max_length=50, default="Asia/Kathmandu")

    # Recognition Settings
    recognition_threshold = models.FloatField(
        default=0.65, help_text="Lower = stricter (0.3-0.9)"
    )
    detection_model = models.CharField(
        max_length=20,
        default="hog",
        choices=[("hog", "HOG (Fast, CPU)"), ("cnn", "CNN (Slow, GPU)")],
    )
    upsample_factor = models.IntegerField(
        default=1,
        choices=[(0, "0 (Fastest)"), (1, "1 (Balanced)"), (2, "2 (Best Quality)")],
    )

    # Camera Settings
    camera_source = models.CharField(
        max_length=10, default="0", help_text="0=built-in, 1=external, or RTSP URL"
    )
    rtsp_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Required if camera_source='rtsp'",
    )
    frame_resolution = models.FloatField(
        default=0.75,
        choices=[
            (0.5, "640x480 (Fast)"),
            (0.75, "960x720 (Balanced)"),
            (1.0, "1280x720 (HD)"),
        ],
    )
    frame_skip = models.IntegerField(
        default=3,
        choices=[
            (1, "Every Frame (Max CPU)"),
            (3, "Every 3rd Frame (Recommended)"),
            (5, "Every 5th Frame (Eco)"),
        ],
    )

    # Attendance Settings
    min_retention_required = models.IntegerField(
        default=80, 
        help_text="Minimum retention percentage to be marked PRESENT"
    )
    partial_retention_threshold = models.IntegerField(
        default=50,
        help_text="Minimum retention percentage for PARTIAL status"
    )
    max_gap_seconds = models.IntegerField(
        default=30,
        help_text="Maximum seconds gap before counting as out of frame"
    )

    # Performance Settings
    cache_size = models.IntegerField(
        default=100, help_text="Number of face encodings to keep in RAM"
    )
    processing_threads = models.IntegerField(
        default=2,
        choices=[
            (1, "1 Thread (Low CPU)"),
            (2, "2 Threads (Balanced)"),
            (4, "4 Threads (High Performance)"),
        ],
    )
    log_retention_days = models.IntegerField(
        default=30, help_text="Days to keep attendance logs"
    )

    # Notification Settings
    notify_session_start = models.BooleanField(default=True)
    notify_session_end = models.BooleanField(default=True)
    notify_low_attendance = models.BooleanField(default=False)
    alert_email = models.EmailField(default="admin@example.com")
    attendance_threshold = models.IntegerField(
        default=50, help_text="Low attendance alert threshold %"
    )
    enable_push_notifications = models.BooleanField(default=True, help_text="Enable push notifications")
    notification_sound = models.BooleanField(default=True, help_text="Play sound for notifications")
    notification_duration = models.IntegerField(default=5, help_text="Notification display duration in seconds")

    # API Settings
    enable_api = models.BooleanField(default=True, help_text="Enable REST API")
    require_api_key = models.BooleanField(
        default=False, help_text="Require API key for access"
    )
    api_key = models.CharField(
        max_length=100, blank=True, help_text="Auto-generated API key"
    )
    webhook_url = models.URLField(
        blank=True, help_text="Send attendance data to external system"
    )

    # Debug Settings
    debug_mode = models.IntegerField(
        default=0,
        choices=[(0, "Disabled"), (1, "Basic Logging"), (2, "Verbose Logging")],
        help_text="Debug logging level",
    )

    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "System Configuration"
        verbose_name_plural = "System Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        if not self.api_key:
            self.generate_api_key()
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def generate_api_key(self):
        alphabet = string.ascii_letters + string.digits
        self.api_key = "sk_live_" + "".join(secrets.choice(alphabet) for _ in range(32))

    def __str__(self):
        return f"System Configuration (v{self.updated_at.strftime('%Y%m%d') if self.updated_at else '1.0'})"


class Notification(models.Model):
    """
    Notification model for system-wide and user-specific notifications
    Supports real-time alerts for attendance, sessions, registrations, etc.
    """
    
    NOTIFICATION_TYPES = (
        ('attendance', 'Attendance Marked'),
        ('session', 'Session Event'),
        ('student', 'Student Registration'),
        ('staff', 'Staff Registration'),
        ('alert', 'Security Alert'),
        ('proxy', 'Proxy Detection'),
        ('system', 'System Update'),
        ('recognition', 'Face Recognition'),
        ('reminder', 'Reminder'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    )
    
    # User association (null = system-wide notification)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True
    )
    
    # Notification type for icon/color styling
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='system'
    )
    
    # Notification content
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Read status
    is_read = models.BooleanField(default=False)
    
    # Optional link to navigate when clicked
    link = models.CharField(max_length=500, blank=True, null=True)
    
    # Additional data stored as JSON
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.title[:50]}"
    
    def time_ago(self):
        """Return human-readable time since creation"""
        from django.utils.timesince import timesince
        from django.utils.timezone import now
        
        if self.created_at:
            return timesince(self.created_at, now())
        return "Just now"
    
    def mark_as_read(self):
        """Mark notification as read and save"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
            return True
        return False
    
    @classmethod
    def send_notification(cls, user, title, message, notification_type='system', link=None, metadata=None):
        """
        Helper method to create and send a notification
        Returns the created notification object
        """
        notification = cls.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
            metadata=metadata or {}
        )
        return notification
    
    @classmethod
    def send_bulk_notification(cls, users, title, message, notification_type='system', link=None, metadata=None):
        """
        Send the same notification to multiple users
        Returns list of created notification objects
        """
        notifications = []
        for user in users:
            notification = cls.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                link=link,
                metadata=metadata or {}
            )
            notifications.append(notification)
        return notifications
    
    @classmethod
    def send_system_notification(cls, title, message, notification_type='system', link=None, metadata=None):
        """
        Send a system-wide notification (visible to all users)
        """
        notification = cls.objects.create(
            user=None,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
            metadata=metadata or {}
        )
        return notification
    
    @classmethod
    def get_unread_count(cls, user):
        """Get unread notification count for a user"""
        return cls.objects.filter(
            models.Q(user=user) | models.Q(user__isnull=True),
            is_read=False
        ).count()
    
    @classmethod
    def get_user_notifications(cls, user, limit=20, include_system=True):
        """Get notifications for a user (including system notifications)"""
        if include_system:
            return cls.objects.filter(
                models.Q(user=user) | models.Q(user__isnull=True)
            ).order_by('-created_at')[:limit]
        else:
            return cls.objects.filter(user=user).order_by('-created_at')[:limit]