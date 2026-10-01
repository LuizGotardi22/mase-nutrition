from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import contas_json, leads
from .forms import CadastroForm, CupomForm, LoginForm, ProfissionalForm
from .models import Assinatura, Comissao, Cupom, Parceiro, Pedido

User = get_user_model()
MAX_CUPONS = 5


def _proximo(request):
    """Endereço para voltar depois do login (só se for do próprio site)."""
    alvo = request.POST.get("next") or request.GET.get("next") or ""
    if alvo and url_has_allowed_host_and_scheme(alvo, {request.get_host()}, request.is_secure()):
        return alvo
    return ""


# ---------- Entrada, cadastro e saída ----------
def entrada(request):
    if request.user.is_authenticated:
        return redirect("index")
    proximo = _proximo(request)
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ident = form.cleaned_data["identificador"].strip()
        senha = form.cleaned_data["senha"]
        usuario = authenticate(request, username=ident, password=senha)
        if usuario is None and "@" in ident:
            usuario = authenticate(request, username=ident.lower(), password=senha)
        if usuario is not None:
            login(request, usuario)
            return redirect(proximo or "index")
        form.add_error(None, "E-mail ou senha incorretos.")
    return render(request, "entrada.html", {"form": form, "proximo": proximo})


def _criar_usuario(request, d, form):
    """Cria a conta (no JSON ou no banco, conforme a configuração). Devolve o usuário ou None (erro já no form)."""
    if settings.CONTAS_EM_JSON:
        try:
            contas_json.criar(d["nome"], d["email"], senha=d["senha"])
        except contas_json.ContaJaExiste:
            form.add_error("email", "Já existe uma conta com este e-mail. Tente entrar.")
            return None
        except contas_json.ContasJsonErro:
            form.add_error(None, "Não foi possível salvar a conta agora. Tente novamente em instantes.")
            return None
        usuario = authenticate(request, username=d["email"], password=d["senha"])
        if usuario is None:
            form.add_error(None, "Conta criada, mas não foi possível entrar. Tente fazer o login.")
        return usuario

    primeiro, _, resto = d["nome"].partition(" ")
    usuario = User.objects.create_user(
        username=d["email"], email=d["email"], password=d["senha"], first_name=primeiro, last_name=resto,
    )
    usuario.backend = "django.contrib.auth.backends.ModelBackend"
    return usuario


def criar_conta(request):
    if request.user.is_authenticated:
        return redirect("index")
    proximo = _proximo(request)
    form = CadastroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = _criar_usuario(request, form.cleaned_data, form)
        if usuario is not None:
            login(request, usuario)
            messages.success(request, "Conta criada! Bem-vindo(a) à Mase Nutrition.")
            return redirect(proximo or "index")
    return render(request, "criar_conta.html", {"form": form, "proximo": proximo})


@require_POST
def sair(request):
    logout(request)
    messages.info(request, "Você saiu da conta.")
    return redirect("index")


@login_required(login_url="entrada")
def minha_conta(request):
    return render(
        request,
        "minha_conta.html",
        {
            "pedidos": Pedido.objects.filter(usuario=request.user)[:20],
            "parceiro": Parceiro.objects.filter(usuario=request.user).first(),
            "assinaturas": Assinatura.objects.filter(usuario=request.user)
            .exclude(status=Assinatura.Status.CANCELADA)
            .select_related("cupom")
            .prefetch_related("itens__produto"),
        },
    )


@login_required(login_url="entrada")
@require_POST
def assinatura_acao(request, pk, acao):
    ass = get_object_or_404(Assinatura, pk=pk, usuario=request.user)
    S = Assinatura.Status
    if acao == "pausar" and ass.status == S.ATIVA:
        ass.status = S.PAUSADA
        messages.info(request, "Assinatura pausada. Você pode retomar quando quiser.")
    elif acao == "retomar" and ass.status == S.PAUSADA:
        ass.status = S.ATIVA
        if not ass.proxima_entrega or ass.proxima_entrega < date.today():
            ass.proxima_entrega = date.today()
        messages.success(request, "Assinatura retomada.")
    elif acao == "cancelar" and ass.status != S.CANCELADA:
        ass.status = S.CANCELADA
        messages.info(request, "Assinatura cancelada.")
    else:
        raise Http404
    ass.save(update_fields=["status", "proxima_entrega"])
    return redirect("minha_conta")


# ---------- Profissionais de saúde: cadastro e painel de cupons ----------
@login_required(login_url="entrada")
def parceiro_cadastro(request):
    if Parceiro.objects.filter(usuario=request.user).exists():
        return redirect("parceiro_painel")
    form = ProfissionalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        parceiro = form.save(commit=False)
        parceiro.usuario = request.user
        parceiro.save()
        if settings.EMAIL_COMERCIAL:
            leads.avisar(
                settings.EMAIL_COMERCIAL,
                "[Site Mase] Novo profissional de saúde aguardando aprovação",
                f"{parceiro.nome} — {parceiro.get_tipo_display()}\n"
                f"Registro: {parceiro.registro_formatado}\nCNPJ: {parceiro.cnpj or '-'}\n"
                f"Instituição: {parceiro.instituicao or '-'}\nTelefone: {parceiro.telefone}\n\n"
                "Confira o registro no site do conselho e aprove em /painel/ > Profissionais de saúde.",
            )
        messages.success(request, "Cadastro enviado! Vamos conferir o seu registro profissional.")
        return redirect("parceiro_painel")
    return render(request, "parceiro_cadastro.html", {"form": form})


def _contexto_painel(parceiro, form=None):
    ctx = {"parceiro": parceiro}
    if parceiro.status == Parceiro.Status.APROVADO:
        def soma(status):
            total = parceiro.comissoes.filter(status=status).aggregate(t=Sum("valor"))["t"]
            return total or Decimal("0.00")

        vendas_qs = Pedido.objects.filter(
            cupom__parceiro=parceiro, status__in=[Pedido.Status.PAGO, Pedido.Status.ENVIADO]
        )
        ctx.update(
            {
                "cupons": parceiro.cupons.annotate(
                    usos=Count(
                        "pedidos",
                        filter=Q(pedidos__status__in=[Pedido.Status.PAGO, Pedido.Status.ENVIADO]),
                    )
                ),
                "vendas": vendas_qs.count(),
                "ultimas_vendas": vendas_qs.select_related("comissao")[:20],
                "com_comissao": parceiro.comissao_percentual > 0,
                "a_receber": soma(Comissao.Status.PENDENTE),
                "recebido": soma(Comissao.Status.PAGA),
                "comissoes": parceiro.comissoes.select_related("pedido")[:20],
                "form": form or CupomForm(),
                "pode_criar": parceiro.cupons.count() < MAX_CUPONS,
                "max_cupons": MAX_CUPONS,
            }
        )
    return ctx


@login_required(login_url="entrada")
def parceiro_painel(request):
    parceiro = Parceiro.objects.filter(usuario=request.user).select_related("usuario").first()
    if not parceiro:
        return redirect("parceiro_cadastro")
    return render(request, "parceiro_painel.html", _contexto_painel(parceiro))


@login_required(login_url="entrada")
@require_POST
def parceiro_cupom_criar(request):
    parceiro = Parceiro.objects.filter(usuario=request.user).first()
    if not parceiro or parceiro.status != Parceiro.Status.APROVADO:
        return redirect("parceiro_painel")
    if parceiro.cupons.count() >= MAX_CUPONS:
        messages.error(request, f"Você já tem {MAX_CUPONS} cupons. Desative um para criar outro.")
        return redirect("parceiro_painel")
    form = CupomForm(request.POST)
    if form.is_valid():
        Cupom.objects.create(parceiro=parceiro, codigo=form.cleaned_data["codigo"])
        messages.success(request, f"Cupom {form.cleaned_data['codigo']} criado.")
        return redirect("parceiro_painel")
    return render(request, "parceiro_painel.html", _contexto_painel(parceiro, form))


@login_required(login_url="entrada")
@require_POST
def parceiro_cupom_alternar(request, pk):
    cupom = get_object_or_404(Cupom, pk=pk, parceiro__usuario=request.user)
    cupom.ativo = not cupom.ativo
    cupom.save(update_fields=["ativo"])
    return redirect("parceiro_painel")
