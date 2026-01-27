from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.conf import settings

class CustomUser(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_staff_member = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        Group,
        related_name="customuser_set",
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customuser_set",
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    roll_number = models.CharField(max_length=50, unique=True) # Added Roll Number
    department = models.CharField(max_length=100, blank=True)
    semester = models.IntegerField(default=1) # Added Semester
    section = models.CharField(max_length=10, blank=True) # Added Section
    
    # Photos stored in media/student_photos/
    photo = models.ImageField(upload_to='student_photos/')
    # Identity documents stored in media/student_docs/
    id_proof = models.FileField(upload_to='student_docs/', blank=True, null=True) # Added ID Proof
    
    registration_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.roll_number} - {self.full_name}"
    
class StaffProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    degree = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    department = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='staff_photos/')
    
    def __str__(self):
        return self.full_name