"""
Views — Loan EMI Tracker
==========================
All HTTP request handlers in one file, organized by feature:

  Auth:    login_view, logout_view
  Core:    dashboard_view
  Members: members_list, member_add, member_detail
  Loans:   loans_list, loan_create, loan_detail, mark_emi_paid, foreclose_loan
  Reports: report_outstanding, export_outstanding_csv

Each view is decorated with @login_required — unauthenticated requests
redirect to /login/ automatically (configured in settings.LOGIN_URL).
"""

import csv
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import LoanForm, MemberForm
from .models import EMISchedule, Loan, Member
from .services import (
    calculate_foreclosure_amount,
    generate_emi_schedule,
)


# ─── Auth Views ───────────────────────────────────────────────────────────────

def login_view(request):
    """
    Login using Django's built-in auth backend.
    POST: authenticate username/password → create session → redirect to dashboard.
    GET:  show the login form.
    """
    # Already logged in? Go straight to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # authenticate() checks the password against the hashed value in DB
        # It returns the User object on success, None on failure
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)  # Creates a session, sets session cookie
            # Respect ?next= param (e.g., if user tried to visit a protected page)
            next_url = request.GET.get('next', '/dashboard/')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'tracker/login.html')


def logout_view(request):
    """Log out and clear the session."""
    logout(request)
    return redirect('login')


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    """
    Landing page after login. Shows summary stats:
    - Total members
    - Active / Closed loan counts
    - Total outstanding principal across all active loans
    - 5 most recent loans
    """
    total_members    = Member.objects.count()
    active_loans     = Loan.objects.filter(status='ACTIVE').count()
    closed_loans     = Loan.objects.filter(status__in=['CLOSED', 'FORECLOSED']).count()
    total_outstanding = Loan.objects.filter(status='ACTIVE').aggregate(
        total=Sum('outstanding_principal')
    )['total'] or Decimal('0')

    recent_loans = Loan.objects.select_related('member').order_by('-created_at')[:5]

    return render(request, 'tracker/dashboard.html', {
        'total_members':    total_members,
        'active_loans':     active_loans,
        'closed_loans':     closed_loans,
        'total_outstanding': total_outstanding,
        'recent_loans':     recent_loans,
    })


# ─── Members ──────────────────────────────────────────────────────────────────

@login_required
def members_list(request):
    """
    List all members with optional search.
    Search query 'q' filters by name OR employee_id (case-insensitive, partial match).
    Django Q objects allow OR conditions in querysets.
    """
    q = request.GET.get('q', '').strip()
    members = Member.objects.all()

    if q:
        # Q object: filter where (name contains q) OR (employee_id contains q)
        members = members.filter(
            Q(name__icontains=q) | Q(employee_id__icontains=q)
        )

    return render(request, 'tracker/members_list.html', {
        'members': members,
        'search_query': q,
    })


@login_required
def member_add(request):
    """
    Add a new member. On success, redirect to members list with a success toast.
    On failure, re-render the form with validation errors displayed.
    """
    if request.method == 'POST':
        form = MemberForm(request.POST)
        if form.is_valid():
            member = form.save()
            messages.success(request, f'Member "{member.name}" added successfully.')
            return redirect('members_list')
    else:
        form = MemberForm()

    return render(request, 'tracker/member_form.html', {'form': form, 'action': 'Add'})


@login_required
def member_detail(request, pk):
    """
    Member profile: their personal info + all loans + total outstanding.
    pk: Member primary key from the URL.
    """
    member = get_object_or_404(Member, pk=pk)
    loans  = member.loan_set.all().order_by('-created_at')

    return render(request, 'tracker/member_detail.html', {
        'member': member,
        'loans':  loans,
    })


@login_required
def member_edit(request, pk):
    """Edit an existing member's details."""
    member = get_object_or_404(Member, pk=pk)

    if request.method == 'POST':
        form = MemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, f'Member "{member.name}" updated.')
            return redirect('member_detail', pk=pk)
    else:
        form = MemberForm(instance=member)

    return render(request, 'tracker/member_form.html', {'form': form, 'action': 'Edit', 'member': member})


# ─── Loans ────────────────────────────────────────────────────────────────────

@login_required
def loans_list(request):
    """
    List all loans with search/filter.
    Filters: status (ACTIVE/CLOSED/FORECLOSED), member search by name.
    """
    status_filter = request.GET.get('status', '').upper()
    q             = request.GET.get('q', '').strip()

    loans = Loan.objects.select_related('member').all()

    if status_filter in ('ACTIVE', 'CLOSED', 'FORECLOSED'):
        loans = loans.filter(status=status_filter)

    if q:
        loans = loans.filter(member__name__icontains=q)

    return render(request, 'tracker/loans_list.html', {
        'loans':         loans,
        'status_filter': status_filter,
        'search_query':  q,
    })


@login_required
def loan_create(request):
    """
    Create a new loan.

    On valid form submission:
    1. Calculate EMI using services.calculate_emi()
    2. Save the Loan record
    3. Generate the full EMI schedule via services.generate_emi_schedule()
    4. Bulk-insert all EMISchedule rows in one DB call (efficient)

    All of this is wrapped in @transaction.atomic — if anything fails,
    the whole operation rolls back (no orphaned loans without schedules).
    """
    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                loan = form.save(commit=False)
                loan.annual_rate = Decimal('8.00')  # Fixed rate per assignment

                # Calculate and store the EMI (so we don't recalculate on every display)
                from .services import calculate_emi
                loan.emi_amount = calculate_emi(
                    principal        = loan.principal,
                    annual_rate_pct  = loan.annual_rate,
                    tenure_months    = loan.tenure_months,
                )
                loan.outstanding_principal = loan.principal  # Starts at full principal
                loan.save()

                # Generate and bulk-insert the schedule rows
                schedule_data = generate_emi_schedule(
                    principal        = loan.principal,
                    annual_rate_pct  = loan.annual_rate,
                    tenure_months    = loan.tenure_months,
                    disbursed_on     = loan.disbursed_on,
                )

                EMISchedule.objects.bulk_create([
                    EMISchedule(loan=loan, **row)
                    for row in schedule_data
                ])

            messages.success(
                request,
                f'Loan #{loan.pk} created for {loan.member.name}. '
                f'EMI: ₹{loan.emi_amount:,.0f}/month for {loan.tenure_months} months.'
            )
            return redirect('loan_detail', pk=loan.pk)
    else:
        # Pre-fill member if passed as query param (from member detail page)
        initial = {}
        member_id = request.GET.get('member')
        if member_id:
            initial['member'] = member_id
        form = LoanForm(initial=initial)

    return render(request, 'tracker/loan_form.html', {'form': form})


@login_required
def loan_detail(request, pk):
    """
    Loan detail page — shows:
    - Loan summary (outstanding, EMI amount, status)
    - Full EMI schedule table
    - Foreclosure button (if ACTIVE)
    """
    loan     = get_object_or_404(Loan.objects.select_related('member'), pk=pk)
    schedule = loan.emischedule_set.all()

    # Pre-calculate foreclosure amount to show in the confirmation modal
    foreclosure_info = None
    if loan.status == 'ACTIVE':
        foreclosure_info = calculate_foreclosure_amount(
            outstanding_principal=loan.outstanding_principal,
            annual_rate_pct=loan.annual_rate,
        )

    return render(request, 'tracker/loan_detail.html', {
        'loan':             loan,
        'schedule':         schedule,
        'foreclosure_info': foreclosure_info,
    })


@login_required
def mark_emi_paid(request, loan_pk, emi_pk):
    """
    Mark a single EMI as paid.

    Steps:
    1. Mark EMISchedule row as paid
    2. Subtract this EMI's principal_component from Loan.outstanding_principal
    3. If all EMIs are now paid → set Loan.status = 'CLOSED'

    Wrapped in atomic transaction for consistency.
    POST only (state change should never be a GET request — idempotency).
    """
    if request.method != 'POST':
        return redirect('loan_detail', pk=loan_pk)

    with transaction.atomic():
        emi  = get_object_or_404(EMISchedule, pk=emi_pk, loan_id=loan_pk)
        loan = get_object_or_404(Loan, pk=loan_pk)

        if emi.is_paid:
            messages.warning(request, f'EMI #{emi.emi_number} is already marked as paid.')
            return redirect('loan_detail', pk=loan_pk)

        if loan.status != 'ACTIVE':
            messages.error(request, 'Cannot mark EMI for a closed/foreclosed loan.')
            return redirect('loan_detail', pk=loan_pk)

        # Mark this EMI as paid
        emi.is_paid = True
        emi.paid_on = date.today()
        emi.save()

        # Reduce the loan's outstanding principal by what was repaid this month
        loan.outstanding_principal -= emi.principal_component

        # Check if all EMIs are now paid
        if not loan.emischedule_set.filter(is_paid=False).exists():
            loan.status = 'CLOSED'
            loan.outstanding_principal = Decimal('0')  # Explicit zero (safety)
            messages.success(request, f'🎉 Loan #{loan.pk} is fully repaid and marked CLOSED!')
        else:
            messages.success(request, f'EMI #{emi.emi_number} marked as paid. ₹{emi.principal_component:,.0f} deducted from outstanding.')

        loan.save()

    return redirect('loan_detail', pk=loan_pk)


@login_required
def foreclose_loan(request, pk):
    """
    Foreclose (early close) a loan.

    Settlement = outstanding principal + current month's interest (future interest waived).
    The borrower pays this lump sum and the loan is marked FORECLOSED.
    All remaining unpaid EMIs are voided (deleted).

    POST only — confirms the amount shown in the modal before action.
    """
    if request.method != 'POST':
        return redirect('loan_detail', pk=pk)

    with transaction.atomic():
        loan = get_object_or_404(Loan, pk=pk, status='ACTIVE')

        info = calculate_foreclosure_amount(
            outstanding_principal=loan.outstanding_principal,
            annual_rate_pct=loan.annual_rate,
        )

        # Delete all unpaid future EMIs
        loan.emischedule_set.filter(is_paid=False).delete()

        # Mark loan as foreclosed
        loan.status = 'FORECLOSED'
        loan.outstanding_principal = Decimal('0')
        loan.save()

    messages.success(
        request,
        f'Loan #{loan.pk} foreclosed. Settlement amount: ₹{info["settlement_amount"]:,.0f} '
        f'(Principal: ₹{info["principal"]:,.0f} + Interest: ₹{info["interest"]:,.0f}).'
    )
    return redirect('loan_detail', pk=pk)


# ─── Reports ──────────────────────────────────────────────────────────────────

@login_required
def report_outstanding(request):
    """
    Member-wise outstanding report.

    For each member, shows total outstanding principal across all ACTIVE loans.
    Ordered by outstanding amount descending (highest risk members first).

    Uses Django's annotate() to do the aggregation in a single SQL query:
        SELECT member.*, SUM(loan.outstanding_principal) as total_outstanding
        FROM member
        LEFT JOIN loan ON loan.member_id = member.id AND loan.status = 'ACTIVE'
        GROUP BY member.id
    """
    # NOTE: We use 'loan_outstanding' (not 'total_outstanding') as the annotation name
    # because Member already has a @property called total_outstanding.
    # annotate() sets the value as an attribute on each model instance,
    # which would fail against a property with no setter.
    members = Member.objects.annotate(
        loan_outstanding=Sum(
            'loan__outstanding_principal',
            filter=Q(loan__status='ACTIVE')
        )
    ).order_by('-loan_outstanding')

    grand_total = members.aggregate(
        grand=Sum('loan_outstanding')
    )['grand'] or Decimal('0')

    return render(request, 'tracker/report_outstanding.html', {
        'members':    members,
        'grand_total': grand_total,
    })


@login_required
def export_outstanding_csv(request):
    """
    Export the member-wise outstanding report as a CSV file.

    Django HttpResponse with content_type='text/csv' streams the file directly
    — no temp file needed, no disk I/O. The 'Content-Disposition' header tells
    the browser to download it rather than display it.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="outstanding_report.csv"'

    writer = csv.writer(response)

    # Header row
    writer.writerow(['Employee ID', 'Member Name', 'Monthly Salary (INR)', 'Total Outstanding (INR)', 'Active Loans'])

    members = Member.objects.annotate(
        loan_outstanding=Sum(
            'loan__outstanding_principal',
            filter=Q(loan__status='ACTIVE')
        ),
        active_loan_count=models_Count('loan', filter=Q(loan__status='ACTIVE'))
    ).order_by('-loan_outstanding')

    for member in members:
        writer.writerow([
            member.employee_id,
            member.name,
            member.monthly_salary,
            member.loan_outstanding or 0,
            member.active_loan_count,
        ])

    return response


# Fix missing import for Count
from django.db.models import Count as models_Count
