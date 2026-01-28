from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.conf import settings


class CustomUser(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_staff_member = models.BooleanField(default=False)

    # Note: Using related_name is good to avoid clashes with default User
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
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    semester = models.IntegerField(default=1)
    section = models.CharField(max_length=10, blank=True)

    photo = models.ImageField(upload_to="student_photos/")
    id_proof = models.FileField(upload_to="student_docs/", blank=True, null=True)
    registration_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.roll_number} - {self.full_name}"


class StaffProfile(models.Model):
    # Link to CustomUser
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile"
    )
    full_name = models.CharField(max_length=255)

    # Matches <input name="phone"> in your HTML
    phone_number = models.CharField(max_length=20)

    # Matches <input name="degree">
    degree = models.CharField(max_length=255)

    # Matches <input name="designation">
    designation = models.CharField(max_length=255)

    # Matches <select name="department">
    department = models.CharField(max_length=100)

    # Matches <input name="photo">
    photo = models.ImageField(upload_to="staff_photos/")

    def __str__(self):
        return f"{self.full_name} ({self.designation})"
