from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.PortalLogoutView.as_view(), name="logout"),
    path("password-reset/", views.PortalPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", views.PortalPasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
    path("account/profile/", views.profile, name="profile"),
    path("account/password/", views.password_change, name="password_change"),
    # Superuser administration
    path("admin/users/", views.user_list, name="user_list"),
    path("admin/users/new/", views.user_create, name="user_create"),
    path("admin/users/import/", views.student_import, name="student_import"),
    path("admin/users/<int:pk>/", views.user_edit, name="user_edit"),
    path("admin/users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("admin/users/<int:pk>/<str:action>/", views.user_action, name="user_action"),
    path("admin/pending/", views.pending_accounts, name="pending_accounts"),
    path("admin/roles/", views.roles, name="roles"),
    path("admin/departments/", views.department_list, name="department_list"),
    path("admin/departments/new/", views.department_form, name="department_create"),
    path("admin/departments/<int:pk>/", views.department_detail, name="department_detail"),
    path("admin/departments/<int:pk>/edit/", views.department_form, name="department_edit"),
    path("admin/departments/<int:pk>/delete/", views.department_delete, name="department_delete"),
    # Department head
    path("department/staff/", views.dept_staff, name="dept_staff"),
]
