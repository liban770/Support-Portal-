from .models import SiteSettings


def portal(request):
    """Shared template context: settings, unread count and role navigation."""
    site = SiteSettings.load()
    ctx = {"site": site, "unread_count": 0, "nav": []}
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return ctx
    ctx["unread_count"] = user.notifications.filter(is_read=False).count()
    ctx["nav"] = build_nav(user)
    return ctx


def build_nav(user):
    """Sidebar sections for the current user's role. Each item: (label, url_name, icon, match_prefix)."""
    R = user.Role
    sections = []
    if user.role == R.STUDENT:
        sections.append(("Student Services", [
            ("Dashboard", "core:dashboard", "space_dashboard", "/dashboard"),
            ("Submit Request", "cases:submit", "add_circle", "/requests/new"),
            ("My Requests", "cases:my_requests", "assignment", "/requests/mine"),
            ("Request History", "cases:history", "history", "/requests/history"),
        ]))
    elif user.role == R.SUPERUSER:
        sections.append(("System", [
            ("System Dashboard", "core:dashboard", "space_dashboard", "/dashboard"),
            ("User Management", "accounts:user_list", "group", "/admin/users/"),
            ("Pending Validation", "accounts:pending_accounts", "how_to_reg", "/admin/pending"),
            ("Departments", "accounts:department_list", "domain", "/admin/departments"),
            ("Roles & Permissions", "accounts:roles", "admin_panel_settings", "/admin/roles"),
            ("Audit Logs", "core:audit_logs", "receipt_long", "/admin/audit"),
            ("System Settings", "core:system_settings", "settings", "/admin/settings"),
        ]))
    else:
        work = [
            ("Dashboard", "core:dashboard", "space_dashboard", "/dashboard"),
            ("Assigned Requests", "cases:queue", "inbox", "/requests/queue"),
        ]
        sections.append(("Workspace", work))
        if user.is_department_head:
            sections.append(("Department", [
                ("Department Requests", "cases:department_requests", "lan", "/requests/department"),
                ("Staff Management", "accounts:dept_staff", "badge", "/department/staff"),
                ("Department Reports", "cases:reports", "analytics", "/requests/reports"),
            ]))
        if user.role == R.ACADEMIC:
            sections.append(("Academic Office", [
                ("Academic Requests", "cases:academic_requests", "school", "/requests/academic"),
                ("Late-Class Reports", "cases:late_class_reports", "schedule", "/requests/late-class"),
                ("Academic Reports", "cases:reports", "analytics", "/requests/reports"),
            ]))
        if user.role == R.DIRECTOR:
            sections.append(("Student Affairs", [
                ("Authorized Requests", "cases:affairs_requests", "diversity_3", "/requests/affairs"),
                ("Follow-up & Escalations", "cases:escalations", "trending_up", "/requests/escalations"),
                ("Late-Class Follow-up", "cases:late_class_reports", "schedule", "/requests/late-class"),
                ("Summary Reports", "cases:reports", "analytics", "/requests/reports"),
            ]))
        if user.role == R.DEAN and not user.is_department_head:
            sections.append(("Department", [
                ("Department Reports", "cases:reports", "analytics", "/requests/reports"),
            ]))
    sections.append(("Account", [
        ("Notifications", "core:notifications", "notifications", "/notifications"),
        ("Profile", "accounts:profile", "person", "/account/profile"),
    ]))
    return sections
