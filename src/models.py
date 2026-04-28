from django.db import models
from django.db.models import Count
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone


# 1) CUSTOM USER (JWT‑friendly)

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    username = None  # we’ll use email
    email = models.EmailField(unique=True)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    email_verified = models.BooleanField(default = False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email


# 2) COMPANY (workspace)

class Company(models.Model):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    PLAN_CHOICES = [
        (FREE, "Free"),
        (PRO, "Pro"),
        (BUSINESS, "Business"),
    ]

    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="owned_companies",
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=FREE)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    is_banned = models.BooleanField(default=False)
    last_active = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


# 3) TEAM MEMBER (user in a company)

class MemberRole(models.IntegerChoices):
    MEMBER = 10, "Member"
    ADMIN = 20, "Admin"
    OWNER = 30, "Owner"

class TeamMember(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="members",
    )
    role = models.IntegerField(choices=MemberRole.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "company")

    def __str__(self):
        return f"{self.user.email} in {self.company.name} ({self.get_role_display()})"


# 4) INVITE (email invitation)

class Invite(models.Model):
    INVITED = "invited"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (INVITED, "Invited"),
        (ACCEPTED, "Accepted"),
        (CANCELLED, "Cancelled"),
    ]

    email = models.EmailField()
    invited_by = models.ForeignKey(
        TeamMember,
        on_delete=models.CASCADE,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="invites", 
    )
    role = models.IntegerField(choices=MemberRole.choices)
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=INVITED)
    created_at = models.DateTimeField(default=timezone.now)
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invite: {self.email} → {self.company.name}"


# 5) PROJECT

class Project(models.Model):
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True) # New
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning') # New
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    @property
    def progress_percentage(self):
        total = self.tasks.count()
        if total == 0:
            return 0
        finished = self.tasks.filter(status='finished').count()
        return int((finished / total) * 100)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

# 6) COMPANY SUBSCRIPTION (Stripe link)

class CompanySubscription(models.Model):
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    stripe_customer_id = models.CharField(max_length=255)
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    stripe_price_id = models.CharField(max_length=255)  # "price_..."
    current_period_end = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Subscription: {self.company.name} ({self.stripe_price_id})"
        
class Task(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('finished', 'Finished'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True) # Your Task Description
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    assigned_to = models.ForeignKey(TeamMember, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # 1. Save the task first so it exists in the DB
        super().save(*args, **kwargs)
        
        # 2. Logic: Auto-update project status
        total_tasks = self.project.tasks.count()
        finished_tasks = self.project.tasks.filter(status='finished').count()

        if total_tasks > 0 and total_tasks == finished_tasks:
            # All tasks done -> Mark Project as Completed
            if self.project.status != 'completed':
                self.project.status = 'completed'
                self.project.save()
        else:
            # If tasks remain or one was moved back from finished -> Ensure Project is Active
            if self.project.status == 'completed':
                self.project.status = 'active'
                self.project.save()

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"