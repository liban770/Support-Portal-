import csv
import io

from django import forms
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm

from cases.forms import StyledFormMixin

from .models import Department, StaffProfile, StudentProfile, User


class LoginForm(StyledFormMixin, forms.Form):
    username = forms.CharField(label="University email or Student ID", max_length=150)
    password = forms.CharField(label="Password", widget=forms.PasswordInput)
    remember = forms.BooleanField(required=False, label="Remember this device for 30 days")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"placeholder": "student ID or email (e.g. info@abaarsotechuniversity.org)", "autocomplete": "username", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"placeholder": "Enter your password", "autocomplete": "current-password"}
        )
        self._style_fields()


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class StyledPasswordResetForm(StyledFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["placeholder"] = "name@abaarsotechuniversity.org"
        self._style_fields()


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self._style_fields()

    def clean_first_name(self):
        fn = (self.cleaned_data.get("first_name") or "").strip()
        if len(fn) < 2:
            raise forms.ValidationError("First name must be at least 2 characters.")
        if any(char.isdigit() for char in fn):
            raise forms.ValidationError("First name cannot contain numbers.")
        return fn

    def clean_last_name(self):
        ln = (self.cleaned_data.get("last_name") or "").strip()
        if len(ln) < 2:
            raise forms.ValidationError("Last name must be at least 2 characters.")
        if any(char.isdigit() for char in ln):
            raise forms.ValidationError("Last name cannot contain numbers.")
        return ln


class AdminUserForm(StyledFormMixin, forms.ModelForm):
    """Used by the Superuser to create and edit accounts of any role."""

    student_id = forms.CharField(required=False, max_length=40, label="Student ID")
    program = forms.CharField(required=False, max_length=150)
    year_of_study = forms.IntegerField(required=False, min_value=1, max_value=8)
    staff_id = forms.CharField(required=False, max_length=40, label="Staff ID")
    position = forms.CharField(required=False, max_length=150, label="Position / title")
    password = forms.CharField(
        required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Leave blank to generate a temporary password the user must change at first login.",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "username", "role", "department"]

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["username"].help_text = "Students: use the student ID. Staff: e.g. a.warsame"
        inst = self.instance
        if inst.pk:
            self.fields["password"].label = "Set New Password (Optional)"
            self.fields["password"].help_text = "Leave blank to keep current password, or enter a new password to update it."
            sp = getattr(inst, "student_profile", None)
            st = getattr(inst, "staff_profile", None)
            if sp:
                self.fields["student_id"].initial = sp.student_id
                self.fields["program"].initial = sp.program
                self.fields["year_of_study"].initial = sp.year_of_study
            if st:
                self.fields["staff_id"].initial = st.staff_id
                self.fields["position"].initial = st.position
            # Users can never change their own role or department (no self-privilege changes).
            if acting_user is not None and inst.pk == acting_user.pk:
                self.fields["role"].disabled = True
                self.fields["department"].disabled = True
                self.fields["role"].help_text = "You cannot change your own role."
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        role = data.get("role")
        if role == User.Role.STUDENT:
            sid = (data.get("student_id") or "").strip()
            if not sid:
                self.add_error("student_id", "Student ID is required for student accounts.")
            elif StudentProfile.objects.filter(student_id__iexact=sid).exclude(user_id=self.instance.pk).exists():
                self.add_error("student_id", "This student ID is already registered.")
        if role in (User.Role.STAFF, User.Role.DEAN, User.Role.ACADEMIC, User.Role.DIRECTOR) and not data.get("department"):
            self.add_error("department", "Staff accounts must belong to a department or office.")
        return data

    def save_profiles(self, user):
        d = self.cleaned_data
        if user.role == User.Role.STUDENT:
            StudentProfile.objects.update_or_create(
                user=user,
                defaults={"student_id": d["student_id"].strip(), "program": d.get("program", ""),
                          "year_of_study": d.get("year_of_study")},
            )
        elif user.role != User.Role.SUPERUSER or d.get("position"):
            StaffProfile.objects.update_or_create(
                user=user, defaults={"staff_id": d.get("staff_id", ""), "position": d.get("position", "")}
            )


class DeanStaffForm(StyledFormMixin, forms.ModelForm):
    """Department heads create *staff* accounts for their own department only.

    Role and department are not editable here — they are forced server-side —
    so heads cannot create Superusers or grant extra privileges.
    """

    staff_id = forms.CharField(required=False, max_length=40, label="Staff ID")
    position = forms.CharField(max_length=150, label="Position / title")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "username"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class DepartmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "code", "kind", "head", "description", "location", "contact_email", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["head"].queryset = User.objects.filter(
            account_status=User.Status.ACTIVE,
            role__in=[User.Role.DEAN, User.Role.STAFF, User.Role.ACADEMIC, User.Role.DIRECTOR],
        )
        self.fields["head"].label = "Dean / Head"
        self.fields["head"].label_from_instance = lambda u: f"{u.display_name} — {u.get_role_display()}"
        self._style_fields()

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class StudentImportForm(StyledFormMixin, forms.Form):
    REQUIRED_COLUMNS = {"student_id", "first_name", "last_name", "email"}

    csv_file = forms.FileField(
        label="Student register (CSV)",
        help_text="Columns: student_id, first_name, last_name, email, department_code, program, year_of_study",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["csv_file"].widget.attrs["accept"] = ".csv"
        self._style_fields()

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a .csv file.")
        if f.size > 2 * 1024 * 1024:
            raise forms.ValidationError("CSV is too large (max 2 MB).")
        try:
            text = f.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            raise forms.ValidationError("CSV must be UTF-8 encoded.")
        reader = csv.DictReader(io.StringIO(text))
        cols = {c.strip().lower() for c in (reader.fieldnames or [])}
        missing = self.REQUIRED_COLUMNS - cols
        if missing:
            raise forms.ValidationError(f"Missing columns: {', '.join(sorted(missing))}")
        rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]
        if not rows:
            raise forms.ValidationError("The CSV has no data rows.")
        if len(rows) > 2000:
            raise forms.ValidationError("Import at most 2000 students at a time.")
        return rows
