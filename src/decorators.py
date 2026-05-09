from django.core.exceptions import PermissionDenied
from functools import wraps
from .models import TeamMember

def require_role(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            member = TeamMember.objects.filter(
                user=request.user
            ).select_related('company').first()

            if not member or member.role not in allowed_roles:
                raise PermissionDenied

            request.member = member
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator