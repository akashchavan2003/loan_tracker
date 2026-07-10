"""
Management Command: seed_data
================================
Creates sample data for demo/testing.
Run: python manage.py seed_data

Creates:
- 1 superuser (admin / admin123)
- 3 demo members
- 2 demo loans with full EMI schedules
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from tracker.models import EMISchedule, Loan, Member
from tracker.services import calculate_emi, generate_emi_schedule


class Command(BaseCommand):
    help = 'Seeds the database with demo data for local development'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Create superuser if not exists
            if not User.objects.filter(username='admin').exists():
                User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
                self.stdout.write(self.style.SUCCESS('Created superuser: admin / admin123'))

            # Clear existing demo data
            Member.objects.all().delete()

            # Create members
            members = [
                Member.objects.create(employee_id='EMP-001', name='Priya Sharma',    monthly_salary=Decimal('75000')),
                Member.objects.create(employee_id='EMP-002', name='Rahul Verma',     monthly_salary=Decimal('55000')),
                Member.objects.create(employee_id='EMP-003', name='Ananya Krishnan', monthly_salary=Decimal('90000')),
            ]
            self.stdout.write(self.style.SUCCESS(f'Created {len(members)} members'))

            # Create a loan for Priya
            principal = Decimal('200000')
            tenure    = 24
            rate      = Decimal('8.00')
            emi       = calculate_emi(principal, rate, tenure)

            loan1 = Loan.objects.create(
                member=members[0],
                principal=principal,
                tenure_months=tenure,
                annual_rate=rate,
                emi_amount=emi,
                outstanding_principal=principal,
                disbursed_on=date(2024, 7, 1),
            )
            schedule = generate_emi_schedule(principal, rate, tenure, date(2024, 7, 1))
            EMISchedule.objects.bulk_create([EMISchedule(loan=loan1, **row) for row in schedule])

            # Mark first 6 EMIs as paid to show partial repayment
            for emi_row in loan1.emischedule_set.all()[:6]:
                emi_row.is_paid = True
                emi_row.paid_on = emi_row.due_date
                emi_row.save()
            paid_principal = sum(
                row.principal_component
                for row in loan1.emischedule_set.filter(is_paid=True)
            )
            loan1.outstanding_principal = principal - paid_principal
            loan1.save()
            self.stdout.write(self.style.SUCCESS(f'Created Loan #1 for {members[0].name} (6 EMIs paid)'))

            # Create a fully active loan for Rahul
            p2, t2 = Decimal('100000'), 12
            loan2 = Loan.objects.create(
                member=members[1],
                principal=p2,
                tenure_months=t2,
                annual_rate=rate,
                emi_amount=calculate_emi(p2, rate, t2),
                outstanding_principal=p2,
                disbursed_on=date(2025, 1, 1),
            )
            schedule2 = generate_emi_schedule(p2, rate, t2, date(2025, 1, 1))
            EMISchedule.objects.bulk_create([EMISchedule(loan=loan2, **row) for row in schedule2])
            self.stdout.write(self.style.SUCCESS(f'Created Loan #2 for {members[1].name} (no EMIs paid)'))

        self.stdout.write(self.style.SUCCESS('\n✅ Seed data created! Login: admin / admin123'))
