from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property


class Department(models.Model):
    """A university department or office that can own student requests."""

    class Kind(models.TextChoices):
        ACADEMIC = "academic", "Academic Department"
        ACADEMIC_OFFICE = "academic_office", "Academic Office"
        STUDENT_AFFAIRS = "student_affairs", "Student Affairs Office"
        SERVICE = "service", "Administrative / Service Unit"

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short code, e.g. CSE")
    kind = models.CharField(max_length=30, choices=Kind.choices, default=Kind.ACADEMIC)
    description = models.TextField(blank=True)
    head = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="headed_departments",
        help_text="Dean or head of department / office.",
    )
    location = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_academic(self):
        return self.kind == self.Kind.ACADEMIC


class PortalUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.SUPERUSER)
        extra_fields.setdefault("account_status", User.Status.ACTIVE)
        # Django admin is not used; portal superusers do not need Django staff flags.
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(username=username, email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        STAFF = "staff", "Department Staff"
        DEAN = "dean", "Dean / Head of Department"
        ACADEMIC = "academic", "Academic Office"
        DIRECTOR = "director", "Director of Student Affairs"
        SUPERUSER = "superuser", "System Administrator"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Validation"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DEACTIVATED = "deactivated", "Deactivated"
        REJECTED = "rejected", "Rejected"

    email = models.EmailField("institutional email", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT, db_index=True)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )
    account_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    must_change_password = models.BooleanField(default=False)
    created_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    validated_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    validated_at = models.DateTimeField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)

    objects = PortalUserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        # Only ACTIVE accounts may log in / receive password resets.
        self.is_active = self.account_status == self.Status.ACTIVE
        super().save(*args, **kwargs)

    # --- Convenience helpers ------------------------------------------------
    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        parts = [p for p in [self.first_name, self.last_name] if p]
        if parts:
            return "".join(p[0] for p in parts[:2]).upper()
        return self.username[:2].upper()

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_sysadmin(self):
        return self.role == self.Role.SUPERUSER

    @property
    def is_handler(self):
        """Users who process student requests (all roles except students and sysadmins)."""
        return self.role in {self.Role.STAFF, self.Role.DEAN, self.Role.ACADEMIC, self.Role.DIRECTOR}

    @cached_property
    def headed_department_ids(self):
        return list(Department.objects.filter(head=self, is_active=True).values_list("id", flat=True))

    @property
    def is_department_head(self):
        return bool(self.headed_department_ids)

    @property
    def role_short(self):
        return {
            self.Role.STUDENT: "Student",
            self.Role.STAFF: "Staff",
            self.Role.DEAN: "Dean",
            self.Role.ACADEMIC: "Academic Office",
            self.Role.DIRECTOR: "Student Affairs",
            self.Role.SUPERUSER: "Superuser",
        }.get(self.role, self.role)

    @property
    def subtitle(self):
        if self.is_student:
            sid = getattr(getattr(self, "student_profile", None), "student_id", "")
            return f"Student · {sid}" if sid else "Student"
        position = getattr(getattr(self, "staff_profile", None), "position", "")
        return position or self.get_role_display()

    def set_status(self, status, by=None):
        self.account_status = status
        self.status_changed_at = timezone.now()
        if status == self.Status.ACTIVE and by is not None and self.validated_by_id is None:
            self.validated_by = by
            self.validated_at = timezone.now()


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    student_id = models.CharField(max_length=40, unique=True)
    program = models.CharField(max_length=150, blank=True)
    year_of_study = models.PositiveSmallIntegerField(null=True, blank=True)
    verified_from_register = models.BooleanField(
        default=False, help_text="Imported from / verified against the official student register."
    )

    def __str__(self):
        return f"{self.student_id} – {self.user.display_name}"


class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    staff_id = models.CharField(max_length=40, blank=True)
    position = models.CharField(max_length=150, blank=True, help_text="Job title, e.g. Academic Coordinator")

    def __str__(self):
        return f"{self.user.display_name} ({self.position or 'Staff'})"
