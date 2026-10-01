"""Programa Mase Contínua: gera o pedido de cada renovação (mantendo o prescritor vinculado)."""
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse

from . import cupons, pagamentos
from .frete import calcular_frete
from .models import Assinatura, ItemPedido, Parceiro, Pedido

logger = logging.getLogger(__name__)


def gerar_renovacao(ass):
    """Cria o pedido (com Pix) da próxima entrega. Devolve o pedido ou None se não deu."""
    origem = ass.origem
    if origem is None:
        return None

    itens = []
    for item in ass.itens.select_related("produto"):
        p = item.produto
        if p.ativo and p.estoque >= item.quantidade:
            itens.append((p, item.quantidade))
    if not itens:
        logger.warning("Assinatura %s sem itens disponíveis; renovação adiada", ass.pk)
        return None

    subtotal = sum((p.preco * q for p, q in itens), Decimal("0"))
    cupom = ass.cupom
    desconto = Decimal("0.00")
    comissao_pct = Decimal("0.00")
    if cupom and cupom.parceiro.status == Parceiro.Status.APROVADO:
        desconto = cupons.calcular_desconto(subtotal, cupom)
        comissao_pct = cupom.parceiro.comissao_percentual
    else:
        cupom = None
    beneficio = cupons.calcular_beneficio_continua(subtotal)
    base = subtotal - desconto - beneficio
    frete = calcular_frete(origem.cep, [{"produto": p, "quantidade": q} for p, q in itens], subtotal - desconto)
    comissao = cupons.calcular_comissao(base, cupom) if cupom else Decimal("0.00")

    with transaction.atomic():
        pedido = Pedido.objects.create(
            usuario=ass.usuario, nome=origem.nome, email=origem.email, cpf=origem.cpf,
            telefone=origem.telefone, cep=origem.cep, rua=origem.rua, numero=origem.numero,
            complemento=origem.complemento, bairro=origem.bairro, cidade=origem.cidade, uf=origem.uf,
            subtotal=subtotal, cupom=cupom, cupom_codigo=cupom.codigo if cupom else "",
            desconto=desconto, desconto_continua=beneficio, assinatura=ass,
            comissao_percentual=comissao_pct, comissao_valor=comissao,
            frete=frete["valor"], frete_nome=frete["nome"][:60], total=base + frete["valor"],
        )
        ItemPedido.objects.bulk_create(
            [ItemPedido(pedido=pedido, produto=p, nome=str(p), preco_unitario=p.preco, quantidade=q) for p, q in itens]
        )
        pagamentos.criar_pix(pedido)
        ass.proxima_entrega = date.today() + timedelta(days=ass.frequencia_dias)
        ass.save(update_fields=["proxima_entrega"])

    link = f"{settings.SITE_URL}{reverse('pedido', args=[pedido.codigo])}"
    send_mail(
        "Sua próxima entrega Mase Contínua está pronta",
        f"Olá, {origem.nome.split()[0]}!\n\nGeramos o pedido {pedido.numero_curto} da sua entrega programada. "
        f"Para confirmar, pague o Pix neste link:\n{link}\n\nMase Nutrition",
        settings.DEFAULT_FROM_EMAIL, [origem.email], fail_silently=True,
    )
    return pedido


def renovacoes_devidas(hoje=None):
    hoje = hoje or date.today()
    return Assinatura.objects.filter(status=Assinatura.Status.ATIVA, proxima_entrega__lte=hoje).select_related(
        "origem", "cupom__parceiro", "usuario"
    )
