import os
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils import timezone


class RequestType(models.TextChoices):
    ABSENCE = "absence", "Absence & Leave"
    PROBLEM = "problem", "Student Problem"
    LATE_CLASS = "late_class", "Late Class Report"


class Status(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under Review"
    IN_PROGRESS = "in_progress", "In Progress"
    WAITING = "waiting", "Waiting for Student"
    ESCALATED = "escalated", "Escalated"
    RESOLVED = "resolved", "Resolved"
    REJECTED = "rejected", "Rejected"
    CLOSED = "closed", "Closed"


OPEN_STATUSES = [Status.SUBMITTED, Status.UNDER_REVIEW, Status.IN_PROGRESS, Status.WAITING, Status.ESCALATED]
FINAL_STATUSES = [Status.RESOLVED, Status.REJECTED, Status.CLOSED]

# Only statuses relevant to each request type are offered.
ALLOWED_STATUSES = {
    RequestType.ABSENCE: [
        Status.SUBMITTED, Status.UNDER_REVIEW, Status.WAITING, Status.ESCALATED,
        Status.RESOLVED, Status.REJECTED, Status.CLOSED,
    ],
    RequestType.PROBLEM: [s for s in Status],
    RequestType.LATE_CLASS: [
        Status.SUBMITTED, Status.UNDER_REVIEW, Status.IN_PROGRESS, Status.WAITING,
        Status.ESCALATED, Status.RESOLVED, Status.REJECTED, Status.CLOSED,
    ],
}

STATUS_STYLES = {
    # (background, text) pairs from the design system
    Status.SUBMITTED: ("#E2E8F0", "#334155"),
    Status.UNDER_REVIEW: ("#DBEAFE", "#1E40AF"),
    Status.IN_PROGRESS: ("#F3E8FF", "#6B21A8"),
    Status.WAITING: ("#FEF3C7", "#92400E"),
    Status.ESCALATED: ("#FFEDD5", "#9A3412"),
    Status.RESOLVED: ("#DCFCE7", "#166534"),
    Status.REJECTED: ("#FEE2E2", "#991B1B"),
    Status.CLOSED: ("#F1F5F9", "#475569"),
}

TYPE_ICONS = {
    RequestType.ABSENCE: "event_busy",
    RequestType.PROBLEM: "report_problem",
    RequestType.LATE_CLASS: "schedule",
}


class RequestCategory(models.Model):
    """Categories drive routing: each may define a default department/office.

    A blank default department means "route to the student's own department".
    """

    name = models.CharField(max_length=120)
    request_type = models.CharField(max_length=20, choices=RequestType.choices)
    description = models.CharField(max_length=255, blank=True)
    default_department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="routed_categories"
    )
    is_sensitive = models.BooleanField(default=False, help_text="Reports in this category are always confidential.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["request_type", "sort_order", "name"]
        unique_together = [("name", "request_type")]
        verbose_name_plural = "request categories"

    def __str__(self):
        return self.name


class Request(models.Model):
    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class LeaveType(models.TextChoices):
        ABSENCE_EXCUSE = "absence_excuse", "Absence excuse"
        LEAVE = "leave", "Leave request"

    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    reference = models.CharField(max_length=20, unique=True, editable=False)
    request_type = models.CharField(max_length=20, choices=RequestType.choices, db_index=True)
    category = models.ForeignKey(RequestCategory, null=True, blank=True, on_delete=models.SET_NULL)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_requests")

    title = models.CharField(max_length=200)
    reason = models.CharField(max_length=200, blank=True)
    description = models.TextField()

    department = models.ForeignKey(
        "accounts.Department", null=True, on_delete=models.SET_NULL, related_name="requests",
        help_text="Department / office currently responsible for the case.",
    )
    related_department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="related_requests",
        help_text="Academic department the case concerns (lets its dean monitor it).",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_requests"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    is_confidential = models.BooleanField(default=False)

    # Absence & leave
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Student problem
    location = models.CharField(max_length=150, blank=True)

    # Late class
    course = models.CharField(max_length=150, blank=True)
    instructor_name = models.CharField(max_length=150, blank=True)
    class_date = models.DateField(null=True, blank=True)
    scheduled_start = models.TimeField(null=True, blank=True)
    actual_start = models.TimeField(null=True, blank=True)
    class_did_not_start = models.BooleanField(default=False)

    # Decision / resolution
    decision = models.CharField(max_length=10, choices=Decision.choices, blank=True)
    decision_note = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["department", "status"]),
            models.Index(fields=["student", "status"]),
        ]

    def __str__(self):
        return f"{self.reference} – {self.title}"

    # --- Reference generation --------------------------------------------
    def save(self, *args, **kwargs):
        if self.reference:
            return super().save(*args, **kwargs)
        year = timezone.localtime(self.created_at or timezone.now()).year
        prefix = f"ATU-{year}-"
        for _ in range(10):
            last = (
                Request.objects.filter(reference__startswith=prefix)
                .order_by("-reference").values_list("reference", flat=True).first()
            )
            seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
            self.reference = f"{prefix}{seq:04d}"
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.reference = ""
                continue
        raise IntegrityError("Could not allocate a unique request reference.")

    def get_absolute_url(self):
        return reverse("cases:detail", args=[self.reference])

    # --- Display helpers --------------------------------------------------
    @property
    def is_open(self):
        return self.status in OPEN_STATUSES

    @property
    def is_overdue(self):
        return bool(self.is_open and self.due_at and timezone.now() > self.due_at)

    @property
    def type_icon(self):
        return TYPE_ICONS.get(self.request_type, "description")

    @property
    def status_colors(self):
        return STATUS_STYLES.get(self.status, ("#F1F5F9", "#475569"))

    @property
    def duration_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return None

    @property
    def delay_minutes(self):
        if self.class_date and self.scheduled_start and self.actual_start:
            start = datetime.combine(self.class_date, self.scheduled_start)
            actual = datetime.combine(self.class_date, self.actual_start)
            return max(int((actual - start).total_seconds() // 60), 0)
        return None

    @property
    def summary_line(self):
        if self.request_type == RequestType.ABSENCE and self.start_date:
            days = self.duration_days
            return f"{self.start_date:%b %d} – {self.end_date:%b %d, %Y} · {days} day{'s' if days != 1 else ''}"
        if self.request_type == RequestType.LATE_CLASS:
            if self.class_did_not_start:
                return f"{self.course} · class did not start"
            if self.delay_minutes is not None:
                return f"{self.course} · {self.delay_minutes} min late"
            return self.course
        return self.category.name if self.category else ""

    def compute_due_at(self, site):
        days = {
            RequestType.ABSENCE: site.sla_days_absence,
            RequestType.PROBLEM: site.sla_days_problem,
            RequestType.LATE_CLASS: site.sla_days_late_class,
        }.get(self.request_type, 5)
        return (self.created_at or timezone.now()) + timedelta(days=days)


class RequestAssignment(models.Model):
    """Routing history: every route, assignment, escalation and return."""

    class Action(models.TextChoices):
        ROUTED = "routed", "Routed"
        ASSIGNED = "assigned", "Assigned"
        TAKEN = "taken", "Taken by staff"
        ESCALATED = "escalated", "Escalated"
        FORWARDED = "forwarded", "Forwarded"
        RETURNED = "returned", "Returned for additional work"

    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name="assignments")
    action = models.CharField(max_length=20, choices=Action.choices)
    from_department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    to_department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]


class RequestComment(models.Model):
    """Unified case timeline: public responses, internal notes and status events."""

    class Kind(models.TextChoices):
        RESPONSE = "response", "Response"
        INTERNAL = "internal", "Internal note"
        STATUS = "status", "Status change"
        SYSTEM = "system", "System event"

    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.RESPONSE)
    body = models.TextField(blank=True)
    is_internal = models.BooleanField(default=False, help_text="Hidden from the student.")
    old_status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    @property
    def icon(self):
        if self.kind == self.Kind.STATUS:
            return "sync_alt"
        if self.kind == self.Kind.SYSTEM:
            return "bolt"
        if self.kind == self.Kind.INTERNAL:
            return "lock"
        return "chat"


def attachment_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"attachments/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class Attachment(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name="attachments")
    comment = models.ForeignKey(
        RequestComment, null=True, blank=True, on_delete=models.SET_NULL, related_name="attachments"
    )
    file = models.FileField(upload_to=attachment_upload_to)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.original_name

    @property
    def extension(self):
        return os.path.splitext(self.original_name)[1].lower().lstrip(".")

    @property
    def size_display(self):
        if self.size >= 1024 * 1024:
            return f"{self.size / (1024 * 1024):.1f} MB"
        return f"{max(self.size // 1024, 1)} KB"
