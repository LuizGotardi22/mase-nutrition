import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

if not password:
    raise RuntimeError("DJANGO_SUPERUSER_PASSWORD não configurada no Render")

user, created = User.objects.get_or_create(
    username=username,
    defaults={
        "email": email,
        "is_staff": True,
        "is_superuser": True,
    },
)

user.email = email
user.is_staff = True
user.is_superuser = True
user.set_password(password)
user.save()

print(f"Usuário do painel pronto: {username}")