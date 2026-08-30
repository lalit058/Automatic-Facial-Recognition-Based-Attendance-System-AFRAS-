import face_recognition
import json
import base64
import smtplib
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from .models import Student, StaffProfile, SystemLog
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail, EmailMultiAlternatives
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from PIL import Image, ImageOps
import numpy as np
from django.contrib import messages
from .models import SystemConfiguration
import io
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from datetime import datetime
import logging

User = get_user_model()

logger = logging.getLogger(__name__)

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
        
        # ============================================================
        # FIX: Better face detection with false positive filtering
        # ============================================================
        
        # First try with HOG model
        face_locations = face_recognition.face_locations(
            image_array, 
            number_of_times_to_upsample=1,  # Reduced from 2 to avoid false positives
            model="hog"
        )
        
        # Filter out small faces (likely false positives)
        MIN_FACE_SIZE = 80  # Minimum pixels for a valid face
        filtered_locations = []
        for (top, right, bottom, left) in face_locations:
            width = right - left
            height = bottom - top
            if width >= MIN_FACE_SIZE and height >= MIN_FACE_SIZE:
                filtered_locations.append((top, right, bottom, left))
        
        face_locations = filtered_locations
        
        # If no face found with HOG, try CNN
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
        
        # ============================================================
        # FIX: If multiple faces, take the LARGEST one (likely the real face)
        # ============================================================
        if len(face_locations) > 1:
            # Find the largest face by area
            largest_area = 0
            largest_face = None
            for (top, right, bottom, left) in face_locations:
                area = (right - left) * (bottom - top)
                if area > largest_area:
                    largest_area = area
                    largest_face = (top, right, bottom, left)
            
            if largest_face:
                face_locations = [largest_face]
                print(f"✅ Selected largest face (area: {largest_area} pixels)")
            else:
                # If something went wrong, take the first one
                face_locations = [face_locations[0]]
                print("⚠️ Using first face as fallback")
        
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
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False, 
            'error': f'Face processing failed: {str(e)}'
        })


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


from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect
from django.contrib import messages

@csrf_protect
def login_user(request):
    if request.user.is_authenticated:
        if request.user.is_student:
            return redirect("student_dashboard")
        return redirect("dashboard_home")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, "accounts/login.html")
        
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Rotate session to prevent session fixation and clear stale cache state
            request.session.cycle_key()
            login(request, user)

            SystemLog.objects.create(
                user=user,
                action="User Login",
                details=f"User {user.username} logged into the dashboard.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            if user.is_student:
                return redirect("student_dashboard")
            elif user.is_staff_member or user.is_staff:
                return redirect("dashboard_home")
            else:
                return redirect("dashboard_home")
        else:
            SystemLog.objects.create(
                user=None,
                action="Failed Login Attempt",
                details=f"Failed login attempt for username: {username}",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            messages.error(request, "Invalid username or password.")
            return render(request, "accounts/login.html")

    return render(request, "accounts/login.html")


@login_required
def logout_user(request):
    SystemLog.objects.create(
        user=request.user,
        action="User Logout",
        details=f"User {request.user.username} logged out.",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    logout(request)
    request.session.flush()
    
    response = redirect("login")
    response.delete_cookie(settings.SESSION_COOKIE_NAME)

    messages.success(request, "You have been logged out successfully.")
    return response


# Optional: View to display staff list with staff_id
@login_required
def staff_list(request):
    staff_members = StaffProfile.objects.select_related("user").all()

    # The staff_id property will automatically show user.username
    context = {"staff_members": staff_members}
    return render(request, "accounts/staff_list.html", context)


def custom_password_reset(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        form = PasswordResetForm({'email': email})
        
        if form.is_valid():
            # Send HTML email with proper headers
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name='registration/password_reset_email.html',
                subject_template_name='registration/password_reset_subject.txt',
            )
            return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Invalid email'})



def password_reset_complete_custom(request):
    """
    Custom view for password reset complete
    """
    print(f"=== PASSWORD RESET COMPLETE CUSTOM ===")
    return render(request, 'home.html', {
        'password_reset_complete': True
    })


@csrf_exempt
def password_reset_request(request):
    """
    Handle password reset request via email
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            return JsonResponse({'success': False, 'error': 'Email is required'}, status=400)
        
        try:
            # Get users with this email (case-insensitive)
            users = User.objects.filter(email__iexact=email)
            
            print(f"🔍 Found {users.count()} user(s) with email: {email}")
            for user in users:
                print(f"   - Username: {user.username}, Email: {user.email}")
            
            if not users.exists():
                print("❌ No user found with this email")
                return JsonResponse({
                    'success': True, 
                    'message': 'If an account exists, a reset link has been sent.'
                })
            
            # Send reset link to each user
            for user in users:
                try:
                    token = default_token_generator.make_token(user)
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    
                    current_site = get_current_site(request)
                    domain = current_site.domain
                    protocol = 'https' if request.is_secure() else 'http'
                    
                    reset_link = f"{protocol}://{domain}{reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})}"
                    
                    print(f"🔗 Reset link: {reset_link}")
                    
                    subject = 'Password Reset Request - AFRAS System'
                    text_message = f"""
Hello {user.get_full_name() or user.username},

You requested a password reset for your AFRAS account.

Username: {user.username}

Click the link below to reset your password:
{reset_link}

This link will expire in 24 hours.

If you didn't request this, please ignore this email.

---
AFRAS System
"""
                    
                    print(f"📤 Sending email to: {email}")
                    
                    # Send email
                    send_mail(
                        subject=subject,
                        message=text_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    
                    print(f"✅ Email sent successfully to {email}")
                    
                except Exception as e:
                    print(f"❌ Error sending to {user.username}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # Return the actual error for debugging
                    return JsonResponse({
                        'success': False,
                        'error': f'Email error: {str(e)}'
                    }, status=500)
            
            return JsonResponse({
                'success': True,
                'message': 'Password reset link sent to your email.'
            })
            
        except Exception as e:
            print(f"❌ General error: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': f'Failed to process request: {str(e)}'
            }, status=500)
    
    return render(request, 'registration/password_reset_form.html')


def password_reset_confirm_view(request, uidb64, token):
    """
    Confirm password reset and allow user to set new password
    """
    # Force Logout
    if request.user.is_authenticated:
        logout(request)
        request.session.flush()
    
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            new_password1 = request.POST.get('new_password1')
            new_password2 = request.POST.get('new_password2')
            
            if new_password1 != new_password2:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'registration/password_reset_confirm.html', {'validlink': True})
            
            if len(new_password1) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
                return render(request, 'registration/password_reset_confirm.html', {'validlink': True})
            
            # Set the new password
            user.set_password(new_password1)
            user.save()
            
            # Clear the session to force re-login
            request.session.flush()
            
            # Log the password reset
            SystemLog.objects.create(
                user=user,
                action="Password Reset",
                details=f"User {user.username} successfully reset their password.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            
            messages.success(request, 'Password reset successfully! Please login with your new password.')
            return redirect('login')
        
        # Show the reset form - user is logged out
        return render(request, 'registration/password_reset_confirm.html', {'validlink': True})
    else:
        messages.error(request, 'This password reset link is invalid or has expired.')
        return render(request, 'registration/password_reset_confirm.html', {'validlink': False})


            
def password_reset_done_view(request):
    """Custom view for password reset done page"""
    return render(request, 'registration/password_reset_done.html')

