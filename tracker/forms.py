"""
Forms — Loan EMI Tracker
==========================
Django ModelForms for Member and Loan creation.
Validation logic lives here (server-side, can't be bypassed by JS).
"""

from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Member, Loan


class MemberForm(forms.ModelForm):
    """Form for creating a new Member."""

    class Meta:
        model  = Member
        fields = ['employee_id', 'name', 'monthly_salary']
        widgets = {
            'employee_id':    forms.TextInput(attrs={'placeholder': 'e.g. EMP-001', 'class': 'form-input'}),
            'name':           forms.TextInput(attrs={'placeholder': 'Full name', 'class': 'form-input'}),
            'monthly_salary': forms.NumberInput(attrs={'placeholder': '50000', 'class': 'form-input', 'min': '1'}),
        }

    def clean_employee_id(self):
        """Employee ID must be unique and non-empty (stripped of whitespace)."""
        employee_id = self.cleaned_data.get('employee_id', '').strip()
        if not employee_id:
            raise ValidationError("Employee ID cannot be empty.")
        return employee_id.upper()  # Normalize to uppercase

    def clean_monthly_salary(self):
        salary = self.cleaned_data.get('monthly_salary')
        if salary is not None and salary <= 0:
            raise ValidationError("Monthly salary must be a positive amount.")
        return salary

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError("Name cannot be empty.")
        if len(name) < 2:
            raise ValidationError("Name must be at least 2 characters.")
        return name


class LoanForm(forms.ModelForm):
    """
    Form for creating a new Loan.

    Business rules enforced here:
    1. Principal and tenure must be positive
    2. TOP-UP GATING: If member already has an active loan,
       at least 33% of that loan's principal must have been repaid.
    """

    class Meta:
        model  = Loan
        fields = ['member', 'principal', 'tenure_months', 'disbursed_on']
        widgets = {
            'member':         forms.Select(attrs={'class': 'form-input'}),
            'principal':      forms.NumberInput(attrs={'placeholder': '100000', 'class': 'form-input', 'min': '1'}),
            'tenure_months':  forms.NumberInput(attrs={'placeholder': '12', 'class': 'form-input', 'min': '1', 'max': '360'}),
            'disbursed_on':   forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def clean_principal(self):
        principal = self.cleaned_data.get('principal')
        if principal is not None and principal <= 0:
            raise ValidationError("Principal must be a positive amount.")
        return principal

    def clean_tenure_months(self):
        tenure = self.cleaned_data.get('tenure_months')
        if tenure is not None:
            if tenure <= 0:
                raise ValidationError("Tenure must be at least 1 month.")
            if tenure > 360:
                raise ValidationError("Tenure cannot exceed 360 months (30 years).")
        return tenure

    def clean(self):
        """
        Cross-field validation: Top-up gating.

        If the selected member already has an ACTIVE loan, check if they've
        repaid ≥ 33% of that loan's principal. If not, block the new loan.

        Why 33%? It's a common risk threshold — borrower must show commitment
        before getting more credit.
        """
        cleaned = super().clean()
        member  = cleaned.get('member')

        if member:
            active_loan = member.active_loan
            if active_loan:
                repaid_pct = active_loan.repaid_percentage
                if repaid_pct < Decimal('33'):
                    raise ValidationError(
                        f"{member.name} already has an active loan "
                        f"(Loan #{active_loan.pk}). "
                        f"Only {repaid_pct:.1f}% of the principal has been repaid. "
                        f"A new loan can only be issued after 33% is repaid. "
                        f"Currently ₹{active_loan.repaid_principal:,.0f} of "
                        f"₹{active_loan.principal:,.0f} has been repaid."
                    )

        return cleaned
