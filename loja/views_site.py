import os

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from . import leads
from .forms import UFS, CdmoForm, ContatoForm
from .models import Artigo, Lead, Linha, Material, Parceiro, PontoVenda, Produto
from .utils import so_digitos


# ---------- Institucional ----------
def home(request):
    destaques = Produto.objects.filter(ativo=True)[:8]
    return render(request, "index.html", {"destaques": destaques})


def quem_somos(request):
    return render(request, "quem_somos.html")


def allergen_free(request):
    return render(request, "allergen_free.html")


def clinical_care(request):
    return render(request, "clinical_care.html", {"linhas": Linha.objects.filter(ativa=True)})


def linha(request, slug):
    obj = get_object_or_404(Linha, slug=slug, ativa=True)
    return render(request, "linha.html", {"linha": obj, "produtos": obj.produtos.filter(ativo=True)})


def mase_continua(request):
    return render(request, "mase_continua.html")


# ---------- CDMO ----------
def cdmo(request):
    return render(request, "cdmo.html")


def cdmo_proposta(request):
    form = CdmoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        extras = {
            "Segmento": d["segmento"],
            "Produto desejado": d["produto_desejado"],
            "Forma farmacêutica": d["forma_farmaceutica"],
            "Quantidade inicial estimada": d["quantidade_inicial"],
            "Possui formulação?": d["possui_formulacao"],
            "Possui marca?": d["possui_marca"],
            "Prazo estimado": d["prazo"],
        }
        leads.registrar_lead(
            tipo=Lead.Tipo.CDMO, nome=d["nome"], empresa=d["empresa"], cnpj=d["cnpj"],
            email=d["email"], telefone=d["telefone"], estado=d["estado"],
            mensagem=d["mensagem"], dados=extras, consentimento=True,
        )
        messages.success(request, "Recebemos o seu projeto. Um consultor Mase entrará em contato em breve.")
        return redirect("cdmo_proposta")
    return render(request, "cdmo_proposta.html", {"form": form})


# ---------- Contato por interesse ----------
def contato(request):
    assunto = request.GET.get("assunto", "")
    inicial = {"assunto": assunto} if assunto in dict(Lead.Tipo.choices) else {}
    form = ContatoForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        leads.registrar_lead(
            tipo=d["assunto"], nome=d["nome"], empresa=d["empresa"], email=d["email"],
            telefone=d["telefone"], mensagem=d["mensagem"], consentimento=True,
        )
        messages.success(request, "Mensagem enviada! Encaminhamos para o responsável e retornaremos em breve.")
        return redirect("contato")
    return render(
        request, "contato.html",
        {"form": form, "assunto_atual": form["assunto"].value(), "opcoes": Lead.Tipo.choices},
    )


# ---------- Profissionais de saúde ----------
def profissionais(request):
    parceiro = None
    if request.user.is_authenticated:
        parceiro = Parceiro.objects.filter(usuario=request.user).first()
    return render(request, "profissionais.html", {"parceiro": parceiro})


@login_required(login_url="entrada")
def profissionais_area(request):
    parceiro = Parceiro.objects.filter(usuario=request.user).first()
    if not parceiro:
        return redirect("parceiro_cadastro")
    grupos = []
    if parceiro.status == Parceiro.Status.APROVADO:
        materiais = list(Material.objects.filter(publicado=True))
        for valor, rotulo in Material.Tipo.choices:
            itens = [m for m in materiais if m.tipo == valor]
            if itens:
                grupos.append((rotulo, itens))
    return render(
        request, "profissionais_area.html",
        {"parceiro": parceiro, "liberado": parceiro.status == Parceiro.Status.APROVADO, "grupos": grupos},
    )


@login_required(login_url="entrada")
def material_abrir(request, pk):
    """Único caminho para os arquivos técnicos: só profissional aprovado."""
    if not Parceiro.objects.filter(usuario=request.user, status=Parceiro.Status.APROVADO).exists():
        raise PermissionDenied
    material = get_object_or_404(Material, pk=pk, publicado=True)
    if material.arquivo:
        return FileResponse(material.arquivo.open("rb"), filename=os.path.basename(material.arquivo.name))
    if material.link:
        return redirect(material.link)
    raise Http404


# ---------- Onde encontrar ----------
def _agrupar(qs):
    grupos = []
    lista = list(qs)
    for valor, rotulo in PontoVenda.Tipo.choices:
        itens = [p for p in lista if p.tipo == valor]
        if itens:
            grupos.append((rotulo, itens))
    return grupos


def onde_encontrar(request):
    cep = so_digitos(request.GET.get("cep", ""))
    cidade = request.GET.get("cidade", "").strip()
    uf = request.GET.get("uf", "").strip().upper()
    buscou = bool(cep or cidade or uf)

    if len(cep) == 8 and (not cidade or not uf):
        try:
            dados = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=5).json()
            if not dados.get("erro"):
                cidade = cidade or dados.get("localidade", "")
                uf = uf or dados.get("uf", "")
        except (requests.RequestException, ValueError):
            pass

    na_cidade, na_regiao = [], []
    if uf in UFS:
        qs = PontoVenda.objects.filter(ativo=True, uf=uf)
        if cidade:
            na_cidade = qs.filter(cidade__iexact=cidade)
            na_regiao = qs.exclude(cidade__iexact=cidade)
        else:
            na_regiao = qs
    return render(
        request, "onde_encontrar.html",
        {
            "buscou": buscou, "cep": request.GET.get("cep", ""), "cidade": cidade, "uf": uf, "ufs": UFS,
            "grupos_cidade": _agrupar(na_cidade), "grupos_regiao": _agrupar(na_regiao),
        },
    )


# ---------- Mase Science ----------
def science(request):
    cat = request.GET.get("cat", "")
    artigos = Artigo.objects.filter(publicado=True)
    if cat in dict(Artigo.CATEGORIAS):
        artigos = artigos.filter(categoria=cat)
    else:
        cat = ""
    return render(
        request, "science.html",
        {"artigos": artigos, "categorias": Artigo.CATEGORIAS, "cat": cat},
    )


def science_artigo(request, slug):
    artigo = get_object_or_404(Artigo, slug=slug, publicado=True)
    return render(request, "science_artigo.html", {"artigo": artigo})
