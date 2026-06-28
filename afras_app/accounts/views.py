import face_recognition
import json
import base64
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from .models import Student, StaffProfile, SystemLog
from django.contrib import messages
from PIL import Image, ImageOps
import numpy as np
from django.contrib import messages
from .models import SystemConfiguration
import io
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile

User = get_user_model()


def get_processed_image(photo):
    """
    Handles rotation, ensures RGB format, and returns a numpy array.
    """
    img = Image.open(photo)
    # Corrects orientation based on EXIF data automatically
    img = ImageOps.exif_transpose(img)
    # Convert to RGB (removes alpha channel from PNGs or CMYK issues)
    img = img.convert("RGB")
    return np.array(img)


# ============================================
# FACE PROCESSING API ENDPOINT (For Auto Capture)
# ============================================

@csrf_exempt
@require_POST
def process_face_api(request):
    """
    API endpoint for processing auto-captured face from camera
    Returns face encoding and validates face presence
    """
    try:
        photo_data = request.POST.get('photo_data')
        
        if not photo_data:
            return JsonResponse({
                'success': False, 
                'error': 'No photo data received'
            })
        
        # Decode base64 image
        if 'base64,' in photo_data:
            photo_data = photo_data.split('base64,')[1]
        elif 'data:image' in photo_data:
            photo_data = photo_data.split(',')[1]
        
        # Convert base64 to image
        image_bytes = base64.b64decode(photo_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Fix orientation
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image_array = np.array(image)
        
        # Detect faces using face_recognition
        face_locations = face_recognition.face_locations(
            image_array, 
            number_of_times_to_upsample=2, 
            model="hog"  # Faster detection
        )
        
        # If no face found, try CNN model
        if not face_locations:
            print("Trying CNN model for auto-capture...")
            face_locations = face_recognition.face_locations(
                image_array, 
                number_of_times_to_upsample=1, 
                model="cnn"
            )
        
        if not face_locations:
            return JsonResponse({
                'success': False, 
                'error': 'No face detected. Please ensure your face is clearly visible and well-lit.'
            })
        
        # If multiple faces detected
        if len(face_locations) > 1:
            return JsonResponse({
                'success': False, 
                'error': f'Multiple faces ({len(face_locations)}) detected. Please ensure only one face is visible.'
            })
        
        # Get face encoding
        encodings = face_recognition.face_encodings(image_array, face_locations)
        
        if not encodings:
            return JsonResponse({
                'success': False, 
                'error': 'Could not encode face features. Please try again with better lighting.'
            })
        
        # Return success with encoding
        encoding_list = encodings[0].tolist()
        
        return JsonResponse({
            'success': True,
            'encoding': encoding_list,
            'face_count': len(face_locations),
            'message': 'Face captured successfully!'
        })
        
    except Exception as e:
        print(f"Face processing error: {e}")
        return JsonResponse({
            'success': False, 
            'error': f'Face processing failed: {str(e)}'
        })


# ============================================
# STUDENT REGISTRATION VIEW (Updated with Auto Capture)
# ============================================

def register_student(request):
    """
    Student registration with auto face capture (Face Lock style)
    """
    if request.method == "POST":
        # ========================================
        # 1. Extract Form Data
        # ========================================
        username = request.POST.get("roll_number")
        full_name = request.POST.get("name")
        phone_number = request.POST.get("phone_number")
        email = request.POST.get("email")
        department = request.POST.get("department")
        year = request.POST.get("year")
        semester = request.POST.get("semester")
        section = request.POST.get("section")
        address = request.POST.get("address")
        
        # ========================================
        # 2. Get Face Data from Hidden Inputs
        # ========================================
        face_encoding_json = request.POST.get("face_encoding")
        photo_data = request.POST.get("photo_data")  # Base64 image data
        
        # ========================================
        # 3. Validate Face Data
        # ========================================
        if not face_encoding_json:
            messages.error(request, "❌ Face capture required. Please look at the camera.")
            return render(request, "accounts/register.html")
        
        if not photo_data:
            messages.error(request, "❌ Photo data missing. Please try again.")
            return render(request, "accounts/register.html")
        
        # Parse face encoding
        try:
            face_value = json.loads(face_encoding_json)
            if not isinstance(face_value, list):
                raise ValueError("Invalid face encoding format")
        except (json.JSONDecodeError, ValueError) as e:
            messages.error(request, f"❌ Invalid face data: {str(e)}")
            return render(request, "accounts/register.html")

        # ========================================
        # 4. Verification: Roll Number exists?
        # ========================================
        if User.objects.filter(username=username).exists():
            messages.error(request, "This Roll Number is already registered.")
            return render(request, "accounts/register.html")

        # Check if email already exists (if provided)
        if email and User.objects.filter(email=email).exists():
            messages.error(request, f"Email {email} already exists!")
            return render(request, "accounts/register.html")

        # ========================================
        # 5. Save Captured Photo as File
        # ========================================
        photo = None
        try:
            # Decode base64 to image
            if 'base64,' in photo_data:
                photo_data_clean = photo_data.split('base64,')[1]
            elif 'data:image' in photo_data:
                photo_data_clean = photo_data.split(',')[1]
            else:
                photo_data_clean = photo_data
            
            # Convert to file
            image_bytes = base64.b64decode(photo_data_clean)
            photo = ContentFile(image_bytes, name=f"{username}_photo.jpg")
            
        except Exception as e:
            messages.error(request, f"❌ Failed to save photo: {str(e)}")
            return render(request, "accounts/register.html")

        # ========================================
        # 6. Save User and Profile
        # ========================================
        try:
            # Create user
            user = User.objects.create_user(username=username)
            user.is_student = True
            if email:
                user.email = email
            user.save()

            print(f"User created: {user.username}")  # Debug print

            # Create student profile with auto-captured face encoding
            student = Student.objects.create(
                user=user,
                full_name=full_name,
                roll_number=username,
                phone_number=phone_number,
                email=email,
                department=department,
                year=year,
                semester=int(semester) if semester else 1,
                section=section,
                address=address,
                photo=photo,  # Auto-captured photo
                face_encoding=face_value,  # Auto-captured encoding
            )

            # Add System Log for Student Registration
            SystemLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action="Student Registered (Auto Face Capture)",
                details=f"Student {full_name} (Roll: {username}) successfully enrolled using auto face capture.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            messages.success(request, f"Enrollment successful for {full_name}!")

            # Redirect to student directory or clear form
            return redirect("student-directory")  

        except Exception as e:
            # If user was created but student creation failed, delete the user
            if "user" in locals():
                user.delete()
                print(f"User deleted due to error: {e}")  # Debug print
            messages.error(request, f"Registration failed: {str(e)}")
            return render(request, "accounts/register.html")

    return render(request, "accounts/register.html")



def register_staff(request):
    INSTITUTIONAL_MASTER_KEY = "AFRAS-ROOT-2026"

    if request.method == "POST":
        staff_id = request.POST.get("staff_id")
        auth_key = request.POST.get("auth_key")
        password = request.POST.get("password")
        role = request.POST.get("role")
        email = request.POST.get("email")
        full_name = request.POST.get("name")
        phone = request.POST.get("phone")
        degree = request.POST.get("degree")
        designation = request.POST.get("designation")
        department = request.POST.get("department")
        address = request.POST.get("address")
        photo = request.FILES.get("photo")

        if auth_key != INSTITUTIONAL_MASTER_KEY:
            messages.error(request, "Invalid Institutional Auth Key.")
            return render(request, "accounts/register_staff.html")

        if not staff_id:
            messages.error(request, "Staff ID is required.")
            return render(request, "accounts/register_staff.html")

        if User.objects.filter(username=staff_id).exists():
            messages.error(request, "Staff ID already registered.")
            return render(request, "accounts/register_staff.html")

        if email and User.objects.filter(email=email).exists():
            messages.error(request, f"Email {email} already exists!")
            return render(request, "accounts/register_staff.html")

        if not photo:
            messages.error(request, "Profile photo is required.")
            return render(request, "accounts/register_staff.html")

        try:
            # Create user with staff_id as username
            user = User.objects.create_user(
                username=staff_id, email=email if email else "", password=password
            )

            # Set user permissions
            user.is_staff = True
            user.is_staff_member = True

            if role == "admin":
                user.is_superuser = True

            user.save()

            # Create staff profile - staff_id field is not needed as it's a property
            staff_profile = StaffProfile.objects.create(
                user=user,
                full_name=full_name,
                phone_number=phone,
                degree=degree,
                designation=designation,
                department=department,
                address=address,
                photo=photo,
            )

            # Add System Log for Staff Registration
            SystemLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action="Staff Registered",
                details=f"New {'Admin' if role == 'admin' else 'Staff'} {full_name} registered with ID {staff_id}.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            messages.success(
                request,
                f"{'Admin' if role == 'admin' else 'Staff'} {full_name} Registered successfully!",
            )
            return redirect("register-staff")

        except Exception as e:
            if "user" in locals():
                user.delete()
            messages.error(request, f"System Error: {e}")

    return render(request, "accounts/register_staff.html")


def login_user(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            messages.success(request, "Login successful!")

            # LOGGING: Successful Login
            SystemLog.objects.create(
                user=user,
                action="User Login",
                details=f"User {user.username} logged into the dashboard.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            # Redirect based on user type
            if user.is_student:
                return redirect("student_dashboard")
            elif user.is_staff_member or user.is_staff:
                return redirect("dashboard_home")
            else:
                return redirect("dashboard_home")
        else:
            # Log failed attempts
            SystemLog.objects.create(
                user=None,
                action="Failed Login Attempt",
                details=f"Failed login attempt for username: {username}",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html")


@login_required
def logout_user(request):
    # LOGGING: Logout
    SystemLog.objects.create(
        user=request.user,
        action="User Logout",
        details=f"User {request.user.username} logged out.",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    request.session.flush()  # This destroys the session and CSRF token

    # Logout the user
    logout(request)

    messages.success(request, "You have been logged out successfully.")
    return redirect("login")


# Optional: View to display staff list with staff_id
@login_required
def staff_list(request):
    staff_members = StaffProfile.objects.select_related("user").all()

    # The staff_id property will automatically show user.username
    context = {"staff_members": staff_members}
    return render(request, "accounts/staff_list.html", context)

