from django.db import models
from accounts.models import Student

class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, default="Present")

    class Meta:
        unique_together = ('student', 'date') # Prevents duplicate attendance on the same day