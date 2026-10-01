from django.conf import settings

from .cart import Carrinho


def loja(request):
    return {
        "carrinho_qtd": Carrinho(request).total_itens,
        "WHATSAPP_NUMBER": settings.WHATSAPP_NUMBER,
        "STORE_NAME": settings.STORE_NAME,
        "LOGIN_OBRIGATORIO": settings.LOGIN_OBRIGATORIO,
        "PRESCRITOR_OBRIGATORIO": settings.PRESCRITOR_OBRIGATORIO,
        "MP_PUBLIC_KEY": settings.MP_PUBLIC_KEY,
        "CONTINUA_BENEFICIO": settings.CONTINUA_BENEFICIO_PERCENTUAL,
        "REDES_SOCIAIS": [(n, u) for n, u in settings.REDES_SOCIAIS if u],
    }
