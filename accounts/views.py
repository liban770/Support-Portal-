import secrets
import string

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from cases.models import OPEN_STATUSES, Request, Status
from core.models import Notification
from core.services import log_action, notify

from .decorators import department_head_required, role_required
from .forms import (
    AdminUserForm,
    DeanStaffForm,
    DepartmentForm,
    LoginForm,
    ProfileForm,
    StudentImportForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)
from .models import Department, StaffProfile, StudentProfile, User

SU = User.Role.SUPERUSER


def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(length - 2))
    return core + secrets.choice("!@#$%") + secrets.choice(string.digits)


# =============================================================================
# Authentication
# =============================================================================
def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from django.contrib.auth import authenticate

        user = authenticate(request, username=form.cleaned_data["username"], password=form.cleaned_data["password"])
        if user is None:
            log_action(None, "auth.login_failed", None, {"username": form.cleaned_data["username"][:80]}, request)
            messages.error(request, "Invalid credentials. Check your email / student ID and password.")
        elif user.account_status != User.Status.ACTIVE:
            log_action(user, "auth.login_blocked", user, {"status": user.account_status}, request)
            template = "accounts/account_pending.html" if user.account_status == User.Status.PENDING else "accounts/access_denied.html"
            return render(request, template, {"blocked_user": user}, status=403)
        else:
            login(request, user)
            request.session.set_expiry(60 * 60 * 24 * 30 if form.cleaned_data.get("remember") else 0)
            log_action(user, "auth.login", user, {}, request)
            messages.success(request, f"Welcome back, {user.display_name}! Signed in successfully as {user.get_role_display()}.")
            nxt = request.GET.get("next", "")
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect("core:dashboard")
    return render(request, "accounts/login.html", {"form": form})


class PortalLogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            log_action(request.user, "auth.logout", request.user, {}, request)
            messages.info(request, "You have been signed out successfully.")
        return super().post(request, *args, **kwargs)


class PortalPasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/emails/password_reset_email.txt"
    subject_template_name = "accounts/emails/password_reset_subject.txt"
    form_class = StyledPasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")


class PortalPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


@login_required
def password_change(request):
    is_first_login = request.user.must_change_password or not request.user.has_usable_password()
    FormClass = StyledSetPasswordForm if is_first_login else StyledPasswordChangeForm
    form = FormClass(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save()
        update_session_auth_hash(request, user)
        log_action(user, "auth.password_changed", user, {}, request)
        messages.success(request, "Your password has been changed successfully.")
        return redirect("core:dashboard")
    return render(request, "accounts/password_change.html", {"form": form, "is_first_login": is_first_login})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request.user, "account.profile_updated", request.user, {}, request)
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


# =============================================================================
# Superuser: user management & validation
# =============================================================================
@role_required(SU)
def user_list(request):
    qs = User.objects.select_related("department", "student_profile", "staff_profile").order_by("-date_joined")
    tab = request.GET.get("tab", "")
    counts = {
        "all": User.objects.count(),
        "staff": User.objects.exclude(role=User.Role.STUDENT).count(),
        "students": User.objects.filter(role=User.Role.STUDENT).count(),
        "pending": User.objects.filter(account_status=User.Status.PENDING).count(),
    }
    if tab == "staff":
        qs = qs.exclude(role=User.Role.STUDENT)
    elif tab == "students":
        qs = qs.filter(role=User.Role.STUDENT)
    elif tab == "pending":
        qs = qs.filter(account_status=User.Status.PENDING)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
            | Q(username__icontains=q) | Q(student_profile__student_id__icontains=q)
        )
    for key, field in (("role", "role"), ("status", "account_status"), ("department", "department_id")):
        value = request.GET.get(key)
        if value:
            qs = qs.filter(**{field: value})

    stats = {
        "total": counts["all"],
        "active": User.objects.filter(account_status=User.Status.ACTIVE).count(),
        "pending": counts["pending"],
        "inactive": User.objects.filter(
            account_status__in=[User.Status.SUSPENDED, User.Status.DEACTIVATED, User.Status.REJECTED]
        ).count(),
    }
    return render(request, "accounts/user_list.html", {
        "page_obj": Paginator(qs, 15).get_page(request.GET.get("page")),
        "tab": tab, "counts": counts, "stats": stats,
        "roles": User.Role.choices, "statuses": User.Status.choices,
        "departments": Department.objects.all(),
    })


@role_required(SU)
def pending_accounts(request):
    qs = User.objects.filter(account_status=User.Status.PENDING).select_related(
        "department", "created_by", "staff_profile", "student_profile"
    ).order_by("date_joined")
    return render(request, "accounts/pending_accounts.html", {"pending": qs})


@role_required(SU)
@transaction.atomic
def user_create(request):
    form = AdminUserForm(request.POST or None, acting_user=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        password = form.cleaned_data.get("password") or generate_temp_password()
        user.set_password(password)
        user.must_change_password = not form.cleaned_data.get("password")
        user.created_by = request.user
        user.set_status(User.Status.ACTIVE, by=request.user)  # created & verified by the Superuser
        user.save()
        form.save_profiles(user)
        log_action(request.user, "account.created", user, {"role": user.role, "department": str(user.department or "")}, request)
        if user.must_change_password:
            messages.success(request, f"Account created for {user.display_name}. Temporary password: {password} "
                                      "(shown once — share it securely).")
        else:
            messages.success(request, f"Account created for {user.display_name}.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form, "is_create": True})


@role_required(SU)
@transaction.atomic
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    old = {"role": target.role, "department": str(target.department or "")}
    form = AdminUserForm(request.POST or None, instance=target, acting_user=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        new_pwd = form.cleaned_data.get("password")
        if new_pwd:
            user.set_password(new_pwd)
            user.must_change_password = False
            user.save()
            log_action(request.user, "account.password_reset", user, {"by_admin": True}, request)
        form.save_profiles(user)
        new = {"role": user.role, "department": str(user.department or "")}
        log_action(request.user, "account.updated", user, {"before": old, "after": new}, request)
        if old["role"] != new["role"]:
            notify([user], "Your role was updated", f"Your role is now {user.get_role_display()}.",
                   "/account/profile/", kind=Notification.Kind.ACCOUNT)
        msg = f"Account updated for {user.display_name}."
        if new_pwd:
            msg += " New password was set successfully."
        messages.success(request, msg)
        return redirect("accounts:user_list")
    activity = target.audit_entries.all()[:10]
    return render(request, "accounts/user_form.html", {"form": form, "target": target, "activity": activity})


USER_ACTIONS = {
    # action: (allowed current statuses, new status, audit action, message)
    "validate": ({User.Status.PENDING}, User.Status.ACTIVE, "account.validated", "Account validated and activated."),
    "reject": ({User.Status.PENDING}, User.Status.REJECTED, "account.rejected", "Account request rejected."),
    "activate": ({User.Status.SUSPENDED, User.Status.DEACTIVATED, User.Status.REJECTED}, User.Status.ACTIVE,
                 "account.activated", "Account activated."),
    "suspend": ({User.Status.ACTIVE}, User.Status.SUSPENDED, "account.suspended", "Account suspended."),
    "deactivate": ({User.Status.ACTIVE, User.Status.SUSPENDED}, User.Status.DEACTIVATED,
                   "account.deactivated", "Account deactivated."),
}


@role_required(SU)
@require_POST
@transaction.atomic
def user_action(request, pk, action):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        # Users can never approve or change their own status/privileges.
        raise PermissionDenied("You cannot change your own account status.")
    nxt = request.POST.get("next") or "accounts:user_list"

    if action == "reset_password":
        temp = generate_temp_password()
        target.set_password(temp)
        target.must_change_password = True
        target.save()
        log_action(request.user, "account.password_reset", target, {}, request)
        messages.success(request, f"Temporary password for {target.display_name}: {temp} (shown once — share it securely).")
        return redirect(nxt)

    if action not in USER_ACTIONS:
        raise PermissionDenied
    allowed_from, new_status, audit, msg = USER_ACTIONS[action]
    if target.account_status not in allowed_from:
        messages.error(request, f"Cannot {action} an account that is {target.get_account_status_display().lower()}.")
        return redirect(nxt)

    old_status = target.account_status
    target.set_status(new_status, by=request.user)
    temp_password = None
    if action == "validate":
        target.validated_by = request.user
        target.validated_at = timezone.now()
        if not target.has_usable_password():
            temp_password = generate_temp_password()
            target.set_password(temp_password)
            target.must_change_password = True
    target.save()
    log_action(request.user, audit, target, {"from": old_status, "to": new_status,
                                             "reason": request.POST.get("reason", "")[:300]}, request)

    if action in ("validate", "reject"):
        approved = action == "validate"
        notify([target], "Your account was approved" if approved else "Your account request was rejected",
               "You can now sign in to the ATU Support Portal." if approved else request.POST.get("reason", ""),
               "/", kind=Notification.Kind.ACCOUNT)
        if target.created_by_id and target.created_by_id != request.user.pk:
            notify([target.created_by], f"Account for {target.display_name} {'approved' if approved else 'rejected'}",
                   f"{target.email}", "/department/staff/", kind=Notification.Kind.ACCOUNT)
    if temp_password:
        msg += f" Temporary password: {temp_password} (shown once — share it securely)."
    messages.success(request, msg)
    return redirect(nxt)


@role_required(SU)
@require_POST
@transaction.atomic
def user_delete(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "Security restriction: You cannot delete your own account.")
        return redirect("accounts:user_list")

    if target.role == User.Role.SUPERUSER and User.objects.filter(role=User.Role.SUPERUSER).count() <= 1:
        messages.error(request, "Security restriction: You cannot delete the sole remaining System Administrator.")
        return redirect("accounts:user_list")

    expected_name = target.username
    confirm_name = request.POST.get("confirm_name", "").strip()

    if confirm_name != expected_name:
        messages.error(
            request,
            f"Deletion cancelled: Verification name mismatch. You entered '{confirm_name}', but '{expected_name}' is required to confirm deletion."
        )
        return redirect("accounts:user_list")

    target_display = target.display_name
    target_username = target.username
    target_role = target.get_role_display()

    # Log action before deletion so target metadata is recorded
    log_action(
        request.user,
        "account.deleted",
        target,
        {
            "deleted_username": target_username,
            "deleted_display_name": target_display,
            "role": target.role,
            "email": target.email,
        },
        request,
    )

    # Unlink headed departments if any
    Department.objects.filter(head=target).update(head=None)

    # Clean up submitted requests to bypass ProtectedError
    target.submitted_requests.all().delete()

    target.delete()
    messages.success(request, f"User account '{target_username}' ({target_display} · {target_role}) has been permanently deleted.")
    return redirect("accounts:user_list")


@role_required(SU)
def student_import(request):
    form = StudentImportForm(request.POST or None, request.FILES or None)
    results = None
    if request.method == "POST" and form.is_valid():
        results = {"created": [], "skipped": []}
        depts = {d.code.upper(): d for d in Department.objects.all()}
        with transaction.atomic():
            for i, row in enumerate(form.cleaned_data["csv_file"], start=2):
                sid, email = row.get("student_id", ""), row.get("email", "").lower()
                if not sid or not email:
                    results["skipped"].append((i, sid or email, "Missing student ID or email"))
                    continue
                if StudentProfile.objects.filter(student_id__iexact=sid).exists() or \
                        User.objects.filter(Q(email__iexact=email) | Q(username__iexact=sid)).exists():
                    results["skipped"].append((i, sid, "Already registered"))
                    continue
                temp = generate_temp_password()
                user = User(
                    username=sid, email=email, first_name=row.get("first_name", ""),
                    last_name=row.get("last_name", ""), role=User.Role.STUDENT,
                    department=depts.get(row.get("department_code", "").upper()),
                    must_change_password=True, created_by=request.user,
                )
                user.set_password(temp)
                user.set_status(User.Status.ACTIVE, by=request.user)
                user.save()
                year = row.get("year_of_study", "")
                StudentProfile.objects.create(
                    user=user, student_id=sid, program=row.get("program", ""),
                    year_of_study=int(year) if year.isdigit() else None, verified_from_register=True,
                )
                results["created"].append((user, temp))
        log_action(request.user, "account.students_imported", None,
                   {"created": len(results["created"]), "skipped": len(results["skipped"])}, request)
        messages.success(request, f"Imported {len(results['created'])} students; skipped {len(results['skipped'])}.")
    return render(request, "accounts/student_import.html", {"form": form, "results": results})


@role_required(SU)
def roles(request):
    role_counts = dict(User.objects.values_list("role").annotate(n=Count("id")))
    matrix = [
        ("Submit & track own requests", ["student"]),
        ("View department requests (non-confidential)", ["staff", "dean", "academic", "director"]),
        ("Respond, add internal notes, update status", ["staff", "dean", "academic", "director"]),
        ("Assign / return cases to staff", ["dean"]),
        ("Approve / reject absence & leave", ["dean", "academic", "director"]),
        ("Escalate to dean or another office", ["staff", "dean", "academic", "director"]),
        ("Cross-department student-support monitoring", ["director"]),
        ("Create staff accounts (pending validation)", ["dean"]),
        ("Validate / activate / suspend accounts", ["superuser"]),
        ("Manage departments & system settings", ["superuser"]),
        ("View audit logs & platform statistics", ["superuser"]),
    ]
    return render(request, "accounts/roles.html", {
        "roles": User.Role.choices, "role_counts": role_counts, "matrix": matrix,
    })


# =============================================================================
# Superuser: departments
# =============================================================================
@role_required(SU)
def department_list(request):
    depts = Department.objects.select_related("head").annotate(
        member_count=Count("members", distinct=True),
        open_count=Count("requests", filter=Q(requests__status__in=OPEN_STATUSES), distinct=True),
        total_count=Count("requests", distinct=True),
    )
    return render(request, "accounts/department_list.html", {"departments": depts})


@role_required(SU)
def department_form(request, pk=None):
    dept = get_object_or_404(Department, pk=pk) if pk else None
    old_head = dept.head_id if dept else None
    form = DepartmentForm(request.POST or None, instance=dept)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        log_action(request.user, "department.updated" if dept else "department.created", obj,
                   {"head": str(obj.head or "")}, request)
        if obj.head_id and obj.head_id != old_head:
            notify([obj.head], f"You are now head of {obj.name}", "You can assign cases and manage department staff.",
                   "/requests/department/", kind=Notification.Kind.ACCOUNT)
        messages.success(request, f"Department '{obj.name}' saved.")
        return redirect("accounts:department_detail", pk=obj.pk)
    return render(request, "accounts/department_form.html", {"form": form, "dept": dept})


@role_required(SU)
def department_detail(request, pk):
    dept = get_object_or_404(Department.objects.select_related("head"), pk=pk)
    reqs = Request.objects.filter(department=dept)
    stats = {
        "total": reqs.count(),
        "open": reqs.filter(status__in=OPEN_STATUSES).count(),
        "overdue": reqs.filter(status__in=OPEN_STATUSES, due_at__lt=timezone.now()).count(),
        "resolved": reqs.filter(status__in=[Status.RESOLVED, Status.CLOSED]).count(),
    }
    members = dept.members.select_related("staff_profile").exclude(role=User.Role.STUDENT)
    history = dept.requests.order_by("-created_at").values("reference", "request_type", "status", "created_at")[:10]
    return render(request, "accounts/department_detail.html", {
        "dept": dept, "stats": stats, "members": members,
        "student_count": dept.members.filter(role=User.Role.STUDENT).count(), "history": history,
    })


@role_required(SU)
@require_POST
@transaction.atomic
def department_delete(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    expected_name = dept.name
    confirm_name = request.POST.get("confirm_name", "").strip()

    if confirm_name != expected_name:
        messages.error(
            request,
            f"Deletion cancelled: Verification name mismatch. You entered '{confirm_name}', but '{expected_name}' is required to confirm deletion."
        )
        return redirect("accounts:department_detail", pk=dept.pk)

    dept_name = dept.name
    dept_code = dept.code

    # Log action before deletion so dept metadata is recorded in audit entry
    log_action(
        request.user,
        "department.deleted",
        dept,
        {
            "deleted_name": dept_name,
            "deleted_code": dept_code,
        },
        request,
    )

    # Unlink department members and requests
    User.objects.filter(department=dept).update(department=None)
    Request.objects.filter(department=dept).update(department=None)
    Request.objects.filter(related_department=dept).update(related_department=None)

    dept.delete()
    messages.success(request, f"Department '{dept_name}' ({dept_code}) has been permanently deleted.")
    return redirect("accounts:department_list")


# =============================================================================
# Dean / head: staff management within the department
# =============================================================================
@department_head_required
@transaction.atomic
def dept_staff(request):
    head_ids = request.user.headed_department_ids
    departments = Department.objects.filter(pk__in=head_ids)
    dept = departments.filter(pk=request.GET.get("dept") or request.POST.get("dept")).first() or departments.first()

    form = DeanStaffForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.role = User.Role.STAFF          # forced: heads cannot grant other roles
        user.department = dept               # forced: only their own department
        user.account_status = User.Status.PENDING
        user.created_by = request.user
        user.set_unusable_password()
        user.save()
        StaffProfile.objects.create(user=user, staff_id=form.cleaned_data.get("staff_id", ""),
                                    position=form.cleaned_data["position"])
        log_action(request.user, "account.created_pending", user, {"department": dept.name}, request)
        admins = User.objects.filter(role=SU, account_status=User.Status.ACTIVE)
        notify(admins, f"Account pending validation: {user.display_name}",
               f"Requested by {request.user.display_name} for {dept.name}.", "/admin/pending/",
               kind=Notification.Kind.ACCOUNT)
        messages.success(request, f"Staff account for {user.display_name} created and sent to the Superuser for validation.")
        return redirect(f"{request.path}?dept={dept.pk}")

    members = (
        User.objects.filter(department=dept).exclude(role=User.Role.STUDENT).select_related("staff_profile")
        .annotate(
            open_cases=Count("assigned_requests", filter=Q(assigned_requests__status__in=OPEN_STATUSES)),
            overdue_cases=Count("assigned_requests", filter=Q(assigned_requests__status__in=OPEN_STATUSES,
                                                               assigned_requests__due_at__lt=timezone.now())),
            resolved_cases=Count("assigned_requests", filter=Q(assigned_requests__status__in=[Status.RESOLVED, Status.CLOSED])),
        )
    )
    return render(request, "accounts/dept_staff.html", {
        "dept": dept, "departments": departments, "members": members, "form": form,
    })
