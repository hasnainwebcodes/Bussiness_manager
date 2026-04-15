from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from uuid import uuid4

from .models import (
    CustomUser,
    Company,
    TeamMember,
    MemberRole,
    Invite,
    Project,
    CompanySubscription,
)
import stripe
from django.views.decorators.http import require_http_methods
import logging

logger = logging.getLogger(__name__)


# ---- AUTH & ONBOARDING ----

def index(request):
    return render(request, "index.html")


def register(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if not email or not password1 or not password2:
            messages.error(request, "All fields are required.")
            return render(request, "register.html")

        if password1 != password2:
            messages.error(request, "Passwords don't match.")
            return render(request, "register.html")

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return render(request, "register.html")

        try:
            user = CustomUser.objects.create_user(email=email, password=password1)
            user.save()
            logger.info("User created: %s", user.email)
        except Exception as e:
            logger.error("User create failed: %s", str(e))
            messages.error(request, "Account creation failed. Check server logs.")
            return render(request, "register.html")

        login(request, user)
        return redirect("dashboard")

    return render(request, "register.html")


def verify_email(request, token):
    messages.success(request, "Email verification not wired yet (stub).")
    return redirect("dashboard")


def user_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid email or password.")
            return render(request, "login.html")

    return render(request, "login.html")


def user_logout(request):
    logout(request)
    messages.info(request, "You are logged out.")
    return redirect("home")


# ---- COMPANY / WORKSPACE ----

@login_required
def create_company(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if not name:
            messages.error(request, "Company name is required.")
            return redirect("create_company")

        company = Company.objects.create(
            name=name,
            owner=request.user,
        )

        TeamMember.objects.create(
            user=request.user,
            company=company,
            role=MemberRole.OWNER,
        )

        messages.success(request, f"Company '{company.name}' created.")
        return redirect("dashboard")

    return render(request, "company/create.html")


@login_required
def dashboard(request):
    member = TeamMember.objects.filter(
        user=request.user
    ).select_related("company").first()

    if not member:
        return render(request, "dashboard.html", {"company": None})

    company = member.company
    projects = company.projects.all()[:10]

    context = {
        "company": company,
        "projects": projects,
        "team": company.members.select_related("user"),
    }
    return render(request, "dashboard.html", context)


# ---- TEAM & INVITES ----

@login_required
def view_team(request):
    member = get_object_or_404(
        TeamMember,
        user=request.user,
        role__in=[MemberRole.OWNER, MemberRole.ADMIN],
    )

    company = member.company
    invites = Invite.objects.filter(
        company=company,
        status=Invite.INVITED,
    )

    members = company.members.select_related("user")

    context = {
        "company": company,
        "members": members,
        "invites": invites,
    }
    return render(request, "team/view.html", context)


@login_required
def invite(request):
    current_member = get_object_or_404(
        TeamMember,
        user=request.user,
        role__in=[MemberRole.OWNER, MemberRole.ADMIN],
    )

    if request.method != "POST":
        return redirect("view_team")

    email = request.POST.get("email")
    role_str = request.POST.get("role")

    logger.info("INVITE DEBUG: email=%s, role_str=%s", email, role_str)

    if not email or not role_str:
        messages.error(request, "Email and role are required.")
        return redirect("view_team")

    role_value = int(role_str)
    if role_value not in dict(MemberRole.choices).keys():
        messages.error(request, "Invalid role.")
        return redirect("view_team")

    if email == request.user.email:
        messages.error(request, "You cannot invite yourself.")
        return redirect("view_team")

    existing_user = CustomUser.objects.filter(email=email).first()

    if existing_user:
        if TeamMember.objects.filter(
            user=existing_user,
            company=current_member.company,
        ).exists():
            messages.error(request, "This user is already a member.")
            return redirect("view_team")

    if Invite.objects.filter(
        email=email,
        company=current_member.company,
        status=Invite.INVITED,
    ).exists():
        messages.error(request, "This email is already invited.")
        return redirect("view_team")

    # TRY CREATING invite
    try:
        token = str(uuid4()).replace("-", "")
        invite = Invite.objects.create(
            email=email,
            invited_by=current_member,
            company=current_member.company,
            role=role_value,
            token=token,
            status=Invite.INVITED,
        )
        logger.info("Invite CREATED in DB: %s -> id=%d", email, invite.id)
        messages.success(request, f"Invite sent to {email} (stub).")
    except Exception as e:
        logger.error("Invite create FAILED: %s", str(e))
        messages.error(request, "Failed to create invite. Check server logs.")
        return redirect("view_team")

    return redirect("view_team")


def accept_invite(request, token):
    invite = get_object_or_404(Invite, token=token)

    if request.user.is_authenticated:
        if TeamMember.objects.filter(
            user=request.user,
            company=invite.company,
        ).exists():
            messages.info(request, "You are already a member of this company.")
            invite.status = Invite.ACCEPTED
            invite.accepted_at = timezone.now()
            invite.save()
            return redirect("dashboard")

        TeamMember.objects.create(
            user=request.user,
            company=invite.company,
            role=invite.role,
        )

        invite.status = Invite.ACCEPTED
        invite.accepted_at = timezone.now()
        invite.save()
        messages.success(request, "You joined the company.")
        return redirect("dashboard")

    request.session["pending_invite_token"] = invite.token
    messages.info(request, "Please log in or register to accept this invite.")
    return redirect("register")


@login_required
def change_user_role(request, user_id):
    current_member = get_object_or_404(
        TeamMember,
        user=request.user,
        company__members__user_id=user_id,
        role__in=[MemberRole.OWNER, MemberRole.ADMIN],
    )

    target_member = get_object_or_404(
        TeamMember,
        user_id=user_id,
        company=current_member.company,
    )

    if current_member.role != MemberRole.OWNER:
        messages.error(request, "Only owner can change roles.")
        return redirect("view_team")

    if target_member.role == MemberRole.MEMBER:
        target_member.role = MemberRole.ADMIN
        messages.success(request, "Member promoted to Admin.")
    elif target_member.role == MemberRole.ADMIN:
        target_member.role = MemberRole.MEMBER
        messages.success(request, "Admin demoted to Member.")
    else:
        messages.error(request, "Invalid role state.")

    target_member.save()
    return redirect("view_team")


# ---- PROJECTS ----

@login_required
def projects(request):
    member = get_object_or_404(TeamMember, user=request.user)
    company = member.company

    projects = company.projects.all()
    context = {
        "company": company,
        "projects": projects,
    }
    return render(request, "projects/list.html", context)


@login_required
def create_projects(request):
    member = get_object_or_404(TeamMember, user=request.user)
    company = member.company

    if (company.plan == "free") and company.projects.count() >= 3:
        messages.error(request, "Free plan only allows 3 projects. Upgrade to Pro.")
        return redirect("billing")

    if request.method == "POST":
        name = request.POST.get("name")
        if not name:
            messages.error(request, "Project name is required.")
            return redirect("create_projects")

        Project.objects.create(
            name=name,
            company=company,
        )
        messages.success(request, "Project created.")
        return redirect("projects")

    return render(request, "projects/create.html")


# ---- BILLING / STRIPE ----

@login_required
def billing(request):
    member = get_object_or_404(
        TeamMember,
        user=request.user,
        role=MemberRole.OWNER,
    )

    subscription = None
    try:
        subscription = CompanySubscription.objects.get(company=member.company)
    except CompanySubscription.DoesNotExist:
        pass

    context = {
        "company": member.company,
        "subscription": subscription,
    }
    return render(request, "billing/index.html", context)


@login_required
def upgrade_pro(request):
    member = get_object_or_404(
        TeamMember,
        user=request.user,
        role=MemberRole.OWNER,
    )

    messages.info(request, "Stripe integration stub: would open checkout.")
    return redirect("billing")


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def checkout_session(request):
    member = get_object_or_404(
        TeamMember,
        user=request.user,
        role=MemberRole.OWNER,
    )

    # Stub URL for demo; in real app this will be Stripe Session URL
    stripe_url = "https://checkout.stripe.com/..."  # replace when Stripe is live

    return JsonResponse({"checkout_url": stripe_url})


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    print("Stripe webhook received (stub)")
    return HttpResponse(status=200)


@login_required
def billing_success(request):
    member = get_object_or_404(
        TeamMember,
        user=request.user,
        role=MemberRole.OWNER,
    )

    member.company.plan = "pro"
    member.company.save()

    messages.success(request, "Plan upgraded to Pro (stub).")
    return redirect("projects")


@login_required
def billing_cancel(request):
    member = get_object_or_404(
        TeamMember,
        user=request.user,
        role=MemberRole.OWNER,
    )

    messages.info(request, "Billing cancellation stub.")
    return redirect("billing")


# ---- ADMIN / INTERNAL DASHBOARD ----

@login_required
def admin(request):
    if not request.user.is_superuser:
        return HttpResponse("Forbidden", status=403)

    companies = Company.objects.all().order_by("-last_active")
    context = {
        "companies": companies,
    }
    return render(request, "admin/companies.html", context)


@login_required
def company_single(request, pk):
    if not request.user.is_superuser:
        return HttpResponse("Forbidden", status=403)

    company = get_object_or_404(Company, pk=pk)
    members = company.members.select_related("user")
    projects = company.projects.all()
    subscription = None

    try:
        subscription = CompanySubscription.objects.get(company=company)
    except CompanySubscription.DoesNotExist:
        pass

    context = {
        "company": company,
        "members": members,
        "projects": projects,
        "subscription": subscription,
    }
    return render(request, "admin/company.html", context)


@login_required
def company_upgrade(request, pk):
    if not request.user.is_superuser:
        return HttpResponse("Forbidden", status=403)

    company = get_object_or_404(Company, pk=pk)

    company.plan = "pro"
    company.save()

    CompanySubscription.objects.get_or_create(
        company=company,
        defaults={
            "stripe_customer_id": "stub_customer",
            "stripe_subscription_id": "stub_subscription",
            "stripe_price_id": "price_stub_pro",
            "current_period_end": timezone.now() + timezone.timedelta(days=30),
        },
    )

    messages.success(request, f"Company '{company.name}' upgraded to Pro (free).")
    return redirect("company_single", pk=company.pk)


@login_required
def company_ban(request, pk):
    if not request.user.is_superuser:
        return HttpResponse("Forbidden", status=403)

    company = get_object_or_404(Company, pk=pk)

    company.is_banned = True
    company.save()
    messages.success(request, f"Company '{company.name}' banned.")
    return redirect("company_single", pk=company.pk)