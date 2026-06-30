# import cv2
# from django.http import StreamingHttpResponse
# from django.shortcuts import render
# from django.utils import timezone
# from attendance.models import AttendanceSession, AttendanceLog

# # from .utils import recognize_faces  # Comment this out until utils.py is ready


# def gen_frames():
#     camera = cv2.VideoCapture(0)
#     while True:
#         success, frame = camera.read()
#         if not success:
#             break
#         else:
#             # Placeholder for processing logic
#             ret, buffer = cv2.imencode(".jpg", frame)
#             frame = buffer.tobytes()
#             yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


# def video_feed(request):
#     """This is the view that the dashboard <img> tag calls"""
#     return StreamingHttpResponse(
#         gen_frames(), content_type="multipart/x-mixed-replace; boundary=frame"
#     )


# def scan_face(request):
#     """This matches your recognition/urls.py 'scan/' path"""
#     return render(request, "recognition/scan.html")







# recognition/views.py
import cv2
import numpy as np
import json
import logging
import base64
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from attendance.models import AttendanceSession, AttendanceLog
from accounts.models import Student, SystemConfiguration, Notification
from .hybrid_recognizer import HybridFaceRecognizer  # Correct import name

logger = logging.getLogger(__name__)

# Global recognizer instance with semester filter
_active_recognizer = None
_current_semester = None
_current_session_id = None


def get_recognizer_for_semester(semester, session_id=None):
    """
    Get or create a recognizer instance for a specific semester
    Only loads students from that semester
    """
    global _active_recognizer, _current_semester, _current_session_id
    
    # If semester changed or no recognizer, create new one
    if (_active_recognizer is None or 
        _current_semester != semester or 
        _current_session_id != session_id):
        
        # Create new recognizer
        recognizer = HybridFaceRecognizer()
        
        # Get students for this semester with face encodings
        students = Student.objects.filter(
            semester=semester
        ).exclude(
            face_encoding__isnull=True
        ).exclude(
            face_encoding__exact=''
        ).exclude(
            face_encoding__exact='null'
        )
        
        # Add each student to the recognizer
        for student in students:
            try:
                encoding = None
                if isinstance(student.face_encoding, str):
                    encoding = np.array(json.loads(student.face_encoding))
                elif isinstance(student.face_encoding, list):
                    encoding = np.array(student.face_encoding)
                else:
                    encoding = np.array(student.face_encoding)
                
                if encoding is not None and len(encoding) > 0:
                    recognizer.add_student(
                        encoding=encoding,
                        name=student.full_name,
                        student_id=student.id
                    )
            except Exception as e:
                logger.warning(f"Error loading encoding for student {student.id}: {e}")
                continue
        
        _active_recognizer = recognizer
        _current_semester = semester
        _current_session_id = session_id
        
        logger.info(f"Loaded recognizer for Semester {semester} with {len(recognizer.known_encodings)} students")
    
    return _active_recognizer


def gen_frames_with_recognition(session_id, semester):
    """
    Generate video frames with face recognition for a specific semester
    Only recognizes students from that semester
    """
    camera = cv2.VideoCapture(0)
    
    # Set camera properties for better performance
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)
    
    # Get recognizer for this semester
    recognizer = get_recognizer_for_semester(semester, session_id)
    
    # Get session
    try:
        session = AttendanceSession.objects.get(id=session_id)
    except AttendanceSession.DoesNotExist:
        logger.error(f"Session {session_id} not found")
        camera.release()
        return
    
    frame_count = 0
    recognition_interval = 3  # Process every 3rd frame for performance
    last_recognized = {}  # Track last recognition time per student
    recognition_cooldown = 10  # Seconds before re-recognizing same student
    
    while True:
        success, frame = camera.read()
        if not success:
            break
        
        frame_count += 1
        
        # Only process every Nth frame for recognition
        if frame_count % recognition_interval == 0:
            try:
                # Process frame with recognizer
                results = recognizer.process_frame(frame, resize_factor=0.25)
                
                for result in results:
                    if result['name'] != 'Unknown' and result['student_id']:
                        student_id = result['student_id']
                        confidence = result['confidence']
                        
                        # Check cooldown
                        current_time = timezone.now()
                        if student_id in last_recognized:
                            time_diff = (current_time - last_recognized[student_id]).total_seconds()
                            if time_diff < recognition_cooldown:
                                continue
                        
                        try:
                            student = Student.objects.get(id=student_id)
                            
                            # Double-check semester
                            if student.semester != semester:
                                continue
                            
                            # Get or create attendance log
                            attendance_log, created = AttendanceLog.objects.get_or_create(
                                session=session,
                                student=student,
                                defaults={
                                    'status': 'PRESENT',
                                    'confidence': confidence / 100.0,  # Convert to 0-1 scale
                                    'first_seen': timezone.now(),
                                    'last_seen': timezone.now(),
                                    'is_manual': False,
                                    'detection_count': 1,
                                    'total_presence_seconds': 0,
                                }
                            )
                            
                            if not created:
                                # Update existing log
                                attendance_log.last_seen = timezone.now()
                                attendance_log.detection_count += 1
                                if confidence / 100.0 > (attendance_log.confidence or 0):
                                    attendance_log.confidence = confidence / 100.0
                                attendance_log.save()
                            else:
                                # Send notification for new attendance
                                try:
                                    if hasattr(student, 'user'):
                                        Notification.send_notification(
                                            user=student.user,
                                            title='Attendance Marked',
                                            message=f'Attendance marked for {session.subject_name}',
                                            notification_type='attendance'
                                        )
                                except Exception as e:
                                    logger.warning(f"Could not send notification: {e}")
                                
                                logger.info(f"✅ Marked attendance for {student.full_name} (Semester {student.semester})")
                            
                            # Update last recognized time
                            last_recognized[student_id] = current_time
                            
                            # Draw label on frame
                            top, right, bottom, left = result['location']
                            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                            cv2.putText(frame, f"{student.full_name} ✓", 
                                      (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                                      0.6, (0, 255, 0), 2)
                            
                        except Student.DoesNotExist:
                            logger.warning(f"Student {student_id} not found")
                            continue
                
            except Exception as e:
                logger.error(f"Recognition error: {e}")
        
        # Encode frame for streaming
        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = buffer.tobytes()
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
    
    camera.release()


def gen_frames_without_recognition():
    """
    Original function for video feed without recognition (for testing)
    """
    camera = cv2.VideoCapture(0)
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode(".jpg", frame)
            frame = buffer.tobytes()
            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    camera.release()


def video_feed(request, session_id=None):
    """
    Video feed with optional recognition for a specific session
    If session_id provided, uses semester-based filtering
    """
    if session_id:
        try:
            session = AttendanceSession.objects.get(id=session_id)
            semester = session.semester if hasattr(session, 'semester') else None
            
            if not semester:
                # Try to get semester from session or default
                return StreamingHttpResponse(
                    gen_frames_without_recognition(), 
                    content_type="multipart/x-mixed-replace; boundary=frame"
                )
            
            return StreamingHttpResponse(
                gen_frames_with_recognition(session_id, semester),
                content_type="multipart/x-mixed-replace; boundary=frame"
            )
        except AttendanceSession.DoesNotExist:
            return StreamingHttpResponse(
                gen_frames_without_recognition(),
                content_type="multipart/x-mixed-replace; boundary=frame"
            )
    else:
        # Fallback to basic video feed
        return StreamingHttpResponse(
            gen_frames_without_recognition(),
            content_type="multipart/x-mixed-replace; boundary=frame"
        )


def scan_face(request, session_id=None):
    """
    Scan face view with semester filtering
    """
    context = {
        'session_id': session_id,
        'semester_filter_applied': False,
        'enrolled_students': 0,
        'students_with_encoding': 0,
    }
    
    if session_id:
        try:
            session = AttendanceSession.objects.get(id=session_id)
            semester = session.semester if hasattr(session, 'semester') else None
            
            if semester:
                # Get statistics for this semester
                total_students = Student.objects.filter(semester=semester).count()
                with_encoding = Student.objects.filter(
                    semester=semester
                ).exclude(
                    face_encoding__isnull=True
                ).exclude(
                    face_encoding__exact=''
                ).count()
                
                context.update({
                    'semester_filter_applied': True,
                    'semester': semester,
                    'enrolled_students': total_students,
                    'students_with_encoding': with_encoding,
                    'session': session,
                    'subject_name': getattr(session, 'subject_name', 'N/A'),
                    'department': getattr(session, 'department', 'N/A'),
                    'year': getattr(session, 'year', 'N/A'),
                    'section': getattr(session, 'section', 'N/A'),
                })
        except AttendanceSession.DoesNotExist:
            pass
    
    return render(request, "recognition/scan.html", context)


@login_required
@csrf_exempt
def mark_attendance_with_semester_filter(request, session_id):
    """
    API endpoint to mark attendance with semester filtering
    Called by JavaScript when a face is detected
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        session = get_object_or_404(AttendanceSession, id=session_id)
        semester = session.semester if hasattr(session, 'semester') else None
        
        if not semester:
            return JsonResponse({
                'success': False,
                'error': 'Semester not specified for this session'
            }, status=400)
        
        # Get image from request
        if not request.FILES.get('image'):
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        image_file = request.FILES['image']
        nparr = np.frombuffer(image_file.read(), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return JsonResponse({'error': 'Invalid image'}, status=400)
        
        # Get recognizer for this semester
        recognizer = get_recognizer_for_semester(semester, session_id)
        
        # Process frame with recognizer
        results = recognizer.process_frame(img, resize_factor=0.5)
        
        recognized_student = None
        for result in results:
            if result['name'] != 'Unknown' and result['student_id']:
                recognized_student = result
                break
        
        if recognized_student:
            student_id = recognized_student['student_id']
            confidence = recognized_student['confidence']
            
            student = Student.objects.get(id=student_id)
            
            # Double-check semester
            if student.semester != semester:
                return JsonResponse({
                    'success': False,
                    'error': 'Student not enrolled in this semester',
                    'semester_mismatch': True
                }, status=403)
            
            # Get or create attendance log
            attendance_log, created = AttendanceLog.objects.get_or_create(
                session=session,
                student=student,
                defaults={
                    'status': 'PRESENT',
                    'first_seen': timezone.now(),
                    'last_seen': timezone.now(),
                    'is_manual': False,
                    'detection_count': 1,
                    'total_presence_seconds': 0,
                    'confidence': confidence / 100.0,
                }
            )
            
            if created:
                # Send notification for new attendance
                try:
                    if hasattr(student, 'user'):
                        Notification.send_notification(
                            user=student.user,
                            title='Attendance Marked',
                            message=f'You have been marked present for {session.subject_name}',
                            notification_type='attendance'
                        )
                except Exception as e:
                    logger.warning(f"Could not send notification: {e}")
                
                return JsonResponse({
                    'success': True,
                    'student': {
                        'id': student.id,
                        'name': student.full_name,
                        'roll_number': student.roll_number,
                        'semester': student.semester,
                        'department': student.department,
                        'photo_url': student.photo.url if student.photo else None
                    },
                    'is_new_record': True,
                    'status': attendance_log.status,
                    'confidence': confidence
                })
            else:
                # Update existing log
                attendance_log.last_seen = timezone.now()
                attendance_log.detection_count += 1
                if confidence / 100.0 > (attendance_log.confidence or 0):
                    attendance_log.confidence = confidence / 100.0
                attendance_log.save()
                
                return JsonResponse({
                    'success': True,
                    'student': {
                        'id': student.id,
                        'name': student.full_name,
                        'roll_number': student.roll_number,
                    },
                    'is_new_record': False,
                    'already_marked': True,
                    'status': attendance_log.status,
                    'detection_count': attendance_log.detection_count
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Face not recognized or student not in this semester',
                'semester_applied': semester
            }, status=404)
            
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Session not found'}, status=404)
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in mark_attendance_with_semester_filter: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def get_semester_students_api(request):
    """
    API endpoint to get students for a specific semester
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET method required'}, status=405)
    
    semester = request.GET.get('semester')
    
    if not semester:
        return JsonResponse({'error': 'Semester parameter required'}, status=400)
    
    try:
        semester = int(semester)
    except ValueError:
        return JsonResponse({'error': 'Invalid semester value'}, status=400)
    
    students = Student.objects.filter(semester=semester).values(
        'id', 'full_name', 'roll_number', 'department', 'year', 'section'
    )
    
    students_with_encoding = Student.objects.filter(
        semester=semester
    ).exclude(
        face_encoding__isnull=True
    ).exclude(
        face_encoding__exact=''
    ).count()
    
    return JsonResponse({
        'success': True,
        'semester': semester,
        'total_students': students.count(),
        'students_with_encoding': students_with_encoding,
        'students': list(students)
    })


@login_required
def get_semester_stats(request):
    """
    Get statistics about students per semester
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET method required'}, status=405)
    
    semesters = Student.objects.values_list('semester', flat=True).distinct().order_by('semester')
    
    stats = []
    for sem in semesters:
        total = Student.objects.filter(semester=sem).count()
        with_encoding = Student.objects.filter(
            semester=sem
        ).exclude(
            face_encoding__isnull=True
        ).exclude(
            face_encoding__exact=''
        ).count()
        
        stats.append({
            'semester': sem,
            'total_students': total,
            'students_with_encoding': with_encoding,
            'percentage_with_encoding': round((with_encoding / total * 100) if total > 0 else 0, 2)
        })
    
    return JsonResponse({
        'success': True,
        'stats': stats
    })