from django.http import HttpResponseForbidden
from django.urls import resolve
from .models import TeamMember

PROTECTED_URL_NAMES = {
    'project_detail', 'add_task', 'update_task_progress',
    'update_task_status', 'projects', 'project_list',
    'create_projects', 'view_team', 'invite', 'team_settings',
}

class WorkspaceIsolationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            resolved = resolve(request.path_info)
            if resolved.url_name in PROTECTED_URL_NAMES:
                member = TeamMember.objects.filter(
                    user=request.user
                ).select_related('company').first()

                if member and member.company.is_banned:
                    return HttpResponseForbidden(
                        "This workspace has been suspended."
                    )

                request.current_company = member.company if member else None

        return self.get_response(request)