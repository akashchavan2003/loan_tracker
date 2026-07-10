"""
Unit Tests — EMI Calculation
==============================
Tests the pure functions in services.py.
Run with: python manage.py test tracker.tests

We test:
1. EMI formula correctness against a known value
2. Full schedule balances to ₹0 at the end
3. Interest decreases each month (reducing balance property)
4. 1-month edge case
5. Last EMI rounding absorption
6. Total payments = principal + total interest
7. Foreclosure calculation
"""

from decimal import Decimal
from datetime import date
from django.test import TestCase
from .services import calculate_emi, generate_emi_schedule, calculate_foreclosure_amount


class EMIFormulaTest(TestCase):
    """Test the EMI formula calculation."""

    def test_standard_emi_known_value(self):
        """
        ₹1,00,000 at 8% p.a. for 12 months.
        Known EMI ≈ ₹8,698 (verified independently).
        Formula: P × r × (1+r)^n / ((1+r)^n - 1)
        """
        emi = calculate_emi(
            principal=Decimal('100000'),
            annual_rate_pct=Decimal('8'),
            tenure_months=12,
        )
        # Allow ±1 rupee for rounding
        self.assertAlmostEqual(float(emi), 8698, delta=1)

    def test_single_month_loan(self):
        """
        For n=1: EMI = principal + one month's interest.
        ₹10,000 at 8% → monthly rate = 0.006667
        EMI = 10,000 + (10,000 × 0.006667) = ₹10,067
        """
        emi = calculate_emi(
            principal=Decimal('10000'),
            annual_rate_pct=Decimal('8'),
            tenure_months=1,
        )
        self.assertAlmostEqual(float(emi), 10067, delta=1)

    def test_emi_is_positive(self):
        """EMI must always be positive for valid inputs."""
        emi = calculate_emi(
            principal=Decimal('500000'),
            annual_rate_pct=Decimal('8'),
            tenure_months=60,
        )
        self.assertGreater(emi, 0)

    def test_invalid_tenure_raises(self):
        """Zero or negative tenure must raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_emi(Decimal('100000'), Decimal('8'), 0)

    def test_invalid_principal_raises(self):
        """Zero principal must raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_emi(Decimal('0'), Decimal('8'), 12)


class EMIScheduleTest(TestCase):
    """Test the full schedule generation."""

    def setUp(self):
        """Common test data — used across multiple test methods."""
        self.principal = Decimal('100000')
        self.rate      = Decimal('8')
        self.tenure    = 12
        self.start     = date(2025, 1, 1)
        self.schedule  = generate_emi_schedule(
            self.principal, self.rate, self.tenure, self.start
        )

    def test_schedule_has_correct_row_count(self):
        """Schedule must have exactly n rows for n months."""
        self.assertEqual(len(self.schedule), self.tenure)

    def test_last_row_outstanding_is_zero(self):
        """
        After the final EMI, outstanding balance must be ₹0.
        This is the critical correctness check.
        """
        last_row = self.schedule[-1]
        self.assertEqual(last_row['outstanding_balance'], Decimal('0'))

    def test_interest_decreases_over_time(self):
        """
        In a reducing-balance loan, interest component must shrink each month
        because the outstanding principal decreases each month.
        This is the KEY property that distinguishes reducing-balance from flat-rate.
        """
        interests = [row['interest_component'] for row in self.schedule]
        for i in range(len(interests) - 1):
            self.assertGreaterEqual(
                interests[i], interests[i + 1],
                msg=f"Interest at month {i+1} should be ≥ month {i+2}"
            )

    def test_principal_component_increases_over_time(self):
        """
        As interest decreases, the principal component of each EMI increases
        (since EMI amount is fixed). Money that used to go to interest now goes to principal.
        """
        principals = [row['principal_component'] for row in self.schedule]
        for i in range(len(principals) - 1):
            self.assertLessEqual(
                principals[i], principals[i + 1],
                msg=f"Principal component at month {i+1} should be ≤ month {i+2}"
            )

    def test_emi_equals_interest_plus_principal(self):
        """For every row: EMI amount = interest component + principal component."""
        for row in self.schedule:
            self.assertEqual(
                row['emi_amount'],
                row['interest_component'] + row['principal_component'],
                msg=f"EMI components don't add up at month {row['emi_number']}"
            )

    def test_outstanding_reduces_by_principal_component(self):
        """
        outstanding_balance[i] = outstanding_balance[i-1] - principal_component[i]
        Verifies the running balance is correctly tracked.
        """
        prev_outstanding = self.principal
        for row in self.schedule:
            expected_outstanding = prev_outstanding - row['principal_component']
            self.assertEqual(row['outstanding_balance'], expected_outstanding)
            prev_outstanding = row['outstanding_balance']

    def test_total_principal_repaid_equals_loan_principal(self):
        """Sum of all principal components must equal the original loan amount."""
        total_principal = sum(row['principal_component'] for row in self.schedule)
        self.assertEqual(total_principal, self.principal)

    def test_due_dates_are_monthly(self):
        """Each EMI due date must be exactly 1 month after the previous."""
        dates = [row['due_date'] for row in self.schedule]
        for i in range(len(dates) - 1):
            diff = (dates[i+1].year - dates[i].year) * 12 + dates[i+1].month - dates[i].month
            self.assertEqual(diff, 1, msg=f"Gap between EMI {i+1} and {i+2} is not 1 month")

    def test_single_month_loan_clears_to_zero(self):
        """Edge case: 1-month loan must clear in one payment."""
        schedule = generate_emi_schedule(
            Decimal('50000'), Decimal('8'), 1, date(2025, 6, 1)
        )
        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0]['outstanding_balance'], Decimal('0'))


class ForeclosureTest(TestCase):
    """Test foreclosure settlement calculation."""

    def test_foreclosure_is_principal_plus_one_month_interest(self):
        """
        Foreclosure = outstanding_principal + (outstanding × monthly_rate)
        No future interest is charged.
        """
        result = calculate_foreclosure_amount(
            outstanding_principal=Decimal('50000'),
            annual_rate_pct=Decimal('8'),
        )
        # Monthly rate = 8/12/100 = 0.006667
        # Interest = 50000 × 0.006667 = ₹333
        self.assertEqual(result['principal'], Decimal('50000'))
        self.assertAlmostEqual(float(result['interest']), 333, delta=1)
        self.assertEqual(
            result['settlement_amount'],
            result['principal'] + result['interest']
        )
