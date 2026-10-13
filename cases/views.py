import csv
import mimetypes
from datetime import timedelta
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import Department, User
from core.models import SiteSettings
from core.services import log_action

from . import permissions as perms
from . import services
from .forms import (
    SUBMISSION_FORMS,
    AssignForm,
    CommentForm,
    EscalateForm,
    RequestFilterForm,
    StatusForm,
)
from .models import (
    FINAL_STATUSES,
    OPEN_STATUSES,
    Attachment,
    Request,
    RequestAssignment,
    RequestType,
    Status,
)


# =============================================================================
# Submission
# =============================================================================
TYPE_CARDS = [
    {
        "key": RequestType.ABSENCE.value, "title": "Absence & Leave", "icon": "event_busy",
        "text": "Absence excuses and leave requests with supporting documents.",
        "meta": "Department review", "meta_icon": "verified",
    },
    {
        "key": RequestType.PROBLEM.value, "title": "Student Problem", "icon": "report_problem",
        "text": "Facilities, student services, administrative or academic concerns.",
        "meta": "Routed by category", "meta_icon": "alt_route",
    },
    {
        "key": RequestType.LATE_CLASS.value, "title": "Late Class", "icon": "schedule",
        "text": "Report a scheduled class that did not start on time.",
        "meta": "Academic Office review", "meta_icon": "bolt",
    },
]


@role_required(User.Role.STUDENT)
def submit_request(request):
    site_settings = SiteSettings.load()
    max_active = site_settings.max_active_requests_per_student
    open_count = Request.objects.filter(student=request.user, status__in=OPEN_STATUSES).count()
    limit_reached = (max_active > 0 and open_count >= max_active)

    if limit_reached and request.method == "POST":
        messages.error(
            request,
            f"Active Request Limit Reached: You currently have {open_count} open request(s) undergoing review "
            f"(maximum allowed: {max_active}). To ensure timely processing and prevent duplicates, you cannot submit a new ticket until an existing one is resolved or closed."
        )
        return redirect("cases:my_requests")

    rtype = request.POST.get("request_type") or request.GET.get("type") or RequestType.ABSENCE
    if rtype not in SUBMISSION_FORMS:
        rtype = RequestType.ABSENCE
    form_class = SUBMISSION_FORMS[rtype]

    kwargs = {}
    if rtype in (RequestType.ABSENCE, RequestType.LATE_CLASS):
        kwargs["student"] = request.user

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, **kwargs)
        if form.is_valid():
            data = form.cleaned_data
            req = services.submit_request(
                request.user, rtype, data, files=data.get("attachments"), http_request=request
            )
            messages.success(request, f"Request {req.reference} submitted and routed to {req.department or 'the university'}.")
            return redirect(req.get_absolute_url())
        messages.error(request, "Please correct the highlighted fields.")
    else:
        form = form_class(**kwargs)

    return render(request, "cases/submit.html", {
        "form": form,
        "rtype": rtype,
        "type_cards": TYPE_CARDS,
        "type_label": RequestType(rtype).label,
        "limit_reached": limit_reached,
        "open_count": open_count,
        "max_active": max_active,
        "site_settings": site_settings,
    })


# =============================================================================
# Lists
# =============================================================================
SCOPES = {
    "mine": {"title": "My Submitted Requests", "eyebrow": "Student Support Desk",
             "subtitle": "Track progress, respond to university inquiries, and view outcomes for all your requests."},
    "history": {"title": "Request History", "eyebrow": "Student Support Desk",
                "subtitle": "Resolved, rejected and closed requests with their recorded decisions."},
    "queue": {"title": "Assigned Requests", "eyebrow": "Staff Workspace",
              "subtitle": "Requests assigned to you and your department. Review, respond and update status."},
    "department": {"title": "Department Requests", "eyebrow": "Dean Overview",
                   "subtitle": "All requests owned by or concerning the department(s) you head."},
    "academic": {"title": "Academic Requests", "eyebrow": "Academic Office",
                 "subtitle": "Academic matters, timetable and scheduling issues routed to the Academic Office."},
    "late_class": {"title": "Late-Class Reports", "eyebrow": "Lecture Verification",
                   "subtitle": "Reports are allegations to be verified against the timetable — not proof of misconduct."},
    "affairs": {"title": "Authorized Student-Support Requests", "eyebrow": "Student Affairs",
                "subtitle": "Cross-department student-support cases you are authorized to monitor."},
    "escalations": {"title": "Follow-up & Escalations", "eyebrow": "Monitoring",
                    "subtitle": "Escalated and overdue cases that need follow-up."},
}


def _scope_queryset(request, scope):
    user = request.user
    qs = perms.visible_requests(user)
    tab = request.GET.get("tab", "")
    tabs = []

    if scope in ("mine", "history"):
        if not user.is_student:
            raise PermissionDenied
        if scope == "history":
            qs = qs.filter(status__in=FINAL_STATUSES)
        else:
            base = qs
            tabs = [
                ("", "All", base.count()),
                ("active", "Active", base.filter(status__in=OPEN_STATUSES).exclude(status=Status.WAITING).count()),
                ("action", "Action Required", base.filter(status=Status.WAITING).count()),
                ("resolved", "Resolved", base.filter(status__in=FINAL_STATUSES).count()),
            ]
            if tab == "active":
                qs = qs.filter(status__in=OPEN_STATUSES).exclude(status=Status.WAITING)
            elif tab == "action":
                qs = qs.filter(status=Status.WAITING)
            elif tab == "resolved":
                qs = qs.filter(status__in=FINAL_STATUSES)
    else:
        if not user.is_handler:
            raise PermissionDenied
        if scope == "queue":
            base = qs
            mine = base.filter(assigned_to=user)
            unassigned = base.filter(assigned_to__isnull=True, status__in=OPEN_STATUSES)
            if user.department_id:
                unassigned = unassigned.filter(department_id=user.department_id)
            tabs = [
                ("", "Assigned to Me", mine.filter(status__in=OPEN_STATUSES).count()),
                ("unassigned", "Unassigned Queue", unassigned.count()),
                ("waiting", "Waiting for Student", base.filter(status=Status.WAITING).count()),
                ("all", "All Visible", base.count()),
            ]
            if tab == "unassigned":
                qs = unassigned
            elif tab == "waiting":
                qs = base.filter(status=Status.WAITING)
            elif tab == "all":
                qs = base
            else:
                qs = mine
        elif scope == "department":
            if not user.is_department_head:
                raise PermissionDenied
            ids = user.headed_department_ids
            qs = qs.filter(Q(department_id__in=ids) | Q(related_department_id__in=ids))
            tabs = [
                ("", "All", qs.count()),
                ("unassigned", "Unassigned", qs.filter(assigned_to__isnull=True, status__in=OPEN_STATUSES).count()),
                ("review", "Requiring Review", qs.filter(status=Status.ESCALATED).count()),
                ("overdue", "Overdue", qs.filter(perms.overdue_q()).count()),
            ]
            if tab == "unassigned":
                qs = qs.filter(assigned_to__isnull=True, status__in=OPEN_STATUSES)
            elif tab == "review":
                qs = qs.filter(status=Status.ESCALATED)
            elif tab == "overdue":
                qs = qs.filter(perms.overdue_q())
        elif scope == "academic":
            if user.role != User.Role.ACADEMIC:
                raise PermissionDenied
            qs = qs.exclude(request_type=RequestType.LATE_CLASS)
        elif scope == "late_class":
            if user.role not in (User.Role.ACADEMIC, User.Role.DIRECTOR) and not user.is_department_head:
                raise PermissionDenied
            qs = qs.filter(request_type=RequestType.LATE_CLASS)
        elif scope == "affairs":
            if user.role != User.Role.DIRECTOR:
                raise PermissionDenied
        elif scope == "escalations":
            if user.role != User.Role.DIRECTOR and not user.is_department_head:
                raise PermissionDenied
            qs = qs.filter(Q(status=Status.ESCALATED) | perms.overdue_q())
    return qs, tabs, tab


def _apply_filters(qs, form):
    if not form.is_valid():
        return qs
    d = form.cleaned_data
    if d.get("q"):
        term = d["q"].strip()
        qs = qs.filter(
            Q(reference__icontains=term) | Q(title__icontains=term) | Q(course__icontains=term)
            | Q(student__first_name__icontains=term) | Q(student__last_name__icontains=term)
            | Q(student__student_profile__student_id__icontains=term)
        )
    if d.get("type"):
        qs = qs.filter(request_type=d["type"])
    if d.get("status"):
        qs = qs.filter(status=d["status"])
    if d.get("department"):
        qs = qs.filter(department=d["department"])
    if d.get("overdue"):
        qs = qs.filter(perms.overdue_q())
    return qs


@login_required
def request_list(request, scope):
    if scope not in SCOPES:
        raise Http404
    qs, tabs, tab = _scope_queryset(request, scope)
    filter_form = RequestFilterForm(request.GET or None)
    qs = _apply_filters(qs, filter_form).order_by("-created_at")

    if request.GET.get("export") == "csv" and request.user.is_handler:
        return _export_csv(request, qs, scope)

    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "cases/list.html", {
        "scope": scope,
        "meta": SCOPES[scope],
        "page_obj": page,
        "tabs": tabs,
        "active_tab": tab,
        "filter_form": filter_form,
        "statuses": Status.choices,
        "types": RequestType.choices,
        "departments": Department.objects.filter(is_active=True),
        "now": timezone.now(),
        "is_student_view": request.user.is_student,
    })


def _export_csv(request, qs, scope):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="atu-requests-{scope}-{timezone.localdate()}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Reference", "Type", "Title", "Status", "Department", "Assigned to", "Submitted", "Due", "Overdue"])
    for r in qs[:5000]:
        writer.writerow([
            r.reference, r.get_request_type_display(), r.title, r.get_status_display(),
            r.department or "", r.assigned_to.display_name if r.assigned_to else "",
            timezone.localtime(r.created_at).strftime("%Y-%m-%d %H:%M"),
            timezone.localtime(r.due_at).strftime("%Y-%m-%d") if r.due_at else "", "Yes" if r.is_overdue else "No",
        ])
    log_action(request.user, "report.exported", None, {"scope": scope, "rows": qs.count()}, request)
    return response


@login_required
def search(request):
    q = request.GET.get("q", "").strip()
    qe = quote(q)
    user = request.user
    if user.is_sysadmin:
        return redirect(f"/admin/users/?q={qe}")
    if user.is_student:
        return redirect(f"/requests/mine/?q={qe}")
    match = perms.visible_requests(user).filter(reference__iexact=q).first()
    if match:
        return redirect(match.get_absolute_url())
    return redirect(f"/requests/queue/?tab=all&q={qe}")


# =============================================================================
# Detail & actions
# =============================================================================
def _get_visible_or_404(user, reference):
    # 404 (not 403) so the existence of other people's requests is not revealed.
    return get_object_or_404(perms.visible_requests(user), reference=reference)


@login_required
def request_detail(request, reference):
    user = request.user
    req = _get_visible_or_404(user, reference)
    show_internal = perms.can_view_internal(user)

    timeline = req.comments.select_related("author").prefetch_related("attachments")
    attachments = req.attachments.select_related("uploaded_by")
    if not show_internal:
        timeline = timeline.filter(is_internal=False)
        attachments = attachments.filter(is_internal=False)

    p = {
        "process": perms.can_process(user, req),
        "take": perms.can_take(user, req),
        "assign": perms.can_assign(user, req),
        "return": perms.can_return(user, req) and req.assigned_to_id is not None,
        "escalate": perms.can_escalate(user, req),
        "decide": perms.can_decide(user, req),
        "delete": perms.can_delete(user, req),
        "internal": perms.can_add_internal_note(user, req),
        "student_reply": perms.can_student_reply(user, req),
    }
    status_choices = perms.allowed_status_choices(user, req)

    assign_dept = req.department
    if req.related_department and perms.is_head_of(user, req.related_department_id) and not perms.is_head_of(user, req.department_id):
        assign_dept = req.related_department

    ctx = {
        "req": req,
        "timeline": timeline,
        "attachments": attachments,
        "assignments": req.assignments.select_related("to_department", "from_department", "assigned_to", "performed_by")
        if show_internal else [],
        "p": p,
        "show_internal": show_internal,
        "comment_form": CommentForm(
            allow_internal=p["internal"], force_internal=p["internal"] and not p["process"], prefix="c"
        ) if (p["process"] or p["internal"] or p["student_reply"]) else None,
        "status_form": StatusForm(choices=status_choices, request_obj=req, prefix="s") if status_choices else None,
        "assign_form": AssignForm(department=assign_dept, prefix="a") if p["assign"] else None,
        "return_form": AssignForm(department=assign_dept, note_required=True, prefix="r") if p["return"] else None,
        "escalate_form": EscalateForm(request_obj=req, user=user, prefix="e") if p["escalate"] else None,
        "can_upload_more": p["student_reply"],
    }
    return render(request, "cases/detail.html", ctx)


@login_required
@require_POST
def request_action(request, reference, action):
    user = request.user
    req = _get_visible_or_404(user, reference)
    url = req.get_absolute_url()

    if action == "comment":
        allowed = perms.can_process(user, req) or perms.can_add_internal_note(user, req) or perms.can_student_reply(user, req)
        if not allowed:
            raise PermissionDenied
        force_internal = perms.can_add_internal_note(user, req) and not perms.can_process(user, req)
        form = CommentForm(request.POST, request.FILES, allow_internal=perms.can_add_internal_note(user, req),
                           force_internal=force_internal, prefix="c")
        if form.is_valid():
            internal = force_internal or form.cleaned_data.get("is_internal", False)
            services.add_comment(req, user, form.cleaned_data["body"], internal=internal,
                                 files=form.cleaned_data.get("attachments"), http_request=request)
            messages.success(request, f"Internal note recorded on {req.reference}." if internal else f"Official response posted to {req.reference}.")
        else:
            _flash_errors(request, form)

    elif action == "status":
        choices = perms.allowed_status_choices(user, req)
        if not choices:
            raise PermissionDenied
        form = StatusForm(request.POST, choices=choices, request_obj=req, prefix="s")
        if form.is_valid():
            services.change_status(req, user, form.cleaned_data["status"], form.cleaned_data["message"].strip(),
                                   http_request=request)
            messages.success(request, f"Case {req.reference}: Status successfully updated to '{Status(form.cleaned_data['status']).label}'.")
        else:
            _flash_errors(request, form)

    elif action == "take":
        if not perms.can_take(user, req):
            raise PermissionDenied
        services.assign(req, user, user, action=RequestAssignment.Action.TAKEN, http_request=request)
        messages.success(request, f"Case {req.reference}: You have successfully taken ownership of this request.")

    elif action in ("assign", "return"):
        allowed = perms.can_assign(user, req) if action == "assign" else perms.can_return(user, req)
        if not allowed:
            raise PermissionDenied
        assign_dept = req.department
        if req.related_department and perms.is_head_of(user, req.related_department_id) and not perms.is_head_of(user, req.department_id):
            assign_dept = req.related_department
        form = AssignForm(request.POST, department=assign_dept, note_required=action == "return",
                          prefix="a" if action == "assign" else "r")
        if form.is_valid():
            services.assign(
                req, user, form.cleaned_data["staff"], form.cleaned_data["note"],
                action=RequestAssignment.Action.ASSIGNED if action == "assign" else RequestAssignment.Action.RETURNED,
                http_request=request,
            )
            messages.success(
                request,
                f"Case {req.reference} successfully assigned to {form.cleaned_data['staff'].display_name}."
                if action == "assign" else
                f"Case {req.reference} successfully returned to staff for additional work."
            )
        else:
            _flash_errors(request, form)

    elif action == "escalate":
        if not perms.can_escalate(user, req):
            raise PermissionDenied
        form = EscalateForm(request.POST, request_obj=req, user=user, prefix="e")
        if form.is_valid():
            target = form.cleaned_data["target"]
            services.escalate(req, user, target, form.cleaned_data["note"], http_request=request)
            target_name = f"the Head of Department" if target == "head" else getattr(target, "name", str(target))
            messages.success(request, f"Case {req.reference} successfully escalated to {target_name}.")
            if not perms.can_view(user, req):
                return redirect("core:dashboard")
        else:
            _flash_errors(request, form)
    else:
        raise Http404
    return redirect(url)


@login_required
@require_POST
def request_delete(request, reference):
    user = request.user
    req = _get_visible_or_404(user, reference)
    if not perms.can_delete(user, req):
        raise PermissionDenied
    verification = (request.POST.get("confirm_name") or request.POST.get("verification") or "").strip()
    if verification.upper() != req.reference.upper():
        messages.error(request, f"Deletion failed: Please type exactly '{req.reference}' to confirm deletion.")
        return redirect(req.get_absolute_url())
    ref = req.reference
    services.delete_request(req, user, http_request=request)
    messages.success(request, f"Case {ref} has been permanently deleted.")
    if user.is_department_head:
        return redirect("cases:department_requests")
    return redirect("core:dashboard")


def _flash_errors(request, form):
    messages.error(request, "Action unsuccessful. Please review and correct the errors below:")
    for field, errors in form.errors.items():
        label = form.fields[field].label if field in form.fields else ""
        for e in errors:
            messages.error(request, f"{label}: {e}" if label else e)


@login_required
def attachment_download(request, pk):
    att = get_object_or_404(Attachment.objects.select_related("request"), pk=pk)
    if not perms.can_view(request.user, att.request):
        raise Http404
    if att.is_internal and not perms.can_view_internal(request.user):
        raise Http404
    try:
        fh = att.file.open("rb")
    except FileNotFoundError:
        raise Http404("File no longer available.")
    content_type = mimetypes.guess_type(att.original_name)[0] or "application/octet-stream"
    inline = request.GET.get("inline") == "1" and content_type in ("application/pdf", "image/png", "image/jpeg")
    log_action(request.user, "attachment.downloaded", att.request, {"file": att.original_name}, request)
    return FileResponse(fh, as_attachment=not inline, filename=att.original_name, content_type=content_type)


# =============================================================================
# Reports
# =============================================================================
def build_stats(qs):
    now = timezone.now()
    total = qs.count()
    by_status = {row["status"]: row["n"] for row in qs.values("status").annotate(n=Count("id"))}
    by_type = {row["request_type"]: row["n"] for row in qs.values("request_type").annotate(n=Count("id"))}
    pending = sum(by_status.get(s, 0) for s in OPEN_STATUSES)
    resolved = by_status.get(Status.RESOLVED, 0) + by_status.get(Status.CLOSED, 0)
    overdue = qs.filter(status__in=OPEN_STATUSES, due_at__lt=now).count()
    six_months = now - timedelta(days=180)
    trend = list(
        qs.filter(created_at__gte=six_months).annotate(m=TruncMonth("created_at"))
        .values("m").annotate(n=Count("id")).order_by("m")
    )
    return {
        "total": total,
        "pending": pending,
        "resolved": resolved,
        "rejected": by_status.get(Status.REJECTED, 0),
        "overdue": overdue,
        "escalated": by_status.get(Status.ESCALATED, 0),
        "waiting": by_status.get(Status.WAITING, 0),
        "by_status": by_status,
        "by_type": by_type,
        "status_chart": {
            "labels": [s.label for s in Status],
            "values": [by_status.get(s.value, 0) for s in Status],
        },
        "type_chart": {
            "labels": [t.label for t in RequestType],
            "values": [by_type.get(t.value, 0) for t in RequestType],
        },
        "trend_chart": {
            "labels": [timezone.localtime(r["m"]).strftime("%b %Y") if r["m"] else "" for r in trend],
            "values": [r["n"] for r in trend],
        },
        "resolution_rate": round(100 * resolved / total) if total else 0,
    }


@login_required
def reports(request):
    user = request.user
    if not user.is_handler:
        raise PermissionDenied
    qs = perms.visible_requests(user)
    if user.is_department_head and user.role != User.Role.DIRECTOR:
        ids = user.headed_department_ids
        qs = qs.filter(Q(department_id__in=ids) | Q(related_department_id__in=ids))
        scope_label = "Department Reports"
    elif user.role == User.Role.ACADEMIC:
        scope_label = "Academic Reports"
    elif user.role == User.Role.DIRECTOR:
        scope_label = "Student Support Summary Reports"
    else:
        scope_label = "My Department Reports"

    period = request.GET.get("period", "all")
    if period in ("30", "90", "365"):
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=int(period)))

    stats = build_stats(qs)
    by_department = list(
        qs.values("department__name").annotate(
            total=Count("id"),
            open=Count("id", filter=Q(status__in=OPEN_STATUSES)),
            overdue=Count("id", filter=Q(status__in=OPEN_STATUSES, due_at__lt=timezone.now())),
            resolved=Count("id", filter=Q(status__in=[Status.RESOLVED, Status.CLOSED])),
        ).order_by("-total")
    )
    recurring = list(
        qs.filter(request_type=RequestType.PROBLEM).values("category__name").annotate(n=Count("id")).order_by("-n")[:6]
    )
    recurring_locations = list(
        qs.exclude(location="").values("location").annotate(n=Count("id")).filter(n__gte=2).order_by("-n")[:5]
    )
    late_courses = list(
        qs.filter(request_type=RequestType.LATE_CLASS).values("course").annotate(n=Count("id")).order_by("-n")[:6]
    )
    staff_workload = list(
        qs.filter(status__in=OPEN_STATUSES, assigned_to__isnull=False)
        .values("assigned_to__first_name", "assigned_to__last_name").annotate(n=Count("id")).order_by("-n")[:8]
    )
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="atu-report-{timezone.localdate()}.csv"'
        w = csv.writer(response)
        w.writerow(["Department", "Total", "Open", "Overdue", "Resolved/Closed"])
        for row in by_department:
            w.writerow([row["department__name"] or "Unassigned", row["total"], row["open"], row["overdue"], row["resolved"]])
        log_action(user, "report.exported", None, {"report": scope_label}, request)
        return response

    return render(request, "cases/reports.html", {
        "stats": stats, "scope_label": scope_label, "by_department": by_department, "recurring": recurring,
        "recurring_locations": recurring_locations, "late_courses": late_courses,
        "staff_workload": staff_workload, "period": period,
    })
