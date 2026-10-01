"""Cálculo de frete pelo CEP.

Ordem: 1) frete grátis acima do valor configurado; 2) cotação do Melhor Envio (se houver token);
3) tabela "Frete por estado" do painel; 4) FRETE_FIXO.
"""
import logging
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

from .models import FaixaFrete
from .utils import so_digitos, uf_do_cep

logger = logging.getLogger(__name__)


def _escolher(resposta):
    """Da lista devolvida pelo Melhor Envio, pega a opção disponível mais barata."""
    melhor = None
    if not isinstance(resposta, list):
        return None
    for opcao in resposta:
        if not isinstance(opcao, dict) or opcao.get("error"):
            continue
        try:
            valor = Decimal(str(opcao.get("custom_price") or opcao.get("price")))
        except (InvalidOperation, TypeError):
            continue
        empresa = (opcao.get("company") or {}).get("name", "")
        nome = f"{empresa} {opcao.get('name', '')}".strip() or "Transportadora"
        dias = opcao.get("custom_delivery_time") or opcao.get("delivery_time")
        candidato = {"nome": nome, "valor": valor, "prazo": f"{dias} dias úteis" if dias else "", "pendente": False}
        if melhor is None or valor < melhor["valor"]:
            melhor = candidato
    return melhor


def _melhor_envio(cep, itens):
    if not (settings.MELHOR_ENVIO_TOKEN and settings.CEP_ORIGEM and itens):
        return None
    base = "https://sandbox.melhorenvio.com.br" if settings.MELHOR_ENVIO_SANDBOX else "https://melhorenvio.com.br"
    produtos = [
        {
            "id": i["produto"].slug,
            "width": max(int(i["produto"].largura_cm), 1),
            "height": max(int(i["produto"].altura_cm), 1),
            "length": max(int(i["produto"].comprimento_cm), 1),
            "weight": float(i["produto"].peso_kg),
            "insurance_value": float(i["produto"].preco),
            "quantity": int(i["quantidade"]),
        }
        for i in itens
    ]
    contato = settings.EMAIL_COMERCIAL or settings.DEFAULT_FROM_EMAIL
    try:
        r = requests.post(
            f"{base}/api/v2/me/shipment/calculate",
            json={"from": {"postal_code": settings.CEP_ORIGEM}, "to": {"postal_code": cep}, "products": produtos},
            headers={
                "Authorization": f"Bearer {settings.MELHOR_ENVIO_TOKEN}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": f"{settings.STORE_NAME} ({contato})",
            },
            timeout=8,
        )
        if r.status_code != 200:
            logger.warning("Melhor Envio respondeu %s: %s", r.status_code, r.text[:300])
            return None
        return _escolher(r.json())
    except (requests.RequestException, ValueError):
        logger.exception("Falha ao cotar frete no Melhor Envio")
        return None


def _tabela_por_estado(cep):
    uf = uf_do_cep(cep)
    faixa = FaixaFrete.objects.filter(uf=uf).first() if uf else None
    if faixa is None:
        return None
    return {
        "nome": f"Entrega para {uf}",
        "valor": faixa.valor,
        "prazo": f"{faixa.prazo_dias} dias úteis" if faixa.prazo_dias else "",
        "pendente": False,
    }


def calcular_frete(cep, itens, subtotal):
    """Devolve {"nome", "valor", "prazo", "pendente"}. `subtotal` = produtos já com o desconto do cupom."""
    digitos = so_digitos(cep)
    if len(digitos) != 8:
        return {"nome": "informe o CEP", "valor": Decimal("0.00"), "prazo": "", "pendente": True}

    gratis_acima = settings.FRETE_GRATIS_ACIMA
    if gratis_acima and subtotal >= gratis_acima:
        return {"nome": "Frete grátis", "valor": Decimal("0.00"), "prazo": "", "pendente": False}

    return (
        _melhor_envio(digitos, itens)
        or _tabela_por_estado(digitos)
        or {"nome": "Entrega padrão", "valor": settings.FRETE_FIXO, "prazo": "", "pendente": False}
    )
