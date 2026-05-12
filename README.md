# BusinessManager

A multi-tenant SaaS workspace platform where companies register, invite their team, manage projects and tasks, and pay monthly via Stripe.

> Built with Django · PostgreSQL · Stripe · Bootstrap 5

---

## What It Does

BusinessManager is the shell every SaaS is built on. It handles everything except the product inside:

- Company registration and private workspaces
- Email verification and invite-based team onboarding
- Role-based access control (Owner, Admin, Member)
- Project and task management with progress tracking
- Stripe subscription billing with webhook automation
- Superuser admin panel to monitor and manage all companies

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2 |
| Database | PostgreSQL |
| Payments | Stripe |
| Email | Gmail SMTP |
| Frontend | Bootstrap 5 + Bootstrap Icons |
| Auth | Custom email-based auth |

---

## Features

### Authentication
- Email/password registration
- Email verification on signup
- Forgot password flow (Django built-in)
- Invite-based team onboarding

### Workspaces
- Each company gets its own private workspace
- Cross-company data access blocked via middleware
- Banned workspace detection and recovery

### Team Management
- Owner / Admin / Member role hierarchy
- Email invitations with token-based acceptance
- Role promotion and demotion by Owner

### Projects
- Create, edit, delete projects
- Project status: Planning, Active, On Hold, Completed
- Auto-complete when all tasks finish
- Real-time progress bar based on task completion

### Tasks
- Create, edit, delete tasks
- Assign to team members
- Status: Not Started, In Progress, Finished
- Granular 0–100% progress slider for in-progress tasks
- Project progress auto-updates from task progress

### Billing
- Free plan: 3 projects max
- Pro plan: $5/month via Stripe
- Stripe Checkout integration
- Webhook automation for subscription lifecycle
- Stripe Customer Portal for card management and cancellation
- Manual upgrade/downgrade via admin panel

### Admin Panel (`/company/admin/`)
- View all companies, plans, member counts, last active
- Manually upgrade any company to Pro
- Ban companies that violate terms
- View Stripe subscription details per company

---

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL
- Stripe account (test keys for development)
- Gmail account with App Password enabled

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/yourusername/businessmanager.git
cd businessmanager
```

**2. Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Create `.env` file in root directory**
```env
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=manager
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
DEFAULT_FROM_EMAIL=BusinessManager <your@gmail.com>

STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...
```

**5. Run migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

**6. Create superuser (for admin panel)**
```bash
python manage.py createsuperuser
```

**7. Run the server**
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

---

## Stripe Setup (Development)

1. Create a Stripe account at stripe.com
2. Get test keys from Dashboard → Developers → API Keys
3. Create a product → $5/month recurring → copy `price_...` ID
4. Install Stripe CLI and run webhook listener:
```bash
stripe listen --forward-to localhost:8000/webhook/stripe/
```
5. Copy the webhook secret from CLI output to `.env`

---

## Project Structure

```
BusinessManager/
├── BussinessManager/       # Project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── src/                    # Main app
│   ├── models.py           # All database models
│   ├── views.py            # All views
│   ├── urls.py             # URL routing
│   ├── decorators.py       # require_role decorator
│   ├── middleware.py       # Workspace isolation
│   └── tokens.py           # Email verification tokens
├── templates/              # All HTML templates
│   ├── home.html           # Base template with sidebar
│   ├── dashboard.html
│   ├── billing/
│   ├── projects/
│   ├── tasks/
│   ├── team/
│   ├── admin/
│   └── auth/               # Password reset templates
├── .env                    # Environment variables (not in git)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Roles & Permissions

| Action | Member | Admin | Owner |
|---|---|---|---|
| View projects | ✅ | ✅ | ✅ |
| Create projects | ❌ | ✅ | ✅ |
| Edit projects | ❌ | ✅ | ✅ |
| Delete projects | ❌ | ❌ | ✅ |
| Create tasks | ❌ | ✅ | ✅ |
| Edit tasks | ❌ | ✅ | ✅ |
| Delete tasks | ❌ | ✅ | ✅ |
| Invite members | ❌ | ✅ | ✅ |
| Change roles | ❌ | ❌ | ✅ |
| Manage billing | ❌ | ❌ | ✅ |
| Delete workspace | ❌ | ❌ | ✅ |

---

## Pricing Plans

| Feature | Free | Pro ($5/mo) |
|---|---|---|
| Projects | 3 max | Unlimited |
| Team members | 10 max | 50 max |
| Task management | ✅ | ✅ |
| Analytics charts | ❌ | ✅ |
| Priority support | ❌ | ✅ |

---

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | True for development, False for production |
| `ALLOWED_HOSTS` | Comma separated list of allowed hosts |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | Database host |
| `DB_PORT` | Database port |
| `EMAIL_HOST_USER` | Gmail address |
| `EMAIL_HOST_PASSWORD` | Gmail app password |
| `DEFAULT_FROM_EMAIL` | Display name + email for outgoing mail |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `STRIPE_PRO_PRICE_ID` | Stripe price ID for Pro plan |

---


---

Built by [Hasnain](https://github.com/yourusername)
