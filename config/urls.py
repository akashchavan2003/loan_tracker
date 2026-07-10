"""
Root URL Configuration
========================
All routes are defined here or delegated to tracker.urls.
Django admin is also wired in for user/staff management.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # Django admin — this is how staff users are created/managed
    path('admin/', admin.site.urls),

    # All app routes delegated to tracker app
    path('', include('tracker.urls')),

    # Redirect bare root to dashboard (tracker handles auth redirect)
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
]
