"""Pix via Mercado Pago (API de Pagamentos)."""
import base64
import io
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import Pedido

logger = logging.getLogger(__name__)

API = "https://api.mercadopago.com"


class PagamentoErro(Exception):
    """Erro que pode ser mostrado ao cliente."""


def modo_simulacao():
    """Sem token e em DEBUG: gera um Pix falso para testar o fluxo localmente."""
    return not settings.MP_ACCESS_TOKEN and settings.DEBUG


# ---------- Pix de demonstração (modo teste) ----------
def _crc16(texto):
    """CRC16-CCITT exigido no final do código Pix (BR Code)."""
    crc = 0xFFFF
    for byte in texto.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def _campo(id_, valor):
    return f"{id_}{len(valor):02d}{valor}"


def _brcode_demo(pedido):
    """Monta um código copia-e-cola no formato oficial do Pix, com chave fictícia.
    O QR Code é válido de ler, mas NÃO recebe dinheiro (a chave não existe)."""
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", str(pedido.codigo))
    payload = (
        _campo("00", "01")
        + _campo("26", conta)
        + _campo("52", "0000")
        + _campo("53", "986")
        + _campo("54", f"{pedido.total:.2f}")
        + _campo("58", "BR")
        + _campo("59", "MASE NUTRITION")
        + _campo("60", "SAO PAULO")
        + _campo("62", _campo("05", pedido.codigo.hex[:25]))
        + "6304"
    )
    return payload + _crc16(payload)


def _qr_base64(texto):
    """Gera a imagem do QR Code (PNG em base64). Vazio se a biblioteca não estiver instalada."""
    try:
        import qrcode

        imagem = qrcode.make(texto, box_size=8, border=2)
        buffer = io.BytesIO()
        imagem.save(buffer)
        return base64.b64encode(buffer.getvalue()).decode()
    except Exception:  # noqa: BLE001 - qualquer falha cai no placeholder da tela
        logger.exception("Não foi possível gerar o QR Code de demonstração")
        return ""


def _headers(idempotency_key=None):
    headers = {
        "Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key
    return headers


def _criar_no_mercado_pago(pedido, expira):
    nome, _, sobrenome = pedido.nome.partition(" ")
    payload = {
        "transaction_amount": float(pedido.total),
        "description": f"Pedido {pedido.numero_curto} - {settings.STORE_NAME}",
        "payment_method_id": "pix",
        "external_reference": str(pedido.codigo),
        "date_of_expiration": expira.isoformat(timespec="milliseconds"),
        "payer": {
            "email": pedido.email,
            "first_name": nome,
            "last_name": sobrenome or nome,
            "identification": {"type": "CPF", "number": pedido.cpf},
        },
    }
    # O Mercado Pago só aceita notification_url pública e HTTPS.
    if settings.SITE_URL.startswith("https://"):
        payload["notification_url"] = f"{settings.SITE_URL}{reverse('webhook_mp')}"

    try:
        r = requests.post(
            f"{API}/v1/payments",
            json=payload,
            headers=_headers(f"{pedido.codigo}-{pedido.tentativas}"),
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.exception("Falha de rede ao criar Pix")
        raise PagamentoErro("Não conseguimos falar com o Mercado Pago. Tente de novo em instantes.") from exc

    if r.status_code not in (200, 201):
        logger.error("Mercado Pago recusou o Pix (%s): %s", r.status_code, r.text)
        raise PagamentoErro("Não foi possível gerar o Pix agora. Confira seus dados ou tente de novo.")
    return r.json()


def criar_pix(pedido):
    """Gera a cobrança Pix e grava QR Code / copia-e-cola no pedido."""
    # Pix no Mercado Pago exige expiração entre 30 minutos e 30 dias no futuro.
    minutos = max(settings.PIX_EXPIRA_MINUTOS, 31)
    expira = timezone.now() + timedelta(minutes=minutos)
    pedido.tentativas += 1

    if modo_simulacao():
        pedido.mp_payment_id = f"SIM-{pedido.codigo.hex[:12]}-{pedido.tentativas}"
        pedido.pix_copia_cola = _brcode_demo(pedido)
        pedido.pix_qr_base64 = _qr_base64(pedido.pix_copia_cola)
    else:
        if not settings.MP_ACCESS_TOKEN:
            raise PagamentoErro("O pagamento por Pix ainda não está configurado.")
        dados = _criar_no_mercado_pago(pedido, expira)
        try:
            tx = dados["point_of_interaction"]["transaction_data"]
            pedido.mp_payment_id = str(dados["id"])
            pedido.pix_copia_cola = tx["qr_code"]
            pedido.pix_qr_base64 = tx["qr_code_base64"]
        except (KeyError, TypeError) as exc:
            logger.error("Resposta inesperada do Mercado Pago: %s", dados)
            raise PagamentoErro("Resposta inesperada do Mercado Pago. Tente de novo.") from exc

    pedido.pix_expira_em = expira
    pedido.status = Pedido.Status.AGUARDANDO
    pedido.save(
        update_fields=[
            "mp_payment_id", "pix_copia_cola", "pix_qr_base64",
            "pix_expira_em", "tentativas", "status",
        ]
    )


def cartao_disponivel():
    """Só dá para mostrar o formulário de cartão embutido com as duas chaves configuradas."""
    return bool(settings.MP_PUBLIC_KEY and settings.MP_ACCESS_TOKEN)


# Mensagens em português para os motivos mais comuns de recusa do Mercado Pago.
MENSAGENS_RECUSA = {
    "cc_rejected_bad_filled_card_number": "Confira o número do cartão.",
    "cc_rejected_bad_filled_date": "Confira a validade do cartão.",
    "cc_rejected_bad_filled_security_code": "Confira o código de segurança (CVV).",
    "cc_rejected_bad_filled_other": "Confira os dados do cartão.",
    "cc_rejected_call_for_authorize": "O banco pediu para você autorizar esse pagamento diretamente com ele.",
    "cc_rejected_card_disabled": "Cartão desabilitado. Ligue para o banco para ativá-lo ou use outro cartão.",
    "cc_rejected_duplicated_payment": "Já existe um pagamento igual a esse. Se precisar comprar de novo, gere um novo pedido.",
    "cc_rejected_high_risk": "O pagamento foi recusado por segurança. Tente outro cartão ou use o Pix.",
    "cc_rejected_insufficient_amount": "Saldo ou limite insuficiente.",
    "cc_rejected_invalid_installments": "Esse cartão não aceita esse número de parcelas.",
    "cc_rejected_max_attempts": "Número máximo de tentativas atingido. Use outro cartão ou tente mais tarde.",
    "cc_rejected_other_reason": "O cartão recusou o pagamento. Tente outro cartão ou use o Pix.",
}


def pagar_com_cartao(pedido, *, token, parcelas, payment_method_id, issuer_id, email, doc_tipo, doc_numero):
    """Cobra o cartão já tokenizado pelo formulário embutido (o número e o CVV nunca passam pelo servidor)."""
    if not cartao_disponivel():
        raise PagamentoErro("O pagamento com cartão ainda não está configurado.")

    pedido.tentativas += 1
    pedido.save(update_fields=["tentativas"])

    payload = {
        "transaction_amount": float(pedido.total),
        "token": token,
        "description": f"Pedido {pedido.numero_curto} - {settings.STORE_NAME}",
        "installments": int(parcelas or 1),
        "payment_method_id": payment_method_id,
        "external_reference": str(pedido.codigo),
        "payer": {
            "email": email or pedido.email,
            "identification": {"type": doc_tipo or "CPF", "number": doc_numero or pedido.cpf},
        },
    }
    if issuer_id:
        payload["issuer_id"] = issuer_id
    if settings.SITE_URL.startswith("https://"):
        payload["notification_url"] = f"{settings.SITE_URL}{reverse('webhook_mp')}"

    try:
        r = requests.post(
            f"{API}/v1/payments",
            json=payload,
            headers=_headers(f"{pedido.codigo}-cartao-{pedido.tentativas}"),
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.exception("Falha de rede ao cobrar o cartão")
        raise PagamentoErro("Não conseguimos falar com o Mercado Pago. Tente de novo em instantes.") from exc

    dados = r.json() if r.content else {}
    if r.status_code not in (200, 201):
        logger.error("Mercado Pago recusou a cobrança (%s): %s", r.status_code, dados)
        detalhe = dados.get("message") or "Não foi possível processar o cartão agora."
        return {"status": "erro", "mensagem": detalhe}

    status = dados.get("status")
    status_detail = dados.get("status_detail", "")
    cartao = dados.get("card") or {}

    pedido.mp_payment_id = str(dados.get("id", ""))
    pedido.parcelas = int(parcelas or 1)
    pedido.cartao_final = cartao.get("last_four_digits", "")
    pedido.cartao_bandeira = dados.get("payment_method_id", "")
    pedido.save(update_fields=["mp_payment_id", "parcelas", "cartao_final", "cartao_bandeira"])

    if status == "approved":
        pedido.marcar_pago()
        return {"status": "approved", "mensagem": "Pagamento aprovado!"}
    if status in ("in_process", "pending"):
        return {"status": "in_process", "mensagem": "Seu pagamento está em análise pelo banco. Avisamos assim que for confirmado."}

    mensagem = MENSAGENS_RECUSA.get(status_detail, "O pagamento não foi aprovado. Tente outro cartão ou use o Pix.")
    return {"status": "rejected", "mensagem": mensagem}


def consultar_pagamento(payment_id):
    """Busca o pagamento direto no Mercado Pago (fonte da verdade). None se não existir."""
    r = requests.get(f"{API}/v1/payments/{payment_id}", headers=_headers(), timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def aplicar_status(pedido, dados):
    """Atualiza o pedido a partir de um pagamento consultado no Mercado Pago."""
    status = dados.get("status")
    pagamento_id = str(dados.get("id", ""))

    if status == "approved":
        try:
            pago = Decimal(str(dados.get("transaction_amount", "0")))
        except InvalidOperation:
            pago = Decimal("0")
        if pago < pedido.total:
            logger.error("Pagamento %s com valor menor que o pedido %s", pagamento_id, pedido.pk)
            return
        if pagamento_id and pagamento_id != pedido.mp_payment_id:
            pedido.mp_payment_id = pagamento_id
            pedido.save(update_fields=["mp_payment_id"])
        pedido.marcar_pago()
        return

    # Pagamentos antigos (Pix anterior já expirado) não devem mexer no pedido atual.
    if pagamento_id != pedido.mp_payment_id or pedido.status != Pedido.Status.AGUARDANDO:
        return
    if status in ("cancelled", "expired"):
        novo = Pedido.Status.EXPIRADO
    elif status == "rejected":
        novo = Pedido.Status.CANCELADO
    else:
        return
    pedido.status = novo
    pedido.save(update_fields=["status"])


def sincronizar(pedido):
    """Consulta o gateway (quando aplicável) e expira Pix vencido."""
    if pedido.status != Pedido.Status.AGUARDANDO:
        return
    if pedido.mp_payment_id and not pedido.mp_payment_id.startswith("SIM-"):
        dados = consultar_pagamento(pedido.mp_payment_id)
        if dados:
            aplicar_status(pedido, dados)
            pedido.refresh_from_db()
    if (
        pedido.status == Pedido.Status.AGUARDANDO
        and pedido.pix_expira_em
        and timezone.now() > pedido.pix_expira_em + timedelta(minutes=2)
    ):
        Pedido.objects.filter(pk=pedido.pk, status=Pedido.Status.AGUARDANDO).update(
            status=Pedido.Status.EXPIRADO
        )
        pedido.refresh_from_db()
