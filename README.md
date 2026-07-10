# Loan EMI Tracker

A staff-facing loan management system. Login → add members → create loans → track EMI repayments.

## Quick Start

```bash
# 1. Clone / unzip
cd loan_emi_tracker

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create database
python manage.py migrate

# 4. Load demo data (creates admin user + 2 sample loans)
python manage.py seed_data

# 5. Start server
python manage.py runserver

# Open: http://localhost:8000
# Login: admin / admin123
```

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | Django 5.1 | Built-in auth, ORM, admin panel |
| Frontend | Django Templates + Vanilla JS | Zero CORS, zero build step, rapid |
| Database | SQLite (local) / PostgreSQL (prod) | dj-database-url auto-switches |
| Hosting | Railway | Single Procfile deploy |

**Why not React?** For this scope, Django templates give 100% of the functionality in 30% of the time.
No webpack, no CORS, no separate deploy. Every line is explainable in an interview.

## Features

### Core
- Real Django auth login (not mock/hardcoded)
- Member management (add, list, edit, search)
- Loan creation with auto-generated EMI schedule
- EMI schedule table (EMI #, due date, principal, interest, outstanding balance)
-  Mark individual EMIs as paid
- Member-wise outstanding report + CSV export
- Indian Rupee format (₹1,23,456)

### Bonus
- Foreclosure (early closure with settlement = outstanding + current month interest)
- Top-up gating (33% of principal must be repaid before new loan)
-  Search/filter on members and loans
- 15 unit tests for EMI math

## EMI Math

**Formula:** `EMI = P × r × (1+r)^n / ((1+r)^n - 1)`

- `P` = principal
- `r` = 8 / 12 / 100 = 0.006667 (monthly rate)
- `n` = tenure in months

**Reducing Balance:**
- Each month, interest = `outstanding_principal × r`
- Principal component = `EMI − interest`
- Outstanding reduces by principal component each month

This is why month-1 interest > month-12 interest — the outstanding balance has been
reduced by 11 months of principal repayments by month 12.

**Rounding:** All math uses Python `Decimal` (not float). Last EMI's principal component
is adjusted to absorb cumulative rounding so the final balance is exactly ₹0.

## Running Tests

```bash
python manage.py test tracker.tests -v 2
```

15 tests covering:
- EMI formula correctness
- Schedule balances to ₹0
- Interest decreases each month (reducing balance property)
- Principal component increases each month
- 1-month edge case
- Foreclosure calculation


## Project Structure

```
config/          # Django project settings + root urls
tracker/         # Single app: all models, views, services, tests
  models.py      # Member, Loan, EMISchedule
  services.py    # Pure EMI math functions (testable)
  views.py       # All HTTP handlers
  forms.py       # Validation + top-up gating
  tests.py       # 15 unit tests
  templatetags/  # INR currency format filter
  templates/     # All HTML pages
static/          # CSS + JS

- Docker + docker-compose for easier local setup
# loan_tracker
