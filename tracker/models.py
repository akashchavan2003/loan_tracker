"""
Models — Loan EMI Tracker
===========================
Three models, all in one app (tracker):
  1. Member       — a loan applicant / borrower
  2. Loan         — a single loan taken by a Member
  3. EMISchedule  — each row in the repayment table for a Loan

Relationships:
  Member (1) ──→ (Many) Loan ──→ (Many) EMISchedule
"""

from django.db import models
from decimal import Decimal


class Member(models.Model):
    """
    Represents a staff/employee who can take loans.
    monthly_salary is stored for context but not used in EMI math
    (assignment uses a fixed 8% rate regardless of salary).
    """
    employee_id     = models.CharField(max_length=50, unique=True, verbose_name="Employee ID")
    name            = models.CharField(max_length=150, verbose_name="Full Name")
    monthly_salary  = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Monthly Salary (₹)"
    )
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Member"
        verbose_name_plural = "Members"

    def __str__(self):
        return f"{self.name} ({self.employee_id})"

    @property
    def total_outstanding(self):
        """Sum of outstanding principal across all ACTIVE loans for this member."""
        return self.loan_set.filter(
            status='ACTIVE'
        ).aggregate(
            total=models.Sum('outstanding_principal')
        )['total'] or Decimal('0')

    @property
    def active_loan(self):
        """Returns the first active loan, used for top-up gating check."""
        return self.loan_set.filter(status='ACTIVE').first()


class Loan(models.Model):
    """
    A single loan issued to a Member.

    Key fields:
    - principal:              Original loan amount (never changes after creation)
    - emi_amount:             Calculated once via EMI formula, stored for display
    - outstanding_principal:  Starts at principal, reduces as EMIs are paid
    - status:                 ACTIVE → CLOSED (all paid) or FORECLOSED (early closure)

    Note: annual_rate is stored (not hardcoded) so future rate changes only need
    a new migration, not code changes.
    """
    STATUS_CHOICES = [
        ('ACTIVE',     'Active'),
        ('CLOSED',     'Closed'),
        ('FORECLOSED', 'Foreclosed'),
    ]

    member               = models.ForeignKey(Member, on_delete=models.CASCADE)
    principal            = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Principal (₹)")
    tenure_months        = models.IntegerField(verbose_name="Tenure (months)")
    annual_rate          = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('8.00'),
        verbose_name="Annual Interest Rate (%)"
    )
    emi_amount           = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name="Monthly EMI (₹)",
        help_text="Auto-calculated on loan creation"
    )
    outstanding_principal = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name="Outstanding Principal (₹)"
    )
    status               = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    disbursed_on         = models.DateField(verbose_name="Disbursement Date")
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Loan"
        verbose_name_plural = "Loans"

    def __str__(self):
        return f"Loan #{self.pk} — {self.member.name} — ₹{self.principal}"

    @property
    def repaid_principal(self):
        """How much principal has been repaid so far."""
        return self.principal - self.outstanding_principal

    @property
    def repaid_percentage(self):
        """Percentage of principal repaid (used for top-up gating)."""
        if self.principal == 0:
            return Decimal('0')
        return (self.repaid_principal / self.principal) * 100

    @property
    def paid_emi_count(self):
        return self.emischedule_set.filter(is_paid=True).count()

    @property
    def total_emi_count(self):
        return self.emischedule_set.count()


class EMISchedule(models.Model):
    """
    One row per monthly instalment for a Loan.
    Generated in bulk when a Loan is created (via services.generate_emi_schedule).

    How the components work (reducing balance):
    - interest_component = outstanding_balance_before_this_emi × monthly_rate
    - principal_component = emi_amount - interest_component
    - outstanding_balance = previous_outstanding - principal_component

    The last EMI's principal_component is adjusted to clear the balance to exactly ₹0.
    """
    loan                = models.ForeignKey(Loan, on_delete=models.CASCADE)
    emi_number          = models.IntegerField(verbose_name="EMI #")
    due_date            = models.DateField()

    # Financial breakdown — all stored as Decimal, whole rupees
    emi_amount          = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="EMI Amount (₹)")
    principal_component = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Principal (₹)")
    interest_component  = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Interest (₹)")
    outstanding_balance = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Outstanding After (₹)")

    # Payment tracking
    is_paid             = models.BooleanField(default=False)
    paid_on             = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['emi_number']
        unique_together = ('loan', 'emi_number')
        verbose_name = "EMI Schedule Row"

    def __str__(self):
        status = "✓" if self.is_paid else "○"
        return f"{status} EMI #{self.emi_number} for Loan #{self.loan_id} — ₹{self.emi_amount}"
