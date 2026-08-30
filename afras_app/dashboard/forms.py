from django import forms
from accounts.models import StaffProfile, Student, CustomUser
import json
import base64
from django.core.files.base import ContentFile
from django.utils import timezone


class StudentEditForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "john@gmail.com"}
        ),
    )

    # ============================================================
    # ADD THESE HIDDEN FIELDS FOR FACE DATA
    # ============================================================
    face_encoding = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    photo_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    update_face = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )

    face_encoding_file = forms.FileField(
        required=False,
        label="Face Encoding File",
        help_text="Upload a JSON file containing face encoding data",
        widget=forms.FileInput(
            attrs={
                "class": "form-control",
                "accept": "application/json,.json",
                "id": "face_encoding_file",
            }
        ),
    )

    delete_id_proof = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput(attrs={"id": "delete-id-proof"}),
    )

    class Meta:
        model = Student
        fields = [
            "full_name",
            "roll_number",
            "phone_number",
            "department",
            "year",
            "semester",
            "section",
            "address",
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
                }
            ),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Phone Number"}
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "year": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "year",
                    "min": "1",
                    "max": "4",
                }
            ),
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
            "address": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Address"}
            ),
            "photo": forms.FileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
            "id_proof": forms.FileInput(
                attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        departments = Student.objects.values_list("department", flat=True).distinct()
        self.fields["department"].widget.choices = [("", "Select Department")] + [
            (d, d) for d in departments if d
        ]

        if self.instance and self.instance.user:
            user = self.instance.user
            self.fields["email"].initial = user.email

        if self.user:
            if not self.user.is_superuser:
                self.fields["roll_number"].widget.attrs["readonly"] = True
                self.fields["roll_number"].widget.attrs[
                    "class"
                ] = "form-control readonly-field"
                self.fields["roll_number"].help_text = (
                    "Only administrators can modify roll numbers"
                )
            else:
                self.fields["roll_number"].widget.attrs["readonly"] = False
                self.fields["roll_number"].help_text = ""

    def clean_roll_number(self):
        roll_number = self.cleaned_data.get("roll_number")

        if self.user and not self.user.is_superuser:
            if self.instance and self.instance.pk:
                original_roll = Student.objects.get(pk=self.instance.pk).roll_number
                if roll_number != original_roll:
                    roll_number = original_roll

        if roll_number:
            qs = Student.objects.filter(roll_number=roll_number)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("This roll number is already in use.")

        return roll_number

    def clean_face_encoding_file(self):
        file = self.cleaned_data.get("face_encoding_file")
        if file:
            if not file.name.endswith(".json"):
                raise forms.ValidationError("Only JSON files are allowed.")
            try:
                content = file.read().decode("utf-8")
                data = json.loads(content)
                if not isinstance(data, list):
                    raise forms.ValidationError("JSON must contain a list of numbers.")
                for i, item in enumerate(data):
                    try:
                        float(item)
                    except (ValueError, TypeError):
                        raise forms.ValidationError(
                            f"Item at position {i} is not a valid number."
                        )
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON file.")
            except UnicodeDecodeError:
                raise forms.ValidationError("File encoding error.")
        return file

    def save(self, commit=True):
        """Save student with face encoding from hidden input"""
        student = super().save(commit=False)

        # ============================================================
        # HANDLE FACE ENCODING FROM HIDDEN INPUT
        # ============================================================
        update_face = self.cleaned_data.get('update_face') == 'true'
        face_encoding_data = self.cleaned_data.get('face_encoding')
        photo_data = self.cleaned_data.get('photo_data')
        
        if update_face and face_encoding_data:
            try:
                if isinstance(face_encoding_data, str):
                    face_encoding = json.loads(face_encoding_data)
                else:
                    face_encoding = face_encoding_data
                
                if isinstance(face_encoding, list) and len(face_encoding) > 0:
                    student.face_encoding = face_encoding
                    print(f"✅ Face encoding saved for {student.full_name}")
                    
                    if photo_data and photo_data.startswith('data:image'):
                        try:
                            format, imgstr = photo_data.split(';base64,')
                            ext = format.split('/')[-1]
                            
                            # Delete any existing photo first
                            if student.photo and student.photo.name:
                                try:
                                    if student.photo.storage.exists(student.photo.name):
                                        student.photo.storage.delete(student.photo.name)
                                        print(f"🗑️ Deleted old file: {student.photo.name}")
                                except Exception as e:
                                    print(f"Error deleting old file: {e}")
                            
                            # ============================================================
                            # FIX: Just use filename WITHOUT student_photos/
                            # The model's upload_to="student_photos/" will add it
                            # ============================================================
                            filename = f'{student.roll_number}_photo.jpg'
                            data = ContentFile(base64.b64decode(imgstr), name=filename)
                            student.photo = data
                            print(f"✅ Photo saved at: {student.photo.name}")
                            
                        except Exception as e:
                            print(f"Error saving photo: {e}")
            except Exception as e:
                print(f"Error processing face data: {e}")

        # Handle face encoding file if uploaded
        face_encoding_file = self.cleaned_data.get("face_encoding_file")
        if face_encoding_file:
            content = face_encoding_file.read().decode("utf-8")
            student.face_encoding = json.loads(content)

        # Handle ID proof deletion
        delete_id_proof = self.cleaned_data.get("delete_id_proof")
        if delete_id_proof and student.id_proof:
            student.id_proof.delete(save=False)
            student.id_proof = None

        # For non-admin users, ensure roll number doesn't change
        if (
            self.user
            and not self.user.is_superuser
            and self.instance
            and self.instance.pk
        ):
            original_student = Student.objects.get(pk=self.instance.pk)
            student.roll_number = original_student.roll_number

        if commit:
            student.save()

            # Update User model email
            if student.user:
                user = student.user
                user.email = self.cleaned_data["email"]
                if self.user and self.user.is_superuser:
                    user.username = student.roll_number
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

        departments = StaffProfile.objects.values_list(
            "department", flat=True
        ).distinct()
        self.fields["department"].widget.choices = [("", "Select Department")] + [
            (d, d) for d in departments if d
        ]

        if self.instance and self.instance.user:
            user = self.instance.user
            self.fields["email"].initial = user.email
            self.fields["is_admin"].initial = user.is_superuser

    def save(self, commit=True):
        staff_profile = super().save(commit=commit)

        if commit and staff_profile.user:
            user = staff_profile.user
            full_name = self.cleaned_data["full_name"]

            name_parts = full_name.split(" ", 1)
            user.first_name = name_parts[0]
            user.last_name = name_parts[1] if len(name_parts) > 1 else ""

            user.email = self.cleaned_data["email"]
            user.is_superuser = self.cleaned_data["is_admin"]
            user.is_staff = True
            user.save()

        return staff_profile