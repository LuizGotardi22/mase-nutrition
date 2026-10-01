import json
import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import cupons, pagamentos
from .cart import Carrinho
from .forms import CheckoutForm
from .frete import calcular_frete
from .models import Assinatura, ItemAssinatura, ItemPedido, Linha, Pedido, Produto
from .pagamentos import PagamentoErro

logger = logging.getLogger(__name__)


# ---------- Loja ----------
def loja(request):
    linha_slug = request.GET.get("linha", "")
    objetivo = request.GET.get("objetivo", "")
    kits = request.GET.get("kits", "")

    lista = Produto.objects.filter(ativo=True).select_related("linha")
    if linha_slug:
        lista = lista.filter(linha__slug=linha_slug)
    elif objetivo:
        lista = lista.filter(objetivo=objetivo)
    elif kits:
        lista = lista.filter(tipo=Produto.Tipo.KIT)

    base = Produto.objects.filter(ativo=True)
    return render(
        request,
        "loja.html",
        {
            "produtos": lista,
            "linha_ativa": linha_slug,
            "objetivo_ativo": objetivo,
            "kits_ativo": bool(kits),
            "linhas": Linha.objects.filter(ativa=True, produtos__ativo=True).distinct(),
            "objetivos": base.exclude(objetivo="").order_by("objetivo").values_list("objetivo", flat=True).distinct(),
            "tem_kits": base.filter(tipo=Produto.Tipo.KIT).exists(),
        },
    )


def produto(request, slug):
    item = get_object_or_404(Produto, slug=slug, ativo=True)
    return render(request, "produto.html", {"produto": item})


# ---------- Carrinho ----------
def _resumo(request, car, itens):
    """Subtotal, cupom do prescritor (se válido) e desconto. Cupom que deixou de valer é removido."""
    subtotal = sum((i["subtotal"] for i in itens), Decimal("0"))
    cupom, desconto = None, Decimal("0.00")
    if car.cupom_codigo:
        cupom, erro = cupons.validar_cupom(car.cupom_codigo, request.user)
        if erro:
            car.remover_cupom()
            messages.info(request, erro)
            cupom = None
        else:
            desconto = cupons.calcular_desconto(subtotal, cupom)
    return subtotal, cupom, desconto


def carrinho(request):
    car = Carrinho(request)
    itens = car.itens()
    subtotal, cupom, desconto = _resumo(request, car, itens)
    return render(
        request,
        "carrinho.html",
        {"itens": itens, "subtotal": subtotal, "cupom": cupom, "desconto": desconto},
    )


@require_POST
def cupom_aplicar(request):
    cupom, erro = cupons.validar_cupom(request.POST.get("codigo", ""), request.user)
    if erro:
        messages.error(request, erro)
    else:
        Carrinho(request).definir_cupom(cupom.codigo)
        messages.success(request, f"Profissional vinculado ao pedido (cupom {cupom.codigo}).")
    return redirect("carrinho")


@require_POST
def cupom_remover(request):
    Carrinho(request).remover_cupom()
    return redirect("carrinho")


@require_POST
def carrinho_adicionar(request, slug):
    item = get_object_or_404(Produto, slug=slug, ativo=True)
    try:
        quantidade = max(int(request.POST.get("quantidade", 1)), 1)
    except ValueError:
        quantidade = 1

    if item.estoque <= 0:
        messages.error(request, f"{item.nome} está esgotado no momento.")
        return redirect(item)

    car = Carrinho(request)
    nova = car.quantidade_de(slug) + quantidade
    limite = item.max_compra
    if nova > limite:
        messages.info(request, f"Limite de {limite} unidade(s) por pedido para este produto.")
    car.definir(slug, min(nova, limite))
    return redirect("carrinho")


@require_POST
def carrinho_atualizar(request, slug):
    item = get_object_or_404(Produto, slug=slug, ativo=True)
    try:
        quantidade = int(request.POST.get("quantidade", 1))
    except ValueError:
        return redirect("carrinho")
    Carrinho(request).definir(slug, min(quantidade, item.max_compra))
    return redirect("carrinho")


@require_POST
def carrinho_remover(request, slug):
    Carrinho(request).remover(slug)
    return redirect("carrinho")


# ---------- Checkout e pedido ----------
@login_required(login_url="entrada")
def checkout(request):
    car = Carrinho(request)
    itens = car.itens()
    if not itens:
        messages.info(request, "Seu carrinho está vazio.")
        return redirect("carrinho")
    if any(i["indisponivel"] for i in itens):
        messages.error(request, "Alguns itens não têm estoque suficiente. Ajuste as quantidades.")
        return redirect("carrinho")

    subtotal, cupom, desconto = _resumo(request, car, itens)
    if settings.PRESCRITOR_OBRIGATORIO and not cupom:
        messages.error(request, "Informe o cupom do profissional de saúde que indicou o produto para continuar.")
        return redirect("carrinho")

    pode_assinar = all(i["produto"].permite_assinatura for i in itens)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            quer_assinar = dados.pop("assinar", False) and pode_assinar
            frequencia = dados.pop("frequencia", "") or 30
            forma_pagamento = dados.pop("forma_pagamento", "pix")
            if cupom:
                # revalida com o e-mail informado (bloqueia o profissional usando o próprio cupom)
                cupom, erro_cupom = cupons.validar_cupom(cupom.codigo, request.user, email=dados["email"])
                if erro_cupom:
                    car.remover_cupom()
                    form.add_error(None, erro_cupom)
                    cupom, desconto = None, Decimal("0.00")
            if not form.errors:
                beneficio = cupons.calcular_beneficio_continua(subtotal) if quer_assinar else Decimal("0.00")
                base = subtotal - desconto - beneficio
                frete = calcular_frete(dados["cep"], itens, subtotal - desconto)
                frete_nome = frete["nome"] + (f" · {frete['prazo']}" if frete["prazo"] else "")
                comissao = cupons.calcular_comissao(base, cupom) if cupom else Decimal("0.00")
                try:
                    with transaction.atomic():
                        pedido_obj = Pedido.objects.create(
                            **dados,
                            usuario=request.user,
                            subtotal=subtotal,
                            cupom=cupom,
                            cupom_codigo=cupom.codigo if cupom else "",
                            desconto=desconto,
                            desconto_continua=beneficio,
                            comissao_percentual=cupom.parceiro.comissao_percentual if cupom else 0,
                            comissao_valor=comissao,
                            frete=frete["valor"],
                            frete_nome=frete_nome[:60],
                            total=base + frete["valor"],
                        )
                        ItemPedido.objects.bulk_create(
                            [
                                ItemPedido(
                                    pedido=pedido_obj,
                                    produto=i["produto"],
                                    nome=str(i["produto"]),
                                    preco_unitario=i["produto"].preco,
                                    quantidade=i["quantidade"],
                                )
                                for i in itens
                            ]
                        )
                        if quer_assinar:
                            ass = Assinatura.objects.create(
                                usuario=request.user, cupom=cupom, origem=pedido_obj,
                                frequencia_dias=frequencia,
                            )
                            ItemAssinatura.objects.bulk_create(
                                [
                                    ItemAssinatura(assinatura=ass, produto=i["produto"], quantidade=i["quantidade"])
                                    for i in itens
                                ]
                            )
                            pedido_obj.assinatura = ass
                            pedido_obj.save(update_fields=["assinatura"])
                        if forma_pagamento == "cartao":
                            pedido_obj.forma_pagamento = Pedido.FormaPagamento.CARTAO
                            pedido_obj.save(update_fields=["forma_pagamento"])
                            # a cobrança acontece na tela do pedido, com o formulário de cartão embutido
                        else:
                            pagamentos.criar_pix(pedido_obj)
                except PagamentoErro as erro:
                    form.add_error(None, str(erro))
                else:
                    car.limpar()
                    return redirect("pedido", codigo=pedido_obj.codigo)
    else:
        form = CheckoutForm(
            initial={"nome": request.user.get_full_name(), "email": request.user.email, "frequencia": 30}
        )

    querendo = bool(request.method == "POST" and request.POST.get("assinar") and pode_assinar)
    beneficio_previsto = cupons.calcular_beneficio_continua(subtotal) if pode_assinar else Decimal("0.00")
    cep_digitado = request.POST.get("cep", "") if request.method == "POST" else ""
    frete = calcular_frete(cep_digitado, itens, subtotal - desconto)
    base_sem_frete = subtotal - desconto
    total_base = base_sem_frete + frete["valor"]
    return render(
        request,
        "checkout.html",
        {
            "form": form,
            "itens": itens,
            "subtotal": subtotal,
            "cupom": cupom,
            "desconto": desconto,
            "pode_assinar": pode_assinar,
            "querendo": querendo,
            "beneficio_previsto": beneficio_previsto,
            "frete": frete,
            "base_sem_frete": base_sem_frete,
            "total_base": total_base,
            "total": total_base - (beneficio_previsto if querendo else Decimal("0.00")),
        },
    )


@login_required(login_url="entrada")
def frete_calcular(request):
    """Usado pela tela de checkout: devolve o frete do CEP informado (o servidor recalcula ao fechar o pedido)."""
    car = Carrinho(request)
    itens = car.itens()
    if not itens:
        return JsonResponse({"ok": False})
    subtotal = sum((i["subtotal"] for i in itens), Decimal("0"))
    desconto = Decimal("0.00")
    if car.cupom_codigo:
        cupom, erro = cupons.validar_cupom(car.cupom_codigo, request.user)
        if not erro:
            desconto = cupons.calcular_desconto(subtotal, cupom)
    frete = calcular_frete(request.GET.get("cep", ""), itens, subtotal - desconto)
    return JsonResponse(
        {"ok": not frete["pendente"], "nome": frete["nome"], "valor": str(frete["valor"]), "prazo": frete["prazo"]}
    )


def _sincronizar_seguro(pedido):
    try:
        pagamentos.sincronizar(pedido)
    except requests.RequestException:
        logger.exception("Falha ao consultar o Mercado Pago (pedido %s)", pedido.pk)


def pedido(request, codigo):
    obj = get_object_or_404(Pedido, codigo=codigo)
    _sincronizar_seguro(obj)
    return render(
        request,
        "pedido.html",
        {
            "pedido": obj,
            "itens": obj.itens.all(),
            "simulacao": pagamentos.modo_simulacao(),
            "cartao_disponivel": pagamentos.cartao_disponivel(),
        },
    )


@login_required(login_url="entrada")
@require_POST
def cartao_pagar(request, codigo):
    """Recebe o token já gerado no navegador pelo formulário de cartão e cobra o pedido."""
    pedido = get_object_or_404(Pedido, codigo=codigo, usuario=request.user)
    if pedido.status != Pedido.Status.AGUARDANDO or pedido.forma_pagamento != Pedido.FormaPagamento.CARTAO:
        return JsonResponse({"status": "erro", "mensagem": "Este pedido não está mais aguardando pagamento."}, status=400)

    token = request.POST.get("token", "")
    if not token:
        return JsonResponse({"status": "erro", "mensagem": "Não recebemos os dados do cartão. Tente de novo."}, status=400)

    try:
        resultado = pagamentos.pagar_com_cartao(
            pedido,
            token=token,
            parcelas=request.POST.get("installments"),
            payment_method_id=request.POST.get("payment_method_id", ""),
            issuer_id=request.POST.get("issuer_id", ""),
            email=request.POST.get("email", ""),
            doc_tipo=request.POST.get("identification_type", "CPF"),
            doc_numero=request.POST.get("identification_number", ""),
        )
    except PagamentoErro as erro:
        return JsonResponse({"status": "erro", "mensagem": str(erro)}, status=502)
    return JsonResponse(resultado)


def pedido_status(request, codigo):
    obj = get_object_or_404(Pedido, codigo=codigo)
    _sincronizar_seguro(obj)
    return JsonResponse({"status": obj.status})


@require_POST
def pedido_novo_pix(request, codigo):
    obj = get_object_or_404(Pedido, codigo=codigo)
    if obj.status != Pedido.Status.EXPIRADO:
        return redirect("pedido", codigo=codigo)

    for item in obj.itens.select_related("produto"):
        if not item.produto or not item.produto.ativo or item.produto.estoque < item.quantidade:
            messages.error(request, "Um dos produtos deste pedido não está mais disponível.")
            return redirect("pedido", codigo=codigo)
    try:
        pagamentos.criar_pix(obj)
    except PagamentoErro as erro:
        messages.error(request, str(erro))
    return redirect("pedido", codigo=codigo)


@require_POST
def pedido_simular_pagamento(request, codigo):
    """Só existe em modo de teste local (DEBUG sem token do Mercado Pago)."""
    if not pagamentos.modo_simulacao():
        raise Http404
    obj = get_object_or_404(Pedido, codigo=codigo)
    obj.marcar_pago()
    return redirect("pedido", codigo=codigo)


# ---------- Webhook do Mercado Pago ----------
@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    """Recebe o aviso, mas nunca confia nele: consulta o pagamento direto na API."""
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        corpo = {}
    if not isinstance(corpo, dict):
        corpo = {}
    dados_corpo = corpo.get("data") if isinstance(corpo.get("data"), dict) else {}

    tipo = request.GET.get("type") or request.GET.get("topic") or corpo.get("type")
    payment_id = request.GET.get("data.id") or dados_corpo.get("id") or request.GET.get("id")

    if tipo != "payment" or not payment_id:
        return HttpResponse(status=200)
    payment_id = str(payment_id)
    if not payment_id.isdigit():
        return HttpResponse(status=200)

    try:
        dados = pagamentos.consultar_pagamento(payment_id)
    except requests.RequestException:
        logger.exception("Webhook: falha ao consultar pagamento %s", payment_id)
        return HttpResponse(status=500)  # o Mercado Pago tenta de novo
    if not dados:
        return HttpResponse(status=200)

    try:
        pedido_obj = Pedido.objects.get(codigo=dados.get("external_reference"))
    except (Pedido.DoesNotExist, ValueError, ValidationError):
        return HttpResponse(status=200)

    pagamentos.aplicar_status(pedido_obj, dados)
    return HttpResponse(status=200)
