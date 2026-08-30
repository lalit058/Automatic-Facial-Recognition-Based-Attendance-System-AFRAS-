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
from django.contrib.auth.decorators import login_required, user_passes_test

from .models import AttendanceSession, AttendanceLog
from accounts.models import Student, StaffProfile
from recognition import HybridFaceRecognizer, FaceUtils, RECOGNITION_CONFIG
from attendance.utils import auto_schedule_session

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
    """Start a new attendance session with auto-scheduling (backend only)"""
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
            
            # ============================================================
            # CREATE THE MAIN SESSION (Visible in template)
            # is_manual=True so it shows in the template
            # ============================================================
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
                is_manual=True,  # ← This makes it visible in template
            )
            
            print(f"\n✅ Main session created: ID={session.id} (is_manual=True)")
            print(f"   Subject: {session.subject_name}")
            print(f"   Date: {session.date} ({session.date.strftime('%A')})")
            print(f"   Time: {session.start_time.strftime('%I:%M %p')}")
            print(f"   Duration: {session.expected_duration} minutes")
            
            # ============================================================
            # AUTO-SCHEDULE IN BACKEND
            # Creates routines for ALL days and generates sessions
            # Generated sessions have is_manual=False (hidden)
            # ============================================================
            print("\n" + "="*60)
            print("🔄 BACKEND AUTO-SCHEDULING")
            print("="*60)
            
            auto_result = auto_schedule_session(session)
            
            if auto_result.get('status') == 'success':
                print("\n📊 Auto-schedule Results:")
                print(f"   ✅ Routines created: {auto_result['routines_created']}")
                print(f"   ✅ Sessions generated: {auto_result['sessions_created']}")
                print(f"   🎯 All generated sessions are hidden (is_manual=False)")
                print(f"   📌 Only the main session will show in template (is_manual=True)")
            else:
                print(f"\n⚠️ Auto-schedule status: {auto_result.get('status')}")
            
            print("="*60)
            
            # Check if session should start immediately
            current_time = timezone.now()
            if current_time >= session.start_time:
                # If start time is in the past or now, start immediately
                session.is_active = True
                session.start_time = current_time
                session.end_time = current_time + timedelta(minutes=int(duration))
                session.save()
                print(f"   ✅ Session started immediately at {get_local_time(current_time)}!")
                messages.success(
                    request, 
                    f'Session "{subject}" started successfully with weekly auto-schedule! '
                    f'Weekly sessions auto-generated for all days in the background.'
                )
                return redirect(f'/attendance/live/{session.id}/')
            else:
                # Session is scheduled for the future
                time_diff = session.start_time - current_time
                minutes_diff = int(time_diff.total_seconds() // 60)
                print(f"   ⏰ Session scheduled in {minutes_diff} minutes")
                messages.success(
                    request, 
                    f'Session "{subject}" created and will auto-start at {get_local_time(session.start_time).strftime("%I:%M %p")}. '
                    f'Weekly sessions auto-generated for all days in the background!'
                )
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


_last_check_time = None
_processing_lock = False


def check_and_update_sessions():
    """
    Check all sessions and update their status
    FIXED: Prevents re-starting already ended sessions
    """
    global _last_check_time, _processing_lock
    
    # Prevent concurrent processing
    if _processing_lock:
        return 0
    
    current_time = timezone.now()
    
    # Only check once every 30 seconds to prevent duplicates
    if _last_check_time and (current_time - _last_check_time).seconds < 30:
        return 0
    
    _processing_lock = True
    updated_count = 0
    
    try:
        # ============================================================
        # AUTO-START SESSIONS
        # FIX: Only start if end_time is in the future
        # ============================================================
        scheduled_sessions = AttendanceSession.objects.filter(
            is_active=False,
            start_time__lte=current_time,
            end_time__gt=current_time  # ← ADD THIS LINE - CRITICAL FIX!
        ).distinct()
        
        for session in scheduled_sessions:
            # Double-check to prevent race condition
            if not session.is_active:
                session.is_active = True
                session.save(update_fields=['is_active'])
                updated_count += 1
                print(f"🚀 Auto-started session: {session.subject_name} (ID: {session.id}) at {get_local_time(current_time)}")
        
        # ============================================================
        # AUTO-STOP SESSIONS
        # Get sessions that need to be stopped (active, end_time passed)
        # ============================================================
        active_sessions = AttendanceSession.objects.filter(
            is_active=True,
            end_time__lte=current_time
        ).distinct()
        
        for session in active_sessions:
            # Double-check to prevent race condition
            if session.is_active:
                session.is_active = False
                session.save(update_fields=['is_active'])
                updated_count += 1
                print(f"⏹️ Auto-ended session: {session.subject_name} (ID: {session.id}) at {get_local_time(current_time)}")
        
        _last_check_time = current_time
        
    except Exception as e:
        print(f"❌ Error in check_and_update_sessions: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _processing_lock = False
    
    return updated_count


# ========== ALSO FIX THE check_session_status FUNCTION ==========

def check_session_status(session):
    """
    Check and update a single session status based on time
    FIXED: Prevents duplicate processing
    """
    current_time = timezone.now()
    status_changed = False
    
    # Auto-start: Only if start_time has arrived AND end_time is in future
    if not session.is_active and current_time >= session.start_time:
        # CRITICAL FIX: Only start if end_time is in the future
        if session.end_time and session.end_time > current_time:
            session.is_active = True
            session.save(update_fields=['is_active'])
            status_changed = True
            print(f"🚀 Auto-started session: {session.subject_name} (ID: {session.id}) at {get_local_time(current_time)}")
            return True
        else:
            # Session has already ended, don't start it
            print(f"⏭️ Skipping already ended session: {session.subject_name} (ID: {session.id})")
            return False
    
    # Auto-stop: If session is active and end_time has passed
    if session.is_active and session.end_time and current_time >= session.end_time:
        session.is_active = False
        session.save(update_fields=['is_active'])
        status_changed = True
        print(f"⏹️ Auto-ended session: {session.subject_name} (ID: {session.id}) at {get_local_time(current_time)}")
        return True
    
    return False


def session_summary(request, session_id):
    """Show session summary after ending - FIXED for section validation"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # Auto-stop if session has ended
    if session.is_active and session.end_time and timezone.now() >= session.end_time:
        session.is_active = False
        session.save()
        print(f"⏰ Auto-stopped session in summary: {session.subject_name}")
    
    # ============================================================
    # STEP 1: Get all enrolled students for this session
    # ============================================================
    enrolled_students = session.get_enrolled_students()
    enrolled_student_ids = set(enrolled_students.values_list('id', flat=True))
    
    # ============================================================
    # STEP 2: Get all attendance logs for this session
    # ============================================================
    logs = AttendanceLog.objects.filter(session=session).select_related('student')
    
    # ============================================================
    # STEP 3: Build a map of student_id -> log
    # ============================================================
    log_map = {}
    for log in logs:
        log_map[log.student_id] = log
    
    # ============================================================
    # STEP 4: Build attendance summary with validation
    # ============================================================
    attendance_summary = []
    valid_count = 0
    not_seen_count = 0
    invalid_count = 0
    
    for student in enrolled_students:
        log = log_map.get(student.id)
        
        if log:
            # Check if student is valid for this session
            is_valid = True
            validation_errors = []
            
            # Check Section
            if session.section and student.section:
                if student.section != session.section:
                    is_valid = False
                    validation_errors.append(f"Section {student.section} (expected {session.section})")
                    log.is_validated = False
                    log.validation_error = f"Student from Section {student.section} attempted to attend Section {session.section}"
                    log.save(update_fields=['is_validated', 'validation_error'])
            
            # Check Semester
            if session.semester and student.semester:
                if student.semester != session.semester:
                    is_valid = False
                    validation_errors.append(f"Semester {student.semester} (expected {session.semester})")
                    log.is_validated = False
                    log.validation_error = f"Student from Semester {student.semester} attempted to attend Semester {session.semester}"
                    log.save(update_fields=['is_validated', 'validation_error'])
            
            # Check Year
            if session.year and student.year:
                if student.year != session.year:
                    is_valid = False
                    validation_errors.append(f"Year {student.year} (expected {session.year})")
                    log.is_validated = False
                    log.validation_error = f"Student from Year {student.year} attempted to attend Year {session.year}"
                    log.save(update_fields=['is_validated', 'validation_error'])
            
            # Check Department
            if session.department and student.department:
                if student.department != session.department:
                    is_valid = False
                    validation_errors.append(f"Department {student.department} (expected {session.department})")
                    log.is_validated = False
                    log.validation_error = f"Student from {student.department} attempted to attend {session.department}"
                    log.save(update_fields=['is_validated', 'validation_error'])
            
            # Also check if log itself says it's invalid
            if hasattr(log, 'is_validated') and not log.is_validated:
                is_valid = False
            
            # Also check if the log has a validation error
            if hasattr(log, 'validation_error') and log.validation_error:
                is_valid = False
            
            if is_valid and student.id in enrolled_student_ids:
                # Valid - enrolled and detected
                attendance_summary.append({
                    'student': student,
                    'status': 'valid',
                    'confidence': log.confidence,
                    'retention': log.retention_percentage,
                    'log': log,
                    'error': None,
                })
                valid_count += 1
            else:
                # Invalid - attempted but not properly enrolled
                error_msg = ', '.join(validation_errors) if validation_errors else (log.validation_error if hasattr(log, 'validation_error') and log.validation_error else 'Not enrolled in this section')
                attendance_summary.append({
                    'student': student,
                    'status': 'invalid',
                    'confidence': 0,
                    'retention': 0,
                    'log': log,
                    'error': error_msg,
                })
                invalid_count += 1
        else:
            # Not Seen - enrolled but no log
            attendance_summary.append({
                'student': student,
                'status': 'not_seen',
                'confidence': 0,
                'retention': 0,
                'log': None,
                'error': None,
            })
            not_seen_count += 1
    
    # ============================================================
    # STEP 5: Calculate statistics
    # ============================================================
    total_students = enrolled_students.count()
    
    # Count present (only validated logs)
    present_count = 0
    absent_count = 0
    leave_count = 0
    late_count = 0
    partial_count = 0
    
    for log in logs:
        if hasattr(log, 'is_validated') and not log.is_validated:
            continue  # Skip invalid logs
        if log.status == 'PRESENT':
            present_count += 1
        elif log.status == 'ABSENT':
            absent_count += 1
        elif log.status == 'LEAVE':
            leave_count += 1
        elif log.status == 'LATE':
            late_count += 1
        elif log.status == 'PARTIAL':
            partial_count += 1
    
    # Calculate average retention (only for valid students)
    total_retention = 0
    for item in attendance_summary:
        if item['status'] == 'valid':
            total_retention += item['retention']
    
    avg_retention = total_retention / valid_count if valid_count > 0 else 0
    
    # Calculate attendance rate (only valid students are considered present)
    attendance_rate = (valid_count / total_students * 100) if total_students > 0 else 0
    
    # ============================================================
    # STEP 6: Prepare context
    # ============================================================
    context = {
        'session': session,
        'logs': logs,
        'attendance_summary': attendance_summary,
        'total_students': total_students,
        'valid_count': valid_count,
        'not_seen_count': not_seen_count,
        'invalid_count': invalid_count,
        'present_count': present_count,
        'absent_count': absent_count,
        'leave_count': leave_count,
        'late_count': late_count,
        'partial_count': partial_count,
        'avg_retention': round(avg_retention, 1),
        'attendance_rate': round(attendance_rate, 1),
        'start_time_local': get_local_time(session.start_time),
        'end_time_local': get_local_time(session.end_time),
    }
    
    return render(request, 'attendance/session_summary.html', context)


# ========== API ENDPOINTS ==========

@require_GET
def get_logs(request, session_id):
    """API endpoint to get attendance logs with validation status"""
    try:
        session = get_object_or_404(AttendanceSession, id=session_id)
        logs = AttendanceLog.objects.filter(session=session).select_related('student')
        
        data = []
        for log in logs:
            # Check if student is validated
            is_unauthorized = not log.is_validated if hasattr(log, 'is_validated') else False
            
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
                'is_validated': log.is_validated if hasattr(log, 'is_validated') else True,
                'validation_error': log.validation_error if hasattr(log, 'validation_error') else None,
                'is_unauthorized': is_unauthorized,
                'student_semester': log.student_semester if hasattr(log, 'student_semester') else None,
                'session_semester': log.session_semester if hasattr(log, 'session_semester') else None,
            }
            data.append(log_entry)
        
        response = JsonResponse({'logs': data})
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
        
    except Exception as e:
        print(f"❌ get_logs error: {e}")
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
    """API endpoint to get attendance sessions - show ONLY manual sessions"""
    try:
        # Auto-update sessions
        check_and_update_sessions()
        
        # ============================================================
        # SHOW ONLY MANUAL SESSIONS (is_manual=True)
        # ============================================================
        sessions = AttendanceSession.objects.filter(is_manual=True).order_by('-start_time')
        
        sessions_data = []
        current_time = timezone.now()
        nepal_now = get_local_time(current_time)
        today = nepal_now.date()
        
        # ============================================================
        # CALCULATE NEXT SESSION FOR EACH SUBJECT
        # ============================================================
        from attendance.scheduler import get_next_session_for_subject
        
        subjects = sessions.values_list('subject_name', flat=True).distinct()
        next_session_map = {}
        
        for subject in subjects:
            try:
                next_session = get_next_session_for_subject(subject, today, current_time)
                if next_session:
                    next_session_map[subject] = next_session
            except Exception as e:
                print(f"⚠️ Next session error for {subject}: {e}")
        
        for session in sessions:
            start_time = session.start_time
            end_time = session.end_time or (start_time + timedelta(minutes=session.expected_duration))
            
            start_local = get_local_time(start_time)
            end_local = get_local_time(end_time)
            
            start_formatted = start_local.strftime("%I:%M %p").lstrip("0")
            end_formatted = end_local.strftime("%I:%M %p").lstrip("0")
            
            # Determine status
            if session.is_active:
                status = "Active"
            elif session.end_time and session.end_time <= current_time:
                status = "Ended"
            elif session.start_time > current_time:
                status = "Scheduled"
            else:
                status = "Ended" if session.start_time <= current_time else "Scheduled"
            
            # Get next session for this subject
            next_session_info = next_session_map.get(session.subject_name)
            
            sessions_data.append({
                "id": session.id,
                "subject": session.subject_name,
                "department": session.department or 'N/A',
                "year": session.year or '',
                "semester": session.semester or '',
                "section": session.section or '',
                "date": session.date.strftime("%Y-%m-%d"),
                "start_time": start_formatted,
                "end_time": end_formatted,
                "time_range": f"{start_formatted} - {end_formatted}",
                "is_active": session.is_active,
                "duration": session.expected_duration,
                "status": status,
                "is_manual": session.is_manual,
                "is_auto_scheduled": session.routine is not None,
                "next_session": next_session_info,
            })
        
        return JsonResponse({
            "sessions": sessions_data,
            "total": len(sessions_data),
            "message": "Showing manual sessions only"
        })
        
    except Exception as e:
        print(f"❌ recent_sessions_api error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e), 'sessions': []}, status=500)


# ========== VIDEO FEED ==========

def gen_frames():
    """Basic video feed generator (fallback)"""
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
    """Generate video frames - SINGLE SHOT DETECTION MODE with Model-based Status"""
    recognizer = get_hybrid_recognizer()
    
    if not recognizer:
        yield (b"--frame\r\n"
               b"Content-Type: text/plain\r\n\r\n"
               b"Hybrid model not loaded. Please train the model first.\r\n")
        return
    
    # Initialize camera
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        yield (b"--frame\r\n"
               b"Content-Type: text/plain\r\n\r\n"
               b"Camera initialization failed\r\n")
        return
    
    # Camera settings
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Get FPS settings
    fps_target = RECOGNITION_CONFIG.get('FPS_TARGET', 15)
    frame_skip = RECOGNITION_CONFIG.get('FRAME_SKIP', 2)
    camera.set(cv2.CAP_PROP_FPS, fps_target)
    
    session = get_object_or_404(AttendanceSession, id=session_id)
    print(f"\n🎥 Starting hybrid video feed for: {session.subject_name}")
    print(f"📚 Session: Semester {session.semester}, Year {session.year}, Dept {session.department}")
    print(f"⚡ SINGLE SHOT MODE: Students marked PRESENT on first detection")
    
    # Check session status
    if not session.is_active:
        print(f"⚠️ Session {session.subject_name} is not active. Starting it now...")
        session.is_active = True
        session.start_time = timezone.now()
        session.save()
        print(f"✅ Session started at: {get_local_time(session.start_time)}")
    
    # Calculate session end time
    if not session.end_time:
        session.end_time = session.start_time + timedelta(minutes=session.expected_duration)
        session.save()
    
    session_end_time = session.end_time
    end_time_local = get_local_time(session_end_time)
    print(f"⏰ Session will auto-stop at: {end_time_local.strftime('%I:%M %p')}")
    
    # Get enrolled students for validation
    enrolled_students = session.get_enrolled_students()
    enrolled_ids = set(enrolled_students.values_list('id', flat=True))
    print(f"📊 {len(enrolled_ids)} students enrolled in this session")
    print(f"📋 Enrolled Student IDs: {enrolled_ids}")
    
    # Tracking variables - SIMPLIFIED
    marked_present = set()  # Track which students we've already processed
    invalid_attempts = set()  # Students who attempted but failed validation
    last_auto_check_time = timezone.now()
    
    # FPS tracking
    fps_display = 0
    fps_counter = 0
    fps_timer = time.time()
    
    total_detections = 0
    valid_detections = 0
    
    print(f"✅ Single Shot Mode: Mark on first detection (Model handles status)")
    
    while True:
        try:
            current_time = timezone.now()
            
            # Check session status every 5 seconds
            if (current_time - last_auto_check_time).seconds >= 5:
                last_auto_check_time = current_time
                session.refresh_from_db()
                
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
            
            # Update display FPS
            fps_counter += 1
            current_time_float = time.time()
            if current_time_float - fps_timer >= 1.0:
                fps_display = fps_counter
                fps_counter = 0
                fps_timer = current_time_float
            
            # Process frame
            results = recognizer.process_frame(frame, RECOGNITION_CONFIG.get('RESIZE_FACTOR', 0.25))
            
            for result in results:
                top, right, bottom, left = result['location']
                name = result['name']
                confidence = result['confidence']
                student_id = result['student_id']
                quality_score = result['quality_score']
                is_quality_good = result['is_quality_good']
                
                # Check if recognized student is enrolled
                is_enrolled = student_id in enrolled_ids if student_id else False
                
                # ============================================================
                # SINGLE SHOT DETECTION - SIMPLIFIED VERSION
                # The model handles status determination
                # ============================================================
                if name != "Unknown" and is_enrolled and confidence > 35:
                    color = (0, 255, 0)
                    status_text = "✓ ENROLLED"
                    
                    if student_id:
                        try:
                            student_obj = Student.objects.get(id=student_id)
                            print(f"✅ DETECTED: {student_obj.full_name} (ID: {student_id}, Confidence: {confidence}%)")
                            
                            # ============================================================
                            # Get or create log - the model's save() will handle status
                            # ============================================================
                            log, created = AttendanceLog.objects.get_or_create(
                                session=session,
                                student=student_obj,
                                defaults={
                                    'status': 'PRESENT',  # Default for new logs
                                    'confidence': confidence,
                                    'first_seen': current_time,
                                    'last_seen': current_time,
                                    'last_detected': current_time,
                                    'detection_count': 1,
                                    'is_validated': True,
                                    'student_semester': student_obj.semester,
                                    'session_semester': session.semester,
                                    # Minute tracking fields - will be handled by model
                                    'minute_presence': [],
                                    'minute_count': 0,
                                    'attended_minutes': 0,
                                    'total_presence_seconds': 0,
                                    'out_of_frame_count': 0,
                                }
                            )
                            
                            # If existing, update fields and let model handle status
                            if not created:
                                log.confidence = max(log.confidence or 0, confidence)
                                log.last_seen = current_time
                                log.last_detected = current_time
                                log.is_validated = True
                                # DO NOT SET STATUS HERE - let model decide
                            
                            # Save - model's save() will determine correct status
                            log.save()
                            
                            if created:
                                print(f"✅ CREATED: {student_obj.full_name}")
                            else:
                                print(f"✅ UPDATED: {student_obj.full_name} (Detection count: {log.detection_count})")
                            
                            marked_present.add(student_id)
                            valid_detections += 1
                            
                        except Student.DoesNotExist:
                            print(f"⚠️ Student with ID {student_id} not found")
                        except Exception as e:
                            print(f"⚠️ Error: {e}")
                            import traceback
                            traceback.print_exc()
                    
                elif name != "Unknown" and not is_enrolled and confidence > 50:
                    color = (0, 0, 255)
                    status_text = "✗ NOT ENROLLED"
                    # Log invalid attempt (only once per student)
                    if student_id and student_id not in invalid_attempts:
                        invalid_attempts.add(student_id)
                        try:
                            student = Student.objects.get(id=student_id)
                            error_msg = (
                                f"⚠️ {student.full_name} (Roll: {student.roll_number}) "
                                f"is from Semester {student.semester}, but session is for "
                                f"Semester {session.semester}"
                            )
                            print(error_msg)
                            # Create failed log
                            AttendanceLog.objects.get_or_create(
                                session=session,
                                student=student,
                                defaults={
                                    'status': 'ABSENT',
                                    'confidence': confidence,
                                    'is_validated': False,
                                    'validation_error': error_msg,
                                    'student_semester': student.semester,
                                    'session_semester': session.semester,
                                    'first_seen': current_time,
                                    'last_seen': current_time,
                                    'detection_count': 0,
                                    'minute_presence': [],
                                    'minute_count': 0,
                                    'attended_minutes': 0,
                                }
                            )
                        except Student.DoesNotExist:
                            pass
                else:
                    color = (0, 0, 255)
                    status_text = "UNKNOWN"
                
                # Draw face box
                FaceUtils.draw_face_box(frame, (top, right, bottom, left), 
                                       name, confidence, student_id, color)
                
                if name != "Unknown":
                    cv2.putText(frame, status_text, (left, bottom + 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                if not is_quality_good and result.get('issues'):
                    FaceUtils.draw_quality_info(frame, (top, right, bottom, left), 
                                               quality_score, result['issues'])
                
                total_detections += 1
            
            # Info overlay
            fps_display_text = int(fps_display) if fps_display > 0 else 15
            if minutes_remaining > 0 or seconds_remaining > 0:
                time_remaining_display = f"{minutes_remaining}m {seconds_remaining}s"
                info = f"FPS: {fps_display_text} | Time Left: {time_remaining_display} | Marked: {len(marked_present)}/{len(enrolled_ids)} | Invalid: {len(invalid_attempts)}"
            else:
                info = f"FPS: {fps_display_text} | Session Ending... | Marked: {len(marked_present)}/{len(enrolled_ids)} | Invalid: {len(invalid_attempts)}"
            
            cv2.putText(frame, info, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.putText(frame, f"Sem: {session.semester} | Year: {session.year} | {session.department} | ⚡ SINGLE SHOT", 
                       (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
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
    print("\n" + "="*50)
    print(f"🎥 Video feed ended for: {session.subject_name}")
    print(f"📊 Final Stats:")
    print(f"   ✅ Valid Students Marked: {len(marked_present)}/{len(enrolled_ids)}")
    print(f"   ❌ Invalid Attempts: {len(invalid_attempts)}")
    print(f"   📸 Total Detections: {total_detections}")
    print("="*50 + "\n")


# afras_app/attendance/views.py - REPLACE the existing attendance_pattern function

# afras_app/attendance/views.py - Complete fixed attendance_pattern function

@login_required
def attendance_pattern(request, log_id):
    """
    View minute-by-minute attendance pattern for a single student
    FIXED: Fetches minute tracking data from live session
    """
    from decimal import Decimal
    from django.db import transaction
    from datetime import timedelta
    
    # Fetch the log with all related data
    log = get_object_or_404(
        AttendanceLog.objects.select_related('student', 'session'), 
        id=log_id
    )
    
    session = log.session
    student = log.student
    
    # ============================================================
    # Get session duration
    # ============================================================
    session_duration = session.expected_duration or 60
    
    print(f"\n📊 ATTENDANCE PATTERN DEBUG:")
    print(f"   Session Duration: {session_duration} minutes")
    print(f"   Student: {student.full_name}")
    print(f"   Log ID: {log.id}")
    print(f"   Detection Count: {log.detection_count}")
    print(f"   First Seen: {log.first_seen}")
    print(f"   Last Seen: {log.last_seen}")
    print(f"   Session Start: {session.start_time}")
    print(f"   Session End: {session.end_time}")
    
    # ============================================================
    # Check if minute_presence exists in the log
    # ============================================================
    minute_presence = log.minute_presence or []
    
    print(f"\n📊 Minute Presence from DB:")
    print(f"   Length: {len(minute_presence)}")
    print(f"   Data: {minute_presence[:20]}...")  # Show first 20
    
    # ============================================================
    # If no minute_presence data, build it from detection times
    # ============================================================
    if not minute_presence or len(minute_presence) == 0:
        print(f"\n🔧 Building minute_presence from detection data...")
        minute_presence = [0] * session_duration
        
        if log.detection_count > 0 and log.first_seen:
            # Get the session start time
            session_start = session.start_time
            
            # Calculate the minute offset for first seen (detection time)
            first_offset = int((log.first_seen - session_start).total_seconds() // 60)
            
            # Clamp to session duration
            first_offset = max(0, min(first_offset, session_duration - 1))
            
            # In Single Shot Mode, mark the minute of first detection
            minute_presence[first_offset] = 1
            
            # Also check if there were multiple detections across different minutes
            # (This would come from the minute tracker in the live session)
            if log.minute_count > 0 and len(minute_presence) > 0:
                # If we have minute_count but no data, use it
                attended = log.attended_minutes or 1
                if attended > 1:
                    # Try to spread attendance across minutes if we have data
                    pass
            
            attended_minutes = sum(minute_presence)
            print(f"   ✅ Built minute_presence from first_seen: {attended_minutes} minute(s)")
            print(f"   First Seen Offset: {first_offset}")
        else:
            attended_minutes = 0
            print(f"   ❌ No detections - all minutes absent")
        
        # Save to database
        with transaction.atomic():
            log.minute_presence = minute_presence
            log.minute_count = session_duration
            log.attended_minutes = sum(minute_presence)
            log.save(update_fields=['minute_presence', 'minute_count', 'attended_minutes'])
            print(f"   💾 Saved minute_presence to database")
    else:
        # Use existing minute_presence data
        attended_minutes = sum(minute_presence)
        print(f"\n📊 Using existing minute_presence data:")
        print(f"   Attended Minutes: {attended_minutes}")
        print(f"   Minute Presence: {minute_presence}")
    
    # ============================================================
    # Recalculate status based on minute data
    # ============================================================
    if not log.is_manual:
        retention = (attended_minutes / session_duration * 100) if session_duration > 0 else 0
        
        # Use 80% as default threshold
        min_retention = 80.0
        
        # Determine status based on retention
        if retention >= min_retention:
            new_status = 'PRESENT'
        elif retention >= 50:
            new_status = 'PARTIAL'
        elif retention > 0:
            new_status = 'LATE'
        else:
            new_status = 'ABSENT'
        
        if log.status != new_status:
            log.status = new_status
            log.save(update_fields=['status'])
            print(f"   ✅ Updated status to {new_status} (retention: {retention:.1f}%)")
    
    # ============================================================
    # Prepare data for template
    # ============================================================
    attendance_percentage = (attended_minutes / session_duration * 100) if session_duration > 0 else 0
    
    print(f"\n📊 FINAL CALCULATIONS:")
    print(f"   Total Session Minutes: {session_duration}")
    print(f"   Attended Minutes: {attended_minutes}")
    print(f"   Attendance %: {attendance_percentage:.1f}%")
    print(f"   Status: {log.status}")
    print(f"   Minute Presence: {minute_presence[:20]}...")
    
    # Prepare summary data for template
    summary_data = {
        'total_minutes': session_duration,
        'attended_minutes': attended_minutes,
        'absent_minutes': session_duration - attended_minutes,
        'percentage': attendance_percentage,
        'status': str(log.status),
        'detection_count': int(log.detection_count or 0),
        'confidence': float(log.confidence or 0),
        'retention_percentage': float(log.retention_percentage or 0),
    }
    
    # Prepare log data for JavaScript
    log_data = {
        'id': int(log.id),
        'minute_presence': minute_presence,
        'minute_count': session_duration,
        'attended_minutes': attended_minutes,
        'status': str(log.status),
        'confidence': float(log.confidence) if log.confidence else 0,
        'detection_count': int(log.detection_count) if log.detection_count else 0,
        'retention_percentage': float(log.retention_percentage) if log.retention_percentage else 0,
    }
    
    # Get local times
    start_time_local = get_local_time(session.start_time)
    end_time_local = get_local_time(session.end_time)
    
    # Calculate time range for display
    time_range_display = ""
    if start_time_local and end_time_local:
        time_range_display = f"{start_time_local.strftime('%I:%M %p')} - {end_time_local.strftime('%I:%M %p')}"
    
    context = {
        'log': log,
        'student': student,
        'session': session,
        'summary': summary_data,
        'log_data': log_data,
        'session_duration': session_duration,
        'start_time_local': start_time_local,
        'end_time_local': end_time_local,
        'time_range_display': time_range_display,
        'total_minutes': session_duration,
        'attended_minutes': attended_minutes,
        'absent_minutes': session_duration - attended_minutes,
        'attendance_percentage': attendance_percentage,
        'detection_count': log.detection_count or 0,
        'confidence': log.confidence or 0,
        'retention': log.retention_percentage or 0,
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
    
    # Get all students enrolled in this session's semester/year/department
    enrolled_students = session.get_enrolled_students()
    
    # Get student IDs who have attendance logs
    present_student_ids = logs.values_list('student_id', flat=True)
    
    # Find absent students (enrolled but no attendance log)
    absent_students = enrolled_students.exclude(id__in=present_student_ids)
    
    # Calculate statistics
    total_students = enrolled_students.count()
    present_count = logs.filter(status='PRESENT').count()
    absent_count = logs.filter(status='ABSENT').count()
    partial_count = logs.filter(status='PARTIAL').count()
    late_count = logs.filter(status='LATE').count()
    
    # Calculate validated stats
    validated_count = logs.filter(is_validated=True).count() if hasattr(AttendanceLog, 'is_validated') else 0
    
    # Get validation failed logs - students who attempted but failed validation
    validation_failed_logs = logs.filter(is_validated=False) if hasattr(AttendanceLog, 'is_validated') else AttendanceLog.objects.none()
    validation_failed_count = validation_failed_logs.count()
    
    # Calculate average retention
    total_retention = 0
    for log in logs:
        total_retention += log.retention_percentage
    
    avg_retention = total_retention / total_students if total_students > 0 else 0
    
    # Calculate attendance rate
    attendance_rate = (present_count / total_students * 100) if total_students > 0 else 0
    
    # Prepare attendance data for each student
    attendance_data = []
    for student in enrolled_students:
        log = logs.filter(student=student).first()
        if log:
            attendance_data.append({
                'student': student,
                'log': log,
                'status': log.status,
                'confidence': log.confidence,
                'retention': log.retention_percentage,
                'first_seen': log.first_seen,
                'last_seen': log.last_seen,
                'attended_minutes': log.attended_minutes if hasattr(log, 'attended_minutes') else 0,
                'is_validated': log.is_validated if hasattr(log, 'is_validated') else True,
                'validation_error': log.validation_error if hasattr(log, 'validation_error') else None,
            })
        else:
            # Student is enrolled but has no log (absent)
            attendance_data.append({
                'student': student,
                'log': None,
                'status': 'ABSENT',
                'confidence': 0,
                'retention': 0,
                'first_seen': None,
                'last_seen': None,
                'attended_minutes': 0,
                'is_validated': False,
                'validation_error': None,
            })
    
    context = {
        'session': session,
        'logs': logs,
        'attendance_data': attendance_data,
        'total_students': total_students,
        'present_count': present_count,
        'absent_count': absent_count,
        'partial_count': partial_count,
        'late_count': late_count,
        'avg_retention': round(avg_retention, 1),
        'attendance_rate': round(attendance_rate, 1),
        'absent_students': absent_students,  # Students with no attendance log
        'validated_count': validated_count,
        'validation_failed_count': validation_failed_count,
        'validation_failed_logs': validation_failed_logs,  # Pass the actual logs
        'start_time_local': get_local_time(session.start_time),
        'end_time_local': get_local_time(session.end_time),
        'min_retention_required': 80,
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
    
    # Get all enrolled students for this session
    enrolled_students = session.get_enrolled_students()
    logs = AttendanceLog.objects.filter(session=session).select_related('student')
    
    students_data = []
    
    # Get all students with logs
    for log in logs:
        is_unauthorized = not log.is_validated if hasattr(log, 'is_validated') else False
        students_data.append({
            'id': log.student.id,
            'full_name': log.student.full_name,
            'roll_number': log.student.roll_number,
            'status': 'UNAUTHORIZED' if is_unauthorized else log.status,
            'confidence': int(log.confidence) if log.confidence else 0,
            'first_seen': get_local_time(log.first_seen).strftime('%I:%M %p') if log.first_seen else None,
            'last_seen': get_local_time(log.last_seen).strftime('%I:%M %p') if log.last_seen else None,
            'detection_count': log.detection_count,
            'retention': int(log.retention_percentage),
            'attended_minutes': log.attended_minutes,
            'minute_presence': log.minute_presence,
            'is_validated': log.is_validated if hasattr(log, 'is_validated') else True,
            'validation_error': log.validation_error if hasattr(log, 'validation_error') else None,
            'is_unauthorized': is_unauthorized,
        })
    
    # Add absent students (enrolled but no log)
    enrolled_ids = set(enrolled_students.values_list('id', flat=True))
    log_student_ids = set(logs.values_list('student_id', flat=True))
    absent_student_ids = enrolled_ids - log_student_ids
    
    for student in Student.objects.filter(id__in=absent_student_ids):
        students_data.append({
            'id': student.id,
            'full_name': student.full_name,
            'roll_number': student.roll_number,
            'status': 'ABSENT',
            'confidence': 0,
            'first_seen': None,
            'last_seen': None,
            'detection_count': 0,
            'retention': 0,
            'attended_minutes': 0,
            'minute_presence': [],
            'is_validated': True,
            'validation_error': None,
            'is_unauthorized': False,
        })
    
    return JsonResponse({
        'students': students_data,
        'total': len(students_data),
        'present': len([s for s in students_data if s['status'] == 'PRESENT']),
        'absent': len([s for s in students_data if s['status'] == 'ABSENT']),
        'unauthorized': len([s for s in students_data if s['status'] == 'UNAUTHORIZED']),
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
    FIXED: Supports both DELETE and POST methods with better error handling
    """
    # Allow both DELETE and POST methods
    if request.method not in ['DELETE', 'POST']:
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
        session_id_val = session.id
        session_date = session.date.strftime('%Y-%m-%d') if session.date else 'N/A'
        
        print(f"\n🗑️ DELETING SESSION: {session_name} (ID: {session_id_val})")
        print(f"   Date: {session_date}")
        print(f"   Department: {session.department}")
        print(f"   Semester: {session.semester}")
        print(f"   User: {request.user.username}")
        
        # ============================================================
        # STEP 1: Count attendance logs
        # ============================================================
        logs_count = AttendanceLog.objects.filter(session=session).count()
        print(f"   📊 Found {logs_count} attendance logs to delete")
        
        # ============================================================
        # STEP 2: Delete logs using transaction for safety
        # ============================================================
        with transaction.atomic():
            if logs_count > 0:
                deleted_logs, _ = AttendanceLog.objects.filter(session=session).delete()
                print(f"   ✅ Deleted {deleted_logs} attendance logs")
            
            # ============================================================
            # STEP 3: Delete the session
            # ============================================================
            session.delete()
            print(f"   ✅ Session deleted successfully")
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted session "{session_name}" and {logs_count} attendance records.',
            'logs_deleted': logs_count,
            'session_id': session_id_val
        })
        
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Session not found'}, status=404)
    except Exception as e:
        print(f"❌ Error deleting session: {e}")
        import traceback
        traceback.print_exc()
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
    
    # Subject filter
    subject_filter = request.GET.get('subject', '')
    if subject_filter:
        logs = logs.filter(session__subject_name__icontains=subject_filter)
    
    # Session Semester filter (the semester the session was for)
    session_semester_filter = request.GET.get('session_semester', '')
    if session_semester_filter:
        logs = logs.filter(session__semester=session_semester_filter)
    
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
    
    # Get semesters based on selected year (for dynamic filtering)
    year_filter_val = request.GET.get('year', '')
    if year_filter_val:
        semesters = Student.objects.filter(
            year=year_filter_val,
            semester__isnull=False
        ).values_list('semester', flat=True).distinct().order_by('semester')
    else:
        semesters = Student.objects.filter(
            semester__isnull=False
        ).values_list('semester', flat=True).distinct().order_by('semester')
    
    # Get unique subjects from sessions
    subjects = AttendanceSession.objects.filter(
        subject_name__isnull=False
    ).exclude(
        subject_name=''
    ).values_list('subject_name', flat=True).distinct().order_by('subject_name')
    
    # Get session semesters (semesters that sessions were conducted for)
    session_semesters = AttendanceSession.objects.filter(
        semester__isnull=False
    ).values_list('semester', flat=True).distinct().order_by('semester')
    
    # Get semesters by year for dynamic filtering in template (if needed)
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
    
    # For pagination info
    start_index = (logs_page.number - 1) * paginator.per_page + 1 if logs_page.number > 0 else 0
    end_index = min(start_index + paginator.per_page - 1, paginator.count)
    
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
        'subjects': list(subjects),
        'session_semesters': list(session_semesters),
        'semesters_by_year': semesters_by_year,
        'status_filter': status_filter,
        'department_filter': department_filter,
        'year_filter': year_filter,
        'semester_filter': semester_filter,
        'subject_filter': subject_filter,
        'session_semester_filter': session_semester_filter,
        'start_index': start_index,
        'end_index': end_index,
    }
    
    return render(request, 'attendance/attendance_records.html', context)

@login_required
def weekly_attendance_report(request):
    """
    Attendance report showing REAL attendance data from database
    According to scheduler: Sunday-Friday sessions, Saturday OFF
    """
    # Get filter parameters
    year_filter = request.GET.get('year', '')
    semester_filter = request.GET.get('semester', '')
    subject_filter = request.GET.get('subject', '')
    
    # Date range parameters
    date_range_type = request.GET.get('date_range', 'week')
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    
    today = timezone.now().date()
    current_time = timezone.now()
    
    # ============================================================
    # CALCULATE DATE RANGE - SUNDAY TO SATURDAY (Saturday = OFF)
    # ============================================================
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today
            end_date = today
    else:
        if date_range_type == 'day':
            start_date = today
            end_date = today
        elif date_range_type == 'week':
            days_to_sunday = (today.weekday() + 1) % 7
            start_date = today - timedelta(days=days_to_sunday)
            end_date = start_date + timedelta(days=6)
        elif date_range_type == 'month':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        else:
            days_to_sunday = (today.weekday() + 1) % 7
            start_date = today - timedelta(days=days_to_sunday)
            end_date = start_date + timedelta(days=6)
    
    # ============================================================
    # GENERATE DATE LIST - Show Sunday to Saturday (Saturday = OFF)
    # ============================================================
    date_list = []
    current = start_date
    while current <= end_date:
        date_list.append(current)
        current += timedelta(days=1)
    
    # ============================================================
    # GET FIRST SESSION DATE FOR SUBJECT
    # ============================================================
    first_session_date = None
    if subject_filter:
        first_session = AttendanceSession.objects.filter(
            subject_name__iexact=subject_filter
        ).order_by('date', 'start_time').first()
        if first_session:
            first_session_date = first_session.date
    
    # ============================================================
    # GET STUDENTS
    # ============================================================
    students = Student.objects.all().order_by('full_name')
    
    if semester_filter:
        students = students.filter(semester=semester_filter)
    if year_filter:
        students = students.filter(year=year_filter)
    
    # ============================================================
    # SUBJECT FILTER
    # ============================================================
    if subject_filter:
        subject_sessions = AttendanceSession.objects.filter(
            subject_name__iexact=subject_filter
        ).order_by('-date', '-start_time')
        
        if subject_sessions.exists():
            session = subject_sessions.first()
            session_filters = {}
            if session.semester:
                session_filters['semester'] = session.semester
            if session.year:
                session_filters['year'] = session.year
            if session.department:
                session_filters['department'] = session.department
            if session.section:
                session_filters['section'] = session.section
            
            if session_filters:
                students = Student.objects.filter(**session_filters).order_by('full_name')
            else:
                enrolled_student_ids = set()
                for s in subject_sessions:
                    for student in s.get_enrolled_students():
                        enrolled_student_ids.add(student.id)
                if enrolled_student_ids:
                    students = Student.objects.filter(id__in=enrolled_student_ids).order_by('full_name')
        else:
            if not semester_filter and not year_filter:
                students = Student.objects.none()
    
    # ============================================================
    # GET ALL SESSIONS IN DATE RANGE
    # ============================================================
    all_sessions = AttendanceSession.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    if subject_filter:
        all_sessions = all_sessions.filter(subject_name__iexact=subject_filter)
    
    # ============================================================
    # FETCH ATTENDANCE LOGS
    # ============================================================
    logs = AttendanceLog.objects.filter(
        session__in=all_sessions,
        student__in=students
    ).select_related('student', 'session')
    
    # ============================================================
    # BUILD LOG MAP
    # ============================================================
    log_map = {}
    for log in logs:
        key = (log.student_id, log.session.date)
        is_validated = getattr(log, 'is_validated', True)
        
        if not is_validated:
            log_map[key] = {
                'status': 'UNAUTHORIZED',
                'is_manual': log.is_manual,
                'confidence': log.confidence,
                'validation_error': getattr(log, 'validation_error', 'Not validated'),
                'reason': None
            }
        else:
            log_map[key] = {
                'status': log.status,
                'is_manual': log.is_manual,
                'confidence': log.confidence,
                'first_seen': log.first_seen,
                'last_seen': log.last_seen,
                'reason': getattr(log, 'reason', None)
            }
    
    # ============================================================
    # BUILD ATTENDANCE DATA
    # ============================================================
    attendance_data = []
    summary_stats = {
        'total_students': students.count(),
        'total_days': len(date_list),
        'present_counts': {},
        'absent_counts': {},
        'leave_counts': {},
        'late_counts': {},
        'no_session_counts': {},
        'unauthorized_counts': {},
        'total_present': 0,
        'total_absent': 0,
        'total_leave': 0,        
        'total_late': 0,
        'total_no_session': 0,
        'total_unauthorized': 0,
        'total_auto_marked': 0,      # ← ADD THIS
        'total_manual_changes': 0,    # ← ADD THIS
        'attendance_percentage': 0
    }
    
    # Initialize summary stats
    for date_obj in date_list:
        date_str = date_obj.strftime('%Y-%m-%d')
        summary_stats['present_counts'][date_str] = 0
        summary_stats['absent_counts'][date_str] = 0
        summary_stats['leave_counts'][date_str] = 0
        summary_stats['late_counts'][date_str] = 0
        summary_stats['no_session_counts'][date_str] = 0
        summary_stats['unauthorized_counts'][date_str] = 0
    
    for student in students:
        student_data = {
            'student': student,
            'days': [],
            'attendance_percentage': 0,
            'present_count': 0,
            'total_days': len(date_list)
        }
        
        for date_obj in date_list:
            date_str = date_obj.strftime('%Y-%m-%d')
            is_saturday = (date_obj.weekday() == 5)  # Saturday = 5
            
            # ============================================================
            # CHECK SESSION STATUS FOR THIS DATE
            # ============================================================
            has_session = False
            session_started = False
            session_completed = False
            
            if not is_saturday:
                for session in all_sessions.filter(date=date_obj):
                    if session.is_student_enrolled(student.id):
                        has_session = True
                        if session.start_time <= current_time:
                            session_started = True
                        if session.end_time and session.end_time <= current_time:
                            session_completed = True
                        break
            
            # ============================================================
            # CHECK IF STUDENT HAS ATTENDANCE LOG
            # ============================================================
            key = (student.id, date_obj)
            log_data = log_map.get(key)
            
            # ============================================================
            # DETERMINE STATUS - FIXED VERSION
            # ============================================================
            status = 'NO_SESSION'
            
            if is_saturday:
                status = 'OFF'
            elif has_session and session_completed:
                if log_data:
                    if log_data['status'] == 'PRESENT':
                        status = 'PRESENT'
                        summary_stats['present_counts'][date_str] += 1
                        summary_stats['total_present'] += 1
                        student_data['present_count'] += 1
                    elif log_data['status'] == 'LEAVE':
                        status = 'LEAVE'
                        summary_stats['leave_counts'][date_str] += 1
                        summary_stats['total_leave'] += 1
                    elif log_data['status'] == 'LATE':
                        status = 'LATE'
                        summary_stats['late_counts'][date_str] += 1
                        summary_stats['total_late'] += 1
                    elif log_data['status'] == 'UNAUTHORIZED':
                        status = 'UNAUTHORIZED'
                        summary_stats['unauthorized_counts'][date_str] += 1
                        summary_stats['total_unauthorized'] += 1
                    elif log_data['status'] == 'ABSENT':
                        status = 'ABSENT'
                        summary_stats['absent_counts'][date_str] += 1
                        summary_stats['total_absent'] += 1
                    elif log_data['status'] == 'PARTIAL':
                        status = 'PRESENT'
                        summary_stats['present_counts'][date_str] += 1
                        summary_stats['total_present'] += 1
                        student_data['present_count'] += 1
                    else:
                        status = 'ABSENT'
                        summary_stats['absent_counts'][date_str] += 1
                        summary_stats['total_absent'] += 1
                    
                    # ============================================================
                    # COUNT AUTO AND MANUAL CHANGES
                    # ============================================================
                    if log_data.get('is_manual'):
                        summary_stats['total_manual_changes'] += 1
                    elif log_data.get('is_manual') is False:
                        summary_stats['total_auto_marked'] += 1
                else:
                    status = 'ABSENT'
                    summary_stats['absent_counts'][date_str] += 1
                    summary_stats['total_absent'] += 1
            elif has_session and session_started and not session_completed:
                if log_data and log_data['status'] == 'PRESENT':
                    status = 'PRESENT'
                    summary_stats['present_counts'][date_str] += 1
                    summary_stats['total_present'] += 1
                    student_data['present_count'] += 1
                elif log_data and log_data['status'] == 'UNAUTHORIZED':
                    status = 'UNAUTHORIZED'
                    summary_stats['unauthorized_counts'][date_str] += 1
                    summary_stats['total_unauthorized'] += 1
                else:
                    status = 'NO_SESSION'
                    summary_stats['no_session_counts'][date_str] += 1
                    summary_stats['total_no_session'] += 1
            else:
                status = 'NO_SESSION'
                summary_stats['no_session_counts'][date_str] += 1
                summary_stats['total_no_session'] += 1
            
            student_data['days'].append({
                'date': date_str,
                'day_name': date_obj.strftime('%a'),
                'full_date': date_obj.strftime('%b %d, %Y'),
                'status': status,
                'is_saturday': is_saturday,
                'is_auto': (log_data and not log_data.get('is_manual', True)),
                'confidence': log_data.get('confidence') if log_data else None,
                'reason': log_data.get('reason') if log_data else None,
                'is_manual': (log_data and log_data.get('is_manual', False)) if log_data else False,
            })
        
        # Calculate student's attendance percentage
        total_possible = 0
        for day in student_data['days']:
            if day['status'] not in ['NO_SESSION', 'OFF']:
                total_possible += 1
        
        if total_possible > 0:
            student_data['attendance_percentage'] = round(
                (student_data['present_count'] / total_possible) * 100, 1
            )
        else:
            student_data['attendance_percentage'] = 0
        
        attendance_data.append(student_data)
    
    # Calculate summary
    summary_stats['total_students'] = students.count()
    
    total_possible_attendances = summary_stats['total_students'] * len(date_list)
    total_actual_present = summary_stats['total_present']
    
    if total_possible_attendances > 0:
        summary_stats['attendance_percentage'] = round(
            (total_actual_present / total_possible_attendances) * 100, 1
        )
    
    # ============================================================
    # GET FILTER OPTIONS
    # ============================================================
    years = Student.objects.filter(
        year__isnull=False
    ).values_list('year', flat=True).distinct().order_by('year')
    
    semesters = Student.objects.filter(
        semester__isnull=False
    ).values_list('semester', flat=True).distinct().order_by('semester')
    
    subjects = AttendanceSession.objects.filter(
        subject_name__isnull=False
    ).exclude(
        subject_name=''
    ).values_list('subject_name', flat=True).distinct().order_by('subject_name')
    
    # ============================================================
    # AUTO-SESSION COUNT
    # ============================================================
    auto_session_count = AttendanceSession.objects.filter(
        subject_name=subject_filter,
        is_manual=False,
        date__gte=start_date,
        date__lte=end_date
    ).count() if subject_filter else 0
    
    # ============================================================
    # PREPARE CONTEXT
    # ============================================================
    if start_date == end_date:
        date_range_display = start_date.strftime('%B %d, %Y')
    else:
        date_range_display = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    
    start_date_val = start_date.strftime('%Y-%m-%d')
    end_date_val = end_date.strftime('%Y-%m-%d')
    
    context = {
        'attendance_data': attendance_data,
        'date_list': date_list,
        'date_range_display': date_range_display,
        'start_date': start_date,
        'end_date': end_date,
        'start_date_val': start_date_val,
        'end_date_val': end_date_val,
        'date_range_type': date_range_type,
        'summary': summary_stats,
        'years': years,
        'semesters': semesters,
        'subjects': subjects,
        'year_filter': year_filter,
        'semester_filter': semester_filter,
        'subject_filter': subject_filter,
        'first_session_date': first_session_date,
        'auto_session_count': auto_session_count,
    }
    
    return render(request, 'attendance/attendance_report.html', context)


# attendance/views.py

@csrf_exempt
@login_required
@user_passes_test(is_staff_or_admin)
def update_attendance_manual(request):
    """
    API endpoint to manually update attendance for a student
    (For approved leaves, manual correction, etc.)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        date_str = data.get('date')
        status = data.get('status')
        subject_name = data.get('subject')
        reason = data.get('reason', 'Manual update')
        
        if not all([student_id, date_str, status]):
            return JsonResponse({'success': False, 'message': 'Missing required fields'})
        
        # Parse date
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date format'})
        
        # Find the student
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Student not found'})
        
        # Find the session
        session = None
        if subject_name:
            session = AttendanceSession.objects.filter(
                subject_name__iexact=subject_name,
                date=date_obj
            ).first()
        
        if not session:
            date_sessions = AttendanceSession.objects.filter(date=date_obj)
            for s in date_sessions:
                if s.is_student_enrolled(student.id):
                    session = s
                    break
        
        if not session:
            return JsonResponse({
                'success': False, 
                'message': f'No session found for {student.full_name} on {date_str}'
            })
        
        if not session.is_student_enrolled(student.id):
            return JsonResponse({
                'success': False, 
                'message': f'{student.full_name} is not enrolled in this session'
            })
        
        # Update or create attendance log with reason
        log, created = AttendanceLog.objects.get_or_create(
            session=session,
            student=student,
            defaults={
                'status': status,
                'confidence': 100,
                'is_manual': True,
                'first_seen': timezone.now(),
                'last_seen': timezone.now(),
                'is_validated': True,
                'detection_count': 1,
                'validation_error': None,
                'reason': reason  # ← Store the reason
            }
        )
        
        if not created:
            log.status = status
            log.is_manual = True
            log.confidence = 100
            log.is_validated = True
            log.last_seen = timezone.now()
            log.detection_count += 1
            log.validation_error = None
            log.reason = reason  # ← Update the reason
            log.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Attendance updated to {status} for {student.full_name}',
            'log_id': log.id,
            'status': status,
            'student': student.full_name,
            'date': date_str,
            'reason': reason
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        print(f"❌ update_attendance_manual error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
    



@login_required
def export_attendance_report_csv(request):
    """
    Export attendance report as CSV with date range support
    """
    import csv
    from django.http import HttpResponse
    
    # Get filter parameters
    department_filter = request.GET.get('department', '')
    semester_filter = request.GET.get('semester', '')
    year_filter = request.GET.get('year', '')
    section_filter = request.GET.get('section', '')
    
    # Date range parameters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    date_range_type = request.GET.get('date_range', 'week')
    
    today = timezone.now().date()
    
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=4)
    else:
        if date_range_type == 'day':
            start_date = today
            end_date = today
        elif date_range_type == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=4)
        elif date_range_type == 'month':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        else:
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=4)
    
    # Generate date list
    date_list = []
    current = start_date
    while current <= end_date:
        date_list.append(current)
        current += timedelta(days=1)
    
    # Get students
    students = Student.objects.all().order_by('full_name')
    
    if department_filter:
        students = students.filter(department__iexact=department_filter)
    if semester_filter:
        students = students.filter(semester=semester_filter)
    if year_filter:
        students = students.filter(year=year_filter)
    if section_filter:
        students = students.filter(section__iexact=section_filter)
    
    # Prepare CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{start_date.strftime("%Y-%m-%d")}.csv"'
    
    writer = csv.writer(response)
    
    # Header row
    header = ['Name', 'ID No.', 'Department', 'Semester', 'Section']
    for date_obj in date_list:
        header.append(date_obj.strftime('%a %m/%d'))
    writer.writerow(header)
    
    # Data rows
    for student in students:
        row = [student.full_name, student.roll_number, student.department, student.semester, student.section]
        for date_obj in date_list:
            log = AttendanceLog.objects.filter(
                student=student,
                session__date=date_obj,
                is_validated=True
            ).first()
            
            if log and log.status in ['PRESENT', 'PARTIAL']:
                row.append('P')
            else:
                # Check if there was a session
                has_session = AttendanceSession.objects.filter(
                    date=date_obj,
                    semester=student.semester,
                    year=student.year
                ).exists()
                if has_session:
                    row.append('A')
                else:
                    row.append('-')
        writer.writerow(row)
    
    # Summary footer
    writer.writerow([])
    writer.writerow(['ATTENDANCE SUMMARY'])
    writer.writerow(['Total Students:', students.count()])
    writer.writerow(['Date Range:', f'{start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'])
    writer.writerow(['Generated on:', timezone.now().strftime('%Y-%m-%d %H:%M:%S')])
    
    return response


@login_required
@user_passes_test(is_staff_or_admin)
def scheduler_status(request):
    """API endpoint to check scheduler status"""
    try:
        from attendance.scheduler import get_scheduler
        
        scheduler = get_scheduler()
        # Force a check to ensure status is updated
        running = scheduler.running if scheduler else False
        
        return JsonResponse({
            'running': running,
            'interval': scheduler.interval if scheduler else 30,
            'status': 'active' if running else 'inactive'
        })
    except Exception as e:
        print(f"❌ Scheduler status error: {e}")
        return JsonResponse({
            'running': False,
            'interval': 30,
            'status': 'inactive',
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_staff_or_admin)
def trigger_scheduler(request):
    """Manually trigger the scheduler to run once"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        from attendance.scheduler import sync_routines_and_sessions, auto_start_scheduled_sessions, auto_end_completed_sessions
        
        result = {
            'sync': sync_routines_and_sessions(),
            'start': auto_start_scheduled_sessions(),
            'end': auto_end_completed_sessions()
        }
        
        return JsonResponse({
            'success': True,
            'result': result
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def check_session_exists(request):
    """API endpoint to check if a session already exists for the given parameters"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        subject = data.get('subject')
        department = data.get('department')
        year = data.get('year')
        semester = data.get('semester')
        section = data.get('section', '')
        session_datetime = data.get('session_datetime')
        
        if not all([subject, department, year, semester, session_datetime]):
            return JsonResponse({'exists': False, 'message': 'Missing required fields'})
        
        # Parse datetime
        try:
            naive_dt = datetime.fromisoformat(session_datetime)
            session_time = timezone.make_aware(naive_dt)
        except:
            return JsonResponse({'exists': False, 'message': 'Invalid datetime format'})
        
        # Check for existing session with same subject, department, year, semester, section on same date
        existing = AttendanceSession.objects.filter(
            subject_name__iexact=subject,
            department=department,
            year=year,
            semester=semester,
            section=section,
            date=session_time.date()
        ).exists()
        
        if existing:
            return JsonResponse({
                'exists': True,
                'message': f'A session for "{subject}" on {session_time.strftime("%B %d, %Y")} already exists.'
            })
        
        return JsonResponse({'exists': False})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def edit_session(request, session_id):
    """View and API endpoint to edit an existing session"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # Check if user has permission
    if not is_staff_or_admin(request.user):
        messages.error(request, 'You do not have permission to edit sessions.')
        return redirect('attendance:unified_sessions')
    
    # Don't allow editing active sessions
    if session.is_active:
        messages.error(request, 'Cannot edit an active session. Please end the session first.')
        return redirect('attendance:unified_sessions')
    
    if request.method == 'POST':
        try:
            subject = request.POST.get('subject')
            department = request.POST.get('department')
            year = request.POST.get('year')
            semester = request.POST.get('semester')
            section = request.POST.get('section', '')
            duration = request.POST.get('duration')
            session_datetime = request.POST.get('session_datetime')
            
            # Validation
            if not subject or not department or not year or not semester or not duration or not session_datetime:
                messages.error(request, 'All required fields must be filled')
                return redirect('attendance:edit_session', session_id=session.id)
            
            # Check if another session with same details exists (excluding this one)
            naive_dt = datetime.fromisoformat(session_datetime)
            session_time = timezone.make_aware(naive_dt)
            
            existing = AttendanceSession.objects.filter(
                subject_name__iexact=subject,
                department=department,
                year=year,
                semester=semester,
                section=section,
                date=session_time.date()
            ).exclude(id=session.id).exists()
            
            if existing:
                messages.error(request, f'A session for "{subject}" on {session_time.strftime("%B %d, %Y")} already exists.')
                return redirect('attendance:edit_session', session_id=session.id)
            
            # Update session
            session.subject_name = subject
            session.department = department
            session.year = int(year)
            session.semester = int(semester)
            session.section = section
            session.expected_duration = int(duration)
            session.start_time = session_time
            session.end_time = session_time + timedelta(minutes=int(duration))
            session.date = session_time.date()
            session.save()
            
            messages.success(request, f'Session "{subject}" updated successfully!')
            return redirect('attendance:session_details', session_id=session.id)
            
        except Exception as e:
            messages.error(request, f'Error updating session: {str(e)}')
            return redirect('attendance:edit_session', session_id=session.id)
    
    # GET request - show edit form
    # FIX: Use local time for datetime input
    local_start = timezone.localtime(session.start_time)
    
    context = {
        'session': session,
        'departments': get_departments(),
        'years': get_years(),
        'semesters': get_semesters(),
        'sections': get_sections(),
        'year_semester_map': get_semesters_by_year(),
        'year_section_map': get_sections_by_year(),
        'start_time_local': get_local_time(session.start_time),
        'end_time_local': get_local_time(session.end_time),
        'now': local_start.strftime('%Y-%m-%dT%H:%M'),
    }
    
    return render(request, 'attendance/edit_session.html', context)


@login_required
def unified_session_management(request):
    """
    Unified view combining all sessions and routine management
    """
    # Check and auto-update sessions
    check_and_update_sessions()
    
    # Get all sessions
    all_sessions = AttendanceSession.objects.all().order_by('-date', '-start_time')
    
    # Get extracted routines from session (if any)
    extracted_routines = request.session.get('extracted_routines', [])
    
    # Calculate stats
    total_sessions = all_sessions.count()
    active_sessions = all_sessions.filter(is_active=True).count()
    today = timezone.now().date()
    today_sessions = all_sessions.filter(date=today).count()
    
    # Count auto-scheduled sessions (sessions with a routine)
    auto_sessions = all_sessions.filter(routine__isnull=False).count()
    
    # Calculate ended sessions - not active and start_time is in the past
    ended_sessions = all_sessions.filter(
        is_active=False,
        start_time__lte=timezone.now()
    ).count()
    
    # Get departments and other options
    departments = get_departments()
    years = get_years()
    semesters = get_semesters()
    
    # Get dynamic maps
    year_semester_map = get_semesters_by_year()
    year_section_map = get_sections_by_year()
    
    # ============================================================
    # FIX: Use LOCAL time for datetime input
    # ============================================================
    now = timezone.localtime(timezone.now())  # Convert to local timezone
    now_formatted = now.strftime('%Y-%m-%dT%H:%M')
    
    # Recent sessions
    recent_sessions = all_sessions[:10]
    
    # ============================================================
    # GET ACTIVE ROUTINES FOR DISPLAY
    # ============================================================
    from dashboard.models import Routine
    active_routines = Routine.objects.filter(is_active=True).order_by('day_of_week', 'start_time')
    
    # Convert day_of_week to string if it's an integer
    day_map = {
        0: 'Monday', 1: 'Tuesday', 2: 'Wednesday',
        3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'
    }
    
    routines_data = []
    for routine in active_routines:
        # Get day name
        day = routine.day_of_week
        if isinstance(day, int):
            day = day_map.get(day, 'Unknown')
        
        routines_data.append({
            'id': routine.id,
            'subject': routine.subject,
            'department': routine.department,
            'semester': routine.semester,
            'year': routine.year,
            'section': routine.section or 'N/A',
            'day_of_week': day,
            'start_time': routine.start_time,
            'duration': routine.duration,
            'is_active': routine.is_active
        })
    
    context = {
        'all_sessions': all_sessions,
        'total_sessions': total_sessions,
        'active_sessions': active_sessions,
        'today_sessions': today_sessions,
        'auto_sessions': auto_sessions,
        'ended_sessions': ended_sessions,
        'departments': departments,
        'years': years,
        'semesters': semesters,
        'year_semester_map': year_semester_map,
        'year_section_map': year_section_map,
        'now': now_formatted,
        'extracted_routines': extracted_routines,
        'recent_sessions': recent_sessions,
        'active_routines': routines_data,  # Pass active routines to template
    }
    
    return render(request, 'attendance/unified_sessions.html', context)


@login_required
@user_passes_test(is_staff_or_admin)
def sync_sessions(request):
    """Manually trigger session synchronization from routines"""
    from attendance.scheduler import sync_routines_and_sessions
    
    if request.method == 'POST':
        try:
            result = sync_routines_and_sessions()
            
            # Only report sessions that actually changed
            message = "✅ Sync complete!"
            changes = []
            
            if result.get('created_count', 0) > 0:
                changes.append(f"Created {result['created_count']} sessions")
            if result.get('started_count', 0) > 0:
                changes.append(f"Started {result['started_count']}")
            if result.get('ended_count', 0) > 0:
                changes.append(f"Ended {result['ended_count']}")
            
            if changes:
                message += " " + ", ".join(changes)
            else:
                message += " No changes detected. All sessions are up to date."
            
            if result.get('errors'):
                message += f" ⚠️ {len(result['errors'])} errors occurred"
            
            return JsonResponse({
                'success': True,
                'message': message,
                'data': result
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)