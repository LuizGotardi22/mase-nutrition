import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone

from .models import (
    Artigo, Assinatura, Comissao, Cupom, FaixaFrete, ItemAssinatura, ItemPedido, Lead, Linha,
    Material, Parceiro, Pedido, PontoVenda, Produto, RotaContato,
)

admin.site.site_header = "MASE NUTRITION — Painel"
admin.site.site_title = "Painel Mase"


def exportar_csv(modeladmin, request, queryset, colunas, nome):
    """Exporta as linhas selecionadas (colunas = [(título, função)])."""
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{nome}.csv"'
    resposta.write("\ufeff")  # BOM: o Excel abre com acentos corretos
    escritor = csv.writer(resposta, delimiter=";")
    escritor.writerow([c[0] for c in colunas])
    for obj in queryset:
        escritor.writerow([c[1](obj) for c in colunas])
    return resposta


# ---------- Catálogo ----------
@admin.register(Linha)
class LinhaAdmin(admin.ModelAdmin):
    list_display = ("nome", "status", "ordem", "ativa")
    list_editable = ("status", "ordem", "ativa")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("nome", "sabor", "tipo", "linha", "preco", "estoque", "ativo")
    list_editable = ("preco", "estoque", "ativo")
    list_filter = ("tipo", "linha", "ativo")
    search_fields = ("nome", "sabor", "objetivo")
    prepopulated_fields = {"slug": ("nome", "sabor")}
    fieldsets = (
        (None, {"fields": ("nome", "sabor", "slug", "tipo", "linha", "categoria", "objetivo", "ativo", "ordem")}),
        ("Venda", {"fields": ("preco", "estoque", "permite_assinatura")}),
        (
            "Página do produto (só aparecem as seções preenchidas)",
            {
                "fields": (
                    "descricao", "selos", "composicao", "apresentacao", "modo_uso",
                    "informacao_nutricional", "ingredientes", "alergenicos", "diferenciais", "perguntas",
                )
            },
        ),
        ("Frete e embalagem", {"fields": ("peso_kg", "largura_cm", "altura_cm", "comprimento_cm", "cor1", "cor2")}),
    )


# ---------- Pedidos ----------
class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    can_delete = False
    fields = ("nome", "quantidade", "preco_unitario")
    readonly_fields = ("nome", "quantidade", "preco_unitario")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("numero", "nome", "status", "forma_pagamento", "total", "cupom_codigo", "assinatura", "criado_em", "pago_em")
    list_filter = ("status", "forma_pagamento")
    search_fields = ("nome", "email", "cpf", "codigo", "cupom_codigo")
    date_hierarchy = "criado_em"
    inlines = [ItemPedidoInline]
    actions = ["marcar_enviado"]
    exclude = ("pix_copia_cola", "pix_qr_base64")
    readonly_fields = (
        "codigo", "usuario", "criado_em", "pago_em", "nome", "email", "cpf", "telefone", "forma_pagamento",
        "parcelas", "cartao_final", "cartao_bandeira",
        "cep", "rua", "numero", "complemento", "bairro", "cidade", "uf",
        "subtotal", "cupom", "cupom_codigo", "desconto", "desconto_continua", "assinatura",
        "comissao_percentual", "comissao_valor", "frete", "frete_nome", "total",
        "mp_payment_id", "pix_expira_em", "tentativas",
    )

    @admin.display(description="Pedido")
    def numero(self, obj):
        return obj.numero_curto

    @admin.action(description="Marcar pedidos pagos como enviados")
    def marcar_enviado(self, request, queryset):
        queryset.filter(status=Pedido.Status.PAGO).update(status=Pedido.Status.ENVIADO)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.status == Pedido.Status.CANCELADO:  # pedido cancelado não gera comissão
            Comissao.objects.filter(pedido=obj, status=Comissao.Status.PENDENTE).update(
                status=Comissao.Status.CANCELADA
            )

    def has_add_permission(self, request):
        return False


class ItemAssinaturaInline(admin.TabularInline):
    model = ItemAssinatura
    extra = 0


@admin.register(Assinatura)
class AssinaturaAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "status", "frequencia_dias", "proxima_entrega", "cupom")
    list_filter = ("status", "frequencia_dias")
    inlines = [ItemAssinaturaInline]
    readonly_fields = ("usuario", "cupom", "origem", "criado_em")


# ---------- Profissionais de saúde (base do CRM médico/nutricional) ----------
@admin.register(Parceiro)
class ParceiroAdmin(admin.ModelAdmin):
    list_display = (
        "nome_exibicao", "tipo", "registro_formatado", "instituicao", "status",
        "desconto_percentual", "comissao_percentual", "a_pagar_total",
    )
    list_filter = ("status", "tipo", "conselho", "registro_uf")
    search_fields = (
        "usuario__first_name", "usuario__last_name", "usuario__email",
        "registro_profissional", "cnpj", "instituicao",
    )
    readonly_fields = ("usuario", "criado_em")
    actions = ["aprovar", "recusar", "exportar"]

    @admin.display(description="Profissional")
    def nome_exibicao(self, obj):
        return obj.nome

    @admin.display(description="Comissão a pagar (R$)")
    def a_pagar_total(self, obj):
        return obj.a_pagar

    @admin.action(description="Aprovar (libera a área do profissional e os cupons)")
    def aprovar(self, request, queryset):
        queryset.update(status=Parceiro.Status.APROVADO)

    @admin.action(description="Recusar")
    def recusar(self, request, queryset):
        queryset.update(status=Parceiro.Status.RECUSADO)

    @admin.action(description="Exportar selecionados (CSV)")
    def exportar(self, request, queryset):
        colunas = [
            ("Nome", lambda o: o.nome), ("E-mail", lambda o: o.usuario.email),
            ("Profissão", lambda o: o.get_tipo_display()), ("Registro", lambda o: o.registro_formatado),
            ("Instituição", lambda o: o.instituicao), ("CNPJ", lambda o: o.cnpj),
            ("Telefone", lambda o: o.telefone), ("Status", lambda o: o.get_status_display()),
            ("Cadastro", lambda o: o.criado_em.strftime("%d/%m/%Y")),
        ]
        return exportar_csv(self, request, queryset, colunas, "profissionais-mase")


@admin.register(Cupom)
class CupomAdmin(admin.ModelAdmin):
    list_display = ("codigo", "parceiro", "ativo", "criado_em")
    list_filter = ("ativo",)
    search_fields = ("codigo", "parceiro__usuario__first_name", "parceiro__usuario__email")


@admin.register(Comissao)
class ComissaoAdmin(admin.ModelAdmin):
    list_display = ("pedido", "parceiro", "valor", "status", "criado_em", "paga_em")
    list_filter = ("status", "parceiro")
    date_hierarchy = "criado_em"
    readonly_fields = ("parceiro", "pedido", "valor", "criado_em")
    actions = ["marcar_paga", "cancelar"]

    @admin.action(description="Marcar como paga (depois de fazer o pagamento)")
    def marcar_paga(self, request, queryset):
        queryset.filter(status=Comissao.Status.PENDENTE).update(
            status=Comissao.Status.PAGA, paga_em=timezone.now()
        )

    @admin.action(description="Cancelar comissão")
    def cancelar(self, request, queryset):
        queryset.filter(status=Comissao.Status.PENDENTE).update(status=Comissao.Status.CANCELADA)

    def has_add_permission(self, request):
        return False


# ---------- Leads e rotas ----------
@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "tipo", "nome", "empresa", "estado", "status", "responsavel")
    list_editable = ("status", "responsavel")
    list_filter = ("tipo", "status", "estado")
    search_fields = ("nome", "empresa", "email", "cnpj", "mensagem")
    date_hierarchy = "criado_em"
    readonly_fields = ("tipo", "nome", "empresa", "cnpj", "email", "telefone", "estado",
                       "mensagem", "dados", "consentimento", "criado_em", "atualizado_em")
    actions = ["exportar"]

    @admin.action(description="Exportar selecionados (CSV)")
    def exportar(self, request, queryset):
        colunas = [
            ("Data", lambda o: o.criado_em.strftime("%d/%m/%Y %H:%M")), ("Tipo", lambda o: o.get_tipo_display()),
            ("Nome", lambda o: o.nome), ("Empresa", lambda o: o.empresa), ("CNPJ", lambda o: o.cnpj),
            ("E-mail", lambda o: o.email), ("Telefone", lambda o: o.telefone), ("Estado", lambda o: o.estado),
            ("Status", lambda o: o.get_status_display()), ("Responsável", lambda o: o.responsavel),
            ("Detalhes", lambda o: "; ".join(f"{k}: {v}" for k, v in (o.dados or {}).items())),
            ("Mensagem", lambda o: o.mensagem),
        ]
        return exportar_csv(self, request, queryset, colunas, "leads-mase")

    def has_add_permission(self, request):
        return False


@admin.register(RotaContato)
class RotaContatoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "responsavel", "email")
    list_editable = ("responsavel", "email")


# ---------- Conteúdo ----------
@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tipo", "publicado", "criado_em")
    list_filter = ("tipo", "publicado")
    search_fields = ("titulo",)


@admin.register(PontoVenda)
class PontoVendaAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "cidade", "uf", "ativo")
    list_filter = ("tipo", "uf", "ativo")
    search_fields = ("nome", "cidade")


@admin.register(Artigo)
class ArtigoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "publicado_em", "publicado")
    list_filter = ("categoria", "publicado")
    search_fields = ("titulo", "resumo")
    prepopulated_fields = {"slug": ("titulo",)}


@admin.register(FaixaFrete)
class FaixaFreteAdmin(admin.ModelAdmin):
    list_display = ("uf", "valor", "prazo_dias")
    list_editable = ("valor", "prazo_dias")
    search_fields = ("uf",)
