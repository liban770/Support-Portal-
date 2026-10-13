"""Server-side authorization rules for student requests.

Every view that reads or changes a request goes through these functions.
Hiding a button in a template is never relied upon for security.

Summary of the rules
--------------------
Student          – only their own requests; never sees internal notes/attachments.
Department staff – non-confidential requests owned by their department, plus
                   anything assigned to them personally.
Academic Office  – same as staff, scoped to the Academic Office (no automatic
                   access to unrelated or confidential cases).
Dean / head      – all requests owned by the department(s) they head, plus
                   non-confidential requests that concern their department.
Director (SA)    – all requests owned by Student Affairs, plus non-confidential
                   student-support requests across departments (read / monitor /
                   escalate). Confidential cases elsewhere only if the policy
                   toggle `director_can_view_confidential` is enabled.
Superuser        – no access to request contents (aggregate statistics only).
"""
from django.db.models import Q

from accounts.models import Department, User
from core.models import SiteSettings

from .models import FINAL_STATUSES, OPEN_STATUSES, Request, RequestType, Status


def visible_requests(user, base_qs=None):
    qs = base_qs if base_qs is not None else Request.objects.all()
    qs = qs.select_related("student", "department", "related_department", "assigned_to", "category")
    if not getattr(user, "is_authenticated", False) or user.account_status != User.Status.ACTIVE:
        return qs.none()

    role = user.role
    if role == User.Role.STUDENT:
        return qs.filter(student=user)
    if role == User.Role.SUPERUSER:
        return qs.none()

    q = Q(assigned_to=user)
    head_ids = user.headed_department_ids
    if head_ids:
        q |= Q(department_id__in=head_ids)
        q |= Q(related_department_id__in=head_ids, is_confidential=False)

    if user.department_id:
        q |= Q(department_id=user.department_id, is_confidential=False)

    if role == User.Role.DIRECTOR:
        q |= Q(department__kind=Department.Kind.STUDENT_AFFAIRS)
        if SiteSettings.load().director_can_view_confidential:
            q = Q()  # policy explicitly authorizes full visibility
        else:
            q |= Q(is_confidential=False)

    return qs.filter(q) if q else qs


def can_view(user, req):
    return visible_requests(user).filter(pk=req.pk).exists()


def is_head_of(user, department_id):
    return department_id is not None and department_id in user.headed_department_ids


def can_process(user, req):
    """May change status and send official responses on this case."""
    if not user.is_handler or req.status == Status.CLOSED:
        return False
    if req.assigned_to_id == user.id:
        return True
    if is_head_of(user, req.department_id) or is_head_of(user, req.related_department_id):
        return True
    if user.department_id and (req.department_id == user.department_id or req.related_department_id == user.department_id) and not req.is_confidential:
        return True
    if user.role == User.Role.ACADEMIC and req.request_type == RequestType.LATE_CLASS:
        return True
    return False


def can_take(user, req):
    """Staff or department head may pick up an unassigned case in their department."""
    return (
        user.is_handler
        and req.assigned_to_id is None
        and req.status in OPEN_STATUSES
        and (
            (user.department_id is not None and (req.department_id == user.department_id or req.related_department_id == user.department_id))
            or is_head_of(user, req.department_id)
            or is_head_of(user, req.related_department_id)
        )
        and not req.is_confidential
    )


def can_assign(user, req):
    """Deans / heads assign cases to staff within their department."""
    return user.is_handler and req.status != Status.CLOSED and (
        is_head_of(user, req.department_id) or is_head_of(user, req.related_department_id)
    )


def can_return(user, req):
    """Deans / heads may return a case to staff for additional work."""
    return can_assign(user, req) and req.status != Status.CLOSED


def can_escalate(user, req):
    if req.status not in OPEN_STATUSES:
        return False
    if can_process(user, req):
        return True
    # The Director may escalate any student-support case they are authorized to see.
    return user.role == User.Role.DIRECTOR and can_view(user, req)


def can_delete(user, req):
    """Deans / department heads may permanently delete a case in their department."""
    if not getattr(user, "is_authenticated", False) or user.account_status != User.Status.ACTIVE:
        return False
    return is_head_of(user, req.department_id) or is_head_of(user, req.related_department_id)


def can_decide(user, req):
    """Approve / reject an absence or leave request (only when authorized)."""
    if req.request_type != RequestType.ABSENCE or not can_process(user, req):
        return False
    if is_head_of(user, req.department_id):
        return True
    if user.role in (User.Role.DEAN, User.Role.ACADEMIC, User.Role.DIRECTOR):
        return True
    return user.role == User.Role.STAFF and SiteSettings.load().staff_can_decide_absence


def can_add_internal_note(user, req):
    return user.is_handler and can_view(user, req) and req.status != Status.CLOSED


def can_student_reply(user, req):
    return user.is_student and req.student_id == user.id and req.status != Status.CLOSED


def can_view_internal(user):
    return user.is_handler


def allowed_status_choices(user, req):
    """Statuses the user may set via the status form (escalation has its own action)."""
    from .models import ALLOWED_STATUSES

    if not can_process(user, req):
        return []
    choices = []
    for status in ALLOWED_STATUSES.get(req.request_type, []):
        if status in (Status.ESCALATED, req.status):
            continue
        if status == Status.SUBMITTED:
            continue
        if req.request_type == RequestType.ABSENCE and status in (Status.RESOLVED, Status.REJECTED):
            if not can_decide(user, req):
                continue
        choices.append((status.value, status.label))
    return choices


def overdue_q():
    from django.utils import timezone

    return Q(status__in=OPEN_STATUSES, due_at__lt=timezone.now())


__all__ = [
    "visible_requests", "can_view", "can_process", "can_take", "can_assign", "can_return",
    "can_escalate", "can_decide", "can_delete", "can_add_internal_note", "can_student_reply", "can_view_internal",
    "allowed_status_choices", "overdue_q", "FINAL_STATUSES", "OPEN_STATUSES",
]
