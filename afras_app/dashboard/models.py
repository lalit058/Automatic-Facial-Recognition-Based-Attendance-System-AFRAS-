# dashboard/models.py
from django.db import models

class Routine(models.Model):
    subject = models.CharField(max_length=200)
    department = models.CharField(max_length=100)
    semester = models.IntegerField()
    year = models.IntegerField(default=1)  # Add year field
    section = models.CharField(max_length=10, blank=True, null=True)  # Add section
    day_of_week = models.CharField(max_length=20)  # e.g., 'Monday'
    start_time = models.TimeField()
    duration = models.IntegerField(default=60)  # Duration in minutes
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subject} - {self.day_of_week} ({self.start_time})"
    
    def get_next_session_date(self, from_date=None):
        """Get the next date for this routine"""
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        if from_date is None:
            from_date = timezone.now().date()
        
        day_map = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
            'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }
        
        target_day = day_map.get(self.day_of_week)
        if target_day is None:
            return None
        
        current_weekday = from_date.weekday()
        days_ahead = target_day - current_weekday
        
        if days_ahead < 0:
            days_ahead += 7
        
        return from_date + timedelta(days=days_ahead)