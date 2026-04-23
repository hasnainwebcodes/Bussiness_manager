from django.contrib import admin
from .models import (
    CustomUser,
    Company,
    TeamMember,
    Invite,
    Project,
    CompanySubscription,
)


# ====================== CUSTOM USER ======================
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['email']
    ordering = ['-date_joined']


# ====================== COMPANY ======================
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'plan', 'is_banned', 'last_active', 'created_at']
    list_filter = ['plan', 'is_banned']
    search_fields = ['name', 'owner__email']
    ordering = ['-last_active']


# ====================== TEAM MEMBER ======================
@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'role', 'created_at']
    list_filter = ['role', 'company']
    search_fields = ['user__email', 'company__name']
    raw_id_fields = ['user', 'company']   # Better for large data


# ====================== INVITE ======================
@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ['email', 'company', 'role', 'status', 'invited_by', 'created_at']
    list_filter = ['status', 'role', 'company']
    search_fields = ['email', 'company__name']
    ordering = ['-created_at']


# ====================== PROJECT ======================
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'created_at']
    list_filter = ['company']
    search_fields = ['name', 'company__name']
    ordering = ['-created_at']


# ====================== COMPANY SUBSCRIPTION ======================
@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(admin.ModelAdmin):
    list_display = ['company', 'stripe_subscription_id', 'is_active', 'current_period_end']
    list_filter = ['is_active']
    search_fields = ['company__name', 'stripe_subscription_id']
    readonly_fields = ['created_at']

# Customize Admin Site Title
admin.site.site_header = "BusinessManager Admin"
admin.site.site_title = "BusinessManager Admin"
admin.site.index_title = "Welcome to BusinessManager Administration"