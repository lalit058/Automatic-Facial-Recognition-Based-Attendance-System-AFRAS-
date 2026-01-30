from django import forms
from accounts.models import StaffProfile, CustomUser


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
