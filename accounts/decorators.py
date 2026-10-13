from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Restrict a view to users holding one of the given roles (server-side)."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied("Your role does not have access to this page.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def department_head_required(view_func):
    """Restrict a view to users who head at least one active department."""

    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_department_head:
            raise PermissionDenied("Only department heads can access this page.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def handler_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_handler:
            raise PermissionDenied("This workspace is only available to university staff.")
        return view_func(request, *args, **kwargs)

    return _wrapped
