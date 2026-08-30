import os
import json
import pandas as pd
import pdfplumber
import re
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.cache import never_cache
from accounts.models import Student, StaffProfile, SystemLog, SystemConfiguration, Notification
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from attendance.models import AttendanceSession, AttendanceLog
from django.utils import timezone
from .models import Routine
from datetime import datetime, timedelta
from django.contrib import messages
import psutil
import platform
from django.db.models import Q, Count
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from dashboard.forms import StaffProfileEditForm, StudentEditForm, StudentDeleteForm


# Helper function to check if user is staff
def is_staff_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def get_activity_icon(action):
    """Return icon name based on action type"""
    icon_map = {
        'LOGIN': 'sign-in-alt',
        'LOGOUT': 'sign-out-alt',
        'CREATE': 'plus-circle',
        'UPDATE': 'edit',
        'DELETE': 'trash-alt',
        'VIEW': 'eye',
        'EXPORT': 'download',
        'IMPORT': 'upload',
        'CONFIG_UPDATE': 'cog',
        'FACE_REGISTRATION': 'face-smile',
        'ATTENDANCE_MARK': 'check-circle',
    }
    for key, icon in icon_map.items():
        if key in action.upper():
            return icon
    return 'bell'


@login_required
def activity_logs_view(request):
    """View for all activity logs page"""
    return render(request, 'dashboard/activity_logs.html', {
        'page_title': 'Activity Logs'
    })


@login_required
def api_activity_logs(request):
    """API endpoint to get activity logs with pagination"""
    from accounts.models import SystemLog
    from attendance.models import AttendanceLog
    from django.core.paginator import Paginator
    
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        log_type = request.GET.get('type', '')
        
        activities = []
        
        if log_type == '' or log_type == 'system':
            system_logs = SystemLog.objects.select_related('user').order_by('-timestamp')[:100]
            for log in system_logs:
                activities.append({
                    'id': f'sys_{log.id}',
                    'type': 'system',
                    'title': log.get_action_display() if hasattr(log, 'get_action_display') else log.action,
                    'description': log.details or f'{log.action} performed',
                    'user': log.user.username if log.user else 'System',
                    'time_ago': get_time_ago(log.timestamp),
                    'timestamp': log.timestamp.isoformat(),
                    'icon': get_activity_icon(log.action)
                })
        
        if log_type == '' or log_type == 'attendance':
            attendance_logs = AttendanceLog.objects.select_related('student', 'session').order_by('-last_seen')[:100]
            for log in attendance_logs:
                status_icon = 'check-circle' if log.status == 'PRESENT' else 'times-circle' if log.status == 'ABSENT' else 'clock'
                activities.append({
                    'id': f'att_{log.id}',
                    'type': 'attendance',
                    'title': f'Attendance: {log.student.full_name}',
                    'description': f'{log.get_status_display()} for {log.session.subject_name if log.session else "session"}',
                    'user': log.student.full_name,
                    'time_ago': get_time_ago(log.last_seen),
                    'timestamp': log.last_seen.isoformat(),
                    'icon': status_icon,
                    'status': 'success' if log.status == 'PRESENT' else 'danger' if log.status == 'ABSENT' else 'warning'
                })
        
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        paginator = Paginator(activities, per_page)
        page_obj = paginator.get_page(page)
        
        return JsonResponse({
            'success': True,
            'activities': list(page_obj),
            'total': paginator.count,
            'page': page,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous()
        })
    except Exception as e:
        import traceback
        print(f"Error in api_activity_logs: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
     

def get_time_ago(dt):
    
    now = timezone.now()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds < 60:
        return f"{diff.seconds} second{'s' if diff.seconds != 1 else ''} ago"
    elif diff.seconds < 3600:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"


# Notification creation helper

def create_notification(user, title, message, notification_type='system', link=None, metadata=None):
    """Helper function to create a notification for a specific user"""
    try:
        from accounts.models import Notification
        return Notification.send_notification(user, title, message, notification_type, link, metadata)
    except Exception as e:
        print(f"Error creating notification: {e}")
        return None


def create_system_notification(title, message, notification_type='system', link=None, metadata=None):
    """Create a system-wide notification (visible to all users)"""
    try:
        from accounts.models import Notification
        return Notification.send_system_notification(title, message, notification_type, link, metadata)
    except Exception as e:
        print(f"Error creating system notification: {e}")
        return None


# Administrator notifications

def create_admin_system_health_notifications(request):
    """Create system health notifications for admin only"""
    if not request.user.is_superuser:
        return
    
    try:
        import psutil
        
        today = timezone.now().date()
        
        # CPU Alert (>80%)
        cpu_percent = psutil.cpu_percent(interval=0.1)
        if cpu_percent > 80:
            cpu_key = f'high_cpu_{today.isoformat()}'
            if not request.session.get(cpu_key, False):
                create_notification(
                    user=request.user,
                    title="⚠️ High CPU Usage Alert",
                    message=f"System CPU usage is at {cpu_percent}%. Performance may be affected.",
                    notification_type="warning",
                    link="/dashboard/system-health/",
                    metadata={"cpu": cpu_percent}
                )
                request.session[cpu_key] = True
        
        # Memory Alert (>85%)
        memory = psutil.virtual_memory()
        if memory.percent > 85:
            mem_key = f'high_memory_{today.isoformat()}'
            if not request.session.get(mem_key, False):
                create_notification(
                    user=request.user,
                    title="⚠️ High Memory Usage",
                    message=f"System memory usage is at {memory.percent}%. Consider optimizing.",
                    notification_type="warning",
                    link="/dashboard/system-health/",
                    metadata={"memory": memory.percent}
                )
                request.session[mem_key] = True
        
        # Disk Space Alert (<15% free)
        disk = psutil.disk_usage('/')
        free_percent = (disk.free / disk.total) * 100
        if free_percent < 15:
            disk_key = f'low_disk_{today.isoformat()}'
            if not request.session.get(disk_key, False):
                free_gb = disk.free / (1024**3)
                create_notification(
                    user=request.user,
                    title="💾 Low Storage Space",
                    message=f"Only {free_gb:.1f} GB remaining ({disk.percent}% used). Please clean up.",
                    notification_type="warning",
                    link="/dashboard/system-logs/",
                    metadata={"free_gb": free_gb, "used_percent": disk.percent}
                )
                request.session[disk_key] = True
                
    except ImportError:
        pass


def create_admin_security_notifications(request, proxy_alerts, today):
    """Create security-related notifications for admin"""
    if not request.user.is_superuser:
        return
    
    if proxy_alerts > 0:
        proxy_key = f'admin_proxy_alert_{today.isoformat()}'
        if not request.session.get(proxy_key, False):
            # Get detailed suspicious activities
            suspicious = AttendanceLog.objects.filter(
                session__date=today,
                status="PRESENT"
            ).values('student_id').annotate(
                session_count=Count('id')
            ).filter(session_count__gt=3)
            
            student_details = []
            for s in suspicious[:5]:
                student = Student.objects.filter(id=s['student_id']).first()
                if student:
                    student_details.append(f"{student.full_name} ({s['session_count']} sessions)")
            
            message = f"🚨 {proxy_alerts} suspicious attendance pattern(s) detected today."
            if student_details:
                message += f"\nAffected: {', '.join(student_details)}"
            
            create_notification(
                user=request.user,
                title="🔒 Security Alert: Multiple Proxy Attempts",
                message=message,
                notification_type="proxy",
                link="/dashboard/security-logs/",
                metadata={
                    "proxy_count": proxy_alerts,
                    "affected_students": student_details
                }
            )
            request.session[proxy_key] = True


def create_admin_face_registration_milestones(request, total_students, students_with_face):
    """Create milestone notifications for admin"""
    if not request.user.is_superuser:
        return
    
    today = timezone.now().date()
    face_percentage = (students_with_face / total_students * 100) if total_students > 0 else 0
    
    milestones = [25, 50, 75, 100]
    for milestone in milestones:
        if face_percentage >= milestone:
            milestone_key = f'face_milestone_{milestone}_{today.isoformat()}'
            if not request.session.get(milestone_key, False):
                create_notification(
                    user=request.user,
                    title=f"🎯 Face Registration Milestone: {milestone}%",
                    message=f"{milestone}% of students ({students_with_face}/{total_students}) now have face data registered.",
                    notification_type="success",
                    link="/dashboard/student-directory/",
                    metadata={"percentage": milestone, "count": students_with_face, "total": total_students}
                )
                request.session[milestone_key] = True


def create_admin_daily_summary(request):
    """Create daily attendance summary for admin"""
    if not request.user.is_superuser:
        return
    
    today = timezone.now().date()
    summary_key = f'admin_daily_summary_{today.isoformat()}'
    
    if not request.session.get(summary_key, False):
        total_students = Student.objects.count()
        present_today = AttendanceLog.objects.filter(
            session__date=today,
            status="PRESENT"
        ).values_list('student_id', flat=True).distinct().count()
        
        absent_today = total_students - present_today
        attendance_rate = round((present_today / total_students * 100) if total_students > 0 else 0, 1)
        daily_scans = AttendanceLog.objects.filter(session__date=today).count()
        
        message = f"📊 Attendance: {attendance_rate}% ({present_today}/{total_students} students)\n"
        message += f"• Total Scans: {daily_scans}\n"
        message += f"• Absent: {absent_today} students"
        
        create_notification(
            user=request.user,
            title=f"📈 Daily Attendance Summary - {today.strftime('%b %d, %Y')}",
            message=message,
            notification_type="attendance",
            link="/dashboard/attendance-report/",
            metadata={
                "date": today.isoformat(),
                "attendance_rate": attendance_rate,
                "present": present_today,
                "absent": absent_today,
                "total": total_students,
                "scans": daily_scans
            }
        )
        request.session[summary_key] = True


# Staff notifications

def create_staff_department_notifications(request):
    """Create department-specific notifications for staff"""
    if request.user.is_superuser or not hasattr(request.user, "staffprofile"):
        return
    
    staff_profile = request.user.staffprofile
    department = staff_profile.department
    today = timezone.now().date()
    
    # Department stats
    total_dept_students = Student.objects.filter(department=department).count()
    present_dept = AttendanceLog.objects.filter(
        session__date=today,
        student__department=department,
        status="PRESENT"
    ).values_list('student_id', flat=True).distinct().count()
    
    dept_attendance_rate = round((present_dept / total_dept_students * 100) if total_dept_students > 0 else 0, 1)
    
    # Low attendance alert for department
    if dept_attendance_rate < 40 and dept_attendance_rate > 0:
        low_key = f'dept_low_attendance_{department}_{today.isoformat()}'
        if not request.session.get(low_key, False):
            create_notification(
                user=request.user,
                title="📉 Low Attendance Alert",
                message=f"Your department ({department}) attendance is only {dept_attendance_rate}% today.",
                notification_type="warning",
                link=f"/dashboard/department-attendance/",
                metadata={"department": department, "attendance_rate": dept_attendance_rate}
            )
            request.session[low_key] = True
    
    # Students without face data in department
    students_without_face = Student.objects.filter(
        department=department,
        face_encoding__isnull=True
    ).count()
    
    if students_without_face > 0:
        face_key = f'dept_face_reminder_{department}_{today.isoformat()}'
        if not request.session.get(face_key, False):
            create_notification(
                user=request.user,
                title="📸 Face Registration Reminder",
                message=f"{students_without_face} student(s) in {department} need face data registration.",
                notification_type="student",
                link=f"/dashboard/student-directory/",
                metadata={"department": department, "pending_count": students_without_face}
            )
            request.session[face_key] = True


def create_staff_session_notifications(request, active_session):
    """Create session notifications for staff"""
    if request.user.is_superuser or not hasattr(request.user, "staffprofile"):
        return
    
    if not active_session:
        return
    
    staff_profile = request.user.staffprofile
    
    # Notify if session belongs to staff's department
    if active_session.created_by == staff_profile:
        session_key = f'staff_session_notification_{active_session.id}'
        if not request.session.get(session_key, False):
            present_count = AttendanceLog.objects.filter(
                session=active_session,
                status="PRESENT"
            ).count()
            
            message = f"Session '{active_session.subject_name}' is active. {present_count} students marked present."
            
            create_notification(
                user=request.user,
                title="🎓 Active Session",
                message=message,
                notification_type="session",
                link=f"/attendance/session/{active_session.id}/",
                metadata={
                    "session_id": active_session.id,
                    "subject": active_session.subject_name,
                    "present_count": present_count
                }
            )
            request.session[session_key] = True


def create_staff_daily_summary(request):
    """Create daily attendance summary for staff (department only)"""
    if request.user.is_superuser or not hasattr(request.user, "staffprofile"):
        return
    
    staff_profile = request.user.staffprofile
    department = staff_profile.department
    today = timezone.now().date()
    
    summary_key = f'staff_daily_summary_{department}_{today.isoformat()}'
    
    if not request.session.get(summary_key, False):
        total_students = Student.objects.filter(department=department).count()
        present_today = AttendanceLog.objects.filter(
            session__date=today,
            student__department=department,
            status="PRESENT"
        ).values_list('student_id', flat=True).distinct().count()
        
        attendance_rate = round((present_today / total_students * 100) if total_students > 0 else 0, 1)
        
        message = f"📊 {department} Department Report\n"
        message += f"• Attendance: {attendance_rate}% ({present_today}/{total_students} students)"
        
        create_notification(
            user=request.user,
            title=f"📈 Daily Department Summary",
            message=message,
            notification_type="attendance",
            link=f"/dashboard/department-attendance/",
            metadata={
                "department": department,
                "attendance_rate": attendance_rate,
                "present": present_today,
                "total": total_students
            }
        )
        request.session[summary_key] = True


#  Common notifications (Both Admin & Staff) ==========

def create_welcome_notification(request):
    """Create welcome notification for first visit of the day"""
    today = timezone.now().date()
    today_key = f'visited_{today.isoformat()}'
    
    if not request.session.get(today_key, False):
        total_students = Student.objects.count()
        students_with_face = Student.objects.filter(face_encoding__isnull=False).count()
        
        create_system_notification(
            title="Welcome to AFRAS",
            message=f"Good morning! Today's attendance system is ready. {students_with_face}/{total_students} students have registered face data.",
            notification_type="system",
            link="/dashboard/"
        )
        request.session[today_key] = True


def create_low_attendance_alert(request, attendance_rate):
    """Create low attendance alert for user"""
    if attendance_rate < 50 and attendance_rate > 0:
        today = timezone.now().date()
        attendance_key = f'low_attendance_{today.isoformat()}'
        
        if not request.session.get(attendance_key, False):
            create_notification(
                user=request.user,
                title="📊 Low Attendance Alert",
                message=f"Today's attendance is only {attendance_rate}%. Please check the system.",
                notification_type="warning",
                link="/attendance/reports/",
                metadata={"attendance_rate": attendance_rate}
            )
            request.session[attendance_key] = True


def create_low_face_registration_alert(request, face_percentage):
    """Create low face registration alert"""
    if face_percentage < 50:
        today = timezone.now().date()
        alert_key = f'face_reg_alert_{today.isoformat()}'
        
        if not request.session.get(alert_key, False):
            create_notification(
                user=request.user,
                title="⚠️ Face Registration Required",
                message=f"Only {face_percentage}% of students have registered face data.",
                notification_type="alert",
                link="/dashboard/student-directory/",
                metadata={"percentage": face_percentage}
            )
            request.session[alert_key] = True


def create_session_active_notification(request, active_session):
    """Create session active notification"""
    if active_session:
        session_key = f'session_notification_{active_session.id}'
        if not request.session.get(session_key, False):
            create_system_notification(
                title="🎓 Session Active",
                message=f"Attendance session for '{active_session.subject_name}' is currently active.",
                notification_type="session",
                link="/dashboard/",
                metadata={"session_id": active_session.id, "subject": active_session.subject_name}
            )
            request.session[session_key] = True


@login_required
def get_student_details(request, student_id):
    """API endpoint to get student details including face encoding for modal"""
    student = get_object_or_404(Student, id=student_id)

    # Permission check
    if not request.user.is_superuser:
        if hasattr(request.user, "staffprofile"):
            staff_profile = request.user.staffprofile
            if staff_profile.department != student.department:
                return JsonResponse({"error": "Permission denied"}, status=403)
        else:
            return JsonResponse({"error": "Permission denied"}, status=403)

    # Get face encoding data
    face_encoding_data = None
    face_encoding_preview = []
    face_encoding_length = 0

    if student.face_encoding:
        try:
            if isinstance(student.face_encoding, list):
                face_data = student.face_encoding
            elif isinstance(student.face_encoding, str):
                import json
                import ast
                try:
                    face_data = json.loads(student.face_encoding)
                except:
                    try:
                        face_data = ast.literal_eval(student.face_encoding)
                    except:
                        cleaned = student.face_encoding.strip()
                        if cleaned.startswith("[") and cleaned.endswith("]"):
                            cleaned = cleaned.replace('"', "").replace("'", "")
                            face_data = [float(x.strip()) for x in cleaned[1:-1].split(",")]
                        else:
                            face_data = []
            else:
                face_data = []

            if face_data and isinstance(face_data, list):
                face_encoding_length = len(face_data)
                for val in face_data[:10]:
                    try:
                        face_encoding_preview.append(f"{float(val):.6f}")
                    except:
                        face_encoding_preview.append(str(val))
                face_encoding_data = [f"{float(val):.6f}" for val in face_data[:50]]
        except Exception as e:
            print(f"Error parsing face encoding: {e}")

    # Get recent attendance
    recent_attendance = (
        AttendanceLog.objects.filter(student=student)
        .select_related("session")
        .order_by("-last_seen")[:5]
    )

    attendance_history = []
    for att in recent_attendance:
        duration_str = "N/A"
        if hasattr(att, 'presence_duration_minutes'):
            duration = att.presence_duration_minutes
            duration_str = f"{duration:.1f} mins"
        elif att.first_seen and att.last_seen:
            duration = (att.last_seen - att.first_seen).total_seconds() / 60
            duration_str = f"{duration:.1f} mins"
        
        attendance_history.append({
            "date": att.session.date.strftime("%Y-%m-%d") if att.session else "N/A",
            "subject": att.session.subject_name if att.session else "N/A",
            "status": att.status,
            "first_seen": att.first_seen.strftime("%I:%M:%S %p") if att.first_seen else "N/A",
            "last_seen": att.last_seen.strftime("%I:%M:%S %p") if att.last_seen else "N/A",
            "duration": duration_str,
            "is_validated": att.is_validated if hasattr(att, 'is_validated') else True,
            "validation_error": att.validation_error if hasattr(att, 'validation_error') else None,
        })

    return JsonResponse({
        "success": True,
        "student": {
            "id": student.id,
            "full_name": student.full_name,
            "roll_number": student.roll_number,
            "department": student.department,
            "year": student.year,
            "semester": student.semester,
            "section": student.section,
            "email": student.user.email if student.user else "N/A",
            "phone": student.phone_number if hasattr(student, 'phone_number') else "N/A",
            "address": student.address if hasattr(student, 'address') else "N/A",
            "has_id_proof": student.id_proof is not None if hasattr(student, 'id_proof') else False,
            "id_proof_url": student.id_proof.url if hasattr(student, 'id_proof') and student.id_proof else None,
        },
        "face_encoding": {
            "has_data": face_encoding_data is not None,
            "length": face_encoding_length,
            "preview": face_encoding_preview,
            "full_data": face_encoding_data,
        },
        "attendance_history": attendance_history,
        "total_attendance": AttendanceLog.objects.filter(student=student).count(),
    })

@login_required
@user_passes_test(is_staff_user, login_url="login", redirect_field_name=None)
@never_cache
def dashboard_home(request):
    today = timezone.now().date()
    
    # Basic stats
    daily_scans = AttendanceLog.objects.filter(session__date=today).count()
    
    # Calculate present today
    present_today = AttendanceLog.objects.filter(
        session__date=today, 
        status="PRESENT"
    ).values_list('student_id', flat=True).distinct().count()
    
    # Calculate suspicious attendance (proxy alerts)
    suspicious_attendance = AttendanceLog.objects.filter(
        session__date=today,
        status="PRESENT"
    ).values('student_id').annotate(
        session_count=Count('id')
    ).filter(session_count__gt=3)
    proxy_alerts = suspicious_attendance.count()
    
    # Total students
    total_students = Student.objects.count()
    students_with_face = Student.objects.filter(face_encoding__isnull=False).count()
    
    # Face registration percentage
    face_percentage = round((students_with_face / total_students * 100) if total_students > 0 else 0, 1)
    
    # Initialize variables
    attendance_rate = 0
    recent_logs_queryset = []
    staff_sessions = []
    subjects_taught_count = 0
    total_students_for_user = total_students
    weekly_attendance = []
    department_stats = []
    hourly_attendance = []
    total_staff = 0
    
    if request.user.is_superuser:
        # ========== ADMIN DASHBOARD ==========
        total_staff = StaffProfile.objects.count()
        total_students_for_user = total_students
        
        if total_students > 0:
            attendance_rate = round((present_today / total_students) * 100, 1)
        else:
            attendance_rate = 0
        
        recent_logs_queryset = (
            AttendanceLog.objects.select_related("student", "session")
            .all()
            .order_by("-last_seen")[:15]
        )
        
        # Weekly attendance trend (last 7 days)
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            daily_present = AttendanceLog.objects.filter(
                session__date=date, 
                status="PRESENT"
            ).count()
            weekly_attendance.append({
                "date": date.strftime("%a"),
                "count": daily_present,
                "full_date": date.strftime("%Y-%m-%d")
            })
        
        # Department stats
        department_stats = list(Student.objects.values('department').annotate(
            total=Count('id'),
            with_face=Count('id', filter=Q(face_encoding__isnull=False))
        ))
        
        # Hourly attendance
        for hour in range(8, 18):
            hour_count = AttendanceLog.objects.filter(
                session__date=today,
                first_seen__hour=hour
            ).count()
            if hour_count > 0:
                hourly_attendance.append({
                    "hour": f"{hour}:00",
                    "count": hour_count
                })
        
    else:
        # Staff dashboard
        if hasattr(request.user, "staffprofile"):
            staff_profile = request.user.staffprofile
            dept = staff_profile.department
            
            total_students_for_user = Student.objects.filter(department__iexact=dept).count()
            
            recent_logs_queryset = (
                AttendanceLog.objects.select_related("student", "session")
                .filter(student__department__iexact=dept)
                .order_by("-last_seen")[:15]
            )
            
            present_today_dept = AttendanceLog.objects.filter(
                session__date=today, 
                student__department__iexact=dept, 
                status="PRESENT"
            ).values_list('student_id', flat=True).distinct().count()
            
            if total_students_for_user > 0:
                attendance_rate = round((present_today_dept / total_students_for_user) * 100, 1)
            else:
                attendance_rate = 0
            
            staff_sessions = AttendanceSession.objects.filter(
                created_by=staff_profile
            ).order_by('-date')[:5]
            
            subjects_taught_count = AttendanceSession.objects.filter(
                created_by=staff_profile
            ).values('subject_name').distinct().count()
            
            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                daily_present = AttendanceLog.objects.filter(
                    session__date=date, 
                    student__department__iexact=dept,
                    status="PRESENT"
                ).count()
                weekly_attendance.append({
                    "date": date.strftime("%a"),
                    "count": daily_present,
                    "full_date": date.strftime("%Y-%m-%d")
                })
            
        else:
            total_students_for_user = total_students
            recent_logs_queryset = (
                AttendanceLog.objects.select_related("student", "session")
                .all()
                .order_by("-last_seen")[:15]
            )
            attendance_rate = round((present_today / total_students) * 100, 1) if total_students > 0 else 0
    
    # Prepare enhanced student data for the table with validation data
    enhanced_logs = []
    for log in recent_logs_queryset:
        student = log.student
        if student:
            log_data = {
                "log": log,
                "student_id": student.id,
                "student_roll": student.roll_number,
                "student_full_name": student.full_name,
                "student_department": student.department if hasattr(student, 'department') else 'N/A',
                "student_semester": student.semester if hasattr(student, 'semester') else 'N/A',
                "has_face_encoding": student.face_encoding is not None,
                "is_validated": log.is_validated if hasattr(log, 'is_validated') else True,
                "validation_error": log.validation_error if hasattr(log, 'validation_error') else None,
                "session_name": log.session.subject_name if log.session else "General",
                "session_semester": log.session.semester if log.session else "N/A",
            }
            enhanced_logs.append(log_data)
    
    # Recent activities for activity feed
    recent_activities = []
    recent_logs_for_activity = AttendanceLog.objects.select_related('student').order_by('-last_seen')[:5]
    for log in recent_logs_for_activity:
        recent_activities.append({
            "title": f"Attendance marked for {log.student.full_name}",
            "time_ago": get_time_ago(log.last_seen)
        })
    
    if not recent_activities:
        recent_activities = [
            {"title": "System initialized successfully", "time_ago": "Just now"},
            {"title": "Face recognition engine ready", "time_ago": "Just now"},
            {"title": "Database connection established", "time_ago": "Just now"},
        ]
    
    # Get active session
    active_session = AttendanceSession.objects.filter(is_active=True).first()
    
    # Face registration statistics
    total_students_all = Student.objects.count()
    total_students_with_face = Student.objects.filter(face_encoding__isnull=False).count()
    face_registration_percentage = round(
        (total_students_with_face / total_students_all * 100) if total_students_all > 0 else 0, 1
    )
    
    # System health metrics
    try:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        disk_usage = psutil.disk_usage('/').percent
    except:
        cpu_usage = 0
        memory_usage = 0
        disk_usage = 0
    
    # Get validation statistics
    total_logs = AttendanceLog.objects.count()
    validated_logs = AttendanceLog.objects.filter(is_validated=True).count() if hasattr(AttendanceLog, 'is_validated') else total_logs
    validation_failed = total_logs - validated_logs
    
    # Build main context dictionary
    main_context = {
        # Stats
        "daily_scans": daily_scans,
        "present_today": present_today,
        "proxy_alerts": proxy_alerts,
        "total_students": total_students_for_user,
        "students_with_face": students_with_face,
        "face_percentage": face_percentage,
        "attendance_rate": attendance_rate,
        
        # Performance metrics
        "recognition_accuracy": "98.5",
        "fps_rate": "15",
        "response_time": "1.8",
        "db_query_time": "45",
        
        # Activity and logs
        "recent_activities": recent_activities,
        "recent_logs": enhanced_logs,
        
        # Face registration
        "total_students_with_face": total_students_with_face,
        "face_registration_percentage": face_registration_percentage,
        
        # Session
        "active_session": active_session,
        
        # System health
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "disk_usage": disk_usage,
        
        # Charts
        "weekly_attendance": weekly_attendance,
        "department_stats": department_stats,
        "hourly_attendance": hourly_attendance,
        
        # Staff specific
        "staff_sessions": staff_sessions if not request.user.is_superuser else [],
        "subjects_taught_count": subjects_taught_count,
        "total_staff": total_staff,
        
        # Validation stats
        "total_logs": total_logs,
        "validated_logs": validated_logs,
        "validation_failed": validation_failed,
    }
    
    # Notifications
    
    # Welcome notification for first visit of the day
    today_key = f'visited_{today.isoformat()}'
    if not request.session.get(today_key, False):
        create_system_notification(
            title="Welcome to AFRAS",
            message=f"Good morning! Today's attendance system is ready. {total_students_with_face}/{total_students_all} students have registered face data.",
            notification_type="system",
            link="/dashboard/"
        )
        request.session[today_key] = True
    
    # Low face registration alert
    if face_registration_percentage < 50:
        alert_key = f'face_reg_alert_{today.isoformat()}'
        if not request.session.get(alert_key, False):
            create_notification(
                user=request.user,
                title="⚠️ Action Required: Face Registration",
                message=f"Only {face_registration_percentage}% of students have registered face data. Please complete registrations for accurate attendance.",
                notification_type="alert",
                link="/dashboard/student-directory/?face_status=no_face",
                metadata={"percentage": face_registration_percentage}
            )
            request.session[alert_key] = True
    
    # Low attendance alert
    if attendance_rate < 50 and attendance_rate > 0:
        attendance_key = f'low_attendance_{today.isoformat()}'
        if not request.session.get(attendance_key, False):
            create_notification(
                user=request.user,
                title="📊 Low Attendance Alert",
                message=f"Today's attendance is only {attendance_rate}%. Please check if the system is working correctly.",
                notification_type="warning",
                link="/attendance/reports/",
                metadata={"attendance_rate": attendance_rate}
            )
            request.session[attendance_key] = True
    
    # Proxy alerts notification
    if proxy_alerts > 0:
        proxy_key = f'proxy_alert_{today.isoformat()}'
        if not request.session.get(proxy_key, False):
            create_notification(
                user=request.user,
                title="🔒 Security Alert: Proxy Attempts Detected",
                message=f"{proxy_alerts} suspicious attendance pattern(s) detected today. Please review security logs.",
                notification_type="proxy",
                link="/dashboard/security-logs/",
                metadata={"proxy_count": proxy_alerts}
            )
            request.session[proxy_key] = True
    
    # Session active notification
    if active_session:
        session_key = f'session_notification_{active_session.id}'
        if not request.session.get(session_key, False):
            create_notification(
                user=request.user,
                title="🎓 Session Active",
                message=f"Attendance session for '{active_session.subject_name}' is currently active. Click to monitor.",
                notification_type="session",
                link=f"/attendance/live/{active_session.id}/",
                metadata={"session_id": active_session.id, "subject": active_session.subject_name}
            )
            request.session[session_key] = True
    
    # Admin-specific notifications 
    if request.user.is_superuser:
        # System health notifications
        try:
            if cpu_usage > 80:
                cpu_key = f'high_cpu_{today.isoformat()}'
                if not request.session.get(cpu_key, False):
                    create_notification(
                        user=request.user,
                        title="⚠️ High CPU Usage Alert",
                        message=f"System CPU usage is at {cpu_usage}%. Performance may be affected.",
                        notification_type="warning",
                        link="/dashboard/system-health/",
                        metadata={"cpu": cpu_usage}
                    )
                    request.session[cpu_key] = True
            
            if memory_usage > 85:
                mem_key = f'high_memory_{today.isoformat()}'
                if not request.session.get(mem_key, False):
                    create_notification(
                        user=request.user,
                        title="⚠️ High Memory Usage",
                        message=f"System memory usage is at {memory_usage}%. Consider optimizing.",
                        notification_type="warning",
                        link="/dashboard/system-health/",
                        metadata={"memory": memory_usage}
                    )
                    request.session[mem_key] = True
            
            if disk_usage > 85:
                disk_key = f'low_disk_{today.isoformat()}'
                if not request.session.get(disk_key, False):
                    free_gb = psutil.disk_usage('/').free / (1024**3)
                    create_notification(
                        user=request.user,
                        title="💾 Low Storage Space",
                        message=f"Only {free_gb:.1f} GB remaining ({disk_usage}% used). Please clean up.",
                        notification_type="warning",
                        link="/dashboard/system-logs/",
                        metadata={"free_gb": free_gb, "used_percent": disk_usage}
                    )
                    request.session[disk_key] = True
        except:
            pass
        
        # Face registration milestones
        milestones = [25, 50, 75, 100]
        for milestone in milestones:
            if face_registration_percentage >= milestone:
                milestone_key = f'face_milestone_{milestone}_{today.isoformat()}'
                if not request.session.get(milestone_key, False):
                    create_notification(
                        user=request.user,
                        title=f"🎯 Face Registration Milestone: {milestone}%",
                        message=f"{milestone}% of students ({total_students_with_face}/{total_students_all}) now have face data registered.",
                        notification_type="success",
                        link="/dashboard/student-directory/",
                        metadata={"percentage": milestone, "count": total_students_with_face, "total": total_students_all}
                    )
                    request.session[milestone_key] = True
        
        # Daily admin summary (once per day)
        summary_key = f'admin_daily_summary_{today.isoformat()}'
        if not request.session.get(summary_key, False):
            absent_today = total_students_all - present_today
            message = f"📊 Attendance: {attendance_rate}% ({present_today}/{total_students_all} students)\n"
            message += f"• Total Scans: {daily_scans}\n"
            message += f"• Absent: {absent_today} students"
            
            create_notification(
                user=request.user,
                title=f"📈 Daily Attendance Summary - {today.strftime('%b %d, %Y')}",
                message=message,
                notification_type="attendance",
                link="/dashboard/attendance-report/",
                metadata={
                    "date": today.isoformat(),
                    "attendance_rate": attendance_rate,
                    "present": present_today,
                    "absent": absent_today,
                    "total": total_students_all,
                    "scans": daily_scans
                }
            )
            request.session[summary_key] = True
    
    # Staff-specific notifications 
    if not request.user.is_superuser and hasattr(request.user, "staffprofile"):
        staff_profile = request.user.staffprofile
        department = staff_profile.department
        
        total_dept_students = Student.objects.filter(department__iexact=department).count()
        present_dept = AttendanceLog.objects.filter(
            session__date=today,
            student__department__iexact=department,
            status="PRESENT"
        ).values_list('student_id', flat=True).distinct().count()
        dept_attendance_rate = round((present_dept / total_dept_students * 100) if total_dept_students > 0 else 0, 1)
        
        if dept_attendance_rate < 40 and dept_attendance_rate > 0:
            low_key = f'dept_low_attendance_{department}_{today.isoformat()}'
            if not request.session.get(low_key, False):
                create_notification(
                    user=request.user,
                    title="📉 Low Attendance Alert",
                    message=f"Your department ({department}) attendance is only {dept_attendance_rate}% today.",
                    notification_type="warning",
                    link="/dashboard/department-attendance/",
                    metadata={"department": department, "attendance_rate": dept_attendance_rate}
                )
                request.session[low_key] = True
        
        students_without_face_dept = Student.objects.filter(
            department__iexact=department,
            face_encoding__isnull=True
        ).count()
        
        if students_without_face_dept > 0:
            face_key = f'dept_face_reminder_{department}_{today.isoformat()}'
            if not request.session.get(face_key, False):
                create_notification(
                    user=request.user,
                    title="📸 Face Registration Reminder",
                    message=f"{students_without_face_dept} student(s) in {department} need face data registration.",
                    notification_type="student",
                    link="/dashboard/student-directory/?face_status=no_face",
                    metadata={"department": department, "pending_count": students_without_face_dept}
                )
                request.session[face_key] = True

    return render(request, "dashboard/home.html", main_context)

def student_profile(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    return render(request, "dashboard/student_profile.html", {"student": student})


@login_required
def get_student_face_encoding(request, student_id):
    """API endpoint to get full face encoding data"""
    student = get_object_or_404(Student, id=student_id)

    # Permission check
    if not request.user.is_superuser:
        if hasattr(request.user, "staffprofile"):
            staff_profile = request.user.staffprofile
            if staff_profile.department != student.department:
                return JsonResponse({"error": "Permission denied"}, status=403)
        else:
            return JsonResponse({"error": "Permission denied"}, status=403)

    if student.face_encoding:
        try:
            # Handle different formats of face_encoding
            face_encoding = None

            # Case 1: Already a list
            if isinstance(student.face_encoding, list):
                face_encoding = student.face_encoding

            # Case 2: String that needs parsing
            elif isinstance(student.face_encoding, str):
                try:
                    import json

                    # Try to parse as JSON
                    face_encoding = json.loads(student.face_encoding)
                except json.JSONDecodeError:
                    # Try to parse as Python list literal
                    try:
                        import ast

                        face_encoding = ast.literal_eval(student.face_encoding)
                    except:
                        # Try to clean up and parse
                        cleaned = student.face_encoding.strip()
                        if cleaned.startswith("[") and cleaned.endswith("]"):
                            # Remove any extra quotes
                            cleaned = cleaned.replace('"', "").replace("'", "")
                            # Convert to list
                            face_encoding = [
                                float(x.strip()) for x in cleaned[1:-1].split(",")
                            ]
                        else:
                            raise ValueError("Cannot parse face encoding string")

            # Case 3: Bytes or other format
            else:
                try:
                    # Try to convert to string and then parse
                    face_str = str(student.face_encoding)
                    import json

                    face_encoding = json.loads(face_str)
                except:
                    raise ValueError(
                        f"Unknown face encoding type: {type(student.face_encoding)}"
                    )

            # Ensure it's a list
            if not isinstance(face_encoding, list):
                raise ValueError("Face encoding is not a list")

            # Convert all values to float and format to 6 decimal places
            formatted_face_encoding = []
            for value in face_encoding:
                try:
                    # Convert to float and format
                    num_value = float(value)
                    formatted_face_encoding.append(float(f"{num_value:.6f}"))
                except (ValueError, TypeError):
                    # If conversion fails, keep original value
                    formatted_face_encoding.append(value)

            # Return the face encoding data
            return JsonResponse(
                {
                    "success": True,
                    "student_name": student.full_name,
                    "student_id": student.id,
                    "roll_number": student.roll_number,
                    "department": student.department,
                    "vector_length": len(formatted_face_encoding),
                    "face_encoding": formatted_face_encoding,
                },
                json_dumps_params={"ensure_ascii": False},
            )

        except Exception as e:
            # Log the error for debugging
            import traceback

            print(f"Error in get_student_face_encoding: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            print(f"Face encoding type: {type(student.face_encoding)}")
            print(f"Face encoding value: {student.face_encoding}")

            return JsonResponse(
                {
                    "success": False,
                    "error": f"Error parsing face encoding. Data may be in an unexpected format.",
                },
                status=500,
            )
    else:
        return JsonResponse(
            {"success": False, "error": "No face encoding data available"}, status=404
        )

def get_user_department_students(user):
    """Get students filtered by user's department"""
    if user.is_superuser:
        return Student.objects.all()
    
    dept = get_department_from_user(user)
    if dept:
        return Student.objects.filter(department__iexact=dept)
    return Student.objects.none()

@login_required
def student_directory(request):
    if request.user.is_superuser:
        students = Student.objects.all()
    else:
        students = get_user_department_students(request.user)

    # Apply filters
    search_query = request.GET.get('search', '')
    department_filter = request.GET.get('department', '')
    year_filter = request.GET.get('year', '')
    semester_filter = request.GET.get('semester', '')
    face_status = request.GET.get('face_status', '')

    if search_query:
        students = students.filter(
            Q(full_name__icontains=search_query) |
            Q(roll_number__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if department_filter:
        students = students.filter(department__iexact=department_filter)
    
    if year_filter:
        students = students.filter(year=year_filter)
    
    if semester_filter:
        students = students.filter(semester=semester_filter)
    
    if face_status == 'has_face':
        students = students.filter(face_encoding__isnull=False)
    elif face_status == 'no_face':
        students = students.filter(face_encoding__isnull=True)

    # Count students with face encoding
    students_with_face = students.filter(face_encoding__isnull=False).count()
    total_students = students.count()
    students_without_face = total_students - students_with_face

    # Calculate percentage
    face_completion_rate = (students_with_face / total_students * 100) if total_students > 0 else 0

    # Prepare student data with face encoding information
    students_data = []
    for student in students:
        has_face_encoding = student.face_encoding is not None
        face_value_length = 0
        face_preview = []

        if has_face_encoding:
            try:
                face_data = None
                if isinstance(student.face_encoding, list):
                    face_data = student.face_encoding
                elif isinstance(student.face_encoding, str):
                    try:
                        import json
                        face_data = json.loads(student.face_encoding)
                    except json.JSONDecodeError:
                        try:
                            import ast
                            face_data = ast.literal_eval(student.face_encoding)
                        except:
                            face_data = []
                else:
                    face_data = []

                if isinstance(face_data, list) and face_data:
                    face_value_length = len(face_data)
                    for value in face_data[:5]:
                        try:
                            float_value = float(value)
                            face_preview.append(float(f"{float_value:.6f}"))
                        except (ValueError, TypeError):
                            face_preview.append(value)
            except Exception as e:
                print(f"Error processing face encoding for student {student.id}: {e}")

        students_data.append({
            "object": student,
            "has_face_encoding": has_face_encoding,
            "face_value_length": face_value_length,
            "face_preview": face_preview,
        })

    # Pagination
    paginator = Paginator(students_data, 15)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Get filter options
    departments = Student.objects.values_list('department', flat=True).distinct().order_by('department')
    years = Student.objects.values_list('year', flat=True).distinct().order_by('year')
    semesters = Student.objects.values_list('semester', flat=True).distinct().order_by('semester')

    active_session = AttendanceSession.objects.filter(is_active=True).first()
    
    context = {
        "page_obj": page_obj,
        "total_students": total_students,
        "students_with_face": students_with_face,
        "students_without_face": students_without_face,
        "face_completion_rate": face_completion_rate,
        "departments": departments,
        "years": years,
        "semesters": semesters,
        "active_session": active_session,
        "search_query": search_query,
        "department_filter": department_filter,
        "year_filter": year_filter,
        "semester_filter": semester_filter,
        "face_status": face_status,
    }
    return render(request, "dashboard/student_directory.html", context)


@login_required
def staff_directory(request):
    # Fetch all staff profiles from the real backend database
    all_staff = StaffProfile.objects.all().select_related("user").order_by("full_name")
    
    # Pagination - 15 items per page (same as System Logs)
    paginator = Paginator(all_staff, 15)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    active_session = AttendanceSession.objects.filter(is_active=True).first()
    context = {
        "page_obj": page_obj,
        "total_staff": all_staff.count(),
        "active_session": active_session,
    }
    return render(request, "dashboard/staff_directory.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_staff(request, staff_id):
    staff_profile = get_object_or_404(StaffProfile, id=staff_id)

    if request.method == "POST":
        form = StaffProfileEditForm(request.POST, request.FILES, instance=staff_profile)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Staff member {staff_profile.full_name} updated successfully!"
            )

            return redirect("staff-directory")
    else:
        # Pass the instance so __init__ can pre-fill data
        form = StaffProfileEditForm(instance=staff_profile)

    active_session = AttendanceSession.objects.filter(is_active=True).first()
    context = {
        "form": form,
        "staff_profile": staff_profile,
        "user": staff_profile.user,
        "page_title": f"Edit Staff: {staff_profile.full_name}",
        "active_session": active_session,
    }
    return render(request, "dashboard/edit_staff.html", context)


@login_required
def edit_student(request, student_id):
    """Edit student profile"""
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        # ============================================================
        # Create form with instance
        # ============================================================
        form = StudentEditForm(request.POST, request.FILES, instance=student, user=request.user)
        
        # ============================================================
        # The form's save() method will handle the face encoding and photo
        # ============================================================
        if form.is_valid():
            try:
                # Save the form - this will handle face_encoding and photo_data
                form.save()
                
                messages.success(
                    request, f"Student {student.full_name} updated successfully!"
                )
                return redirect("student-directory")
            except Exception as e:
                messages.error(request, f"Error updating student: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = StudentEditForm(instance=student, user=request.user)

    context = {
        "form": form,
        "student": student,
        "page_title": "Edit Student",
        "can_edit": True,
        "is_superuser": request.user.is_superuser,
    }
    return render(request, "dashboard/edit_student.html", context)


@login_required
@require_http_methods(["DELETE", "POST"])
def delete_student(request, student_id):
    """Delete student (AJAX or regular)"""
    # Get student object
    student = get_object_or_404(Student, id=student_id)

    # Permission check: only superusers can delete
    if not request.user.is_superuser:
        # Check if user has staff profile
        if not hasattr(request.user, "staff_profile"):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": "Permission denied"}, status=403)
            messages.error(request, "You don't have permission to delete students.")
            return redirect("student-directory")

        staff_profile = request.user.staff_profile

        # Check if staff is from the same department as student
        if staff_profile.department != student.department:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": "You can only delete students from your department"},
                    status=403,
                )
            messages.error(
                request, "You can only delete students from your department."
            )
            return redirect("student-directory")

    if request.method == "DELETE" or (
        request.method == "POST"
        and request.headers.get("X-Requested-With") == "XMLHttpRequest"
    ):
        # AJAX request
        try:
            # Store student info for response
            student_name = student.full_name
            student_roll = student.roll_number

            # Delete the user account (cascades to student due to CASCADE)
            user = student.user
            user.delete()

            # Store message in session for the next request
            messages.success(request, f"Student {student_name} deleted successfully!")

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Student {student_name} deleted successfully!",
                    "student_id": student_id,
                }
            )
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Error deleting student: {str(e)}"},
                status=500,
            )

    elif request.method == "POST":
        # Regular form submission
        form = StudentDeleteForm(request.POST)
        if form.is_valid() and form.cleaned_data["confirm"]:
            try:
                student_name = student.full_name
                student_roll = student.roll_number

                # Delete the user account
                user = student.user
                user.delete()

                messages.success(
                    request,
                    f"Student {student_name} ({student_roll}) deleted successfully!",
                )
                return redirect("student-directory")
            except Exception as e:
                messages.error(request, f"Error deleting student: {str(e)}")
                return redirect("student-directory")
        else:
            messages.error(request, "Please confirm deletion.")
            return redirect("student-directory")

    # GET request - show confirmation page
    form = StudentDeleteForm()
    context = {
        "form": form,
        "student": student,
        "page_title": "Delete Student",
    }
    return render(request, "dashboard/delete_student.html", context)


@login_required
@staff_member_required
def system_logs_view(request):
    """View for system logs with filtering and soft delete support"""
    
    # Get filter parameters
    search_query = request.GET.get('q', '')
    action_filter = request.GET.get('action', 'all')
    status_filter = request.GET.get('status', 'active')
    page = request.GET.get('page', 1)
    
    # Base queryset - Exclude soft deleted logs by default
    if status_filter == 'all' and request.user.is_superuser:
        logs = SystemLog.objects.all()
    elif status_filter == 'archived':
        logs = SystemLog.objects.filter(is_deleted=True)
    else:  # active (default)
        logs = SystemLog.objects.filter(is_deleted=False)
    
    # Apply search filter
    if search_query:
        logs = logs.filter(
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(details__icontains=search_query) |
            Q(action__icontains=search_query) |
            Q(deleted_username__icontains=search_query) |
            Q(ip_address__icontains=search_query)
        )
    
    # Apply action filter
    if action_filter != 'all':
        logs = logs.filter(action__icontains=action_filter)
    
    # Pagination - 15 items per page
    paginator = Paginator(logs, 25)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # Get action choices for filter dropdown
    action_choices = [choice[1] for choice in SystemLog.ACTION_CHOICES]
    
    context = {
        "page_obj": page_obj,
        "total_logs": logs.count(),
        "search_query": search_query,
        "action_filter": action_filter,
        "status_filter": status_filter,
        "is_superuser": request.user.is_superuser,
        "action_choices": action_choices,
    }
    
    return render(request, "dashboard/system_logs.html", context)


@login_required
@staff_member_required
def soft_delete_log(request, log_id):
    """Soft delete a single log"""
    try:
        log = get_object_or_404(SystemLog, id=log_id)
        
        # Check if already deleted
        if log.is_deleted:
            return JsonResponse({
                'success': False,
                'error': 'Log already archived'
            }, status=400)
        
        # Get reason from request
        try:
            data = json.loads(request.body)
            reason = data.get('reason', 'Manually archived')
        except:
            reason = 'Manually archived'
        
        # IMPORTANT: Update the fields directly instead of using soft_delete method
        log.is_deleted = True
        log.deleted_at = timezone.now()
        log.deleted_by = request.user
        log.deletion_reason = reason
        
        # Store user info before deletion
        if log.user:
            log.deleted_username = log.user.username
            log.deleted_user_email = log.user.email
        
        # Save the changes
        log.save(update_fields=[
            'is_deleted', 'deleted_at', 'deleted_by', 
            'deletion_reason', 'deleted_username', 'deleted_user_email'
        ])
        
        # Try to create notification
        try:
            from accounts.models import Notification
            Notification.send_notification(
                user=request.user,
                title='Log Archived',
                message=f'Log #{log.id} ({log.action}) was archived successfully',
                notification_type='success'
            )
        except Exception as e:
            print(f"Notification error (non-critical): {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Log archived successfully'
        })
        
    except SystemLog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Log not found'
        }, status=404)
    except Exception as e:
        import traceback
        print(f"Error in soft_delete_log: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
        

@login_required
@staff_member_required
@require_POST
def restore_log(request, log_id):
    """Restore a soft-deleted log"""
    try:
        log = get_object_or_404(SystemLog, id=log_id)
        
        if not log.is_deleted:
            return JsonResponse({
                'success': False,
                'error': 'Log is not archived'
            }, status=400)
        
        log.restore()
        
        # Create notification
        Notification.send_notification(
            user=request.user,
            title='Log Restored',
            message=f'Log #{log.id} ({log.action}) was restored successfully',
            notification_type='success'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Log restored successfully'
        })
        
    except SystemLog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Log not found'
        }, status=404)


@login_required
@staff_member_required
@require_http_methods(["DELETE"])
def permanent_delete_log(request, log_id):
    """Permanently delete a log (superuser only)"""
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Only superusers can permanently delete logs'
        }, status=403)
    
    try:
        log = get_object_or_404(SystemLog, id=log_id)
        log.delete()
        
        # Create notification
        Notification.send_notification(
            user=request.user,
            title='Log Permanently Deleted',
            message=f'Log #{log.id} ({log.action}) was permanently deleted',
            notification_type='warning'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Log permanently deleted'
        })
        
    except SystemLog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Log not found'
        }, status=404)


@login_required
@staff_member_required
@require_POST
def bulk_soft_delete_logs(request):
    """Bulk soft delete multiple logs"""
    try:
        data = json.loads(request.body)
        log_ids = data.get('log_ids', [])
        
        if not log_ids:
            return JsonResponse({
                'success': False,
                'error': 'No logs selected'
            }, status=400)
        
        logs = SystemLog.objects.filter(id__in=log_ids, is_deleted=False)
        count = logs.count()
        
        for log in logs:
            # Update fields directly
            log.is_deleted = True
            log.deleted_at = timezone.now()
            log.deleted_by = request.user
            log.deletion_reason = f"Bulk archived ({count} logs)"
            
            if log.user:
                log.deleted_username = log.user.username
                log.deleted_user_email = log.user.email
            
            log.save(update_fields=[
                'is_deleted', 'deleted_at', 'deleted_by', 
                'deletion_reason', 'deleted_username', 'deleted_user_email'
            ])
        
        # Create notification
        try:
            from accounts.models import Notification
            Notification.send_notification(
                user=request.user,
                title='Bulk Archive Complete',
                message=f'{count} logs were archived successfully',
                notification_type='success'
            )
        except:
            pass
        
        return JsonResponse({
            'success': True,
            'message': f'{count} logs archived successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@staff_member_required
@require_POST
def bulk_restore_logs(request):
    """Bulk restore multiple logs"""
    try:
        data = json.loads(request.body)
        log_ids = data.get('log_ids', [])
        
        if not log_ids:
            return JsonResponse({
                'success': False,
                'error': 'No logs selected'
            }, status=400)
        
        logs = SystemLog.objects.filter(id__in=log_ids, is_deleted=True)
        count = logs.count()
        
        for log in logs:
            log.restore()
        
        # Create notification
        Notification.send_notification(
            user=request.user,
            title='Bulk Restore Complete',
            message=f'{count} logs were restored successfully',
            notification_type='success'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{count} logs restored successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@staff_member_required
def export_logs(request):
    """Export logs to CSV"""
    import csv
    from django.http import HttpResponse
    
    # Get filter parameters
    action_filter = request.GET.get('action', 'all')
    status_filter = request.GET.get('status', 'active')
    
    # Base queryset
    if status_filter == 'all' and request.user.is_superuser:
        logs = SystemLog.objects.all()
    elif status_filter == 'archived':
        logs = SystemLog.objects.filter(is_deleted=True)
    else:
        logs = SystemLog.objects.filter(is_deleted=False)
    
    if action_filter != 'all':
        logs = logs.filter(action__icontains=action_filter)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="system_logs_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'User', 'Action', 'Details', 'IP Address',
        'Timestamp', 'Status', 'Deleted By', 'Deleted At', 'Deletion Reason'
    ])
    
    for log in logs:
        writer.writerow([
            log.id,
            log.user.username if log.user else (log.deleted_username or 'Deleted User'),
            log.action,
            log.details,
            log.ip_address or 'N/A',
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Archived' if log.is_deleted else 'Active',
            log.deleted_by.username if log.deleted_by else 'N/A',
            log.deleted_at.strftime('%Y-%m-%d %H:%M:%S') if log.deleted_at else 'N/A',
            log.deletion_reason or 'N/A'
        ])
    
    return response


@login_required
@staff_member_required
def api_get_log_details(request, log_id):
    """API endpoint to get log details"""
    try:
        log = get_object_or_404(SystemLog, id=log_id)
        
        return JsonResponse({
            'success': True,
            'log': {
                'id': log.id,
                'action': log.action,
                'details': log.details,
                'ip_address': log.ip_address,
                'timestamp': log.timestamp.isoformat(),
                'is_deleted': log.is_deleted,
                'user': log.user.username if log.user else (log.deleted_username or 'Deleted User'),
                'deleted_by': log.deleted_by.username if log.deleted_by else None,
                'deleted_at': log.deleted_at.isoformat() if log.deleted_at else None,
                'deletion_reason': log.deletion_reason
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["DELETE"])
@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_staff(request, staff_id):
    try:
        staff = StaffProfile.objects.get(id=staff_id)
        staff_name = staff.full_name

        # Delete the user account too
        if staff.user:
            staff.user.delete()
        else:
            staff.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f"Staff member {staff_name} deleted successfully",
            }
        )
    except StaffProfile.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Staff member not found"}, status=404
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@staff_member_required
@require_http_methods(["DELETE"])
def delete_single_log(request, log_id):
    """Delete a single log (soft delete)"""
    try:
        log = get_object_or_404(SystemLog, id=log_id)
        
        if log.is_deleted:
            return JsonResponse({
                'success': False,
                'error': 'Log already archived'
            }, status=400)
        
        # Soft delete the log
        log.soft_delete(
            deleted_by=request.user,
            reason='Deleted by admin'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Log archived successfully'
        })
        
    except SystemLog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Log not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@login_required
def start_manual_session(request):
    """Start a manual attendance session"""
    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "error": "Method not allowed. Please use POST."
        }, status=405)
    
    try:
        # Get form data
        subject = request.POST.get("subject")
        department = request.POST.get("department")
        semester = request.POST.get("semester", 1)
        duration = int(request.POST.get("duration", 60))
        
        # Validate inputs
        if not subject:
            return JsonResponse({
                "success": False,
                "message": "Subject is required"
            }, status=400)
        
        # Get current time for start time
        now = timezone.now()
        
        # Get staff profile
        staff_profile = None
        if hasattr(request.user, "staffprofile"):
            staff_profile = request.user.staffprofile
        elif request.user.is_superuser:
            staff_profile = StaffProfile.objects.first()
        
        # Create the session
        session = AttendanceSession.objects.create(
            subject_name=subject[:100],
            date=now.date(),
            start_time=now,
            expected_duration=duration,
            is_active=True,
            created_by=staff_profile,
        )
        
        # Log the activity
        try:
            SystemLog.objects.create(
                user=request.user,
                action="CREATE_SESSION",
                details=f"Manual session created: {subject}",
                ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0')
            )
        except:
            pass
        
        return JsonResponse({
            "success": True,
            "message": f"Session '{subject}' started successfully!",
            "session_id": session.id,
            "redirect_url": f"/attendance/live/{session.id}/"
        })
        
    except Exception as e:
        import traceback
        print(f"Error starting manual session: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            "success": False,
            "message": f"Error starting session: {str(e)}"
        }, status=500)


@login_required
def api_session_stats(request):
    """API endpoint to get session statistics"""
    today = timezone.now().date()

    total_sessions = AttendanceSession.objects.count()
    active_sessions = AttendanceSession.objects.filter(is_active=True).count()
    today_sessions = AttendanceSession.objects.filter(date=today).count()

    return JsonResponse(
        {"total": total_sessions, "active": active_sessions, "today": today_sessions}
    )


@login_required
def api_recent_sessions(request):
    """API endpoint to get recent sessions"""
    recent_sessions = AttendanceSession.objects.order_by("-date", "-start_time")[:10]
    
    sessions_data = []
    for session in recent_sessions:
        sessions_data.append({
            "id": session.id,
            "subject": session.subject_name,
            "date": session.date.strftime("%Y-%m-%d"),
            "semester": session.semester,
            "year": session.year,
            "department": session.department,
            "time": (
                f"{session.start_time.strftime('%I:%M %p')} - {session.end_time.strftime('%I:%M %p')}"
                if session.end_time
                else session.start_time.strftime("%I:%M %p")
            ),
            "is_active": session.is_active,
        })
    
    return JsonResponse({"sessions": sessions_data})


@login_required
def api_recent_attendance(request):
    """API endpoint for recent attendance feed"""
    today = timezone.now().date()
    
    if request.user.is_superuser:
        logs = AttendanceLog.objects.select_related('student', 'session').order_by('-last_seen')[:20]
    else:
        if hasattr(request.user, 'staffprofile'):
            dept = request.user.staffprofile.department
            logs = AttendanceLog.objects.select_related('student', 'session').filter(
                student__department=dept
            ).order_by('-last_seen')[:20]
        else:
            logs = AttendanceLog.objects.select_related('student', 'session').order_by('-last_seen')[:20]
    
    attendance_data = []
    for log in logs:
        attendance_data.append({
            "id": log.id,
            "student_id": log.student.id,
            "student_name": log.student.full_name,
            "student_roll": log.student.roll_number,
            "student_dept": log.student.department,
            "student_semester": log.student.semester,
            "subject": log.session.subject_name if log.session else "Unknown",
            "session_semester": log.session.semester if log.session else "N/A",
            "status": log.status,
            "status_display": log.get_status_display(),
            "time": log.first_seen.strftime("%I:%M:%S %p") if log.first_seen else "N/A",
            "has_face": log.student.face_encoding is not None,
            "is_validated": log.is_validated if hasattr(log, 'is_validated') else True,
            "validation_error": log.validation_error if hasattr(log, 'validation_error') else None,
        })
    
    return JsonResponse({
        "success": True,
        "attendance": attendance_data,
        "total": len(attendance_data)
    })


@csrf_exempt
def extract_routine_ai(request):
    # ===== DEBUG SECTION =====
    print("=" * 60)
    print("🔍 EXTRACT ROUTINE AI CALLED")
    print(f"📌 Request Method: {request.method}")
    print(f"📌 Content Type: {request.content_type}")
    print(f"📌 FILES present: {bool(request.FILES)}")
    if request.FILES:
        print(f"📌 File keys: {list(request.FILES.keys())}")
        for key, file in request.FILES.items():
            print(f"📌 File: {key} - {file.name} ({file.size} bytes)")
    print(f"📌 POST keys: {list(request.POST.keys())}")
    print("=" * 60)
    # ===== END DEBUG =====
    if request.method == "POST" and request.FILES.get("routine_file"):
        uploaded_file = request.FILES["routine_file"]

        # Check if required libraries are installed
        try:
            import pandas as pd
            import pdfplumber
        except ImportError as e:
            return JsonResponse({
                "success": False,
                "message": f"Required library not installed: {str(e)}. Please run: pip install pandas openpyxl pdfplumber xlrd",
            }, status=500)

        try:
            # Save file temporarily
            file_path = default_storage.save(
                f"temp_routines/{uploaded_file.name}", ContentFile(uploaded_file.read())
            )
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)

            sessions_created = []
            extracted_data = []

            # Parse based on file extension
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()

            if file_extension in [".xlsx", ".xls", ".csv"]:
                # Parse Excel/CSV
                try:
                    if file_extension == ".csv":
                        encodings = ["utf-8", "latin1", "cp1252", "iso-8859-1"]
                        df = None
                        for encoding in encodings:
                            try:
                                df = pd.read_csv(full_path, encoding=encoding)
                                print(f"Successfully read CSV with {encoding} encoding")
                                break
                            except UnicodeDecodeError:
                                continue

                        if df is None:
                            df = pd.read_csv(full_path, engine="python")
                    else:
                        df = pd.read_excel(full_path)

                    df.columns = [str(col).strip() for col in df.columns]
                    extracted_data = df.to_dict("records")
                except Exception as e:
                    print(f"Error reading file with pandas: {e}")
                    return JsonResponse({
                        "success": False,
                        "message": f"Error reading file: {str(e)}. Make sure it's a valid CSV/Excel file.",
                    }, status=400)

            elif file_extension == ".pdf":
                try:
                    with pdfplumber.open(full_path) as pdf:
                        for page in pdf.pages:
                            tables = page.extract_tables()
                            for table in tables:
                                if len(table) > 1:
                                    headers = [str(h).strip() if h else "" for h in table[0]]
                                    for row in table[1:]:
                                        if row and any(cell for cell in row):
                                            clean_row = []
                                            for cell in row:
                                                if cell is None:
                                                    clean_row.append("")
                                                else:
                                                    clean_row.append(str(cell).strip())
                                            if len(clean_row) == len(headers):
                                                entry = dict(zip(headers, clean_row))
                                                extracted_data.append(entry)
                except Exception as e:
                    print(f"Error reading PDF: {e}")
                    return JsonResponse({
                        "success": False,
                        "message": f"Error reading PDF: {str(e)}",
                    }, status=400)
            else:
                return JsonResponse({
                    "success": False,
                    "message": "Unsupported file format. Please upload CSV, Excel, or PDF files.",
                }, status=400)

            if not extracted_data:
                return JsonResponse({
                    "success": False,
                    "message": "No data found in the uploaded file.",
                }, status=400)

            # Get current staff profile
            staff_profile = None
            if hasattr(request.user, "staffprofile"):
                staff_profile = request.user.staffprofile
            elif request.user.is_superuser:
                staff_profile = StaffProfile.objects.first()

            # Process extracted data
            today = timezone.now().date()
            created_sessions = []

            for idx, item in enumerate(extracted_data):
                try:
                    # Get subject name
                    subject = None
                    for key in ["Subject", "subject", "COURSE", "Course", "MODULE", "Class", "class", "Subject Name", "subject_name"]:
                        if key in item and item[key] and str(item[key]).strip():
                            subject = str(item[key]).strip()
                            break

                    if not subject:
                        continue

                    # Parse date
                    session_date = today
                    for date_key in ["Date", "date", "DATE", "Session Date", "Day", "day"]:
                        if date_key in item and item[date_key] and str(item[date_key]).strip():
                            date_val = item[date_key]
                            date_str = str(date_val).strip()

                            try:
                                day_map = {
                                    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                                    "Friday": 4, "Saturday": 5, "Sunday": 6,
                                    "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6
                                }
                                if date_str in day_map:
                                    days_ahead = day_map[date_str] - today.weekday()
                                    if days_ahead < 0:
                                        days_ahead += 7
                                    session_date = today + timedelta(days=days_ahead)
                                    break

                                if isinstance(date_val, str):
                                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
                                        try:
                                            session_date = datetime.strptime(date_str, fmt).date()
                                            break
                                        except:
                                            continue
                                elif hasattr(date_val, "date"):
                                    session_date = date_val.date()
                                break
                            except:
                                continue

                    # Parse time
                    start_time = None
                    for time_key in ["Time", "time", "TIME", "Start Time", "Start_Time", "start_time"]:
                        if time_key in item and item[time_key] and str(item[time_key]).strip():
                            time_str = str(item[time_key]).strip()

                            try:
                                if "-" in time_str:
                                    start_str = time_str.split("-")[0].strip()
                                else:
                                    start_str = time_str.strip()

                                for fmt in ["%H:%M", "%I:%M %p", "%H.%M", "%I.%M %p", "%H%M"]:
                                    try:
                                        parsed_time = datetime.strptime(start_str, fmt).time()
                                        start_time = timezone.make_aware(datetime.combine(session_date, parsed_time))
                                        break
                                    except:
                                        continue
                                if start_time:
                                    break
                            except:
                                continue

                    if not start_time:
                        start_time = timezone.make_aware(
                            datetime.combine(session_date, datetime.strptime("09:00", "%H:%M").time())
                        )

                    # Parse duration
                    expected_duration = 60
                    for duration_key in ["Duration", "duration", "DURATION", "Minutes", "mins", "Length"]:
                        if duration_key in item and item[duration_key]:
                            try:
                                duration_val = str(item[duration_key]).strip()
                                numbers = re.findall(r"\d+", duration_val)
                                if numbers:
                                    expected_duration = int(numbers[0])
                                break
                            except:
                                pass

                    # Check if session already exists
                    existing_session = AttendanceSession.objects.filter(
                        subject_name=subject,
                        date=session_date,
                        start_time__hour=start_time.hour,
                        start_time__minute=start_time.minute,
                    ).first()

                    if existing_session:
                        created_sessions.append({
                            "subject": existing_session.subject_name,
                            "date": existing_session.date.strftime("%Y-%m-%d"),
                            "time": existing_session.start_time.strftime("%H:%M"),
                            "duration": expected_duration,
                            "status": "already_exists",
                            "id": existing_session.id
                        })
                    else:
                        # Create new session
                        session = AttendanceSession.objects.create(
                            subject_name=subject[:100],
                            date=session_date,
                            start_time=start_time,
                            expected_duration=expected_duration,
                            is_active=False,
                            created_by=staff_profile,
                        )

                        created_sessions.append({
                            "subject": session.subject_name,
                            "date": session.date.strftime("%Y-%m-%d"),
                            "time": session.start_time.strftime("%H:%M"),
                            "duration": expected_duration,
                            "status": "created",
                            "id": session.id
                        })

                except Exception as e:
                    print(f"Error processing row {idx}: {e}")
                    continue

            # Store extracted routines in session for display
            request.session['extracted_routines'] = created_sessions
            
            # Clean up temp file
            default_storage.delete(file_path)

            created_count = len([s for s in created_sessions if s["status"] == "created"])
            existing_count = len([s for s in created_sessions if s["status"] == "already_exists"])

            if created_count == 0 and existing_count == 0:
                return JsonResponse({
                    "success": False,
                    "message": "No valid sessions could be extracted from the file.",
                }, status=400)

            return JsonResponse({
                "success": True,
                "message": f"Extraction complete! Created {created_count} new sessions, found {existing_count} existing sessions.",
                "classes_count": len(created_sessions),
                "sessions": created_sessions,
                "created_count": created_count,
                "existing_count": existing_count
            })

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            if os.path.exists(full_path):
                default_storage.delete(file_path)
            return JsonResponse({
                "success": False,
                "message": f"Error processing file: {str(e)}",
            }, status=500)

    return JsonResponse({"success": False, "message": "No file provided."}, status=400)


@login_required
def clear_extracted_routines(request):
    """Clear extracted routines from session"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False, 
            'error': 'Method not allowed. Use POST.'
        }, status=405)
    
    try:
        # Clear the session data
        if 'extracted_routines' in request.session:
            del request.session['extracted_routines']
        
        return JsonResponse({
            'success': True, 
            'message': 'Extracted routines cleared successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
def apply_extracted_routines(request):
    """Apply extracted routines to create attendance sessions"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False, 
            'error': 'Method not allowed. Use POST.'
        }, status=405)
    
    try:
        # Get routines from session
        routines = request.session.get('extracted_routines', [])
        
        if not routines:
            return JsonResponse({
                'success': False, 
                'error': 'No extracted routines found in session'
            }, status=400)
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        # Get staff profile
        staff_profile = None
        if hasattr(request.user, "staffprofile"):
            staff_profile = request.user.staffprofile
        elif request.user.is_superuser:
            staff_profile = StaffProfile.objects.first()
        
        for routine in routines:
            # Skip if already exists
            if routine.get('status') == 'already_exists':
                skipped_count += 1
                continue
                
            try:
                # Parse date
                date_str = routine.get('date')
                if not date_str:
                    continue
                    
                # Try different date formats
                date_obj = None
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
                    try:
                        date_obj = datetime.strptime(date_str, fmt).date()
                        break
                    except:
                        continue
                
                if not date_obj:
                    errors.append(f"Could not parse date: {date_str}")
                    continue
                
                # Parse time
                time_str = routine.get('time')
                if not time_str:
                    errors.append(f"No time for: {routine.get('subject')}")
                    continue
                
                # Try different time formats
                time_obj = None
                for fmt in ["%H:%M", "%I:%M %p", "%H.%M", "%I.%M %p", "%H%M"]:
                    try:
                        # If format has AM/PM but no AM/PM in string, skip
                        if 'p' in fmt.lower() and not any(x in time_str.lower() for x in ['am', 'pm']):
                            # Add AM/PM if not present (assume AM)
                            time_str = time_str + " AM"
                        parsed_time = datetime.strptime(time_str.strip(), fmt).time()
                        time_obj = parsed_time
                        break
                    except:
                        continue
                
                if not time_obj:
                    errors.append(f"Could not parse time: {time_str}")
                    continue
                
                # Create timezone-aware datetime
                start_time = timezone.make_aware(
                    datetime.combine(date_obj, time_obj)
                )
                
                # Get duration
                duration = int(routine.get('duration', 60))
                
                # Create session
                session = AttendanceSession.objects.create(
                    subject_name=routine.get('subject', 'Unknown')[:100],
                    date=date_obj,
                    start_time=start_time,
                    expected_duration=duration,
                    is_active=False,
                    created_by=staff_profile,
                )
                created_count += 1
                
            except Exception as e:
                errors.append(f"Error creating session for {routine.get('subject')}: {str(e)}")
                continue
        
        # Clear routines after applying
        request.session['extracted_routines'] = []
        
        # Build response message
        message = f"Created {created_count} sessions"
        if skipped_count > 0:
            message += f", skipped {skipped_count} existing sessions"
        if errors:
            message += f", {len(errors)} errors occurred"
        
        return JsonResponse({
            'success': True,
            'message': message,
            'created': created_count,
            'skipped': skipped_count,
            'errors': errors[:5]  # Return first 5 errors
        })
        
    except Exception as e:
        import traceback
        print(f"Error in apply_extracted_routines: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@user_passes_test(lambda u: u.is_superuser)
def system_configuration_view(request):
    config = SystemConfiguration.load()
    
    if request.method == "POST":
        try:
            # Basic Settings
            config.institution_name = request.POST.get("institution_name", "Far Western University")
            config.timezone = request.POST.get("timezone", "Asia/Kathmandu")
            
            # Recognition Settings
            config.recognition_threshold = float(request.POST.get("threshold", 0.65))
            config.detection_model = request.POST.get("detection_model", "hog")
            config.upsample_factor = int(request.POST.get("upsample", 1))
            
            # Camera Settings
            config.camera_source = request.POST.get("camera", "0")
            config.rtsp_url = request.POST.get("rtsp_url", "")
            config.frame_resolution = float(request.POST.get("resolution", 0.75))
            config.frame_skip = int(request.POST.get("frame_skip", 3))
            
            # Attendance Settings
            config.min_retention_required = int(request.POST.get("retention", 80))
            config.default_duration = int(request.POST.get("default_duration", 60))
            config.auto_stop_minutes = int(request.POST.get("auto_stop", 5))
            
            # Performance Settings
            config.cache_size = int(request.POST.get("cache_size", 100))
            config.processing_threads = int(request.POST.get("threads", 2))
            config.log_retention_days = int(request.POST.get("log_retention", 30))
            
            # Notification Settings
            config.notify_session_start = request.POST.get("notify_session_start") == "on"
            config.notify_session_end = request.POST.get("notify_session_end") == "on"
            config.notify_low_attendance = request.POST.get("notify_low_attendance") == "on"
            config.alert_email = request.POST.get("alert_email", "admin@example.com")
            config.attendance_threshold = int(request.POST.get("attendance_threshold", 50))
            
            # API Settings
            config.enable_api = request.POST.get("enable_api") == "on"
            config.require_api_key = request.POST.get("require_api_key") == "on"
            # Don't overwrite API key if not provided
            new_api_key = request.POST.get("api_key", "")
            if new_api_key and new_api_key != config.api_key:
                config.api_key = new_api_key
            config.webhook_url = request.POST.get("webhook_url", "")
            
            # Debug Settings
            config.debug_mode = int(request.POST.get("debug_mode", 0))
            
            # Metadata
            config.updated_by = request.user.username
            
            config.save()
            
            # Log the change
            SystemLog.objects.create(
                user=request.user,
                action="CONFIG_UPDATE",
                details=f"System configuration updated"
            )
            
            messages.success(request, "Configuration saved successfully!")
            return redirect("system_configuration")
            
        except Exception as e:
            messages.error(request, f"Error saving configuration: {str(e)}")
    
    # Get system stats
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_used_gb = memory.used / (1024**3)
        memory_total_gb = memory.total / (1024**3)
        
        # Check face recognition
        face_recognition_active = False
        try:
            import face_recognition
            face_recognition_active = True
        except ImportError:
            face_recognition_active = False
        
        # Database status
        from django.db import connection
        connection.ensure_connection()
        db_status = "Connected"
        
        # Student stats
        total_students = Student.objects.count()
        students_with_face = Student.objects.exclude(face_encoding__isnull=True).count()
        face_percentage = (students_with_face / total_students * 100) if total_students > 0 else 0
        
    except Exception as e:
        cpu_percent = 0
        memory_used_gb = 0
        memory_total_gb = 4
        face_recognition_active = False
        db_status = "Error"
        total_students = 0
        students_with_face = 0
        face_percentage = 0
    
    active_session = AttendanceSession.objects.filter(is_active=True).first()
    
    context = {
        "config": config,
        "system_stats": {
            "cpu": f"{cpu_percent}%",
            "memory": f"{memory_used_gb:.1f}GB/{memory_total_gb:.1f}GB",
            "face_recognition": "Active" if face_recognition_active else "Inactive",
            "database": db_status,
            "total_students": total_students,
            "students_with_face": students_with_face,
            "face_percentage": f"{face_percentage:.1f}%",
        },
        "active_session": active_session,
    }
    
    return render(request, "dashboard/configuration.html", context)


@user_passes_test(lambda u: u.is_superuser)
def test_configuration_api(request):
    """API endpoint to test configuration settings using saved values"""
    from attendance.models import AttendanceSession
    import cv2
    import numpy as np
    from django.db import connection
    
    # Load the current configuration
    config = SystemConfiguration.load()
    
    results = []
    
    # Test 1: Camera with configured resolution
    try:
        # Get camera source from config
        if config.camera_source == "rtsp" and config.rtsp_url:
            camera_source = config.rtsp_url
        else:
            camera_source = int(config.camera_source) if config.camera_source.isdigit() else 0
        
        camera = cv2.VideoCapture(camera_source)
        
        if camera.isOpened():
            # Try to set resolution based on config
            if config.frame_resolution == 0.5:
                width, height = 640, 480
            elif config.frame_resolution == 0.75:
                width, height = 960, 720
            else:
                width, height = 1280, 720
            
            # Attempt to set resolution (may not be supported by all cameras)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # Read a test frame
            ret, frame = camera.read()
            if ret and frame is not None:
                actual_height, actual_width = frame.shape[:2]
                results.append({
                    "test": "Camera", 
                    "status": "success", 
                    "message": f"Working (Requested: {width}x{height}, Actual: {actual_width}x{actual_height})"
                })
            else:
                results.append({
                    "test": "Camera", 
                    "status": "warning", 
                    "message": "Camera opened but no frame"
                })
            camera.release()
        else:
            results.append({
                "test": "Camera", 
                "status": "error", 
                "message": f"Cannot open camera source: {camera_source}"
            })
    except Exception as e:
        results.append({"test": "Camera", "status": "error", "message": str(e)})
    
    # Test 2: Face Recognition - unchanged
    try:
        import face_recognition
        results.append({
            "test": "Face Recognition", 
            "status": "success", 
            "message": f"Library loaded (v{face_recognition.__version__})"
        })
    except ImportError:
        results.append({
            "test": "Face Recognition", 
            "status": "error", 
            "message": "face_recognition not installed"
        })
    except Exception as e:
        results.append({"test": "Face Recognition", "status": "error", "message": str(e)})
    
    # Test 3: Database - unchanged
    try:
        connection.ensure_connection()
        results.append({"test": "Database", "status": "success", "message": "Connected"})
    except Exception as e:
        results.append({"test": "Database", "status": "error", "message": str(e)})
    
    # Test 4: Student Face Data - unchanged
    total = Student.objects.count()
    with_face = Student.objects.exclude(face_encoding__isnull=True).count()
    if total > 0:
        percentage = (with_face / total) * 100
        status = "success" if percentage > 50 else "warning"
        results.append({
            "test": "Face Data", 
            "status": status,
            "message": f"{with_face}/{total} students ({percentage:.1f}%)"
        })
    else:
        results.append({
            "test": "Face Data", 
            "status": "warning", 
            "message": "No students in database"
        })
    
    return JsonResponse({"success": True, "results": results})


@user_passes_test(lambda u: u.is_superuser)
def generate_api_key_api(request):
    """Generate a new API key"""
    config = SystemConfiguration.load()
    config.generate_api_key()
    config.save()
    
    return JsonResponse({
        "success": True, 
        "api_key": config.api_key
    })


@login_required
def active_routines_api(request):
    """
    API endpoint to get active routines
    """
    routines = Routine.objects.filter(is_active=True).order_by('day_of_week', 'start_time')
    
    day_map = {
        0: 'Monday', 1: 'Tuesday', 2: 'Wednesday',
        3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'
    }
    
    data = []
    for routine in routines:
        # Convert day_of_week to string if it's an integer
        day = routine.day_of_week
        if isinstance(day, int):
            day = day_map.get(day, 'Unknown')
        
        data.append({
            'id': routine.id,
            'subject': routine.subject,
            'department': routine.department,
            'semester': routine.semester,
            'year': routine.year,
            'section': routine.section or 'N/A',
            'day_of_week': day,
            'start_time': routine.start_time.strftime('%I:%M %p'),
            'duration': routine.duration,
            'is_active': routine.is_active
        })
    
    return JsonResponse({
        'routines': data,
        'total': len(data)
    })
    

@user_passes_test(lambda u: u.is_superuser)
def system_status_api(request):
    """Real-time system status"""
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Check if face recognition is working
        face_status = "Active"
        try:
            import face_recognition
            face_status = "Active"
        except:
            face_status = "Inactive"
        
        return JsonResponse({
            "cpu": f"{cpu}%",
            "memory": f"{memory.used / (1024**3):.1f}GB/{memory.total / (1024**3):.1f}GB",
            "face_recognition": face_status,
            "database": "Connected",
            "timestamp": timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    

@login_required
def api_dashboard_stats(request):
    """API endpoint for dashboard statistics"""
    today = timezone.now().date()
    
    total_students = Student.objects.count()
    students_with_face = Student.objects.filter(face_encoding__isnull=False).count()
    
    # Today's attendance - SQLite compatible way
    attendance_records = AttendanceLog.objects.filter(
        session__date=today,
        status="PRESENT"
    ).values_list('student_id', flat=True).distinct()
    today_present = len(attendance_records)
    
    # Active sessions
    active_sessions = AttendanceSession.objects.filter(is_active=True).count()
    
    # System health
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
    except:
        cpu_percent = 0
        memory_percent = 0
    
    stats = {
        "success": True,
        "total_students": total_students,
        "students_with_face": students_with_face,
        "face_completion_percent": round((students_with_face / total_students * 100) if total_students > 0 else 0, 1),
        "today_present": today_present,
        "today_absent": total_students - today_present,
        "attendance_percent": round((today_present / total_students * 100) if total_students > 0 else 0, 1),
        "active_sessions": active_sessions,
        "daily_scans": AttendanceLog.objects.filter(session__date=today).count(),
        "system_cpu": f"{cpu_percent}%",
        "system_memory": f"{memory_percent}%",
    }
    
    return JsonResponse(stats)



@login_required
def api_attendance_summary(request):
    """API endpoint for attendance summary charts"""
    today = timezone.now().date()
    
    # Get weekly data
    weekly_data = []
    for i in range(7):
        date = today - timedelta(days=i)
        present_count = AttendanceLog.objects.filter(
            session__date=date, 
            status="PRESENT"
        ).count()
        total_students = Student.objects.count()
        
        weekly_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "day": date.strftime("%a"),
            "present": present_count,
            "total": total_students,
            "percentage": round((present_count / total_students * 100) if total_students > 0 else 0, 1)
        })
    
    # Get hourly distribution for today
    hourly_data = []
    for hour in range(8, 18):
        hour_count = AttendanceLog.objects.filter(
            session__date=today,
            first_seen__hour=hour
        ).count()
        hourly_data.append({
            "hour": f"{hour}:00",
            "count": hour_count
        })
    
    # Get department distribution
    dept_data = []
    depts = Student.objects.values('department').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for dept in depts:
        dept_data.append({
            "name": dept['department'] or "Unassigned",
            "count": dept['count']
        })
    
    return JsonResponse({
        "success": True,
        "weekly": weekly_data,
        "hourly": hourly_data,
        "departments": dept_data,
        "total_students": Student.objects.count(),
        "students_with_face": Student.objects.filter(face_encoding__isnull=False).count()
    })


@login_required
def api_export_attendance(request):
    """API endpoint to export attendance data"""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        attendance_ids = data.get('attendance_ids', [])
        
        if request.user.is_superuser:
            if attendance_ids and len(attendance_ids) > 0:
                logs = AttendanceLog.objects.filter(id__in=attendance_ids).select_related('student', 'session')
            else:
                logs = AttendanceLog.objects.select_related('student', 'session').order_by('-last_seen')[:100]
        else:
            if hasattr(request.user, 'staffprofile'):
                staff_profile = request.user.staffprofile
                dept = staff_profile.department
                
                if attendance_ids and len(attendance_ids) > 0:
                    logs = AttendanceLog.objects.filter(
                        id__in=attendance_ids,
                        student__department=dept
                    ).select_related('student', 'session')
                else:
                    logs = AttendanceLog.objects.filter(
                        student__department=dept
                    ).select_related('student', 'session').order_by('-last_seen')[:100]
            else:
                logs = AttendanceLog.objects.none()
        
        export_data = []
        for log in logs:
            try:
                duration_str = "N/A"
                if log.first_seen and log.last_seen:
                    duration = (log.last_seen - log.first_seen).total_seconds() / 60
                    duration_str = f"{duration:.1f} mins"
                
                export_data.append({
                    "Student Name": log.student.full_name,
                    "Roll Number": log.student.roll_number,
                    "Department": getattr(log.student, 'department', 'N/A'),
                    "Semester": getattr(log.student, 'semester', 'N/A'),
                    "Year": getattr(log.student, 'year', 'N/A'),
                    "Subject": log.session.subject_name if log.session else "Unknown",
                    "Session Semester": log.session.semester if log.session else "N/A",
                    "Status": log.get_status_display(),
                    "Date": log.session.date.strftime("%Y-%m-%d") if log.session else "",
                    "Time": log.first_seen.strftime("%I:%M:%S %p") if log.first_seen else "",
                    "Duration": duration_str,
                    "Is Validated": "Yes" if (hasattr(log, 'is_validated') and log.is_validated) else "No",
                    "Validation Error": log.validation_error if hasattr(log, 'validation_error') and log.validation_error else "N/A",
                })
            except Exception as e:
                print(f"Error processing log {log.id}: {e}")
                continue
        
        return JsonResponse({
            "success": True,
            "data": export_data,
            "count": len(export_data)
        })
        
    except Exception as e:
        import traceback
        print(f"Export error: {traceback.format_exc()}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
def api_filter_attendance(request):
    """API endpoint for filtering attendance logs"""
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')
    semester_filter = request.GET.get('semester', '')
    
    logs = AttendanceLog.objects.select_related('student', 'session')
    
    if search:
        logs = logs.filter(
            Q(student__full_name__icontains=search) |
            Q(student__roll_number__icontains=search)
        )
    
    if status_filter:
        logs = logs.filter(status=status_filter)
    
    if date_filter:
        logs = logs.filter(session__date=date_filter)
    
    if semester_filter:
        logs = logs.filter(session__semester=semester_filter)
    
    # Permission filter
    if not request.user.is_superuser and hasattr(request.user, "staffprofile"):
        dept = request.user.staffprofile.department
        logs = logs.filter(student__department=dept)
    
    logs = logs.order_by('-last_seen')[:50]
    
    attendance_data = []
    for log in logs:
        attendance_data.append({
            "id": log.id,
            "student_name": log.student.full_name,
            "student_roll": log.student.roll_number,
            "student_dept": log.student.department,
            "student_semester": log.student.semester,
            "subject": log.session.subject_name if log.session else "Unknown",
            "session_semester": log.session.semester if log.session else "N/A",
            "status": log.status,
            "status_display": log.get_status_display(),
            "time": log.first_seen.strftime("%I:%M:%S %p") if log.first_seen else "N/A",
            "date": log.session.date.strftime("%Y-%m-%d") if log.session else "",
            "has_face": log.student.face_encoding is not None,
            "is_validated": log.is_validated if hasattr(log, 'is_validated') else True,
        })
    
    return JsonResponse({
        "success": True,
        "attendance": attendance_data,
        "count": len(attendance_data)
    })

    
def get_department_from_user(user):
    """Get department from user's staff profile"""
    if user.is_superuser:
        return None
    if hasattr(user, 'staffprofile'):
        return user.staffprofile.department
    return None
    
# ========== NOTIFICATION API VIEWS ==========

@login_required
def api_get_notifications(request):
    """API endpoint to get user notifications"""
    try:
        from accounts.models import Notification
    except ImportError:
        return JsonResponse({
            "success": True,
            "unread_count": 0,
            "notifications": []
        })
    
    limit = int(request.GET.get('limit', 20))
    
    # Get notifications for current user (including system notifications)
    notifications = Notification.get_user_notifications(request.user, limit=limit)
    
    # Get unread count
    unread_count = Notification.get_unread_count(request.user)
    
    notification_list = []
    for notif in notifications:
        notification_list.append({
            "id": notif.id,
            "type": notif.notification_type,
            "title": notif.title,
            "message": notif.message,
            "is_read": notif.is_read,
            "time_ago": notif.time_ago(),
            "created_at": notif.created_at.isoformat(),
            "link": notif.link,
            "metadata": notif.metadata
        })
    
    return JsonResponse({
        "success": True,
        "unread_count": unread_count,
        "notifications": notification_list
    })


@login_required
def api_mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    try:
        from accounts.models import Notification
        notification = Notification.objects.get(id=notification_id)
        
        # Check if user has permission (notification belongs to user or is system notification)
        if notification.user and notification.user != request.user:
            return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
        
        notification.mark_as_read()
        return JsonResponse({"success": True, "message": "Notification marked as read"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def api_mark_all_notifications_read(request):
    """Mark all notifications as read for current user"""
    try:
        from accounts.models import Notification
        Notification.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            is_read=False
        ).update(is_read=True)
        return JsonResponse({"success": True, "message": "All notifications marked as read"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


from django.contrib import messages

@login_required
def api_delete_notification(request, notification_id):
    """Delete a notification"""
    try:
        from accounts.models import Notification
        notification = Notification.objects.get(id=notification_id)
        
        # Check permission
        if notification.user and notification.user != request.user:
            return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
        
        notification.delete()
        
        # Add success message
        messages.success(request, f'Notification "{notification.title}" deleted successfully!')
        
        return JsonResponse({
            "success": True, 
            "message": "Notification deleted",
            "toast": {
                "type": "success",
                "text": f'Notification "{notification.title}" deleted successfully!'
            }
        })
    except Exception as e:
        messages.error(request, f'Error deleting notification: {str(e)}')
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def api_create_notification(request):
    """Create a new notification (for testing/events)"""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        import json
        from accounts.models import Notification
        
        data = json.loads(request.body)
        title = data.get('title', '')
        message = data.get('message', '')
        notification_type = data.get('notification_type', 'system')
        link = data.get('link', '')
        user_id = data.get('user_id', None)
        is_system = data.get('is_system', False)
        
        if not title or not message:
            return JsonResponse({"success": False, "error": "Title and message required"}, status=400)
        
        if is_system or not user_id:
            # System notification
            notification = Notification.send_system_notification(title, message, notification_type, link)
        else:
            # User-specific notification
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            notification = Notification.send_notification(user, title, message, notification_type, link)
        
        return JsonResponse({
            "success": True,
            "message": "Notification created",
            "notification_id": notification.id
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# Helper function to create notifications from other parts of the system
def create_notification(user, title, message, notification_type='system', link=None, metadata=None):
    """Helper function to create a notification"""
    try:
        from accounts.models import Notification
        return Notification.send_notification(user, title, message, notification_type, link, metadata)
    except Exception as e:
        print(f"Error creating notification: {e}")
        return None


def create_system_notification(title, message, notification_type='system', link=None, metadata=None):
    """Create a system-wide notification"""
    try:
        from accounts.models import Notification
        return Notification.send_system_notification(title, message, notification_type, link, metadata)
    except Exception as e:
        print(f"Error creating system notification: {e}")
        return None
    



# ========== VIEW ALL NOTIFICATIONS PAGE ==========

@login_required
def notifications_list(request):
    """Render the notifications list page"""
    return render(request, "dashboard/notifications_list.html", {
        "page_title": "All Notifications"
    })


@login_required
def api_get_all_notifications(request):
    """API endpoint to get all notifications with pagination"""
    try:
        from accounts.models import Notification
        from django.core.paginator import Paginator
    except ImportError:
        return JsonResponse({
            "success": True,
            "notifications": [],
            "total": 0,
            "page": 1,
            "total_pages": 0,
            "unread_count": 0
        })
    
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    # Get notifications for user (including system)
    notifications = Notification.get_user_notifications(request.user, limit=1000, include_system=True)
    
    # Paginate
    paginator = Paginator(notifications, per_page)
    page_obj = paginator.get_page(page)
    
    notification_list = []
    for notif in page_obj:
        notification_list.append({
            "id": notif.id,
            "type": notif.notification_type,
            "title": notif.title,
            "message": notif.message,
            "is_read": notif.is_read,
            "time_ago": notif.time_ago(),
            "created_at": notif.created_at.isoformat(),
            "link": notif.link,
            "metadata": notif.metadata
        })
    
    return JsonResponse({
        "success": True,
        "notifications": notification_list,
        "total": paginator.count,
        "page": page,
        "total_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
        "unread_count": Notification.get_unread_count(request.user)
    })


@login_required
def export_notifications(request):
    """Export notifications to CSV"""
    import csv
    from django.http import HttpResponse
    from accounts.models import Notification
    
    # Get filter
    filter_type = request.GET.get('filter', 'all')
    
    # Get notifications for user (including system)
    notifications = Notification.get_user_notifications(request.user, limit=1000, include_system=True)
    
    if filter_type == 'unread':
        notifications = [n for n in notifications if not n.is_read]
    elif filter_type == 'read':
        notifications = [n for n in notifications if n.is_read]
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="notifications_export_{timezone.now().date()}.csv"'
    response['X-Content-Type-Options'] = 'nosniff'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Title', 'Message', 'Type', 'Status', 
        'Created At', 'Link'
    ])
    
    for notif in notifications:
        writer.writerow([
            notif.id,
            notif.title,
            notif.message,
            notif.notification_type,
            'Read' if notif.is_read else 'Unread',
            notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            notif.link or ''
        ])
    
    return response

@login_required
def api_test_real_time_notification(request):
    """Create a real-time test notification"""
    try:
        from accounts.models import Notification
        import random
    except ImportError:
        return JsonResponse({"success": False, "error": "Notification model not found"}, status=500)
    
    test_messages = [
        {"title": "🎓 Student Registered", "message": "New student John Doe has been registered successfully.", "type": "student"},
        {"title": "✅ Attendance Marked", "message": "45 students marked present for Computer Science lecture.", "type": "attendance"},
        {"title": "⚠️ Proxy Alert", "message": "Suspicious attendance pattern detected for roll number 2024-CS-001.", "type": "proxy"},
        {"title": "🔔 Session Started", "message": "New attendance session 'Software Engineering' has been started.", "type": "session"},
        {"title": "📊 Weekly Report", "message": "Weekly attendance report is now available for download.", "type": "system"},
        {"title": "🎯 Recognition Update", "message": "Face recognition accuracy improved to 99.2%", "type": "success"},
        {"title": "👥 Bulk Registration", "message": "25 new students have been registered via bulk upload.", "type": "student"},
        {"title": "⚙️ System Update", "message": "AFRAS system has been updated to version 2.5.0", "type": "system"},
    ]
    
    test_data = random.choice(test_messages)
    
    notification = Notification.send_notification(
        user=request.user,
        title=test_data["title"],
        message=test_data["message"],
        notification_type=test_data["type"],
        link="/dashboard/"
    )
    
    return JsonResponse({
        "success": True,
        "message": "Real-time notification created",
        "notification": {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "type": notification.notification_type,
            "time_ago": notification.time_ago()
        }
    })


@login_required
def api_simulate_bulk_notifications(request):
    """Create multiple test notifications at once"""
    try:
        from accounts.models import Notification
        import random
    except ImportError:
        return JsonResponse({"success": False, "error": "Notification model not found"}, status=500)
    
    count = int(request.GET.get('count', 5))
    count = min(count, 20)  # Max 20 at once
    
    titles = [
        "📚 Lecture Started", "✓ Attendance Recorded", "⚠️ Security Alert", 
        "👤 New Registration", "📈 Performance Update", "🔧 System Maintenance",
        "🎯 Recognition Success", "⏰ Session Reminder", "📊 Report Ready",
        "🔔 Reminder", "✅ Task Completed", "📝 Document Uploaded"
    ]
    
    messages_list = [
        "Computer Science lecture attendance is now active",
        "Student attendance has been successfully recorded",
        "Unusual activity detected in the system",
        "A new student has been enrolled in the system",
        "Face recognition speed has been optimized",
        "System update scheduled for tonight",
        "High accuracy face detection active",
        "Don't forget to start your attendance session",
        "Weekly attendance summary is ready",
        "Please review pending face registrations",
        "Backup completed successfully",
        "Database optimization performed"
    ]
    
    types = ['attendance', 'session', 'proxy', 'student', 'success', 'warning', 'system']
    
    created = []
    for i in range(count):
        notif = Notification.send_notification(
            user=request.user,
            title=random.choice(titles),
            message=f"{random.choice(messages_list)} (Test #{i+1})",
            notification_type=random.choice(types)
        )
        created.append(notif.id)
    
    return JsonResponse({
        "success": True,
        "message": f"Created {count} test notifications",
        "notification_ids": created,
        "count": count
    })
    
    
@login_required
def student_profile(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    
    # Permission check
    if not request.user.is_superuser:
        dept = get_department_from_user(request.user)
        if dept and student.department != dept:
            messages.error(request, "You don't have permission to view this student's profile.")
            return redirect('student-directory')
    
    # Get attendance statistics
    total_logs = AttendanceLog.objects.filter(student=student).count()
    present_logs = AttendanceLog.objects.filter(student=student, status='PRESENT').count()
    partial_logs = AttendanceLog.objects.filter(student=student, status='PARTIAL').count()
    absent_logs = AttendanceLog.objects.filter(student=student, status='ABSENT').count()
    
    # Get validation stats
    validated_logs = AttendanceLog.objects.filter(student=student, is_validated=True).count() if hasattr(AttendanceLog, 'is_validated') else total_logs
    validation_failed = total_logs - validated_logs
    
    # Get recent attendance
    recent_logs = AttendanceLog.objects.filter(
        student=student
    ).select_related('session').order_by('-last_seen')[:10]
    
    # Get semester-wise attendance
    semester_stats = {}
    for log in AttendanceLog.objects.filter(student=student).select_related('session'):
        sem = log.session.semester if log.session else 0
        if sem not in semester_stats:
            semester_stats[sem] = {'present': 0, 'absent': 0, 'total': 0}
        semester_stats[sem]['total'] += 1
        if log.status in ['PRESENT', 'PARTIAL']:
            semester_stats[sem]['present'] += 1
        else:
            semester_stats[sem]['absent'] += 1
    
    # Prepare face encoding data for JavaScript
    face_encoding_data = student.face_encoding
    if face_encoding_data is not None:
        # If it's a string, try to parse it as JSON
        if isinstance(face_encoding_data, str):
            try:
                import json
                face_encoding_data = json.loads(face_encoding_data)
            except:
                # If it's a Python list string, try to evaluate it
                try:
                    import ast
                    face_encoding_data = ast.literal_eval(face_encoding_data)
                except:
                    face_encoding_data = None
        # If it's a list, convert to JSON string for JavaScript
        if isinstance(face_encoding_data, list):
            import json
            face_encoding_data = json.dumps(face_encoding_data)
    
    context = {
        'student': student,
        'total_logs': total_logs,
        'present_logs': present_logs,
        'partial_logs': partial_logs,
        'absent_logs': absent_logs,
        'validated_logs': validated_logs,
        'validation_failed': validation_failed,
        'recent_logs': recent_logs,
        'semester_stats': semester_stats,
        'page_title': f'Student Profile: {student.full_name}',
        'face_encoding_json': face_encoding_data,  # Pass serialized data
    }
    return render(request, "dashboard/student_profile.html", context)


def staff_profile(request, staff_id):
    """Staff profile page"""
    staff = get_object_or_404(StaffProfile, id=staff_id)
    return render(request, "dashboard/staff_profile.html", {"staff": staff})