from django.db import models

class Routine(models.Model):
    subject = models.CharField(max_length=200)
    department = models.CharField(max_length=100)
    semester = models.IntegerField()
    day_of_week = models.CharField(max_length=20)  # e.g., 'Monday'
    start_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    def __clstr__(self):
        return f"{self.subject} - {self.day_of_week}"