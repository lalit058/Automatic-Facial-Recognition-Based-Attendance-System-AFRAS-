from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from accounts.models import Student, StaffProfile
from attendance.models import Attendance
from django.utils import timezone
from django.core.exceptions import FieldError


# Helper function to check if user is staff
def is_staff_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
@user_passes_test(is_staff_user, login_url="login", redirect_field_name=None)
def home(request):
    total = Student.objects.count()
    today = timezone.now().date()
    present = Attendance.objects.filter(date=today).values("student").distinct().count()
    recent = Attendance.objects.select_related("student").order_by("-timestamp")[:5]

    context = {
        "total_students": total,
        "present_today": present,
        "recent_logs": recent,
        "total_staff": 0,  # Placeholder: Add Staff.objects.count() if you have a staff model
    }
    return render(request, "dashboard/home.html", context)


@login_required
def student_directory(request):
    if request.user.is_superuser:
        # Admins see everyone
        students = Student.objects.all()
    else:
        # 1. Get the staff profile for the logged-in user
        staff_profile = StaffProfile.objects.filter(user=request.user).first()

        if staff_profile:
            # 2. Filter students who are in the same department as the staff
            students = Student.objects.filter(department=staff_profile.department)
        else:
            # Fallback if the user is staff but has no profile created yet
            students = Student.objects.none()

    return render(request, "dashboard/student_directory.html", {"students": students})


@login_required
def routine_management(request):
    return render(request, "dashboard/routine_management.html")
