from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

LIVRES_PREFIXOS = ("/static/", "/painel/", "/webhooks/")
LIVRES_NOMES = {"entrada", "criar_conta"}


class LoginObrigatorioMiddleware:
    """Se LOGIN_OBRIGATORIO=True, manda quem não está logado para a página de entrada."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.LOGIN_OBRIGATORIO and not request.user.is_authenticated:
            if not request.path.startswith(LIVRES_PREFIXOS):
                try:
                    nome = resolve(request.path_info).url_name
                except Resolver404:
                    nome = None  # deixa o 404 normal acontecer
                if nome is not None and nome not in LIVRES_NOMES:
                    return redirect(f"{reverse('entrada')}?next={quote(request.get_full_path())}")
        return self.get_response(request)
