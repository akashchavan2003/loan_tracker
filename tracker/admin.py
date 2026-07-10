"""
Django Admin Registration — tracker app
=========================================
Register models so they appear in /admin/ panel.
Staff users are created and managed here.
"""

from django.contrib import admin
from .models import Member, Loan, EMISchedule


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display  = ['employee_id', 'name', 'monthly_salary', 'created_at']
    search_fields = ['name', 'employee_id']
    ordering      = ['name']


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display  = ['id', 'member', 'principal', 'tenure_months', 'emi_amount', 'outstanding_principal', 'status', 'disbursed_on']
    list_filter   = ['status']
    search_fields = ['member__name', 'member__employee_id']
    readonly_fields = ['emi_amount', 'outstanding_principal', 'created_at']


@admin.register(EMISchedule)
class EMIScheduleAdmin(admin.ModelAdmin):
    list_display  = ['loan', 'emi_number', 'due_date', 'emi_amount', 'is_paid', 'paid_on']
    list_filter   = ['is_paid']
    readonly_fields = ['loan', 'emi_number', 'due_date', 'emi_amount', 'principal_component', 'interest_component', 'outstanding_balance']
