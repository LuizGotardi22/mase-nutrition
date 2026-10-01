"""Registro e encaminhamento de leads (cada assunto vai para o responsável certo)."""
import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Lead, RotaContato

logger = logging.getLogger(__name__)


def registrar_lead(**campos):
    """Cria o lead, atribui o consultor responsável pela rota e avisa por e-mail."""
    lead = Lead.objects.create(**campos)
    rota = RotaContato.objects.filter(tipo=lead.tipo).first()
    if rota and rota.responsavel:
        lead.responsavel = rota.responsavel
        lead.save(update_fields=["responsavel"])
    destino = (rota.email if rota and rota.email else "") or settings.EMAIL_COMERCIAL
    if destino:
        linhas = [
            f"Tipo: {lead.get_tipo_display()}",
            f"Nome: {lead.nome}",
            f"Empresa: {lead.empresa}" if lead.empresa else "",
            f"CNPJ: {lead.cnpj}" if lead.cnpj else "",
            f"E-mail: {lead.email}",
            f"Telefone: {lead.telefone}",
            f"Estado: {lead.estado}" if lead.estado else "",
        ]
        linhas += [f"{k}: {v}" for k, v in (lead.dados or {}).items() if v]
        if lead.mensagem:
            linhas += ["", lead.mensagem]
        avisar(destino, f"[Site Mase] Novo contato — {lead.get_tipo_display()}", "\n".join(x for x in linhas if x != ""))
    return lead


def avisar(destino, assunto, corpo):
    """E-mail interno. Nunca derruba a página se o envio falhar."""
    try:
        send_mail(assunto, corpo, settings.DEFAULT_FROM_EMAIL, [destino], fail_silently=True)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao enviar aviso interno")
