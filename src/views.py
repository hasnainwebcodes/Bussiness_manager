from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .tokens import email_verification_token
from .decorators import require_role
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
import stripe
from uuid import uuid4
import logging

from .models import (
    CustomUser,
    Company,
    TeamMember,
    MemberRole,
    Invite,
    Project,
    CompanySubscription,
)

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

# ====================== AUTH & EMAIL VERIFICATION ======================

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
            user = CustomUser.objects.create_user(
                email=email, 
                password=password1
            )
            user.email_verified = False
            user.is_active = False
            user.save()

            # ====================== PENDING INVITE LOGIC ======================
            pending_token = request.session.get("pending_invite_token")

            joined_company = None
            if pending_token:
                try:
                    invite = Invite.objects.get(token=pending_token, status=Invite.INVITED)
                    # Add user to the company immediately
                    TeamMember.objects.create(
                        user=user,
                        company=invite.company,
                        role=invite.role
                    )
                    invite.status = Invite.ACCEPTED
                    invite.accepted_at = timezone.now()
                    invite.save()

                    del request.session["pending_invite_token"]
                    joined_company = invite.company

                    messages.success(request, f"Account created! You have joined {invite.company.name}.")
                except Invite.DoesNotExist:
                    del request.session["pending_invite_token"]

            # ====================== EMAIL VERIFICATION ======================
            token = email_verification_token.make_token(user)
            verify_link = request.build_absolute_uri(
                reverse('verify_email', args=[user.pk, token])
            )

            send_mail(
                subject="Verify your BusinessManager Account",
                message=f"Please click the link to verify your email:\n\n{verify_link}\n\nThis link will expire soon.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            if joined_company:
                messages.info(request, "Please verify your email to access the workspace.")
            else:
                messages.success(request, "Account created! Please check your email to verify your account.")

            return redirect("user_login")

        except Exception as e:
            logger.error(f"Registration failed: {str(e)}")
            messages.error(request, "Account creation failed. Please try again.")
            return render(request, "register.html")

    return render(request, "register.html")


def verify_email(request, user_id, token):
    user = get_object_or_404(CustomUser, pk=user_id)

    if email_verification_token.check_token(user, token):
        user.email_verified = True
        user.is_active = True
        user.save()

        messages.success(request, "Your email has been verified successfully! You can now log in.")
    else:
        messages.error(request, "Verification link is invalid or has expired. Please request a new one.")

    return redirect("user_login")

def user_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not email or not password:
            messages.error(request, "Email and password are required.")
            return render(request, "login.html")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            if not user.email_verified or not user.is_active:
                messages.error(request, "Please verify your email address before logging in.")
                return render(request, "login.html")

            login(request, user)
            messages.success(request, f"Welcome back, {user.email}!")

            if not TeamMember.objects.filter(user=user).exists():
                return redirect("create_company")
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "login.html")

def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")


# ====================== COMPANY / WORKSPACE ======================

@login_required
def create_company(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if not name:
            messages.error(request, "Company name is required.")
            return render(request, "company/create.html")

        company = Company.objects.create(name=name, owner=request.user)

        TeamMember.objects.create(
            user=request.user,
            company=company,
            role=MemberRole.OWNER,
        )

        messages.success(request, f"Workspace '{company.name}' created successfully!")
        return redirect("dashboard")

    return render(request, "company/create.html")


@login_required
def dashboard(request):
    member = TeamMember.objects.filter(user=request.user).select_related("company").first()

    if not member:
        return redirect("create_company")

    company = member.company
    projects = company.projects.all()[:10]

    context = {
         "id" : str(company.id),
        "company": company,
        "projects": projects,
        "team": company.members.select_related("user")[:8],
        "is_owner": member.role == MemberRole.OWNER,
        "is_admin": member.role in [MemberRole.OWNER, MemberRole.ADMIN],
    }
    return render(request, "dashboard.html", context)


# ====================== TEAM MANAGEMENT ======================

@login_required
def view_team(request):
    member = get_object_or_404(
        TeamMember,
        user=request.user,
        role__in=[MemberRole.OWNER, MemberRole.ADMIN]
    )

    company = member.company
    members = company.members.select_related("user")
    invites = Invite.objects.filter(company=company, status=Invite.INVITED)

    context = {
        "company": company,
        "members": members,
        "invites": invites,
        "is_owner": member.role == MemberRole.OWNER,
    }
    return render(request, "team/view.html", context)


@login_required
def invite(request):
    current_member = get_object_or_404(
        TeamMember,
        user=request.user,
        role__in=[MemberRole.OWNER, MemberRole.ADMIN]
    )

    if request.method != "POST":
        return redirect("view_team")

    email = request.POST.get("email")
    role_str = request.POST.get("role")

    if not email or not role_str:
        messages.error(request, "Email and role are required.")
        return redirect("view_team")

    try:
        role_value = int(role_str)
    except ValueError:
        messages.error(request, "Invalid role selected.")
        return redirect("view_team")

    if role_value not in dict(MemberRole.choices):
        messages.error(request, "Invalid role.")
        return redirect("view_team")

    if email == request.user.email:
        messages.error(request, "You cannot invite yourself.")
        return redirect("view_team")

    company = current_member.company

    if TeamMember.objects.filter(user__email=email, company=company).exists():
        messages.error(request, "This user is already a member.")
        return redirect("view_team")

    if Invite.objects.filter(email=email, company=company, status=Invite.INVITED).exists():
        messages.error(request, "This email is already invited.")
        return redirect("view_team")

    token = str(uuid4()).replace("-", "")
    invite = Invite.objects.create(
        email=email,
        invited_by=current_member,
        company=company,
        role=role_value,
        token=token,
        status=Invite.INVITED,
    )

    # Send real invite email
    accept_link = request.build_absolute_uri(reverse('accept_invite', args=[token]))
    send_mail(
        subject=f"Invitation to join {company.name}",
        message=f"You have been invited to join {company.name} as a {dict(MemberRole.choices).get(role_value, 'Member')}.\n\nClick here to accept:\n{accept_link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )

    messages.success(request, f"Invitation sent successfully to {email}")
    return redirect("view_team")


def accept_invite(request, token):
    invite = get_object_or_404(Invite, token=token, status=Invite.INVITED)

    if request.user.is_authenticated:
        if TeamMember.objects.filter(user=request.user, company=invite.company).exists():
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

        messages.success(request, f"Welcome to {invite.company.name}!")
        return redirect("dashboard")

    # Not logged in - save token for after registration
    request.session["pending_invite_token"] = token
    messages.info(request, "Please register or log in to accept this invitation.")
    return redirect("register")


@login_required
def change_user_role(request, user_id):
    current_member = get_object_or_404(
        TeamMember,
        user=request.user,
        role=MemberRole.OWNER
    )

    target_member = get_object_or_404(
        TeamMember,
        user_id=user_id,
        company=current_member.company
    )

    if target_member.role == MemberRole.OWNER:
        messages.error(request, "Cannot change the Owner's role.")
        return redirect("view_team")

    if target_member.role == MemberRole.MEMBER:
        target_member.role = MemberRole.ADMIN
        messages.success(request, "Member promoted to Admin.")
    else:
        target_member.role = MemberRole.MEMBER
        messages.success(request, "Admin demoted to Member.")

    target_member.save()
    return redirect("view_team")


# ====================== PROJECTS ======================

@login_required
def projects(request):
    member = get_object_or_404(TeamMember, user=request.user)
    company = member.company

    context = {
        "company": company,
        "projects": company.projects.all(),
    }
    return render(request, "projects/list.html", context)



@login_required
@require_role([MemberRole.ADMIN, MemberRole.OWNER]) # Members can't create projects
def create_projects(request):
    member = TeamMember.objects.get(user=request.user)
    company = member.company
    
    # THE PAYWALL CHECK
    project_count = company.projects.count()
    if company.plan == 'free' and project_count >= 3:
        messages.error(request, "Free plans are limited to 3 projects. Please upgrade to Pro!")
        return redirect('billing')

    if request.method == "POST":
        name = request.POST.get('name')
        description = request.POST.get('description')
        Project.objects.create(name=name, description=description, company=company)
        messages.success(request, "Project created successfully!")
        return redirect('dashboard')
    
    return render(request, "projects/create.html")
    # ====================== BILLING ======================


@login_required
def billing(request):
    member = get_object_or_404(TeamMember, user=request.user, role=MemberRole.OWNER)
    company = member.company

    # --- HANDLE BUSINESS PLAN CONTACT FORM ---
    if request.method == "POST" and 'contact_sales' in request.POST:
        size = request.POST.get('size')
        message_text = request.POST.get('message')
        
        # Send email to yourself (Admin)
        send_mail(
            subject=f"Enterprise Inquiry: {company.name}",
            message=f"User: {request.user.email}\nCompany: {company.name}\nSize: {size}\nMessage: {message_text}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_FROM_EMAIL],
        )
        messages.success(request, "Inquiry sent! Our sales team will contact you soon.")
        return redirect('billing')

    subscription = CompanySubscription.objects.filter(company=company).first()
    
    context = {
        "company": company,
        "subscription": subscription,
    }
    return render(request, "billing/index.html", context)
@login_required
def upgrade_pro(request):
    return redirect("billing_success")


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def checkout_session(request):
    """
    Scene 4: The 'Mechanical Shell' of the Payment.
    This creates a secure Stripe URL and redirects the user to the sandbox.
    """
    # 1. Permission Check: Only the 'Owner' can manage billing
    member = get_object_or_404(
        TeamMember, 
        user=request.user, 
        role=MemberRole.OWNER
    )
    
    # 2. Your Price ID from the Stripe Dashboard
    PRO_PRICE_ID = "price_1TPeKFDRIV9EVyvDotMBZYqR"  # <--- Paste your price_... ID here

    try:
        # 3. Create the Stripe Checkout Session
        session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            payment_method_types=['card'],
            line_items=[
                {
                    'price': PRO_PRICE_ID,
                    'quantity': 1,
                },
            ],
            mode='subscription',  # Use 'subscription' for recurring monthly payments
            success_url=request.build_absolute_uri(reverse('billing_success')) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse('billing')),
            # CRITICAL: This metadata is what the Webhook uses to upgrade the right company
            metadata={
                'company_id': member.company.id,
                'user_id': request.user.id
            }
        )
        
        # 4. Return the URL so the frontend JavaScript can redirect the user
        return JsonResponse({'checkout_url': session.url})

    except Exception as e:
        # Log the error for debugging
        print(f"Stripe Error: {e}")
        return JsonResponse({'message': "Could not create checkout session. Please try again."}, status=400)
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET 

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    # 1. Payment Successful
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        company_id = session['metadata']['company_id']
        company = Company.objects.get(id=company_id)
        
        company.plan = Company.PRO
        company.save()

        CompanySubscription.objects.update_or_create(
            company=company,
            defaults={
                'stripe_customer_id': session['customer'],
                'stripe_subscription_id': session['subscription'],
                'stripe_price_id': "pro_monthly",
                'current_period_end': timezone.now() + timezone.timedelta(days=30),
                'is_active': True,
            }
        )

    # 2. Subscription Ended or Payment Failed (Scene 4)
    elif event['type'] in ['customer.subscription.deleted', 'invoice.payment_failed']:
        stripe_sub = event['data']['object']
        sub_record = CompanySubscription.objects.filter(stripe_subscription_id=stripe_sub['id']).first()
        if sub_record:
            company = sub_record.company
            company.plan = Company.FREE
            company.save()
            sub_record.is_active = False
            sub_record.save()

    return HttpResponse(status=200)


@login_required
def billing_success(request):
    member = get_object_or_404(TeamMember, user=request.user, role=MemberRole.OWNER)

    company = member.company
    company.plan = "pro"
    company.save()

    CompanySubscription.objects.get_or_create(
        company=company,
        defaults={
            "stripe_customer_id": "cus_sandbox_123",
            "stripe_subscription_id": "sub_sandbox_456",
            "current_period_end": timezone.now() + timezone.timedelta(days=30),
        }
    )

    messages.success(request, "✅ Successfully upgraded to Pro plan!")
    return render(request, "billing/billing_success.html")


@login_required
@require_http_methods(["POST"])
def billing_cancel(request):
    member = get_object_or_404(TeamMember, user=request.user, role=MemberRole.OWNER)
    subscription = get_object_or_404(CompanySubscription, company=member.company)

    try:
        # Don't delete yet, just tell Stripe not to renew
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True
        )
        messages.info(request, "Your subscription is set to cancel at the end of the billing period.")
    except Exception as e:
        messages.error(request, f"Stripe Error: {str(e)}")
        
    return redirect('billing')

# ====================== ADMIN ======================

@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return HttpResponse("Access Denied", status=403)

    companies = Company.objects.all().order_by("-last_active" if hasattr(Company, 'last_active') else "-id")
    context = {"companies": companies}
    return render(request, "admin/companies.html", context)


@login_required
def company_single(request, pk):
    if not request.user.is_superuser:
        return HttpResponse("Access Denied", status=403)

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
        return HttpResponse("Access Denied", status=403)

    company = get_object_or_404(Company, pk=pk)
    company.plan = "pro"
    company.save()

    CompanySubscription.objects.get_or_create(
        company=company,
        defaults={
            "stripe_customer_id": "cus_manual",
            "stripe_subscription_id": "sub_manual",
            "current_period_end": timezone.now() + timezone.timedelta(days=365),
        }
    )

    messages.success(request, f"Company '{company.name}' manually upgraded to Pro.")
    return redirect("company_single", pk=company.pk)


@login_required
def company_ban(request, pk):
    if not request.user.is_superuser:
        return HttpResponse("Access Denied", status=403)

    company = get_object_or_404(Company, pk=pk)
    company.is_banned = True
    company.save()

    messages.success(request, f"Company '{company.name}' has been banned.")
    return redirect("company_single", pk=company.pk)

@login_required
def team_settings(request):
    member = get_object_or_404(TeamMember, user=request.user)
    company = member.company
    members = company.members.all().select_related('user')
    invites = company.invites.filter(status='invited')

    return render(request, "team/settings.html", {
        "company": company,
        "members": members,
        "invites": invites,
        "is_owner": member.role == MemberRole.OWNER
    })