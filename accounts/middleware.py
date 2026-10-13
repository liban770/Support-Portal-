from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse


class AccountStatusMiddleware:
    """Enforces account status on every request.

    * Ends the session of any user whose account is no longer ACTIVE
      (e.g. suspended by the Superuser while logged in).
    * Forces users with a temporary password to change it first.
    """

    EXEMPT_PREFIXES = ("/static/", "/login/", "/logout/", "/password-reset/", "/account/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            path = request.path
            if user.account_status != user.Status.ACTIVE:
                logout(request)
                messages.error(request, "Your account is not active. Please contact the system administrator.")
                return redirect("accounts:login")
            if user.must_change_password and not path.startswith(self.EXEMPT_PREFIXES):
                change_url = reverse("accounts:password_change")
                if path != change_url:
                    messages.warning(request, "Please set a new password before continuing.")
                    return redirect(change_url)
        return self.get_response(request)
