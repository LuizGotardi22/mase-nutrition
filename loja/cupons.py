from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

from .models import Cupom, Parceiro

CENTAVOS = Decimal("0.01")


def _arredondar(valor):
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def validar_cupom(codigo, usuario=None, email=""):
    """Devolve (cupom, "") se puder usar, ou (None, mensagem de erro)."""
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None, "Digite o código do cupom."

    cupom = Cupom.objects.select_related("parceiro__usuario").filter(codigo=codigo).first()
    # Mesma mensagem para inexistente/inativo, para não revelar quais códigos existem.
    if not cupom or not cupom.ativo or cupom.parceiro.status != Parceiro.Status.APROVADO:
        return None, "Cupom inválido ou indisponível."

    dono = cupom.parceiro.usuario
    proprio = usuario is not None and usuario.is_authenticated and usuario.pk == dono.pk
    if not proprio and email and dono.email:
        proprio = email.strip().lower() == dono.email.strip().lower()
    if proprio:
        return None, "Você não pode usar o seu próprio cupom."

    return cupom, ""


def calcular_desconto(subtotal, cupom):
    return _arredondar(subtotal * cupom.parceiro.desconto_percentual / Decimal("100"))


def calcular_comissao(base, cupom):
    """Comissão sobre o valor dos produtos já com desconto (sem frete)."""
    return _arredondar(base * cupom.parceiro.comissao_percentual / Decimal("100"))


def calcular_beneficio_continua(subtotal):
    """Benefício comercial do Programa Mase Contínua sobre o valor dos produtos."""
    return _arredondar(subtotal * settings.CONTINUA_BENEFICIO_PERCENTUAL / Decimal("100"))
