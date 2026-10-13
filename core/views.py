from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import Department, User
from cases import permissions as perms
from cases.models import FINAL_STATUSES, OPEN_STATUSES, Request, RequestComment, RequestType, Status
from cases.views import build_stats

from .forms import SiteSettingsForm
from .models import AuditLog, Notification, SiteSettings
from .services import log_action


# =============================================================================
# Dashboards
# =============================================================================
@login_required
def dashboard(request):
    user = request.user
    R = User.Role
    if user.role == R.STUDENT:
        return _student_dashboard(request)
    if user.role == R.SUPERUSER:
        return _admin_dashboard(request)
    if user.role == R.DIRECTOR:
        return _director_dashboard(request)
    if user.role == R.ACADEMIC:
        return _academic_dashboard(request)
    if user.role == R.DEAN or user.is_department_head:
        return _dean_dashboard(request)
    return _staff_dashboard(request)


def _recent_activity(qs, include_internal=True, limit=6):
    entries = RequestComment.objects.filter(request__in=qs.values("pk")).select_related("author", "request")
    if not include_internal:
        entries = entries.filter(is_internal=False)
    return entries.order_by("-created_at")[:limit]


def _student_dashboard(request):
    user = request.user
    qs = perms.visible_requests(user)
    stats = {
        "total": qs.count(),
        "pending": qs.filter(status__in=OPEN_STATUSES).count(),
        "waiting": qs.filter(status=Status.WAITING).count(),
        "resolved": qs.filter(status__in=FINAL_STATUSES).count(),
        "this_month": qs.filter(created_at__month=timezone.now().month, created_at__year=timezone.now().year).count(),
    }
    return render(request, "dashboards/student.html", {
        "stats": stats,
        "recent": qs.order_by("-updated_at")[:5],
        "action_needed": qs.filter(status=Status.WAITING)[:3],
        "updates": user.notifications.all()[:5],
    })


def _staff_dashboard(request, template="dashboards/staff.html", extra=None):
    user = request.user
    qs = perms.visible_requests(user)
    mine = qs.filter(assigned_to=user)
    dept_qs = qs.filter(department_id=user.department_id) if user.department_id else qs.none()
    stats = {
        "assigned": mine.filter(status__in=OPEN_STATUSES).count(),
        "new": dept_qs.filter(status=Status.SUBMITTED, assigned_to__isnull=True).count(),
        "in_progress": qs.filter(status__in=[Status.IN_PROGRESS, Status.UNDER_REVIEW]).count(),
        "waiting": qs.filter(status=Status.WAITING).count(),
        "overdue": qs.filter(perms.overdue_q()).count(),
    }
    composition = build_stats(qs.filter(status__in=OPEN_STATUSES))
    ctx = {
        "stats": stats,
        "my_queue": mine.filter(status__in=OPEN_STATUSES).order_by("due_at")[:8],
        "new_requests": dept_qs.filter(status=Status.SUBMITTED, assigned_to__isnull=True).order_by("created_at")[:5],
        "activity": _recent_activity(qs),
        "type_chart": composition["type_chart"],
        "open_total": composition["total"],
    }
    if extra:
        ctx.update(extra)
    return render(request, template, ctx)


def _dean_dashboard(request):
    user = request.user
    ids = user.headed_department_ids
    qs = perms.visible_requests(user).filter(Q(department_id__in=ids) | Q(related_department_id__in=ids))
    stats = build_stats(qs)
    workload = (
        User.objects.filter(department_id__in=ids, account_status=User.Status.ACTIVE)
        .exclude(role=User.Role.STUDENT)
        .annotate(
            open_cases=Count("assigned_requests", filter=Q(assigned_requests__status__in=OPEN_STATUSES)),
            overdue_cases=Count("assigned_requests", filter=Q(
                assigned_requests__status__in=OPEN_STATUSES, assigned_requests__due_at__lt=timezone.now())),
        ).order_by("-open_cases")[:6]
    )
    max_load = max([w.open_cases for w in workload] + [1])
    return render(request, "dashboards/dean.html", {
        "stats": stats,
        "departments": Department.objects.filter(pk__in=ids),
        "review": qs.filter(Q(status=Status.ESCALATED) | Q(status=Status.SUBMITTED, assigned_to__isnull=True))
        .order_by("due_at")[:8],
        "overdue_list": qs.filter(perms.overdue_q()).order_by("due_at")[:5],
        "workload": workload,
        "max_load": max_load,
        "activity": _recent_activity(qs),
    })


def _academic_dashboard(request):
    user = request.user
    qs = perms.visible_requests(user)
    late = qs.filter(request_type=RequestType.LATE_CLASS)
    academic = qs.exclude(request_type=RequestType.LATE_CLASS)
    timetable = qs.filter(category__name__icontains="timetable")
    stats = {
        "academic": academic.filter(status__in=OPEN_STATUSES).count(),
        "late": late.filter(status__in=OPEN_STATUSES).count(),
        "late_total": late.count(),
        "timetable": timetable.filter(status__in=OPEN_STATUSES).count(),
        "pending": qs.filter(status__in=OPEN_STATUSES).count(),
        "overdue": qs.filter(perms.overdue_q()).count(),
        "resolved_30": qs.filter(resolved_at__gte=timezone.now() - timedelta(days=30)).count(),
    }
    top_courses = late.values("course").annotate(n=Count("id")).order_by("-n")[:5]
    return render(request, "dashboards/academic.html", {
        "stats": stats,
        "late_reports": late.filter(status__in=OPEN_STATUSES).order_by("-created_at")[:6],
        "pending_cases": academic.filter(status__in=OPEN_STATUSES).order_by("due_at")[:5],
        "recently_resolved": qs.filter(status__in=[Status.RESOLVED, Status.CLOSED]).order_by("-updated_at")[:5],
        "top_courses": top_courses,
        "chart": build_stats(qs)["status_chart"],
    })


def _director_dashboard(request):
    user = request.user
    qs = perms.visible_requests(user)
    stats = build_stats(qs)
    absence = qs.filter(request_type=RequestType.ABSENCE)
    by_department = list(
        qs.values("department__name").annotate(
            total=Count("id"),
            open=Count("id", filter=Q(status__in=OPEN_STATUSES)),
            overdue=Count("id", filter=Q(status__in=OPEN_STATUSES, due_at__lt=timezone.now())),
        ).order_by("-total")[:8]
    )
    recurring = qs.filter(request_type=RequestType.PROBLEM).values("category__name").annotate(n=Count("id")).order_by("-n")[:5]
    return render(request, "dashboards/director.html", {
        "stats": stats,
        "absence": {
            "total": absence.count(),
            "pending": absence.filter(status__in=OPEN_STATUSES).count(),
            "approved": absence.filter(decision=Request.Decision.APPROVED).count(),
            "rejected": absence.filter(decision=Request.Decision.REJECTED).count(),
        },
        "late_followup": qs.filter(request_type=RequestType.LATE_CLASS, status__in=OPEN_STATUSES).order_by("-created_at")[:5],
        "problems": qs.filter(request_type=RequestType.PROBLEM, status__in=OPEN_STATUSES).order_by("-created_at")[:5],
        "escalations": qs.filter(Q(status=Status.ESCALATED) | perms.overdue_q()).order_by("due_at")[:6],
        "by_department": by_department,
        "recurring": recurring,
    })


def _admin_dashboard(request):
    # Aggregate counts only — the Superuser has no access to request contents.
    users = User.objects.all()
    reqs = Request.objects.all()
    stats = {
        "users": users.count(),
        "active": users.filter(account_status=User.Status.ACTIVE).count(),
        "pending": users.filter(account_status=User.Status.PENDING).count(),
        "suspended": users.filter(account_status__in=[User.Status.SUSPENDED, User.Status.DEACTIVATED]).count(),
        "departments": Department.objects.filter(is_active=True).count(),
        "requests": reqs.count(),
        "open_requests": reqs.filter(status__in=OPEN_STATUSES).count(),
        "overdue": reqs.filter(status__in=OPEN_STATUSES, due_at__lt=timezone.now()).count(),
    }
    role_counts = [
        (label, users.filter(role=value).count()) for value, label in User.Role.choices
    ]
    platform = build_stats(reqs)
    return render(request, "dashboards/admin.html", {
        "stats": stats,
        "role_counts": role_counts,
        "pending_users": users.filter(account_status=User.Status.PENDING).select_related("department", "created_by")[:5],
        "recent_activity": AuditLog.objects.select_related("actor")[:8],
        "type_chart": platform["type_chart"],
        "trend_chart": platform["trend_chart"],
    })


# =============================================================================
# Notifications
# =============================================================================
@login_required
def notifications(request):
    qs = request.user.notifications.all()
    if request.GET.get("filter") == "unread":
        qs = qs.filter(is_read=False)
    return render(request, "core/notifications.html", {
        "page_obj": Paginator(qs, 20).get_page(request.GET.get("page")),
        "filter": request.GET.get("filter", ""),
    })


@login_required
def notification_open(request, pk):
    note = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=["is_read"])
    link = note.link or ""
    if link.startswith("/") and not link.startswith("//"):
        return redirect(link)
    return redirect("core:notifications")


@login_required
@require_POST
def notifications_mark_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("core:notifications")


# =============================================================================
# Superuser: audit logs & system settings
# =============================================================================
@role_required(User.Role.SUPERUSER)
def audit_logs(request):
    qs = AuditLog.objects.select_related("actor")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(action__icontains=q) | Q(target_repr__icontains=q) | Q(actor__first_name__icontains=q)
            | Q(actor__last_name__icontains=q) | Q(actor__email__icontains=q)
        )
    area = request.GET.get("area", "")
    if area:
        qs = qs.filter(action__startswith=f"{area}.")
    return render(request, "core/audit_logs.html", {
        "page_obj": Paginator(qs, 25).get_page(request.GET.get("page")),
        "areas": [("auth", "Authentication"), ("account", "Accounts"), ("department", "Departments"),
                  ("request", "Requests"), ("attachment", "Attachments"), ("settings", "Settings"),
                  ("report", "Reports")],
        "area": area,
    })


@role_required(User.Role.SUPERUSER)
def system_settings(request):
    site = SiteSettings.load()
    form = SiteSettingsForm(request.POST or None, instance=site)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            log_action(request.user, "settings.updated", obj, {"changed": form.changed_data}, request)
            messages.success(request, "System settings and institutional policies updated successfully.")
            return redirect("core:system_settings")
        messages.error(request, "Could not save settings. Please correct the highlighted errors.")
    return render(request, "core/system_settings.html", {"form": form, "site_obj": site})


# =============================================================================
# Error pages
# =============================================================================
def permission_denied(request, exception=None):
    return render(request, "errors/403.html", {"reason": str(exception) if exception else ""}, status=403)


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)
