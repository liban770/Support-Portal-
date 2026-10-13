from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/img/favicon.svg", permanent=True)),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("requests/", include("cases.urls")),
]

handler403 = "core.views.permission_denied"
handler404 = "core.views.page_not_found"
