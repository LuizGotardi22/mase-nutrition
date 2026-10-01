from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from loja import contas_json


class Command(BaseCommand):
    help = "Copia para data/contas.json as contas de clientes criadas antes (não copia administradores)."

    def handle(self, *args, **options):
        User = get_user_model()
        copiadas = 0
        for u in User.objects.filter(is_staff=False, is_superuser=False).exclude(email=""):
            if not u.has_usable_password() or contas_json.buscar(u.email):
                continue
            contas_json.criar(u.get_full_name() or u.email, u.email, senha_hash=u.password)
            copiadas += 1
        self.stdout.write(self.style.SUCCESS(f"{copiadas} conta(s) copiada(s) para {contas_json.settings.CONTAS_JSON_PATH}"))
