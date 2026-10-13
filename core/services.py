"""Helpers for writing audit-log entries and in-app notifications."""
from .models import AuditLog, Notification


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def log_action(actor, action, target=None, details=None, request=None):
    """Append an entry to the audit log. Never raises on missing optional data."""
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target._meta.label if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        target_repr=str(target)[:255] if target is not None else "",
        details=details or {},
        ip_address=client_ip(request),
    )


def notify(recipients, title, message="", link="", request_obj=None, kind=Notification.Kind.INFO, exclude=None):
    """Create in-app notifications for each distinct, active recipient."""
    seen = set()
    exclude_id = getattr(exclude, "pk", None)
    batch = []
    for user in recipients:
        if user is None or user.pk in seen or user.pk == exclude_id:
            continue
        if user.account_status != user.Status.ACTIVE:
            continue
        seen.add(user.pk)
        batch.append(
            Notification(
                recipient=user,
                title=title[:200],
                message=message,
                link=link,
                request=request_obj,
                kind=kind,
            )
        )
    if batch:
        Notification.objects.bulk_create(batch)
    return len(batch)
