import os
import sys
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set default settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django and run migrations automatically on startup
try:
    import django
    django.setup()
    print("Auto-running database migrations on startup...")
    call_command("migrate", interactive=False)
    print("Migrations completed successfully!")
except Exception as e:
    print(f"Warning: Auto-migration on startup failed: {e}", file=sys.stderr)

# Expose 'app' as the WSGI callable for platforms that default to gunicorn app:app
app = get_wsgi_application()
