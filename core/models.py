from django.conf import settings
from django.db import models


class SiteSettings(models.Model):
    """Single-row table of system settings configurable by the Superuser."""

    portal_name = models.CharField(max_length=120, default="ATU Support Portal")
    current_term = models.CharField(max_length=60, default="Fall 2026")
    support_email = models.EmailField(default="info@abaarsotechuniversity.org")
    support_hours = models.CharField(max_length=120, default="Sun – Thu: 8:00 AM – 4:30 PM")
    support_location = models.CharField(max_length=200, default="Building A, Academic Services Wing, Room 104")

    sla_days_absence = models.PositiveSmallIntegerField("Absence & leave SLA (days)", default=2)
    sla_days_problem = models.PositiveSmallIntegerField("Student problem SLA (days)", default=5)
    sla_days_late_class = models.PositiveSmallIntegerField("Late class SLA (days)", default=3)
    max_upload_mb = models.PositiveSmallIntegerField("Maximum upload size (MB)", default=10)

    staff_can_decide_absence = models.BooleanField(
        "Department staff may approve/reject absence & leave requests",
        default=False,
        help_text="If off, only deans/heads, the Academic Office and Student Affairs may record decisions.",
    )
    director_can_view_confidential = models.BooleanField(
        "Director of Student Affairs may view confidential cases in other departments",
        default=False,
        help_text="Enable only if university policy authorizes it.",
    )

    max_active_requests_per_student = models.PositiveSmallIntegerField(
        "Max active requests per student",
        default=2,
        help_text="Maximum open requests allowed per student concurrently (default: 2). Set to 0 for unlimited.",
    )
    absence_requires_document = models.BooleanField(
        "Require supporting document for absence/leave",
        default=True,
        help_text="Require students to attach official documentation (medical slip, letter) when submitting absence requests.",
    )
    block_overlapping_absence = models.BooleanField(
        "Block overlapping absence requests",
        default=True,
        help_text="Prevent students from filing duplicate absence requests covering dates already in progress or approved.",
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "system settings"
        verbose_name_plural = "system settings"

    def __str__(self):
        return "System settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Notification(models.Model):
    class Kind(models.TextChoices):
        INFO = "info", "Information"
        SUBMITTED = "submitted", "Submitted"
        ASSIGNED = "assigned", "Assigned"
        STATUS = "status", "Status change"
        ACTION = "action", "Action required"
        DECISION = "decision", "Decision"
        ESCALATED = "escalated", "Escalated"
        ACCOUNT = "account", "Account"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.INFO)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    request = models.ForeignKey("cases.Request", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient} – {self.title}"

    @property
    def icon(self):
        return {
            "submitted": "send",
            "assigned": "assignment_ind",
            "status": "sync",
            "action": "priority_high",
            "decision": "gavel",
            "escalated": "trending_up",
            "account": "manage_accounts",
        }.get(self.kind, "notifications")


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries"
    )
    action = models.CharField(max_length=60, db_index=True)
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    target_repr = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor} {self.action} {self.target_repr}"

    @property
    def action_label(self):
        return self.action.replace(".", " · ").replace("_", " ").title()
