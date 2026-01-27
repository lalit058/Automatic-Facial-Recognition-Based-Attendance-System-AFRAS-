from django.shortcuts import render
from recognition.utils import recognize_faces  # We'll create this
from attendance.models import Attendance

def mark_attendance(request):
    results = recognize_faces()  # Returns list of student objects recognized
    for student in results:
        Attendance.objects.get_or_create(student=student)
    return render(request, 'attendance/mark_attendance.html', {'students': results})
