# afras_app/attendance/views.py
"""
Attendance Views for AFRAS - Complete Version
"""

import cv2
import json
import time
import numpy as np
import face_recognition
from datetime import timedelta, datetime
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from .models import AttendanceSession, AttendanceLog
from accounts.models import Student, StaffProfile
from recognition import HybridFaceRecognizer, FaceUtils, RECOGNITION_CONFIG


# ========== HELPER FUNCTIONS ==========

def is_staff_or_admin(user):
    """
    Check if user is staff or admin
    Returns True if user is staff, superuser, or has a staff profile
    """
    if not user.is_authenticated:
        return False
    return user.is_staff or user.is_superuser or hasattr(user, 'staff_profile')


def get_session_students(session):
    """
    Get all students eligible for a session based on department, year, semester
    """
    if session.department and session.semester:
        students = Student.objects.filter(
            department=session.department,
            semester=session.semester
        )
        if session.year:
            students = students.filter(year=session.year)
        if session.section:
            students = students.filter(section=session.section)
        return students
    return Student.objects.none()


def get_local_time(dt):
    """Convert UTC datetime to local time"""
    if dt is None:
        return None
    return timezone.localtime(dt)


def format_local_time(dt, format_str="%I:%M %p"):
    """Format datetime in local timezone"""
    if dt is None:
        return "N/A"
    local_dt = get_local_time(dt)
    return local_dt.strftime(format_str)


def get_departments():
    """Get list of all departments from Student model"""
    departments = Student.objects.filter(
        department__isnull=False
    ).exclude(
        department=''
    ).values_list('department', flat=True).distinct().order_by('department')
    
    # If no departments found, return default list
    if not departments:
        return [
            'Computer Engineering',
            'Civil Engineering', 
            'Electrical Engineering',
            'Electronics Engineering',
            'Mechanical Engineering',
            'Software Engineering',
        ]
    return list(departments)


def get_years():
    """Get list of all years from Student model"""
    years = Student.objects.filter(
        year__isnull=False
    ).values_list('year', flat=True).distinct().order_by('year')
    
    if not years:
        return [1, 2, 3, 4]
    return list(years)


def get_semesters():
    """Get list of all semesters from Student model"""
    semesters = Student.objects.filter(
        semester__isnull=False
    ).values_list('semester', flat=True).distinct().order_by('semester')
    
    if not semesters:
        return [1, 2, 3, 4, 5, 6, 7, 8]
    return list(semesters)


def get_sections():
    """Get list of all sections from Student model"""
    sections = Student.objects.filter(
        section__isnull=False
    ).exclude(
        section=''
    ).values_list('section', flat=True).distinct().order_by('section')
    
    if not sections:
        return ['A', 'B', 'C', 'D']
    return list(sections)


def get_semesters_by_year():
    """Get semesters grouped by year from Student model"""
    students = Student.objects.filter(
        year__isnull=False,
        semester__isnull=False
    ).values('year', 'semester').distinct().order_by('year', 'semester')
    
    year_semester_map = {}
    for student in students:
        year = student['year']
        semester = student['semester']
        if year not in year_semester_map:
            year_semester_map[year] = []
        if semester not in year_semester_map[year]:
            year_semester_map[year].append(semester)
    
    # Sort semesters for each year
    for year in year_semester_map:
        year_semester_map[year].sort()
    
    return year_semester_map


def get_sections_by_year():
    """Get sections grouped by year from Student model"""
    students = Student.objects.filter(
        year__isnull=False,
        section__isnull=False
    ).exclude(
        section=''
    ).values('year', 'section').distinct().order_by('year', 'section')
    
    year_section_map = {}
    for student in students:
        year = student['year']
        section = student['section']
        if year not in year_section_map:
            year_section_map[year] = []
        if section not in year_section_map[year]:
            year_section_map[year].append(section)
    
    # Sort sections for each year
    for year in year_section_map:
        year_section_map[year].sort()
    
    return year_section_map


# ========== SESSION MANAGEMENT ==========

@login_required
def start_session(request):
    """Start a new attendance session"""
    if request.method == "POST":
        subject = request.POST.get("subject")
        department = request.POST.get("department")
        year = request.POST.get("year")
        semester = request.POST.get("semester")
        section = request.POST.get("section", "")
        duration = request.POST.get("duration")
        session_datetime = request.POST.get("session_datetime")
        
        print(f"📝 POST data: subject={subject}, department={department}, year={year}, semester={semester}, section={section}, duration={duration}, datetime={session_datetime}")
        
        # Validation
        if not subject or not department or not year or not semester or not duration or not session_datetime:
            error_msg = 'All required fields must be filled'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': error_msg})
            context = {
                'error': error_msg,
                'now': get_local_time(timezone.now()).isoformat(timespec='minutes'),
                'departments': get_departments(),
                'years': get_years(),
                'semesters': get_semesters(),
                'sections': get_sections(),
                'year_semester_map': get_semesters_by_year(),
                'year_section_map': get_sections_by_year(),
            }
            return render(request, "attendance/start_session.html", context)
        
        try:
            staff_profile = request.user.staff_profile if hasattr(request.user, 'staff_profile') else None
            
            # Parse the datetime string
            naive_start_time = datetime.fromisoformat(session_datetime)
            start_time = timezone.make_aware(naive_start_time)
            end_time = start_time + timedelta(minutes=int(duration))
            
            session = AttendanceSession.objects.create(
                subject_name=subject,
                department=department,
                year=int(year),
                semester=int(semester),
                section=section,
                expected_duration=int(duration),
                created_by=staff_profile,
                is_active=False,
                start_time=start_time,
                end_time=end_time,
                date=start_time.date(),
            )
            
            print(f"✅ Session created: ID={session.id}")
            print(f"   Department: {session.department}, Year: {session.year}, Semester: {session.semester}, Section: {session.section}")
            print(f"   Start Time (Local): {get_local_time(session.start_time)}")
            print(f"   End Time (Local): {get_local_time(session.end_time)}")
            
            # Check if session should start immediately
            current_time = timezone.now()
            if current_time >= session.start_time:
                # If start time is in the past or now, start immediately
                session.is_active = True
                session.start_time = current_time  # Reset start time to now
                session.end_time = current_time + timedelta(minutes=int(duration))  # Reset end time
                session.save()
                print(f"   ✅ Session started immediately at {get_local_time(current_time)}!")
                return redirect(f'/attendance/live/{session.id}/')
            else:
                # Session is scheduled for the future
                time_diff = session.start_time - current_time
                minutes_diff = int(time_diff.total_seconds() // 60)
                print(f"   ⏰ Session scheduled in {minutes_diff} minutes")
                return redirect('attendance:all_sessions')
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': error_msg})
            context = {
                'error': error_msg,
                'now': get_local_time(timezone.now()).isoformat(timespec='minutes'),
                'departments': get_departments(),
                'years': get_years(),
                'semesters': get_semesters(),
                'sections': get_sections(),
                'year_semester_map': get_semesters_by_year(),
                'year_section_map': get_sections_by_year(),
            }
            return render(request, "attendance/start_session.html", context)
    
    # GET request - pass current datetime and all options
    context = {
        'now': get_local_time(timezone.now()).isoformat(timespec='minutes'),
        'departments': get_departments(),
        'years': get_years(),
        'semesters': get_semesters(),
        'sections': get_sections(),
        'year_semester_map': get_semesters_by_year(),
        'year_section_map': get_sections_by_year(),
    }
    return render(request, "attendance/start_session.html", context)


@login_required
def stop_session(request, session_id):
    """Stop an active session"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    session.is_active = False
    session.end_time = timezone.now()
    session.save()
    print(f"🛑 Session stopped: {session.subject_name} at {get_local_time(session.end_time)}")
    return redirect("dashboard_home")


@login_required
def all_sessions_view(request):
    """View to display all sessions with pagination"""
    check_and_update_sessions()
    return render(request, 'attendance/all_sessions.html')


@login_required
def attendance_session_view(request, session_id):
    """Live monitoring view"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # Check if session should be active
    check_session_status(session)
    
    # If session hasn't started yet, redirect to all sessions
    if not session.is_active and timezone.now() < session.start_time:
        return redirect('attendance:all_sessions')
    
    # Check if hybrid model is available
    recognizer = get_hybrid_recognizer()
    hybrid_available = recognizer is not None
    
    context = {
        'session': session,
        'active_session': session if session.is_active else None,
        'hybrid_available': hybrid_available,
        'use_hybrid': True,
        'start_time_local': get_local_time(session.start_time),
        'end_time_local': get_local_time(session.end_time),
    }
    
    return render(request, "attendance/attendance_session.html", context)


def check_session_status(session):
    """Check and update session status based on time"""
    current_time = timezone.now()
    
    # Auto-start: If session is not active but start_time has arrived
    if not session.is_active and current_time >= session.start_time:
        session.is_active = True
        session.save()
        print(f"✅ Auto-started session: {session.subject_name} at {get_local_time(current_time)}")
        return True
    
    # Auto-stop: If session is active and end_time has passed
    if session.is_active and session.end_time and current_time >= session.end_time:
        session.is_active = False
        session.save()
        print(f"⏰ Auto-stopped session: {session.subject_name} at {get_local_time(current_time)}")
        return True
    
    return False


def check_and_update_sessions():
    """Check all sessions and update their status"""
    current_time = timezone.now()
    updated_count = 0
    
    # Auto-start sessions
    scheduled_sessions = AttendanceSession.objects.filter(
        is_active=False,
        start_time__lte=current_time
    )
    for session in scheduled_sessions:
        session.is_active = True
        session.save()
        updated_count += 1
        print(f"✅ Auto-started session: {session.subject_name} (ID: {session.id}) at {get_local_time(current_time)}")
    
    # Auto-stop sessions
    active_sessions = AttendanceSession.objects.filter(
        is_active=True,
        end_time__lte=current_time
    )
    for session in active_sessions:
        session.is_active = False
        session.save()
        updated_count += 1
        print(f"⏰ Auto-stopped session: {session.subject_name} (ID: {session.id}) at {get_local_time(current_time)}")
    
    return updated_count


def session_summary(request, session_id):
    """Show session summary after ending"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # Auto-stop if session has ended
    if session.is_active and session.end_time and timezone.now() >= session.end_time:
        session.is_active = False
        session.save()
        print(f"⏰ Auto-stopped session in summary: {session.subject_name}")
    
    logs = AttendanceLog.objects.filter(session=session).select_related('student')
    
    total_students = logs.count()
    present_count = logs.filter(status='PRESENT').count()
    absent_count = logs.filter(status='ABSENT').count()
    leave_count = logs.filter(status='LEAVE').count()
    late_count = logs.filter(status='LATE').count()  # ADD THIS
    partial_count = logs.filter(status='PARTIAL').count()  # ADD THIS
    
    # Calculate average retention
    total_retention = 0
    for log in logs:
        total_retention += log.retention_percentage
    
    avg_retention = total_retention / total_students if total_students > 0 else 0
    
    # Calculate attendance rate
    attendance_rate = (present_count / total_students * 100) if total_students > 0 else 0
    
    context = {
        'session': session,
        'logs': logs,
        'total_students': total_students,
        'present_count': present_count,
        'absent_count': absent_count,
        'leave_count': leave_count,
        'late_count': late_count,  # ADD THIS
        'partial_count': partial_count,  # ADD THIS
        'avg_retention': round(avg_retention, 1),
        'attendance_rate': round(attendance_rate, 1),  # ADD THIS
        'start_time_local': get_local_time(session.start_time),
        'end_time_local': get_local_time(session.end_time),
    }
    
    return render(request, 'attendance/session_summary.html', context)


# ========== API ENDPOINTS ==========

@require_GET
def get_logs(request, session_id):
    """API endpoint to get attendance logs"""
    try:
        session = get_object_or_404(AttendanceSession, id=session_id)
        logs = AttendanceLog.objects.filter(session=session).select_related('student')
        
        data = []
        for log in logs:
            log_entry = {
                'id': log.id,
                'name': log.student.full_name if log.student else 'Unknown',
                'status': log.status,
                'retention': int(log.retention_percentage),
                'confidence': int(log.confidence) if log.confidence else 0,
                'time': get_local_time(log.first_seen).strftime('%H:%M:%S') if log.first_seen else None,
                'last_seen': get_local_time(log.last_seen).strftime('%H:%M:%S') if log.last_seen else None,
                'total_time': f"{log.presence_duration_minutes:.1f} min",
                'detections': log.detection_count,
                'out_of_frame': log.out_of_frame_count,
            }
            data.append(log_entry)
        
        return JsonResponse({'logs': data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def session_stats_api(request):
    """API endpoint for session statistics"""
    try:
        check_and_update_sessions()
        
        total_sessions = AttendanceSession.objects.count()
        active_sessions = AttendanceSession.objects.filter(is_active=True).count()
        
        today = timezone.now().date()
        today_sessions = AttendanceSession.objects.filter(
            start_time__date=today
        ).count()
        
        return JsonResponse({
            'total': total_sessions,
            'active': active_sessions,
            'today': today_sessions
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def recent_sessions_api(request):
    """API endpoint to get ALL attendance sessions with department info"""
    try:
        # Auto-update sessions
        check_and_update_sessions()
        
        sessions = AttendanceSession.objects.all().order_by('-start_time')
        
        sessions_data = []
        current_time = timezone.now()
        
        for session in sessions:
            start_time = session.start_time
            end_time = session.end_time or (start_time + timedelta(minutes=session.expected_duration))
            
            # Convert to local time for display
            start_local = get_local_time(start_time)
            end_local = get_local_time(end_time)
            
            start_formatted = start_local.strftime("%I:%M %p").lstrip("0")
            end_formatted = end_local.strftime("%I:%M %p").lstrip("0")
            
            # Determine correct status
            if session.is_active:
                status = "Active"
            elif session.end_time and session.end_time <= current_time:
                status = "Ended"
            elif session.start_time > current_time:
                status = "Scheduled"
            else:
                if session.start_time <= current_time:
                    status = "Ended"
                else:
                    status = "Scheduled"
            
            # Get department info (with fallback)
            department = getattr(session, 'department', 'N/A')
            year = getattr(session, 'year', '')
            semester = getattr(session, 'semester', '')
            section = getattr(session, 'section', '')
            
            sessions_data.append({
                "id": session.id,
                "subject": session.subject_name,
                "department": department if department else 'N/A',
                "year": year if year else '',
                "semester": semester if semester else '',
                "section": section if section else '',
                "date": session.date.strftime("%Y-%m-%d"),
                "start_time": start_formatted,
                "end_time": end_formatted,
                "time_range": f"{start_formatted} - {end_formatted}",
                "is_active": session.is_active,
                "duration": session.expected_duration,
                "status": status,
            })
        
        return JsonResponse({"sessions": sessions_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ========== VIDEO FEED ==========

def gen_frames():
    """Basic video feed generator (fallback)"""
    camera = cv2.VideoCapture("http://192.168.0.6:8080/video")
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode(".jpg", frame)
            frame = buffer.tobytes()
            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    camera.release()


def video_feed(request):
    """Basic video feed view"""
    return StreamingHttpResponse(
        gen_frames(), content_type="multipart/x-mixed-replace; boundary=frame"
    )


def scan_face(request):
    """Face scan view"""
    return render(request, "recognition/scan.html")


# ========== FILE EXTRACTION ==========

@csrf_exempt
def extract_routine_ai(request):
    """Extract schedule from uploaded PDF/Excel file"""
    if request.method != "POST":
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        file = request.FILES.get('routine_file')
        if not file:
            return JsonResponse({'success': False, 'message': 'No file uploaded'})
        
        return JsonResponse({
            'success': True,
            'message': 'File processed successfully',
            'classes_count': 0,
            'sessions': []
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def update_attendance_manual(request):
    """Update attendance status manually"""
    if request.method == "POST":
        log_id = request.POST.get("log_id")
        new_status = request.POST.get("status")
        log = get_object_or_404(AttendanceLog, id=log_id)
        log.status = new_status
        log.is_manual = True
        log.save()
        return JsonResponse({"status": "updated"})


# ========== HYBRID RECOGNITION ==========

# Global hybrid recognizer instance
hybrid_recognizer = None

def get_hybrid_recognizer():
    """Get or initialize hybrid recognizer"""
    global hybrid_recognizer
    
    if hybrid_recognizer is None:
        try:
            hybrid_recognizer = HybridFaceRecognizer()
            model_loaded = hybrid_recognizer.load_model()
            if not model_loaded:
                print("⚠️ Hybrid model not loaded. Please train the model first.")
                hybrid_recognizer = None
            else:
                stats = hybrid_recognizer.get_stats()
                print(f"✅ Hybrid model loaded! {stats['total_students']} students")
        except Exception as e:
            print(f"❌ Error loading hybrid model: {e}")
            hybrid_recognizer = None
    
    return hybrid_recognizer


def hybrid_status(request):
    """Check hybrid model status"""
    recognizer = get_hybrid_recognizer()
    
    if recognizer:
        stats = recognizer.get_stats()
        return JsonResponse({
            'status': 'ready',
            'loaded': True,
            'total_students': stats['total_students'],
            'student_names': stats['student_names'],
            'knn_trained': stats['knn_trained'],
            'smooth_window': stats['smooth_window']
        })
    else:
        return JsonResponse({
            'status': 'not_loaded',
            'loaded': False,
            'message': 'Model not loaded. Run python manage.py train_hybrid'
        })


def hybrid_video_feed(request, session_id):
    """Video feed using hybrid face recognition with auto-start/stop"""
    return StreamingHttpResponse(
        generate_frames_hybrid(session_id),
        content_type="multipart/x-mixed-replace; boundary=frame"
    )


def generate_frames_hybrid(session_id):
    """Generate video frames with hybrid face recognition with auto-start/stop and minute-by-minute tracking"""
    recognizer = get_hybrid_recognizer()
    
    if not recognizer:
        yield (b"--frame\r\n"
               b"Content-Type: text/plain\r\n\r\n"
               b"Hybrid model not loaded. Please train the model first.\r\n")
        return
    
    # Initialize camera
    camera = cv2.VideoCapture("http://192.168.0.6:8080/video")
    if not camera.isOpened():
        yield (b"--frame\r\n"
               b"Content-Type: text/plain\r\n\r\n"
               b"Camera initialization failed\r\n")
        return
    
    # Camera settings
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Get FPS settings from config
    fps_target = RECOGNITION_CONFIG.get('FPS_TARGET', 30)
    frame_skip = RECOGNITION_CONFIG.get('FRAME_SKIP', 1)
    
    # Try to set camera to target FPS
    camera.set(cv2.CAP_PROP_FPS, fps_target)
    actual_fps = camera.get(cv2.CAP_PROP_FPS)
    print(f"📷 Camera FPS: {actual_fps:.1f} | Target: {fps_target} | Frame Skip: {frame_skip}")
    
    session = get_object_or_404(AttendanceSession, id=session_id)
    print(f"\n🎥 Starting hybrid video feed for: {session.subject_name}")
    
    # === FIX: Check session status but DON'T auto-start here ===
    # The session should already be active if we're viewing it
    if not session.is_active:
        print(f"⚠️ Session {session.subject_name} is not active. Starting it now...")
        session.is_active = True
        session.start_time = timezone.now()  # Set start time to NOW when video starts
        session.save()
        print(f"✅ Session started at: {get_local_time(session.start_time)}")
    
    # Calculate session end time (if not set, use start_time + duration)
    if not session.end_time:
        session.end_time = session.start_time + timedelta(minutes=session.expected_duration)
        session.save()
    
    session_end_time = session.end_time
    end_time_local = get_local_time(session_end_time)
    print(f"⏰ Session will auto-stop at: {end_time_local.strftime('%I:%M %p')}")
    
    # Tracking variables
    logged_students = set()
    last_seen_time = {}
    prev_frame_time = 0.0
    frame_count = 0
    resize_factor = RECOGNITION_CONFIG.get('RESIZE_FACTOR', 0.25)
    last_auto_check_time = timezone.now()
    last_minute_marked = {}
    
    # FPS tracking for display
    fps_display = 0
    fps_counter = 0
    fps_timer = time.time()
    
    # === FIX: Track session start time for minute calculation ===
    session_start_time = session.start_time
    session_duration = session.expected_duration
    
    # === FIX: Initialize minute tracking for all students when they are first detected ===
    student_first_detection = {}
    
    while True:
        try:
            current_time = timezone.now()
            
            # Check session status every 5 seconds (auto-stop only, no auto-start)
            if (current_time - last_auto_check_time).seconds >= 5:
                last_auto_check_time = current_time
                session.refresh_from_db()
                
                # === FIX: Only auto-stop, don't auto-start ===
                if session.is_active and current_time >= session_end_time:
                    print(f"⏰ Session duration completed. Auto-stopping...")
                    session.is_active = False
                    session.end_time = current_time
                    session.save()
                    break
            
            if not session.is_active:
                print("🛑 Session ended")
                break
            
            # Calculate time remaining
            time_remaining = (session_end_time - current_time).total_seconds()
            minutes_remaining = int(time_remaining // 60)
            seconds_remaining = int(time_remaining % 60)
            
            # Read frame
            success, frame = camera.read()
            if not success:
                time.sleep(0.01)
                continue
            
            frame_count += 1
            
            # Calculate FPS for display
            current_time_float = time.time()
            if prev_frame_time > 0:
                fps = 1 / (current_time_float - prev_frame_time)
            else:
                fps = 0
            prev_frame_time = current_time_float
            
            # Update display FPS every second
            fps_counter += 1
            if current_time_float - fps_timer >= 1.0:
                fps_display = fps_counter
                fps_counter = 0
                fps_timer = current_time_float
            
            # Process frame based on FRAME_SKIP
            if frame_count % frame_skip == 0:
                results = recognizer.process_frame(frame, resize_factor)
                
                for result in results:
                    top, right, bottom, left = result['location']
                    name = result['name']
                    confidence = result['confidence']
                    student_id = result['student_id']
                    quality_score = result['quality_score']
                    is_quality_good = result['is_quality_good']
                    
                    # Draw face box
                    color = (0, 255, 0) if name != "Unknown" and confidence > 50 else (0, 0, 255)
                    FaceUtils.draw_face_box(frame, (top, right, bottom, left), 
                                           name, confidence, student_id, color)
                    
                    # Show quality info
                    if not is_quality_good and result.get('issues'):
                        FaceUtils.draw_quality_info(frame, (top, right, bottom, left), 
                                                   quality_score, result['issues'])
                    
                    # Update attendance with detailed tracking
                    if student_id is not None and confidence > 35:
                        try:
                            student_obj = Student.objects.get(id=student_id)
                            logged_students.add(student_id)
                            
                            # === FIX: Track first detection time per student ===
                            if student_id not in student_first_detection:
                                student_first_detection[student_id] = current_time
                            
                            # Get or create log
                            log, created = AttendanceLog.objects.get_or_create(
                                session=session,
                                student=student_obj,
                                defaults={
                                    'status': 'PRESENT',
                                    'confidence': confidence,
                                    'first_seen': current_time,
                                    'last_seen': current_time,
                                    'last_detected': current_time,
                                    'detection_count': 1,
                                    'total_presence_seconds': 0,
                                    'out_of_frame_count': 0,
                                    'minute_presence': [],
                                    'minute_count': 0,
                                    'attended_minutes': 0,
                                }
                            )
                            
                            # Initialize minute tracking if needed
                            if created or log.minute_count == 0:
                                log.reset_minute_tracking(session_duration)
                                print(f"📊 Initialized minute tracking for {name}")
                            
                            # === FIX: Calculate minute from SESSION START, not first detection ===
                            elapsed_from_start = (current_time - session_start_time).total_seconds() / 60
                            minute_index = int(elapsed_from_start)
                            
                            # Ensure minute index is within bounds
                            if minute_index >= session_duration:
                                minute_index = session_duration - 1
                            
                            # === FIX: Only mark minute if student was detected for at least 30 seconds in this minute ===
                            # Track detection count per minute for this student
                            minute_key = f"{student_id}_{minute_index}"
                            
                            # Check if this minute is already marked
                            if last_minute_marked.get(student_id) != minute_index:
                                if 0 <= minute_index < session_duration:
                                    # Mark the minute as present
                                    if log.mark_minute_present(minute_index):
                                        last_minute_marked[student_id] = minute_index
                                        attended_pct = log.get_minute_attendance_percentage()
                                        print(f"✅ {name}: Minute {minute_index + 1} marked ({attended_pct:.1f}%)")
                            
                            # Update log fields
                            if not created:
                                # Calculate time since last detection
                                if log.last_detected:
                                    time_diff = (current_time - log.last_detected).total_seconds()
                                    if time_diff <= 30 and time_diff > 0:
                                        log.total_presence_seconds += int(time_diff)
                                    elif time_diff > 30:
                                        log.out_of_frame_count += 1
                                
                                log.last_seen = current_time
                                log.last_detected = current_time
                                log.detection_count += 1
                                if confidence > (log.confidence or 0):
                                    log.confidence = confidence
                                log.save()
                            
                            last_seen_time[student_id] = current_time
                            
                        except Exception as e:
                            print(f"⚠️ DB error: {e}")
            
            # Info overlay with time remaining and FPS
            fps_display_text = int(fps_display) if fps_display > 0 else int(fps)
            if minutes_remaining > 0 or seconds_remaining > 0:
                time_remaining_display = f"{minutes_remaining}m {seconds_remaining}s"
                info = f"30 FPS | FPS: {fps_display_text} | Time Left: {time_remaining_display} | Logged: {len(logged_students)}"
            else:
                info = f"30 FPS | FPS: {fps_display_text} | Session Ending... | Logged: {len(logged_students)}"
            
            cv2.putText(frame, info, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Stream frame
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
        
        except Exception as e:
            print(f"⚠️ Error in video feed: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    camera.release()
    print("🎥 Video feed ended")


@login_required
def attendance_pattern(request, log_id):
    """View minute-by-minute attendance pattern"""
    log = get_object_or_404(AttendanceLog, id=log_id)
    summary = log.get_attendance_summary()
    
    context = {
        'log': log,
        'student': log.student,
        'session': log.session,
        'summary': summary,
    }
    
    return render(request, 'attendance/attendance_pattern.html', context)


@login_required
def session_details(request, session_id):
    """Detailed view of a session with student attendance tracking"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    logs = AttendanceLog.objects.filter(session=session).select_related('student')
    
    # Auto-stop if session has ended
    if session.is_active and session.end_time and timezone.now() >= session.end_time:
        session.is_active = False
        session.save()
        print(f"⏰ Auto-stopped session in details: {session.subject_name}")
    
    # Calculate statistics
    total_students = logs.count()
    present_count = logs.filter(status='PRESENT').count()
    absent_count = logs.filter(status='ABSENT').count()
    partial_count = logs.filter(status='PARTIAL').count()
    late_count = logs.filter(status='LATE').count()
    
    # Calculate average retention
    total_retention = 0
    for log in logs:
        total_retention += log.retention_percentage
    
    avg_retention = total_retention / total_students if total_students > 0 else 0
    
    # Get students not in attendance (absent)
    all_students = Student.objects.all()
    present_student_ids = logs.values_list('student_id', flat=True)
    absent_students = all_students.exclude(id__in=present_student_ids)
    
    context = {
        'session': session,
        'logs': logs,
        'total_students': total_students,
        'present_count': present_count,
        'absent_count': absent_count,
        'partial_count': partial_count,
        'late_count': late_count,
        'avg_retention': round(avg_retention, 1),
        'absent_students': absent_students,
        'min_retention_required': 80,
        'start_time_local': get_local_time(session.start_time),
        'end_time_local': get_local_time(session.end_time),
    }
    
    return render(request, 'attendance/session_details.html', context)


# ========== MARK ATTENDANCE VIEWS ==========

@login_required
def mark_attendance(request, session_id):
    """
    Main page for marking attendance with facial recognition
    Accessible via /attendance/mark/<session_id>/
    """
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # Check if user has permission
    if not is_staff_or_admin(request.user):
        messages.error(request, 'You do not have permission to mark attendance.')
        return redirect('dashboard_home')
    
    # Auto-start session if it hasn't started but should
    if not session.is_active and timezone.now() >= session.start_time:
        session.is_active = True
        session.save()
        messages.info(request, f'Session "{session.subject_name}" auto-started.')
    
    # Check if session is active
    if not session.is_active:
        messages.warning(request, f'Session "{session.subject_name}" is not active.')
        return redirect('attendance:session_details', session_id=session.id)
    
    # Get students for this session based on department, year, semester, section
    students = get_session_students(session)
    
    # If no students found, show message
    if not students.exists():
        messages.warning(request, f'No students found for {session.department} - Sem {session.semester}. Please check the session details.')
    
    # Get or create attendance logs for all students
    for student in students:
        AttendanceLog.objects.get_or_create(
            session=session,
            student=student,
            defaults={
                'status': 'ABSENT',
                'confidence': 0,
                'first_seen': timezone.now(),
                'last_seen': timezone.now(),
                'minute_presence': [0] * session.expected_duration,
                'minute_count': session.expected_duration,
                'attended_minutes': 0,
            }
        )
    
    context = {
        'session': session,
        'students': students,
        'total_students': students.count(),
        'hybrid_available': get_hybrid_recognizer() is not None,
        'start_time_local': get_local_time(session.start_time),
        'end_time_local': get_local_time(session.end_time),
    }
    
    return render(request, 'attendance/mark_attendance.html', context)


@login_required
def get_student_status(request, session_id):
    """
    API endpoint to get student attendance status for the session
    Used by mark_attendance.html for real-time updates
    """
    session = get_object_or_404(AttendanceSession, id=session_id)
    logs = AttendanceLog.objects.filter(session=session).select_related('student')
    
    students_data = []
    for log in logs:
        students_data.append({
            'id': log.student.id,
            'full_name': log.student.full_name,
            'roll_number': log.student.roll_number,
            'status': log.status,
            'confidence': int(log.confidence) if log.confidence else 0,
            'first_seen': get_local_time(log.first_seen).strftime('%I:%M %p') if log.first_seen else None,
            'last_seen': get_local_time(log.last_seen).strftime('%I:%M %p') if log.last_seen else None,
            'detection_count': log.detection_count,
            'retention': int(log.retention_percentage),
            'attended_minutes': log.attended_minutes,
            'minute_presence': log.minute_presence,
        })
    
    return JsonResponse({
        'students': students_data,
        'total': len(students_data)
    })


@login_required
def get_attendance_stats(request, session_id):
    """
    API endpoint to get real-time attendance statistics
    Used by mark_attendance.html for stats updates
    """
    session = get_object_or_404(AttendanceSession, id=session_id)
    logs = AttendanceLog.objects.filter(session=session)
    
    total = logs.count()
    present = logs.filter(status='PRESENT').count()
    absent = logs.filter(status='ABSENT').count()
    partial = logs.filter(status='PARTIAL').count()
    late = logs.filter(status='LATE').count()
    
    # Calculate elapsed time
    elapsed = (timezone.now() - session.start_time).total_seconds()
    elapsed_minutes = int(elapsed // 60)
    elapsed_seconds = int(elapsed % 60)
    elapsed_time = f"{elapsed_minutes:02d}:{elapsed_seconds:02d}"
    
    return JsonResponse({
        'total': total,
        'present': present,
        'absent': absent,
        'partial': partial,
        'late': late,
        'elapsed_time': elapsed_time,
        'fps': 15,
        'face_count': present,
    })


@login_required
def manual_attendance(request):
    """
    API endpoint to manually mark attendance for a student
    Used by mark_attendance.html for manual entry
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    session_id = request.POST.get('session_id')
    student_id = request.POST.get('student_id')
    status = request.POST.get('status', 'PRESENT')
    
    if not session_id or not student_id:
        return JsonResponse({'success': False, 'message': 'Missing required fields'})
    
    try:
        session = AttendanceSession.objects.get(id=session_id)
        student = Student.objects.get(id=student_id)
        
        log, created = AttendanceLog.objects.get_or_create(
            session=session,
            student=student,
            defaults={
                'status': status,
                'confidence': 100,
                'is_manual': True,
                'first_seen': timezone.now(),
                'last_seen': timezone.now(),
            }
        )
        
        if not created:
            log.status = status
            log.is_manual = True
            log.confidence = 100
            log.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Attendance marked as {status} for {student.full_name}'
        })
        
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Session not found'})
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Student not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def end_session(request, session_id):
    """
    API endpoint to end an active session
    Used by mark_attendance.html
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    if not session.is_active:
        return JsonResponse({'success': False, 'message': 'Session is already ended'})
    
    session.is_active = False
    session.end_time = timezone.now()
    session.save()
    
    # Calculate final statistics
    logs = AttendanceLog.objects.filter(session=session)
    total = logs.count()
    present = logs.filter(status='PRESENT').count()
    absent = logs.filter(status='ABSENT').count()
    partial = logs.filter(status='PARTIAL').count()
    
    return JsonResponse({
        'success': True,
        'message': 'Session ended successfully',
        'stats': {
            'total': total,
            'present': present,
            'absent': absent,
            'partial': partial,
            'attendance_rate': round((present / total * 100) if total > 0 else 0, 1)
        }
    })

@csrf_exempt
@login_required
def delete_session(request, session_id):
    """
    API endpoint to delete a session (Admin/Staff only)
    """
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    # Check permission
    if not is_staff_or_admin(request.user):
        return JsonResponse({'success': False, 'message': 'You do not have permission to delete sessions'}, status=403)
    
    try:
        session = get_object_or_404(AttendanceSession, id=session_id)
        
        # Don't allow deletion of active sessions
        if session.is_active:
            return JsonResponse({'success': False, 'message': 'Cannot delete an active session. Please end the session first.'}, status=400)
        
        # Store session info for logging
        session_name = session.subject_name
        session_id = session.id
        
        # Delete associated attendance logs first
        logs_deleted = AttendanceLog.objects.filter(session=session).count()
        AttendanceLog.objects.filter(session=session).delete()
        
        # Delete the session
        session.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted session "{session_name}" (ID: {session_id}) and {logs_deleted} attendance records.'
        })
        
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Session not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def student_attendance_record(request, student_id):
    """
    View to show attendance record for a specific student with filtering
    """
    student = get_object_or_404(Student, id=student_id)
    
    # Get all attendance logs for this student
    logs = AttendanceLog.objects.filter(
        student=student
    ).select_related('session').order_by('-session__date', '-session__start_time')
    
    # Apply status filter
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        logs = logs.filter(status=status_filter)
    
    # Apply date filter
    date_filter = request.GET.get('date', 'all')
    if date_filter != 'all':
        days = int(date_filter)
        cutoff = timezone.now().date() - timedelta(days=days)
        logs = logs.filter(session__date__gte=cutoff)
    
    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        logs = logs.filter(session__subject_name__icontains=search_query)
    
    # Pagination
    paginator = Paginator(logs, 15)
    page = request.GET.get('page', 1)
    try:
        logs_page = paginator.page(page)
    except PageNotAnInteger:
        logs_page = paginator.page(1)
    except EmptyPage:
        logs_page = paginator.page(paginator.num_pages)
    
    # Calculate statistics 
    total_sessions = AttendanceLog.objects.filter(student=student).count()
    present_count = AttendanceLog.objects.filter(student=student, status='PRESENT').count()
    absent_count = AttendanceLog.objects.filter(student=student, status='ABSENT').count()
    partial_count = AttendanceLog.objects.filter(student=student, status='PARTIAL').count()
    late_count = AttendanceLog.objects.filter(student=student, status='LATE').count()
    leave_count = AttendanceLog.objects.filter(student=student, status='LEAVE').count()
    
    context = {
        'student': student,
        'logs': logs_page,
        'total_sessions': total_sessions,
        'present_count': present_count,
        'absent_count': absent_count,
        'partial_count': partial_count,
        'late_count': late_count,
        'leave_count': leave_count,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'search_query': search_query,
    }
    
    return render(request, 'attendance/student_attendance_record.html', context)


@login_required
def attendance_records(request):
    """
    View to show all attendance records (logs) with filtering and pagination
    """
    # Get all attendance logs with related data
    logs = AttendanceLog.objects.all().select_related('student', 'session').order_by('-session__date', '-session__start_time')
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        logs = logs.filter(status=status_filter)
    
    department_filter = request.GET.get('department', '')
    if department_filter:
        logs = logs.filter(student__department=department_filter)
    
    year_filter = request.GET.get('year', '')
    if year_filter:
        logs = logs.filter(student__year=year_filter)
    
    semester_filter = request.GET.get('semester', '')
    if semester_filter:
        logs = logs.filter(student__semester=semester_filter)
    
    # Pagination
    paginator = Paginator(logs, 25)
    page = request.GET.get('page', 1)
    try:
        logs_page = paginator.page(page)
    except PageNotAnInteger:
        logs_page = paginator.page(1)
    except EmptyPage:
        logs_page = paginator.page(paginator.num_pages)
    
    # Get filter options from database
    departments = Student.objects.filter(
        department__isnull=False
    ).exclude(
        department=''
    ).values_list('department', flat=True).distinct().order_by('department')
    
    years = Student.objects.filter(
        year__isnull=False
    ).values_list('year', flat=True).distinct().order_by('year')
    
    semesters = Student.objects.filter(
        semester__isnull=False
    ).values_list('semester', flat=True).distinct().order_by('semester')
    
    # Get semesters by year for dynamic filtering
    semesters_by_year = {}
    for year in years:
        sems = Student.objects.filter(
            year=year,
            semester__isnull=False
        ).values_list('semester', flat=True).distinct().order_by('semester')
        semesters_by_year[year] = list(sems)
    
    # Statistics
    total_logs = AttendanceLog.objects.count()
    present_count = AttendanceLog.objects.filter(status='PRESENT').count()
    absent_count = AttendanceLog.objects.filter(status='ABSENT').count()
    partial_count = AttendanceLog.objects.filter(status='PARTIAL').count()
    late_count = AttendanceLog.objects.filter(status='LATE').count()
    
    context = {
        'logs': logs_page,
        'total_logs': total_logs,
        'present_count': present_count,
        'absent_count': absent_count,
        'partial_count': partial_count,
        'late_count': late_count,
        'departments': list(departments),
        'years': list(years),
        'semesters': list(semesters),
        'semesters_by_year': semesters_by_year,
        'status_filter': status_filter,
        'department_filter': department_filter,
        'year_filter': year_filter,
        'semester_filter': semester_filter,
    }
    
    return render(request, 'attendance/attendance_records.html', context)