import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from . import contas_json

logger = logging.getLogger(__name__)


class ContasJsonBackend(BaseBackend):
    """Login com as contas guardadas em data/contas.json.

    Na primeira vez que a pessoa entra, criamos o usuário correspondente no Django
    (sem senha própria): ele é necessário para pedidos, sessão e cadastro de profissional.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            conta = contas_json.autenticar(username, password)
        except contas_json.ContasJsonErro:
            logger.exception("Falha ao ler contas.json no login")
            return None
        if conta is None:
            return None

        User = get_user_model()
        usuario = User.objects.filter(username__iexact=conta["email"]).first()
        if usuario is None:
            primeiro, _, resto = conta["nome"].partition(" ")
            usuario = User(
                username=conta["email"], email=conta["email"],
                first_name=primeiro[:150], last_name=resto[:150],
            )
            usuario.set_unusable_password()
            usuario.save()
        return usuario if usuario.is_active else None

    def get_user(self, user_id):
        User = get_user_model()
        usuario = User.objects.filter(pk=user_id).first()
        return usuario if usuario and usuario.is_active else None
