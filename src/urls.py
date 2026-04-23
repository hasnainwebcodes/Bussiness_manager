from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.index, name="home"),
    path('register/', views.register, name="register"),
    path('verify/<int:user_id>/<str:token>/', views.verify_email, name="verify_email"),
    path('user_login/', views.user_login, name="user_login"),
    path('user_logout/', views.user_logout, name="user_logout"),
    path('companies/new/', views.create_company, name="create_company"),
    path('dashboard/', views.dashboard, name="dashboard"),
    path('team/', views.view_team, name="view_team"),
    path('team/invite/', views.invite, name="invite"),
    path('invite/accept/<str:token>/', views.accept_invite, name="accept_invite"),
    path('team/role/<str:user_id>/toggle/', views.change_user_role, name="change_user_role"),
    path('projects/', views.projects, name="projects"),
    path('projects/create/', views.create_projects, name="create_projects"),
    path('billing/', views.billing, name="billing"),
    path('billing/upgrade/pro/', views.upgrade_pro, name="upgrade_pro"),
    path('billing/checkout-session/', views.checkout_session, name="checkout_session"),
    path('webhook/stripe/', views.stripe_webhook, name="webhook_stripe"),
    path('billing/success/', views.billing_success, name="billing_success"),
    path('billing/cancel/', views.billing_cancel, name="billing_cancel"),
    path('company/admin/', views.admin_dashboard, name="admin"),
    path('company/admin/<str:pk>/', views.company_single, name="company_single"),
    path('company/admin/<str:pk>/upgrade/', views.company_upgrade, name="company_upgrade"),
    path('company/admin/<str:pk>/ban/', views.company_ban, name="company_ban"),
]