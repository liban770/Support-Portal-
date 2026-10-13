from django.urls import path

from . import views

app_name = "cases"

urlpatterns = [
    path("new/", views.submit_request, name="submit"),
    path("search/", views.search, name="search"),
    path("reports/", views.reports, name="reports"),
    path("mine/", views.request_list, {"scope": "mine"}, name="my_requests"),
    path("history/", views.request_list, {"scope": "history"}, name="history"),
    path("queue/", views.request_list, {"scope": "queue"}, name="queue"),
    path("department/", views.request_list, {"scope": "department"}, name="department_requests"),
    path("academic/", views.request_list, {"scope": "academic"}, name="academic_requests"),
    path("late-class/", views.request_list, {"scope": "late_class"}, name="late_class_reports"),
    path("affairs/", views.request_list, {"scope": "affairs"}, name="affairs_requests"),
    path("affairs/", views.request_list, {"scope": "affairs"}, name="affairs"),
    path("escalations/", views.request_list, {"scope": "escalations"}, name="escalations"),
    path("attachments/<int:pk>/", views.attachment_download, name="attachment"),
    path("<str:reference>/", views.request_detail, name="detail"),
    path("<str:reference>/delete/", views.request_delete, name="delete"),
    path("<str:reference>/<str:action>/", views.request_action, name="action"),
]
