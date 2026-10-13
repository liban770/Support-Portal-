from django import template
from django.utils.html import format_html

from cases.models import STATUS_STYLES, Status

register = template.Library()


@register.simple_tag
def status_badge(status, label=None):
    bg, fg = STATUS_STYLES.get(status, ("#F1F5F9", "#475569"))
    try:
        text = label or Status(status).label
    except ValueError:
        text = label or status
    return format_html(
        '<span class="badge" style="background:{};color:{}"><span class="badge-dot" style="background:{}"></span>{}</span>',
        bg, fg, fg, text,
    )


@register.simple_tag
def account_badge(user):
    colors = {
        "active": ("#DCFCE7", "#166534"),
        "pending": ("#FEF3C7", "#92400E"),
        "suspended": ("#FEE2E2", "#991B1B"),
        "deactivated": ("#F1F5F9", "#475569"),
        "rejected": ("#FEE2E2", "#991B1B"),
    }
    bg, fg = colors.get(user.account_status, ("#F1F5F9", "#475569"))
    return format_html(
        '<span class="badge" style="background:{};color:{}"><span class="badge-dot" style="background:{}"></span>{}</span>',
        bg, fg, fg, user.get_account_status_display(),
    )


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    """Return the current querystring with some keys replaced (used for pagination/tabs)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    if "page" not in kwargs:
        params.pop("page", None)
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"


@register.simple_tag(takes_context=True)
def nav_active(context, prefix):
    path = context["request"].path
    if prefix == "/dashboard":
        return path in ("/", "/dashboard/")
    return path.startswith(prefix)


@register.filter
def pct(value, total):
    try:
        return round(100 * float(value) / float(total)) if total else 0
    except (TypeError, ValueError):
        return 0


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None
