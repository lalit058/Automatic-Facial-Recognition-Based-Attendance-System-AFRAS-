from django.shortcuts import render
from recognition.utils import recognize_faces  # We'll create this
from attendance.models import Attendance
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

def mark_attendance(request):
    results = recognize_faces()  # Returns list of student objects recognized
    for student in results:
        Attendance.objects.get_or_create(student=student)
    return render(request, 'attendance/mark_attendance.html', {'students': results})

@login_required
def attendance_scan(request):
    # This will eventually hold your OpenCV/Webcam logic
    return render(request, 'recognition/scan.html')
