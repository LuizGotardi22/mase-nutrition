from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def brl(valor):
    """1234.5 -> R$ 1.234,50"""
    try:
        valor = Decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        return valor
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"
