import cv2
from django.http import StreamingHttpResponse
from django.shortcuts import render
from django.utils import timezone
from attendance.models import Attendance
# from .utils import recognize_faces  # Comment this out until utils.py is ready

def gen_frames():
    camera = cv2.VideoCapture(0)
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Placeholder for processing logic
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def video_feed(request):
    """This is the view that the dashboard <img> tag calls"""
    return StreamingHttpResponse(gen_frames(),
                                 content_type='multipart/x-mixed-replace; boundary=frame')

def scan_face(request):
    """This matches your recognition/urls.py 'scan/' path"""
    return render(request, 'recognition/scan.html')