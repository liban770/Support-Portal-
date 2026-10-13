from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .models import User


class EmailOrUsernameBackend(ModelBackend):
    """Authenticate with either institutional email or username / student ID.

    Accounts that are pending, suspended, etc. are still *identified* here so
    the login view can show the correct "Account Pending" / "Access Denied"
    page; the login view itself refuses to start a session for them.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if not username or not password:
            return None
        username = username.strip()
        try:
            user = User.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
        except User.DoesNotExist:
            User().set_password(password)  # mitigate timing attacks
            return None
        except User.MultipleObjectsReturned:
            return None
        if user.check_password(password):
            return user
        return None

    def user_can_authenticate(self, user):
        return True

    def get_user(self, user_id):
        try:
            return User.objects.select_related("department").get(pk=user_id)
        except User.DoesNotExist:
            return None
