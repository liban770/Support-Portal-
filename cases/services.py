"""Workflow operations on requests.

Each operation updates the request, writes a timeline entry, records routing
history where relevant, sends in-app notifications and writes the audit log.
Callers (views) must check permissions with `cases.permissions` first.
"""
from django.db import transaction
from django.utils import timezone

from accounts.models import Department, User
from core.models import Notification, SiteSettings
from core.services import log_action, notify

from .models import (
    Attachment,
    Request,
    RequestAssignment,
    RequestComment,
    RequestType,
    Status,
)


# --- Recipients ---------------------------------------------------------------
def department_handlers(department, confidential=False):
    """Users who should hear about new work in a department."""
    if department is None:
        return []
    users = []
    if department.head_id:
        users.append(department.head)
    if not confidential:
        users.extend(
            department.members.filter(
                account_status=User.Status.ACTIVE,
                role__in=[User.Role.STAFF, User.Role.ACADEMIC, User.Role.DIRECTOR, User.Role.DEAN],
            )
        )
    return users


def _save_attachments(req, files, user, comment=None, internal=False):
    saved = []
    for f in files or []:
        if not f:
            continue
        saved.append(
            Attachment.objects.create(
                request=req,
                comment=comment,
                file=f,
                original_name=f.name[:255],
                size=f.size,
                content_type=getattr(f, "content_type", "")[:100],
                uploaded_by=user,
                is_internal=internal,
            )
        )
    return saved


def _timeline(req, author, kind, body="", internal=False, old_status="", new_status=""):
    return RequestComment.objects.create(
        request=req, author=author, kind=kind, body=body, is_internal=internal,
        old_status=old_status, new_status=new_status,
    )


# --- Submission -----------------------------------------------------------------
def resolve_department(category, student, chosen_department=None):
    """Route by chosen_department if provided; else category default; else student's department."""
    if chosen_department is not None:
        return chosen_department
    if category and category.default_department_id and category.default_department.is_active:
        if category.default_department.kind == Department.Kind.ACADEMIC and student.department_id:
            return student.department
        return category.default_department
    if student.department_id:
        return student.department
    return Department.objects.filter(kind=Department.Kind.STUDENT_AFFAIRS, is_active=True).first()


@transaction.atomic
def submit_request(student, request_type, data, files=None, http_request=None):
    category = data.get("category")
    chosen = data.get("department")
    department = resolve_department(category, student, chosen)
    if request_type == RequestType.LATE_CLASS:
        # Academic Affairs Office maintains university-wide oversight of late lectures
        related = category.default_department if (category and category.default_department_id) else Department.objects.filter(kind=Department.Kind.ACADEMIC_OFFICE, is_active=True).first()
    else:
        related = student.department if (student.department and department != student.department) else (chosen if chosen else student.department)

    confidential = bool(data.get("is_confidential")) or bool(category and category.is_sensitive)
    req = Request(
        request_type=request_type,
        category=category,
        student=student,
        title=data["title"],
        reason=data.get("reason", ""),
        description=data["description"],
        department=department,
        related_department=related,
        is_confidential=confidential,
        leave_type=data.get("leave_type", ""),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        location=data.get("location", ""),
        course=data.get("course", ""),
        instructor_name=data.get("instructor_name", ""),
        class_date=data.get("class_date"),
        scheduled_start=data.get("scheduled_start"),
        actual_start=data.get("actual_start"),
        class_did_not_start=bool(data.get("class_did_not_start")),
    )
    req.created_at = timezone.now()
    req.due_at = req.compute_due_at(SiteSettings.load())
    req.save()

    _save_attachments(req, files, student)
    _timeline(req, student, RequestComment.Kind.SYSTEM, "Request submitted by student.", new_status=Status.SUBMITTED)
    RequestAssignment.objects.create(
        request=req, action=RequestAssignment.Action.ROUTED, to_department=department, performed_by=student,
        note=f"Automatically routed by category '{category}'." if category else "Automatically routed.",
    )

    link = req.get_absolute_url()
    notify([student], f"Request {req.reference} submitted",
           f"Your {req.get_request_type_display().lower()} has been received and routed to {department or 'the university'}.",
           link, req, Notification.Kind.SUBMITTED)
    notify(department_handlers(department, confidential), f"New request {req.reference} for {department}",
           f"{req.get_request_type_display()}: {req.title}", link, req, Notification.Kind.ASSIGNED)
    log_action(student, "request.submitted", req,
               {"type": request_type, "department": str(department), "confidential": confidential}, http_request)
    return req


# --- Processing -------------------------------------------------------------------
@transaction.atomic
def change_status(req, user, new_status, message="", http_request=None):
    old = req.status
    if new_status == old:
        return req
    now = timezone.now()
    req.status = new_status

    if req.request_type == RequestType.ABSENCE and new_status in (Status.RESOLVED, Status.REJECTED):
        req.decision = Request.Decision.APPROVED if new_status == Status.RESOLVED else Request.Decision.REJECTED
        req.decision_note = message
        req.decided_by = user
        req.decided_at = now
    elif new_status == Status.REJECTED:
        req.decision = Request.Decision.REJECTED
        req.decision_note = message
        req.decided_by = user
        req.decided_at = now

    if new_status == Status.RESOLVED:
        req.resolved_at = now
    if new_status == Status.CLOSED:
        req.closed_at = now
    if new_status in (Status.UNDER_REVIEW, Status.IN_PROGRESS) and req.assigned_to_id is None and user.is_handler:
        if req.department_id == user.department_id or req.department_id in user.headed_department_ids:
            req.assigned_to = user
    req.save()

    _timeline(req, user, RequestComment.Kind.STATUS, message, old_status=old, new_status=new_status)

    label = Status(new_status).label
    kind = Notification.Kind.STATUS
    title = f"{req.reference} is now {label}"
    if new_status == Status.WAITING:
        kind, title = Notification.Kind.ACTION, f"More information needed on {req.reference}"
    elif req.decision and new_status in (Status.RESOLVED, Status.REJECTED):
        kind, title = Notification.Kind.DECISION, f"{req.reference} {req.get_decision_display().lower()}"
    notify([req.student], title, message or f"Status changed from {Status(old).label} to {label}.",
           req.get_absolute_url(), req, kind)
    if req.assigned_to_id and req.assigned_to_id != user.id:
        notify([req.assigned_to], title, f"Updated by {user.display_name}.", req.get_absolute_url(), req, kind)

    log_action(user, "request.status_changed", req, {"from": old, "to": new_status}, http_request)
    return req


@transaction.atomic
def add_comment(req, user, body, internal=False, files=None, http_request=None):
    internal = internal and user.is_handler
    kind = RequestComment.Kind.INTERNAL if internal else RequestComment.Kind.RESPONSE
    comment = _timeline(req, user, kind, body, internal=internal)
    _save_attachments(req, files, user, comment=comment, internal=internal)
    link = req.get_absolute_url()

    if user.is_student:
        recipients = [req.assigned_to] if req.assigned_to_id else department_handlers(req.department, req.is_confidential)
        notify(recipients, f"Student replied on {req.reference}", body[:180], link, req, Notification.Kind.INFO)
        if req.status == Status.WAITING:
            old = req.status
            req.status = Status.UNDER_REVIEW
            req.save(update_fields=["status", "updated_at"])
            _timeline(req, user, RequestComment.Kind.STATUS, "Student provided the requested information.",
                      old_status=old, new_status=Status.UNDER_REVIEW)
    elif not internal:
        notify([req.student], f"New response on {req.reference}", body[:180], link, req, Notification.Kind.INFO)

    log_action(user, "request.internal_note" if internal else "request.comment", req,
               {"attachments": len(files or [])}, http_request)
    return comment


@transaction.atomic
def assign(req, by, staff, note="", action=RequestAssignment.Action.ASSIGNED, http_request=None):
    req.assigned_to = staff
    if req.status in (Status.SUBMITTED, Status.ESCALATED, Status.RESOLVED):
        old = req.status
        req.status = Status.IN_PROGRESS if action == RequestAssignment.Action.RETURNED else Status.UNDER_REVIEW
        _timeline(req, by, RequestComment.Kind.STATUS, "", old_status=old, new_status=req.status)
    req.save()
    RequestAssignment.objects.create(
        request=req, action=action, from_department=req.department, to_department=req.department,
        assigned_to=staff, performed_by=by, note=note,
    )
    verb = {
        RequestAssignment.Action.TAKEN: f"{staff.display_name} took ownership of this case.",
        RequestAssignment.Action.RETURNED: f"Returned to {staff.display_name} for additional work.",
    }.get(action, f"Assigned to {staff.display_name}.")
    _timeline(req, by, RequestComment.Kind.SYSTEM, verb + (f" Note: {note}" if note else ""), internal=True)
    if staff.id != by.id:
        notify([staff], f"{req.reference} assigned to you" if action != RequestAssignment.Action.RETURNED
               else f"{req.reference} returned for additional work",
               note or req.title, req.get_absolute_url(), req, Notification.Kind.ASSIGNED)
    log_action(by, f"request.{action}", req, {"assigned_to": staff.display_name}, http_request)
    return req


@transaction.atomic
def escalate(req, by, target, note, http_request=None):
    """Escalate to the department head (target == 'head') or to another department/office."""
    old_status = req.status
    from_dept = req.department
    if target == "head":
        head = from_dept.head if from_dept else None
        req.assigned_to = head
        to_dept = from_dept
        recipients = [head]
        where = f"the head of {from_dept}"
    else:
        to_dept = target
        req.department = to_dept
        req.assigned_to = None
        recipients = department_handlers(to_dept, req.is_confidential)
        where = str(to_dept)
    req.status = Status.ESCALATED
    req.save()

    RequestAssignment.objects.create(
        request=req, action=RequestAssignment.Action.ESCALATED, from_department=from_dept,
        to_department=to_dept, assigned_to=req.assigned_to, performed_by=by, note=note,
    )
    _timeline(req, by, RequestComment.Kind.STATUS, f"Escalated to {where}. {note}", internal=True,
              old_status=old_status, new_status=Status.ESCALATED)
    _timeline(req, by, RequestComment.Kind.SYSTEM, f"Your request has been escalated to {where} for review.")

    link = req.get_absolute_url()
    notify(recipients, f"{req.reference} escalated to you", note, link, req, Notification.Kind.ESCALATED, exclude=by)
    notify([req.student], f"{req.reference} escalated", f"Your request has been escalated to {where}.",
           link, req, Notification.Kind.ESCALATED)
    log_action(by, "request.escalated", req, {"from": str(from_dept), "to": where, "note": note}, http_request)
    return req


def available_escalation_targets(req):
    return Department.objects.filter(is_active=True).exclude(pk=req.department_id)


@transaction.atomic
def delete_request(req, user, http_request=None):
    ref = req.reference
    log_action(user, "request.deleted", None, {
        "reference": ref,
        "title": req.title,
        "student": req.student.username,
        "department": req.department.name if req.department else "",
    }, http_request)
    req.delete()
