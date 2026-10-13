from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "core"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="core:dashboard", permanent=False)),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read-all/", views.notifications_mark_all, name="notifications_mark_all"),
    path("notifications/<int:pk>/", views.notification_open, name="notification_open"),
    path("admin/audit/", views.audit_logs, name="audit_logs"),
    path("admin/settings/", views.system_settings, name="system_settings"),
]
