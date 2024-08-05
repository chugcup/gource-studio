import argparse
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create initial superuser account if one does not exist."

    def add_arguments(self, parser):
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.description = """
Create initial superuser account if one does not exist.

When creating initial account, will inspect environment variables
or cmdline arguments for default username/password.

    DJANGO_SUPERUSER_USERNAME  or  --username
    DJANGO_SUPERUSER_PASSWORD  or  --password
    DJANGO_SUPERUSER_EMAIL     or  --email

Otherwise a default "admin:admin" account will be created."""
        parser.add_argument('--username', type=str, help="Superuser username")
        parser.add_argument('--password', type=str, help="Superuser password")
        parser.add_argument('--email', type=str, help="Superuser e-mail")

    def handle(self, *args, **options):
        AuthUser = get_user_model()
        if not AuthUser.objects.filter(is_superuser=True).exists():
            username = "admin"
            password = "admin"
            email = ""

            # Inspect cmdline/environment
            if 'username' in options and options['username']:
                username = options['username']
            elif 'DJANGO_SUPERUSER_USERNAME' in os.environ:
                username = os.environ['DJANGO_SUPERUSER_USERNAME']

            if 'password' in options and options['password']:
                password = options['password']
            elif 'DJANGO_SUPERUSER_PASSWORD' in os.environ:
                password = os.environ['DJANGO_SUPERUSER_PASSWORD']

            if 'email' in options and options['email']:
                email = options['email']
            elif 'DJANGO_SUPERUSER_EMAIL' in os.environ:
                email = os.environ['DJANGO_SUPERUSER_EMAIL']

            # Validate username/password/email ?

            # Create account
            account = AuthUser.objects.create_superuser(email=email, username=username, password=password)
            account.is_active = True
            account.is_admin = True
            account.save()

            print("Created new default superuser:")
            print(f"  Username: {username}")
            print(f"  Password: {password}")
        else:
            print("Superuser account already exists.")
