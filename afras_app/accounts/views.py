import face_recognition
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


def register_student(request):
    if request.method == "POST":
        # Data Extraction
        username = request.POST.get("roll_number")
        full_name = request.POST.get("name")
        phone_number = request.POST.get("phone_number")
        email = request.POST.get("email")
        department = request.POST.get("department")
        year=request.POST.get("year")
        semester = request.POST.get("semester")
        section = request.POST.get("section")
        # password = request.POST.get("password")
        address = request.POST.get("address")
        photo = request.FILES.get("photo")
        id_proof = request.FILES.get("id_proof")

        # Verification: Roll Number exists?
        if User.objects.filter(username=username).exists():
            messages.error(request, "This Roll Number is already registered.")
            return render(request, "accounts/register.html")

        # Check if email already exists (if provided)
        if email and User.objects.filter(email=email).exists():
            messages.error(request, f"Email {email} already exists!")
            return render(request, "accounts/register.html")

        # Extract Face Encoding
        face_value = None
        if photo:
            try:
                # Process image and convert to array
                image_array = get_processed_image(photo)

                # Try multiple detection methods
                face_locations = []

                # Method 1: Try with HOG model (faster)
                face_locations = face_recognition.face_locations(
                    image_array, number_of_times_to_upsample=2, model="hog"
                )

                # Method 2: If no face found, try CNN model (more accurate but slower)
                if not face_locations:
                    print("Trying CNN model...")
                    face_locations = face_recognition.face_locations(
                        image_array, number_of_times_to_upsample=1, model="cnn"
                    )

                encodings = face_recognition.face_encodings(image_array, face_locations)

                if encodings:
                    face_value = encodings[0].tolist()
                else:
                    # Save the problematic image for debugging
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_path = f"debug_face_{timestamp}.jpg"
                    Image.fromarray(image_array).save(debug_path)
                    print(f"Failed image saved to: {debug_path}")
                    messages.error(
                        request,
                        "No face detected. Please ensure your face is well-lit and clearly visible.",
                    )
                    return render(request, "accounts/register.html")
            except Exception as e:
                messages.error(request, f"Face processing error: {e}")
                return render(request, "accounts/register.html")
        else:
            messages.error(request, "A profile photo is required for registration.")
            return render(request, "accounts/register.html")

        # Save User and Profile
        try:
            # Create user
            user = User.objects.create_user(username=username)
            user.is_student = True
            if email:
                user.email = email
            user.save()

            print(f"User created: {user.username}")  # Debug print

            # Create student profile
            student = Student.objects.create(
                user=user,
                full_name=full_name,
                roll_number=username,
                phone_number=phone_number,
                email=email,
                department=department,
                year=year,
                semester=semester if semester else 1,
                section=section,
                address=address,
                photo=photo,
                id_proof=id_proof,
                face_encoding=face_value,
            )

            # Add System Log for Student Registration
            SystemLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action="Student Registered",
                details=f"Student {full_name} (Roll: {username}) successfully enrolled.",
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

