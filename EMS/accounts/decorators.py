from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def role_required(*allowed_roles):
    """
    Decorator that checks if the logged-in user has one of the allowed roles.
    Usage: @role_required('admin', 'hr')
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            messages.error(
                request,
                'You do not have permission to access this page.'
            )
            return redirect('dashboard:home')
        return wrapper
    return decorator


def admin_required(view_func):
    """Only admin users can access this view."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_admin_user:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Only administrators can access this page.')
        return redirect('dashboard:home')
    return wrapper


def hr_or_admin_required(view_func):
    """Admin or HR users can access this view."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.can_modify_attendance:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Only Admin or HR can access this page.')
        return redirect('dashboard:home')
    return wrapper


def all_authenticated(view_func):
    """Any authenticated user can access (including owner - view only)."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper
