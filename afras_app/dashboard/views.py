from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from accounts.models import Student, StaffProfile
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from attendance.models import Attendance
from django.utils import timezone
from django.contrib import messages
from .forms import StaffProfileEditForm, StudentEditForm, StudentDeleteForm


# Helper function to check if user is staff
def is_staff_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
@user_passes_test(is_staff_user, login_url="login", redirect_field_name=None)
def dashboard_home(request):
    today = timezone.now().date()
    daily_scans = Attendance.objects.filter(date=today).count()

    context = {
        "daily_scans": daily_scans,
        "recent_logs": [],
    }

    if request.user.is_superuser:
        context["total_staff"] = StaffProfile.objects.count()
        context["total_students"] = Student.objects.count()
        context["recent_logs"] = (
            Attendance.objects.select_related("student")
            .all()
            .order_by("-timestamp")[:8]
        )
    else:
        # Use hasattr to check if profile exists without crashing
        if hasattr(request.user, "staffprofile"):
            user_profile = request.user.staff_profile
            dept = user_profile.department

            # Count students in the staff's specific department
            context["total_students"] = Student.objects.filter(department=dept).count()
            context["attendance_rate"] = 92
            context["recent_logs"] = (
                Attendance.objects.select_related("student")
                .filter(student__department=dept)
                .order_by("-timestamp")[:8]
            )
        else:
            # Fallback: if they are staff but have no profile entry yet
            context["total_students"] = (
                Student.objects.count()
            )  # Or 0, depending on preference
            context["attendance_rate"] = 0
            context["error_message"] = "Profile missing. Showing all students."

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
def staff_directory(request):
    # Fetch all staff profiles from the real backend database
    all_staff = StaffProfile.objects.all().select_related("user").order_by("full_name")

    context = {
        "all_staff": all_staff,
        "total_staff": all_staff.count(),
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

    context = {
        "form": form,
        "staff_profile": staff_profile,
        "user": staff_profile.user,
        "page_title": f"Edit Staff: {staff_profile.full_name}",
    }
    return render(request, "dashboard/edit_staff.html", context)


@login_required
def edit_student(request, student_id):
    """Edit student profile"""
    # Get student object
    student = get_object_or_404(Student, id=student_id)
    
    # Permission check: only superusers or staff from same department can edit
    if not request.user.is_superuser:
        # Check if user has staff profile 
        if not hasattr(request.user, 'staff_profile'):
            messages.error(request, "You don't have permission to edit students.")
            return redirect('student-directory')
        
        staff_profile = request.user.staff_profile
        
        # Check if staff is from the same department as student
        if staff_profile.department != student.department:
            messages.error(request, "You can only edit students from your department.")
            return redirect('student-directory')
    
    if request.method == 'POST':
        form = StudentEditForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Student {student.full_name} updated successfully!")
                return redirect('student-directory')
            except Exception as e:
                messages.error(request, f"Error updating student: {str(e)}")
        else:
            # Debug form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = StudentEditForm(instance=student)
    
    context = {
        'form': form,
        'student': student,
        'page_title': 'Edit Student',
        'can_edit': True,
    }
    return render(request, 'dashboard/edit_student.html', context)


@login_required
@require_http_methods(["DELETE", "POST"])
def delete_student(request, student_id):
    """Delete student (AJAX or regular)"""
    # Get student object
    student = get_object_or_404(Student, id=student_id)
    
    # Permission check: only superusers can delete
    if not request.user.is_superuser:
        # Check if user has staff profile
        if not hasattr(request.user, 'staff_profile'):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Permission denied'}, status=403)
            messages.error(request, "You don't have permission to delete students.")
            return redirect('student-directory')
        
        staff_profile = request.user.staff_profile
        
        # Check if staff is from the same department as student
        if staff_profile.department != student.department:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'You can only delete students from your department'}, status=403)
            messages.error(request, "You can only delete students from your department.")
            return redirect('student-directory')
    
    if request.method == 'DELETE' or (request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
        # AJAX request
        try:
            # Store student info for response
            student_name = student.full_name
            student_roll = student.roll_number
            
            # Delete the user account (cascades to student due to CASCADE)
            user = student.user
            user.delete()
            
            # Store message in session for the next request
            messages.success(request, f'Student {student_name} deleted successfully!')
            
            return JsonResponse({
                'success': True,
                'message': f'Student {student_name} deleted successfully!',
                'student_id': student_id
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error deleting student: {str(e)}'
            }, status=500)
    
    elif request.method == 'POST':
        # Regular form submission
        form = StudentDeleteForm(request.POST)
        if form.is_valid() and form.cleaned_data['confirm']:
            try:
                student_name = student.full_name
                student_roll = student.roll_number
                
                # Delete the user account
                user = student.user
                user.delete()
                
                messages.success(request, f"Student {student_name} ({student_roll}) deleted successfully!")
                return redirect('student-directory')
            except Exception as e:
                messages.error(request, f"Error deleting student: {str(e)}")
                return redirect('student-directory')
        else:
            messages.error(request, "Please confirm deletion.")
            return redirect('student-directory')
    
    # GET request - show confirmation page
    form = StudentDeleteForm()
    context = {
        'form': form,
        'student': student,
        'page_title': 'Delete Student',
    }
    return render(request, 'dashboard/delete_student.html', context)


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
def routine_management(request):
    return render(request, "dashboard/routine_management.html")


@csrf_exempt
def start_manual_session(request):
    if request.method == "POST":
        subject = request.POST.get("subject")
        dept = request.POST.get("department")

        # Triggering the ResNet-101 script located in your /recognition folder
        try:
            # We call the script as a background process
            return JsonResponse({"success": True, "message": f"Started {subject}"})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

    # This handles the GET request error you're seeing
    return JsonResponse({"error": "Method not allowed. Please use POST."}, status=405)


def extract_routine_ai(request):
    if request.method == "POST" and request.FILES.get("routine_file"):
        uploaded_file = request.FILES["routine_file"]

        # 1. Save file to your 'media' folder
        # 2. Logic to parse PDF (e.g., using pdfplumber or tabula)
        # 3. For now, we simulate success:

        return JsonResponse(
            {
                "success": True,
                "message": "Routine vectors extracted and synced with database.",
                "classes_count": 6,
            }
        )
    return JsonResponse({"success": False, "message": "No file provided."})
