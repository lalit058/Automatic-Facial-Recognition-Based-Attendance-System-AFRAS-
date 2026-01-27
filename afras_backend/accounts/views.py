from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from .models import Student, StaffProfile
from django.contrib import messages

User = get_user_model()


def register_student(request):
    if request.method == "POST":
        # Academic & Personal Data
        username = request.POST.get("roll_number")  # Using Roll Number as Username
        full_name = request.POST.get("name")
        department = request.POST.get("department")
        semester = request.POST.get("semester")
        section = request.POST.get("section")
        password = request.POST.get("password")

        # Files
        photo = request.FILES.get("photo")
        id_proof = request.FILES.get("id_proof")

        if User.objects.filter(username=username).exists():
            messages.error(request, "This Roll Number is already registered.")
            return render(request, "accounts/register.html")

        try:
            # Create CustomUser
            user = User.objects.create_user(username=username, password=password)
            user.is_student = True  # Setting the flag from CustomUser model
            user.save()

            # Create Student Profile
            Student.objects.create(
                user=user,
                full_name=full_name,
                roll_number=username,
                department=department,
                semester=semester,
                section=section,
                photo=photo,
                id_proof=id_proof,
            )

            messages.success(request, "Enrollment successful!")
            return redirect("register")

        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, "accounts/register.html")


def register_staff(request):
    # This key should be kept in your .env or settings.py for security
    INSTITUTIONAL_MASTER_KEY = "AFRAS_ROOT_2026"

    if request.method == "POST":
        # Extract Data
        staff_id = request.POST.get("staff_id")
        auth_key = request.POST.get("auth_key")
        password = request.POST.get("password")
        role = request.POST.get("role")

        # 1. Verification of Auth Key
        if auth_key != INSTITUTIONAL_MASTER_KEY:
            messages.error(
                request, "Invalid Institutional Auth Key. Authorization denied."
            )
            return render(request, "accounts/register_staff.html")

        # 2. Check if user already exists
        if User.objects.filter(username=staff_id).exists():
            messages.error(request, "Staff ID already registered.")
            return render(request, "accounts/register_staff.html")

        try:
            # 3. Create the Base User
            user = User.objects.create_user(
                username=staff_id, email=request.POST.get("email"), password=password
            )

            # Set Django Admin permissions if role is admin
            if role == "admin":
                user.is_staff = True
                user.is_superuser = True
            else:
                user.is_staff = True  # Staff can access dashboard but not admin panel

            user.save()

            # 4. Create the Profile with Photo and Extra Fields
            StaffProfile.objects.create(
                user=user,
                full_name=request.POST.get("name"),
                phone_number=request.POST.get("phone"),
                degree=request.POST.get("degree"),
                designation=request.POST.get("designation"),
                department=request.POST.get("department"),
                photo=request.FILES.get("photo"),  # Handled via multipart/form-data
            )

            messages.success(
                request, f"Welcome {request.POST.get('name')}! Registration complete."
            )
            return redirect("login")

        except Exception as e:
            messages.error(request, f"System Error: {e}")

    return render(request, "accounts/register_staff.html")


def login_user(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("dashboard_home")
        else:
            messages.error(request, "Invalid Credentials")
    return render(request, "accounts/login.html")


@login_required
def staff_directory(request):
    # Fetch all staff profiles from the real backend database
    all_staff = StaffProfile.objects.all().select_related('user').order_by('full_name')
    
    context = {
        'all_staff': all_staff,
        'total_staff': all_staff.count(),
    }
    return render(request, 'dashboard/staff_directory.html', context)


@login_required
def logout_user(request):
    logout(request)
    return redirect("login")
