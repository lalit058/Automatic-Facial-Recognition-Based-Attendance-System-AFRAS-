import cv2
import json
import time
from django.utils import timezone
import face_recognition
import numpy as np
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from .models import AttendanceSession, AttendanceLog
from accounts.models import Student, StaffProfile
from datetime import timedelta
import pandas as pd
import PyPDF2
import re
from datetime import datetime

def session_stats_api(request):
    """API endpoint for session statistics"""
    try:
        total_sessions = AttendanceSession.objects.count()
        active_sessions = AttendanceSession.objects.filter(is_active=True).count()
        
        # Get today's sessions
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
    
# 1. Start Session View
def start_session(request):
    if request.method == "POST":
        subject = request.POST.get("subject")
        duration = request.POST.get("duration")
        
        # Validate input
        if not subject or not duration:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Subject and duration are required'})
            return render(request, "dashboard/start_session.html", {'error': 'Subject and duration are required'})
        
        try:
            # Get staff profile
            try:
                staff_profile = request.user.staffprofile
            except AttributeError:
                staff_profile = None
            
            # Create the session
            session = AttendanceSession.objects.create(
                subject_name=subject,
                expected_duration=int(duration),
                created_by=staff_profile,
            )
            
            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'redirect_url': f'/attendance/live/{session.id}/',
                    'session_id': session.id
                })
            
            # Regular form submission redirect
            return redirect('live_monitoring', session_id=session.id)
            
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)})
            return render(request, "dashboard/start_session.html", {'error': str(e)})
    
    return render(request, "dashboard/start_session.html")


@require_GET
def recent_sessions_api(request):
    """API endpoint to get recent attendance sessions"""
    try:
        sessions = AttendanceSession.objects.all().order_by('-start_time')[:10]

        sessions_data = []
        for session in sessions:
            # Calculate end time based on start_time and expected_duration
            start_time = session.start_time
            end_time = start_time + timedelta(minutes=session.expected_duration)
            
            # Format times in 12-hour format with AM/PM
            start_formatted = start_time.strftime("%I:%M %p").lstrip("0")
            end_formatted = end_time.strftime("%I:%M %p").lstrip("0")
            
            sessions_data.append({
                "id": session.id,
                "subject": session.subject_name,
                "date": session.date.strftime("%Y-%m-%d"),
                "start_time": start_formatted,
                "end_time": end_formatted,
                "time_range": f"{start_formatted} - {end_formatted}",
                "is_active": session.is_active,
            })

        return JsonResponse({"sessions": sessions_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# AI Document Extraction View
@csrf_exempt
def extract_routine_ai(request):
    """Extract schedule from uploaded PDF/Excel file and create sessions"""
    if request.method != "POST":
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        file = request.FILES.get('routine_file')
        if not file:
            return JsonResponse({'success': False, 'message': 'No file uploaded'})
        
        # Get file extension
        file_extension = file.name.split('.')[-1].lower()
        
        extracted_data = []
        
        # Process based on file type
        if file_extension == 'pdf':
            extracted_data = extract_from_pdf(file)
        elif file_extension in ['xlsx', 'xls', 'csv']:
            extracted_data = extract_from_excel(file)
        else:
            return JsonResponse({'success': False, 'message': 'Unsupported file format'})
        
        # Create sessions from extracted data
        created_sessions = []
        for item in extracted_data:
            try:
                # Try to get staff profile
                try:
                    staff_profile = request.user.staffprofile
                except:
                    staff_profile = None
                
                # Create session
                session = AttendanceSession.objects.create(
                    subject_name=item['subject'],
                    expected_duration=item['duration'],
                    created_by=staff_profile,
                    is_active=False  # Sessions are created as inactive by default
                )
                
                # Update date and time if provided
                if item.get('date'):
                    session.date = item['date']
                if item.get('start_time'):
                    session.start_time = item['start_time']
                session.save()
                
                created_sessions.append({
                    'id': session.id,
                    'subject': session.subject_name,
                    'date': session.date.strftime('%Y-%m-%d'),
                    'time': session.start_time.strftime('%H:%M')
                })
            except Exception as e:
                print(f"Error creating session: {e}")
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully extracted {len(created_sessions)} sessions',
            'classes_count': len(created_sessions),
            'sessions': created_sessions
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

def extract_from_pdf(file):
    """Extract schedule data from PDF file"""
    extracted = []
    
    try:
        # Read PDF
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        # Simple pattern matching for schedule entries
        # This is a basic example - you'll need to adjust based on your PDF format
        lines = text.split('\n')
        
        for line in lines:
            # Look for patterns like "Subject: Computer Graphics, Time: 10:00, Duration: 60"
            subject_match = re.search(r'Subject:?\s*([A-Za-z\s]+)', line, re.IGNORECASE)
            time_match = re.search(r'Time:?\s*(\d{1,2}:\d{2}\s*[AP]M?)', line, re.IGNORECASE)
            duration_match = re.search(r'Duration:?\s*(\d+)', line, re.IGNORECASE)
            
            if subject_match and time_match:
                subject = subject_match.group(1).strip()
                time_str = time_match.group(1).strip()
                duration = int(duration_match.group(1)) if duration_match else 60
                
                # Parse time
                try:
                    # Convert to datetime object
                    start_time = datetime.strptime(time_str, "%I:%M %p")
                    # Replace with current date (you might want to extract date from PDF)
                    start_time = start_time.replace(
                        year=timezone.now().year,
                        month=timezone.now().month,
                        day=timezone.now().day
                    )
                    
                    extracted.append({
                        'subject': subject,
                        'start_time': start_time,
                        'date': start_time.date(),
                        'duration': duration
                    })
                except:
                    continue
        
    except Exception as e:
        print(f"PDF extraction error: {e}")
    
    return extracted

def extract_from_excel(file):
    """Extract schedule data from Excel/CSV file"""
    extracted = []
    
    try:
        # Read the file
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Look for common column names
        subject_col = None
        time_col = None
        duration_col = None
        date_col = None
        
        # Try to identify columns
        for col in df.columns:
            col_lower = str(col).lower()
            if 'subject' in col_lower or 'course' in col_lower or 'module' in col_lower:
                subject_col = col
            elif 'time' in col_lower or 'start' in col_lower:
                time_col = col
            elif 'duration' in col_lower or 'length' in col_lower:
                duration_col = col
            elif 'date' in col_lower or 'day' in col_lower:
                date_col = col
        
        # If we couldn't identify columns, use first few columns
        if not subject_col and len(df.columns) > 0:
            subject_col = df.columns[0]
        if not time_col and len(df.columns) > 1:
            time_col = df.columns[1]
        
        # Extract data from each row
        for index, row in df.iterrows():
            if index >= 20:  # Limit to 20 rows
                break
                
            subject = str(row[subject_col]) if subject_col and pd.notna(row[subject_col]) else None
            time_str = str(row[time_col]) if time_col and pd.notna(row[time_col]) else None
            
            if not subject or not time_str:
                continue
            
            # Get duration
            duration = 60  # default
            if duration_col and pd.notna(row[duration_col]):
                try:
                    duration = int(float(row[duration_col]))
                except:
                    pass
            
            # Parse time
            try:
                # Try different time formats
                start_time = None
                
                # Try 12-hour format with AM/PM
                try:
                    start_time = datetime.strptime(time_str, "%I:%M %p")
                except:
                    pass
                
                # Try 24-hour format
                if not start_time:
                    try:
                        start_time = datetime.strptime(time_str, "%H:%M")
                    except:
                        pass
                
                # Try just hour
                if not start_time:
                    try:
                        hour = int(time_str)
                        start_time = datetime.now().replace(hour=hour, minute=0)
                    except:
                        pass
                
                if start_time:
                    # Get date
                    session_date = None
                    if date_col and pd.notna(row[date_col]):
                        try:
                            session_date = pd.to_datetime(row[date_col]).date()
                        except:
                            session_date = timezone.now().date()
                    else:
                        session_date = timezone.now().date()
                    
                    # Update start_time with correct date
                    start_time = start_time.replace(
                        year=session_date.year,
                        month=session_date.month,
                        day=session_date.day
                    )
                    
                    extracted.append({
                        'subject': subject,
                        'start_time': start_time,
                        'date': session_date,
                        'duration': duration
                    })
            except:
                continue
        
    except Exception as e:
        print(f"Excel extraction error: {e}")
    
    return extracted

# 2. AJAX API to update status manually
@csrf_exempt
def update_attendance_manual(request):
    if request.method == "POST":
        log_id = request.POST.get("log_id")
        new_status = request.POST.get("status")
        log = get_object_or_404(AttendanceLog, id=log_id)
        log.status = new_status
        log.is_manual = True
        log.save()
        return JsonResponse({"status": "updated"})


# 3. API to fetch logs for the frontend table
def get_logs(request, session_id):
    print("\n" + "="*50)
    print(f"🔍 GET_LOGS called at {datetime.now()}")
    
    try:
        session = AttendanceSession.objects.get(id=session_id)
        logs = AttendanceLog.objects.filter(session=session).select_related('student')
        
        print(f"📊 Found {logs.count()} logs")
        
        data = []
        for log in logs:
            # Calculate retention percentage
            if log.first_seen and session.expected_duration:
                duration = (log.last_seen - log.first_seen).total_seconds() / 60
                retention = min(100, (duration / session.expected_duration) * 100)
            else:
                retention = 0
            
            log_entry = {
                'id': log.id,
                'name': log.student.full_name if log.student else 'Unknown',
                'status': log.status,
                'retention': int(retention),  # Use calculated retention
                'confidence': int(log.confidence) if log.confidence else 0,
                'time': log.first_seen.strftime('%H:%M:%S') if log.first_seen else None,
                'last_seen': log.last_seen.strftime('%H:%M:%S') if log.last_seen else None,
            }
            print(f"  - {log_entry['name']}: {log_entry['time']}")
            data.append(log_entry)
        
        return JsonResponse({'logs': data})
        
    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# 4. Video Feed Wrapper
def video_feed(request, session_id):
    return StreamingHttpResponse(
        gen_frames(session_id), content_type="multipart/x-mixed-replace; boundary=frame"
    )

def session_summary(request, session_id):
    """Show session summary after ending"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    logs = AttendanceLog.objects.filter(session=session).select_related('student')
    
    # Calculate statistics
    total_students = logs.count()
    present_count = logs.filter(status='PRESENT').count()
    absent_count = logs.filter(status='ABSENT').count()
    leave_count = logs.filter(status='LEAVE').count()
    
    # Calculate average retention
    total_retention = 0
    for log in logs:
        if log.first_seen and session.expected_duration:
            duration = (log.last_seen - log.first_seen).total_seconds() / 60
            retention = min(100, (duration / session.expected_duration) * 100)
            total_retention += retention
    
    avg_retention = total_retention / total_students if total_students > 0 else 0
    
    context = {
        'session': session,
        'logs': logs,
        'total_students': total_students,
        'present_count': present_count,
        'absent_count': absent_count,
        'leave_count': leave_count,
        'avg_retention': round(avg_retention, 1),
    }
    
    return render(request, 'dashboard/session_summary.html', context)

# Video Processing (The Generator)
# Video Processing (The Generator) - WITH CONSTANT FACE FRAMES
# Video Processing (The Generator) - FIXED FOR IMMEDIATE RECOGNITION
def gen_frames(session_id):
    import time
    from collections import defaultdict
    from django.db import transaction
    
    # Initialize camera with optimizations
    camera = cv2.VideoCapture(0)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 15)
    
    session = AttendanceSession.objects.get(id=session_id)
    print(f"\n🎥 Starting video feed for session: {session.subject_name} (ID: {session_id})")

    # Pre-fetch students
    students = Student.objects.exclude(face_encoding__isnull=True)
    print(f"👥 Students with face encodings: {students.count()}")
    
    known_encodings = [np.array(s.face_encoding) for s in students]
    student_ids = [s.id for s in students]
    student_names = [s.full_name for s in students]
    
    # Create a dictionary for faster student lookup
    student_dict = {s.id: s for s in students}

    # TRACKING STATE
    tracked_faces = {}
    next_face_id = 0
    face_tracking_threshold = 2.0
    
    # Track which students have been logged to avoid duplicate DB hits
    logged_students = set()  # Student IDs that have been logged in this session
    last_seen_time = {}  # Student ID -> last seen timestamp
    
    prev_frame_time = 0
    frame_count = 0
    last_processed_time = time.time()
    
    # Face position smoothing
    face_positions = defaultdict(lambda: {'bbox': None, 'smoothed': None})

    while True:
        try:
            session.refresh_from_db()
            if not session.is_active:
                break

            success, frame = camera.read()
            if not success:
                print("⚠️ Failed to grab frame")
                time.sleep(0.1)
                continue

            frame_count += 1
            current_time = time.time()
            
            # Calculate FPS
            new_frame_time = current_time
            fps = 1 / (new_frame_time - prev_frame_time) if prev_frame_time > 0 else 0
            prev_frame_time = new_frame_time

            # Clean up old tracked faces
            expired_faces = []
            for face_id, face_data in tracked_faces.items():
                if current_time - face_data['last_seen'] > face_tracking_threshold:
                    expired_faces.append(face_id)
            
            for face_id in expired_faces:
                del tracked_faces[face_id]
                if face_id in face_positions:
                    del face_positions[face_id]

            # Process face recognition every frame for immediate response
            should_process = True  # Process every frame for immediate recognition
            
            current_faces_in_frame = []
            
            if should_process:
                last_processed_time = current_time
                
                # Resize frame for faster processing
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

                # Face detection
                face_locations = face_recognition.face_locations(rgb_small_frame)
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                # Process each detected face
                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    # Scale coordinates back to original size
                    orig_top, orig_right, orig_bottom, orig_left = top*4, right*4, bottom*4, left*4
                    
                    name = "Unknown"
                    confidence = 0
                    student_id = None
                    
                    if len(known_encodings) > 0:
                        # Compare faces
                        matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
                        
                        if True in matches:
                            # Get all matching indices
                            match_indices = [i for i, match in enumerate(matches) if match]
                            
                            if match_indices:
                                # Calculate distances for matches
                                face_distances = face_recognition.face_distance(known_encodings, face_encoding)
                                
                                # Find best match with lowest distance
                                best_idx = match_indices[0]
                                best_distance = face_distances[best_idx]
                                
                                for idx in match_indices[1:]:
                                    if face_distances[idx] < best_distance:
                                        best_distance = face_distances[idx]
                                        best_idx = idx
                                
                                name = student_names[best_idx]
                                student_id = student_ids[best_idx]
                                confidence = max(0, (1 - best_distance) * 100)
                                
                                # IMMEDIATE DATABASE UPDATE - REMOVED THE 5 SECOND DELAY
                                try:
                                    # Check if this student needs to be logged (first time seeing OR significant confidence increase)
                                    should_update = False
                                    
                                    if student_id not in logged_students:
                                        should_update = True
                                        logged_students.add(student_id)
                                    elif student_id in last_seen_time:
                                        # Update if last seen was more than 10 seconds ago (refresh)
                                        if current_time - last_seen_time[student_id] > 10:
                                            should_update = True
                                    
                                    if should_update:
                                        # Use transaction to ensure data integrity
                                        with transaction.atomic():
                                            student_obj = student_dict[student_id]
                                            
                                            # Update or create log
                                            log, created = AttendanceLog.objects.get_or_create(
                                                session=session,
                                                student=student_obj,
                                                defaults={
                                                    'status': 'PRESENT',
                                                    'confidence': confidence,
                                                    'first_seen': timezone.now(),
                                                    'last_seen': timezone.now()
                                                }
                                            )
                                            
                                            if not created:
                                                # Update existing log
                                                log.last_seen = timezone.now()
                                                if confidence > (log.confidence or 0):
                                                    log.confidence = confidence
                                                log.save()
                                            
                                            last_seen_time[student_id] = current_time
                                            print(f"✅ LOGGED: {name} ({confidence:.1f}%) - {timezone.now().strftime('%H:%M:%S')}")
                                            
                                except Exception as e:
                                    print(f"⚠️ DB error: {e}")
                    
                    # Check if this face matches any existing tracked face
                    matched_face_id = None
                    for face_id, face_data in tracked_faces.items():
                        old_bbox = face_data['bbox']
                        old_center = ((old_bbox[1] + old_bbox[3])//2, (old_bbox[0] + old_bbox[2])//2)
                        new_center = ((orig_left + orig_right)//2, (orig_top + orig_bottom)//2)
                        
                        distance = ((old_center[0] - new_center[0])**2 + (old_center[1] - new_center[1])**2)**0.5
                        
                        if distance < 100:
                            matched_face_id = face_id
                            break
                    
                    if matched_face_id:
                        # Update existing tracked face
                        tracked_faces[matched_face_id]['bbox'] = (orig_top, orig_right, orig_bottom, orig_left)
                        tracked_faces[matched_face_id]['name'] = name
                        tracked_faces[matched_face_id]['confidence'] = confidence
                        tracked_faces[matched_face_id]['student_id'] = student_id
                        tracked_faces[matched_face_id]['last_seen'] = current_time
                        current_faces_in_frame.append(matched_face_id)
                    else:
                        # New face - add to tracking
                        new_face_id = next_face_id
                        next_face_id += 1
                        tracked_faces[new_face_id] = {
                            'bbox': (orig_top, orig_right, orig_bottom, orig_left),
                            'name': name,
                            'confidence': confidence,
                            'student_id': student_id,
                            'last_seen': current_time
                        }
                        current_faces_in_frame.append(new_face_id)
            
            # DRAW ALL TRACKED FACES
            for face_id, face_data in tracked_faces.items():
                top, right, bottom, left = face_data['bbox']
                name = face_data['name']
                confidence = face_data['confidence']
                
                # Smooth bounding box position
                if face_id not in face_positions:
                    face_positions[face_id]['bbox'] = (top, right, bottom, left)
                    face_positions[face_id]['smoothed'] = (top, right, bottom, left)
                else:
                    old = face_positions[face_id]['smoothed']
                    alpha = 0.3
                    smoothed = (
                        int(old[0] * (1-alpha) + top * alpha),
                        int(old[1] * (1-alpha) + right * alpha),
                        int(old[2] * (1-alpha) + bottom * alpha),
                        int(old[3] * (1-alpha) + left * alpha)
                    )
                    face_positions[face_id]['smoothed'] = smoothed
                    top, right, bottom, left = smoothed
                
                # Determine color based on recognition status
                if name != "Unknown":
                    color = (0, 255, 0)  # Green for recognized
                else:
                    color = (0, 165, 255)  # Orange for unknown
                
                # Draw bounding box
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                
                # Draw label with background
                label = f"{name} ({confidence:.0f}%)" if confidence > 0 else name
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                
                cv2.rectangle(frame, 
                            (left, top - label_size[1] - 10), 
                            (left + label_size[0], top), 
                            color, -1)
                
                cv2.putText(frame, label, (left, top-5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

            # Add FPS counter and face count
            cv2.putText(frame, f"FPS: {int(fps)} | Faces: {len(tracked_faces)} | Logged: {len(logged_students)}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Encode and yield frame
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue
                
            frame_bytes = buffer.tobytes()
            
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
                   
        except Exception as e:
            print(f"⚠️ Error in video feed: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(0.1)
            continue

    # Cleanup
    camera.release()
    print("🎥 Video feed ended")


# View to stop session
def stop_session(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id)
    session.is_active = False
    session.end_time = timezone.now()
    session.save()
    return redirect("dashboard_home")


def attendance_session_view(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id)
    return render(
        request,
        "dashboard/attendance_session.html",
        {"session": session, "active_session": session},
    )