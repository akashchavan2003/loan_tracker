"""
URL Configuration — tracker app
=================================
Maps URL patterns to view functions.
All routes require login (enforced by @login_required in views.py).
"""

from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ── Dashboard ─────────────────────────────────────────────────────────────
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # ── Members ───────────────────────────────────────────────────────────────
    path('members/',            views.members_list,  name='members_list'),
    path('members/add/',        views.member_add,    name='member_add'),
    path('members/<int:pk>/',   views.member_detail, name='member_detail'),
    path('members/<int:pk>/edit/', views.member_edit, name='member_edit'),

    # ── Loans ─────────────────────────────────────────────────────────────────
    path('loans/',              views.loans_list,    name='loans_list'),
    path('loans/create/',       views.loan_create,   name='loan_create'),
    path('loans/<int:pk>/',     views.loan_detail,   name='loan_detail'),

    # Mark a specific EMI row as paid
    path('loans/<int:loan_pk>/emi/<int:emi_pk>/pay/', views.mark_emi_paid, name='mark_emi_paid'),

    # Foreclose (early close) a loan
    path('loans/<int:pk>/foreclose/', views.foreclose_loan, name='foreclose_loan'),

    # ── Reports ───────────────────────────────────────────────────────────────
    path('reports/outstanding/',     views.report_outstanding,    name='report_outstanding'),
    path('reports/outstanding/csv/', views.export_outstanding_csv, name='export_outstanding_csv'),
]
