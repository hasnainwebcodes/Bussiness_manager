from django.core.exceptions import PermissionDenied
from functools import wraps
from .models import TeamMember, MemberRole

def require_role(allowed_roles):
    """
    Decorator to restrict access based on TeamMember roles.
    allowed_roles: List of integers from MemberRole (e.g. [20, 30])
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1. We assume your URL has a 'company_id' or we fetch from context
            # For simplicity, we fetch the first company the user belongs to
            member = TeamMember.objects.filter(user=request.user).first()
            
            if not member or member.role not in allowed_roles:
                raise PermissionDenied  # Redirects to a 403 page
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator