from django import forms
from accounts.models import StaffProfile, Student, CustomUser


class StudentEditForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Email Address"}
        ),
    )

    class Meta:
        model = Student
        fields = [
            "full_name",
            "roll_number",
            "phone_number",
            "department",
            "semester",
            "section",
            "photo",
            "id_proof",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Full Name"}
            ),
            "roll_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Roll Number",
                    "readonly": "readonly",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Phone Number"}
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "semester": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Semester",
                    "min": "1",
                    "max": "8",
                }
            ),
            "section": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Section"}
            ),
            "photo": forms.FileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
            "id_proof": forms.FileInput(
                attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Load departments dynamically
        departments = Student.objects.values_list("department", flat=True).distinct()
        self.fields["department"].widget.choices = [("", "Select Department")] + [
            (d, d) for d in departments if d
        ]

        # If instance exists, pre-fill email and username
        if self.instance and self.instance.user:
            user = self.instance.user
            self.fields["email"].initial = user.email
            # Make roll_number read-only for existing students
            self.fields["roll_number"].widget.attrs["readonly"] = True

    def save(self, commit=True):
        student = super().save(commit=False)

        if commit:
            student.save()

            # Update User model
            if student.user:
                user = student.user
                full_name = self.cleaned_data["full_name"]
                user.email = self.cleaned_data["email"]
                user.save()

        return student


class StudentDeleteForm(forms.Form):
    """Simple form for student deletion confirmation"""

    confirm = forms.BooleanField(
        required=True,
        label="I confirm that I want to delete this student",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class StaffProfileEditForm(forms.ModelForm):
    # Field for the User model email
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Email Address"}
        ),
    )

    is_admin = forms.BooleanField(
        required=False,
        label="Administrator Privileges",
    )

    class Meta:
        model = StaffProfile
        fields = [
            "full_name",
            "phone_number",
            "degree",
            "designation",
            "department",
            "photo",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Full Name"}
            ),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Phone Number"}
            ),
            "degree": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Degree"}
            ),
            "designation": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Designation"}
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "photo": forms.FileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Load departments dynamically
        departments = StaffProfile.objects.values_list(
            "department", flat=True
        ).distinct()
        self.fields["department"].widget.choices = [("", "Select Department")] + [
            (d, d) for d in departments if d
        ]

        # Fix the AttributeError: Check User fields correctly
        if self.instance and self.instance.user:
            user = self.instance.user
            self.fields["email"].initial = user.email
            self.fields["is_admin"].initial = user.is_superuser

    def save(self, commit=True):
        staff_profile = super().save(commit=commit)

        if commit and staff_profile.user:
            user = staff_profile.user
            full_name = self.cleaned_data["full_name"]

            # Logic to split Full Name into First and Last for the User model
            name_parts = full_name.split(" ", 1)
            user.first_name = name_parts[0]
            user.last_name = name_parts[1] if len(name_parts) > 1 else ""

            user.email = self.cleaned_data["email"]
            user.is_superuser = self.cleaned_data["is_admin"]
            user.is_staff = True
            user.save()

        return staff_profile
