from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.conf import settings


class CustomUser(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_staff_member = models.BooleanField(default=False)

    # Using related_name is good to avoid clashes with default User
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
    staff_id = models.CharField(max_length=50, unique=True, blank=True)  # Added field
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    degree = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    department = models.CharField(max_length=100)
    address = models.CharField(max_length=50, blank=True)
    photo = models.ImageField(upload_to="staff_photos/")

    def save(self, *args, **kwargs):
        # Auto-populate staff_id from username if not set
        if not self.staff_id and self.user:
            self.staff_id = self.user.username
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.staff_id} - {self.full_name} ({self.designation})"


class SystemLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    action = models.CharField(
        max_length=255
    )  # e.g., "Student Registered", "Backup Created"
    details = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    deleted_username = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        ordering = ["-timestamp"]


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
        default=80, help_text="Percentage to be marked PRESENT"
    )
    default_duration = models.IntegerField(
        default=60, help_text="Default session duration in minutes"
    )
    auto_stop_minutes = models.IntegerField(
        default=5, help_text="Auto-stop after N minutes of no detection"
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
        self.pk = 1  # Singleton pattern - always same row
        if not self.api_key:
            self.generate_api_key()
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def generate_api_key(self):
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits
        self.api_key = "sk_live_" + "".join(secrets.choice(alphabet) for _ in range(32))

    def __str__(self):
        return f"System Configuration (v{self.updated_at.strftime('%Y%m%d') if self.updated_at else '1.0'})"
