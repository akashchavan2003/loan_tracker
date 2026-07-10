"""
EMI Math Service — Loan EMI Tracker
=====================================
This module contains pure functions for EMI calculation and schedule generation.
"Pure" means: no database access, no Django imports — just math.
This makes it trivially testable and easy to explain.

HOW REDUCING BALANCE EMI WORKS
================================
A flat-rate loan charges interest on the original principal every month.
A reducing-balance loan charges interest only on what's left outstanding.

Example with ₹1,00,000 at 8% p.a., 12 months:
  Monthly rate r = 8 / 12 / 100 = 0.006667

  Month 1: interest = 1,00,000 × 0.006667 = ₹667   (high — full principal)
  Month 6: interest = ~54,000  × 0.006667 = ₹360   (lower — ~half repaid)
  Month 12: interest = ~8,700  × 0.006667 = ₹58    (near zero — almost done)

This is why the interest component shrinks and the principal component grows
each month — even though the total EMI amount stays constant.
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta  # handles month arithmetic cleanly


# ─── Core EMI Formula ─────────────────────────────────────────────────────────

def calculate_emi(
    principal: Decimal,
    annual_rate_pct: Decimal,
    tenure_months: int,
) -> Decimal:
    """
    Standard reducing-balance EMI formula:

        EMI = P × r × (1+r)^n
              ─────────────────
                (1+r)^n − 1

    where:
        P = principal (loan amount)
        r = monthly interest rate = annual_rate / 12 / 100
        n = tenure in months

    Returns EMI rounded to the nearest whole rupee.

    Edge case — 1 month (n=1):
        Formula simplifies to: P × r × (1+r) / ((1+r) - 1) = P × r × (1+r) / r = P × (1+r)
        i.e., just principal + one month's interest. This is handled naturally by the formula.

    Edge case — 0% interest (r=0):
        Formula breaks (division by zero). Guard with a separate branch.
        Result: EMI = P / n (equal principal split, no interest).
    """
    if tenure_months <= 0:
        raise ValueError(f"Tenure must be a positive integer, got: {tenure_months}")
    if principal <= 0:
        raise ValueError(f"Principal must be positive, got: {principal}")

    r = annual_rate_pct / Decimal('12') / Decimal('100')

    if r == 0:
        # Zero interest — simple equal split
        return _round_rupees(principal / Decimal(tenure_months))

    # (1 + r)^n — use Decimal arithmetic to avoid float drift
    one_plus_r_n = (1 + r) ** tenure_months

    emi = principal * r * one_plus_r_n / (one_plus_r_n - 1)
    return _round_rupees(emi)


# ─── Schedule Generation ──────────────────────────────────────────────────────

def generate_emi_schedule(
    principal: Decimal,
    annual_rate_pct: Decimal,
    tenure_months: int,
    disbursed_on: date,
) -> list[dict]:
    """
    Generates the full repayment schedule as a list of dicts.
    Each dict maps directly to one EMISchedule model row.

    Algorithm (per month):
        1. Calculate interest on the CURRENT outstanding balance (reducing balance)
        2. Principal paid this month = EMI - interest
        3. New outstanding = previous outstanding - principal paid
        4. LAST MONTH: set principal = outstanding (absorbs rounding error)

    Why do we need the last-month adjustment?
        If EMI is rounded to ₹8,698 and the "true" EMI is ₹8,697.47, over 12 months
        we've collected 53 extra paise. The last month's outstanding won't be exactly
        one standard EMI. We clear it exactly — this makes the schedule balance to ₹0.

    Returns: list of dicts with keys:
        emi_number, due_date, emi_amount, interest_component,
        principal_component, outstanding_balance
    """
    emi = calculate_emi(principal, annual_rate_pct, tenure_months)
    r   = annual_rate_pct / Decimal('12') / Decimal('100')

    schedule     = []
    outstanding  = principal  # tracks remaining balance, starts at full principal

    for i in range(1, tenure_months + 1):
        # Interest this month is always on the CURRENT outstanding (reducing balance)
        interest   = _round_rupees(outstanding * r)

        is_last = (i == tenure_months)

        if is_last:
            # Last EMI: clear exactly whatever is left
            # This absorbs any cumulative rounding from previous months
            principal_part = outstanding
            this_emi       = _round_rupees(interest + principal_part)
        else:
            principal_part = emi - interest
            this_emi       = emi

        outstanding = _round_rupees(outstanding - principal_part)

        # Due date: disbursement date + i months (1st EMI = 1 month after disbursement)
        due_date = disbursed_on + relativedelta(months=i)

        schedule.append({
            'emi_number':          i,
            'due_date':            due_date,
            'emi_amount':          this_emi,
            'interest_component':  interest,
            'principal_component': principal_part,
            'outstanding_balance': outstanding,   # balance AFTER this EMI is paid
        })

    return schedule


# ─── Foreclosure Calculation ──────────────────────────────────────────────────

def calculate_foreclosure_amount(
    outstanding_principal: Decimal,
    annual_rate_pct: Decimal,
) -> dict:
    """
    Foreclosure settlement = outstanding principal + current month's interest only.
    All future interest is waived (that's the benefit of foreclosure for the borrower).

    Returns a dict with:
        - settlement_amount: what the member must pay today
        - principal:         their outstanding principal
        - interest:          one month's interest on that principal
    """
    r             = annual_rate_pct / Decimal('12') / Decimal('100')
    current_month_interest = _round_rupees(outstanding_principal * r)
    settlement    = outstanding_principal + current_month_interest

    return {
        'principal':         outstanding_principal,
        'interest':          current_month_interest,
        'settlement_amount': settlement,
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _round_rupees(value: Decimal) -> Decimal:
    """Round to nearest whole rupee using banker's rounding (ROUND_HALF_UP for finance)."""
    return value.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
