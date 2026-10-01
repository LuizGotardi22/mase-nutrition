import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import F, Sum, Value
from django.db.models.functions import Greatest
from django.urls import reverse
from django.utils import timezone

LIMITE_POR_ITEM = 10
# Condições padrão para novos profissionais (ajustáveis por profissional no painel).
# Comissão começa em 0: o vínculo com o prescritor é registrado, mas só há comissão se você ativar.
DESCONTO_PADRAO = Decimal("10.00")
COMISSAO_PADRAO = Decimal("0.00")

validador_cor = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use o formato #RRGGBB.")
validador_percentual = [MinValueValidator(0), MaxValueValidator(100)]


# ======================================================================
# Catálogo
# ======================================================================
class Linha(models.Model):
    """Linhas Mase Clinical Care (Neurocare, Immunocare...). Cada linha tem página própria."""

    class Status(models.TextChoices):
        DESENVOLVIMENTO = "desenvolvimento", "Em desenvolvimento"
        LANCADA = "lancada", "Lançada"

    slug = models.SlugField(unique=True)
    nome = models.CharField(max_length=60)
    foco = models.CharField("resumo curto", max_length=160, blank=True)
    descricao = models.TextField("descrição da página", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DESENVOLVIMENTO)
    ordem = models.PositiveIntegerField(default=0)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("linha", args=[self.slug])


class Produto(models.Model):
    class Tipo(models.TextChoices):
        PRODUTO = "produto", "Produto"
        KIT = "kit", "Kit"

    CATEGORIAS = [
        ("whey", "Whey Protein"),
        ("creatina", "Creatina"),
        ("colageno", "Colágeno & Vitaminas"),
        ("outros", "Barras & Aminoácidos"),
    ]

    slug = models.SlugField(unique=True)
    nome = models.CharField(max_length=120)
    sabor = models.CharField("sabor / apresentação curta", max_length=80, blank=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.PRODUTO)
    linha = models.ForeignKey(
        Linha, related_name="produtos", null=True, blank=True, on_delete=models.SET_NULL
    )
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, blank=True)
    objetivo = models.CharField(
        "objetivo nutricional", max_length=120, blank=True,
        help_text="Use somente objetivos permitidos pela regulamentação aplicável.",
    )
    descricao = models.TextField("descrição", blank=True)
    selos = models.CharField(
        max_length=200, blank=True, help_text="Separe por vírgula. Ex: Sem lactose, Sem glúten"
    )

    # Seções da página do produto (só aparecem as preenchidas, na ordem do briefing)
    composicao = models.TextField("composição", blank=True)
    apresentacao = models.TextField("apresentação", blank=True)
    modo_uso = models.TextField("modo de uso", blank=True)
    informacao_nutricional = models.TextField("informação nutricional", blank=True)
    ingredientes = models.TextField(blank=True)
    alergenicos = models.TextField("alergênicos", blank=True)
    diferenciais = models.TextField(blank=True)
    perguntas = models.TextField(
        "perguntas frequentes", blank=True,
        help_text="Uma pergunta por bloco: 1ª linha = pergunta, linhas seguintes = resposta. Separe blocos com uma linha em branco.",
    )

    preco = models.DecimalField("preço (R$)", max_digits=8, decimal_places=2)
    estoque = models.PositiveIntegerField(default=0)
    permite_assinatura = models.BooleanField("participa do Mase Contínua", default=True)

    # Usados no cálculo de frete
    peso_kg = models.DecimalField("peso (kg)", max_digits=6, decimal_places=3, default=0.5)
    largura_cm = models.PositiveIntegerField("largura (cm)", default=12)
    altura_cm = models.PositiveIntegerField("altura (cm)", default=18)
    comprimento_cm = models.PositiveIntegerField("comprimento (cm)", default=12)

    cor1 = models.CharField("cor 1 da embalagem", max_length=7, default="#0D2356", validators=[validador_cor])
    cor2 = models.CharField("cor 2 da embalagem", max_length=7, default="#1B4A9C", validators=[validador_cor])

    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "nome", "sabor"]

    def __str__(self):
        return f"{self.nome} — {self.sabor}" if self.sabor else self.nome

    def get_absolute_url(self):
        return reverse("produto", args=[self.slug])

    @property
    def rotulo(self):
        return self.linha.nome if self.linha_id else self.get_categoria_display()

    @property
    def selos_lista(self):
        return [s.strip() for s in self.selos.split(",") if s.strip()]

    @property
    def max_compra(self):
        return min(self.estoque, LIMITE_POR_ITEM)

    @property
    def faq_lista(self):
        itens = []
        for bloco in re.split(r"\n\s*\n", self.perguntas.strip()):
            linhas = [x.strip() for x in bloco.splitlines() if x.strip()]
            if len(linhas) >= 2:
                itens.append((linhas[0], " ".join(linhas[1:])))
        return itens


# ======================================================================
# Profissionais de saúde (prescritores), cupons e comissões
# ======================================================================
class Parceiro(models.Model):
    """Profissional de saúde cadastrado. Mantém o nome interno 'Parceiro'."""

    class Tipo(models.TextChoices):
        NUTRICIONISTA = "nutricionista", "Nutricionista clínico"
        ALERGISTA = "alergista", "Alergista / Imunologista"
        NUTROLOGO = "nutrologo", "Nutrólogo"
        GASTRO = "gastroenterologista", "Gastroenterologista"
        PEDIATRA = "pediatra", "Pediatra"
        ALERGOPEDIATRA = "alergopediatra", "Alergopediatra"
        ENDOCRINO = "endocrinologista", "Endocrinologista"
        BARIATRICO = "bariatrico", "Bariátrico (cirurgia / equipe)"
        ONCOLOGISTA = "oncologista", "Oncologista"
        GERIATRA = "geriatra", "Geriatra"
        MEDICO = "medico", "Médico(a) de outra especialidade"
        OUTRO = "outro", "Outro profissional da nutrição clínica"

    class Conselho(models.TextChoices):
        CRM = "CRM", "CRM — Conselho Regional de Medicina"
        CRN = "CRN", "CRN — Conselho Regional de Nutrição"
        OUTRO = "OUTRO", "Outro conselho"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Em análise"
        APROVADO = "aprovado", "Aprovado"
        RECUSADO = "recusado", "Não aprovado"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="parceiro", on_delete=models.CASCADE
    )
    tipo = models.CharField("profissão / especialidade", max_length=20, choices=Tipo.choices)
    conselho = models.CharField(max_length=5, choices=Conselho.choices, blank=True)
    registro_profissional = models.CharField("número do registro", max_length=40, blank=True)
    registro_uf = models.CharField("UF do registro", max_length=2, blank=True)
    cnpj = models.CharField("CNPJ do hospital/clínica", max_length=14, blank=True)
    instituicao = models.CharField("hospital / clínica", max_length=120, blank=True)
    telefone = models.CharField(max_length=20)
    instagram = models.CharField(max_length=60, blank=True)
    chave_pix = models.CharField("chave Pix para receber", max_length=77, blank=True)
    sobre = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    desconto_percentual = models.DecimalField(
        "desconto para o paciente (%)", max_digits=5, decimal_places=2,
        default=DESCONTO_PADRAO, validators=validador_percentual,
        help_text="Desconto que o cliente ganha ao usar o cupom deste profissional.",
    )
    comissao_percentual = models.DecimalField(
        "comissão (%)", max_digits=5, decimal_places=2,
        default=COMISSAO_PADRAO, validators=validador_percentual,
        help_text="0 = sem comissão. Calculada sobre o valor dos produtos com desconto (sem frete). "
                  "Confirme antes as regras do conselho profissional.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "profissional de saúde"
        verbose_name_plural = "profissionais de saúde"

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

    @property
    def nome(self):
        return self.usuario.get_full_name() or self.usuario.username

    @property
    def registro_formatado(self):
        if not self.registro_profissional:
            return ""
        uf = f"/{self.registro_uf}" if self.registro_uf else ""
        return f"{self.conselho} {self.registro_profissional}{uf}".strip()

    @property
    def a_pagar(self):
        total = self.comissoes.filter(status=Comissao.Status.PENDENTE).aggregate(t=Sum("valor"))["t"]
        return total or Decimal("0.00")


class Cupom(models.Model):
    parceiro = models.ForeignKey(Parceiro, related_name="cupons", on_delete=models.CASCADE)
    codigo = models.CharField(max_length=20, unique=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name_plural = "cupons"

    def save(self, *args, **kwargs):
        self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.codigo


# ======================================================================
# Pedidos
# ======================================================================
class Pedido(models.Model):
    class Status(models.TextChoices):
        AGUARDANDO = "aguardando", "Aguardando pagamento"
        PAGO = "pago", "Pago"
        ENVIADO = "enviado", "Enviado"
        CANCELADO = "cancelado", "Cancelado"
        EXPIRADO = "expirado", "Pix expirado"

    class FormaPagamento(models.TextChoices):
        PIX = "pix", "Pix"
        CARTAO = "cartao", "Cartão de crédito ou débito"

    codigo = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="pedidos", null=True, blank=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AGUARDANDO)
    forma_pagamento = models.CharField(max_length=10, choices=FormaPagamento.choices, default=FormaPagamento.PIX)

    nome = models.CharField(max_length=120)
    email = models.EmailField()
    cpf = models.CharField(max_length=11)
    telefone = models.CharField(max_length=20)

    cep = models.CharField(max_length=8)
    rua = models.CharField(max_length=150)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=80, blank=True)
    bairro = models.CharField(max_length=80)
    cidade = models.CharField(max_length=80)
    uf = models.CharField(max_length=2)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    cupom = models.ForeignKey(
        Cupom, related_name="pedidos", null=True, blank=True, on_delete=models.PROTECT
    )
    cupom_codigo = models.CharField(max_length=20, blank=True)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto_continua = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    assinatura = models.ForeignKey(
        "Assinatura", related_name="pedidos", null=True, blank=True, on_delete=models.SET_NULL
    )
    comissao_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    comissao_valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    frete = models.DecimalField(max_digits=8, decimal_places=2)
    frete_nome = models.CharField(max_length=60, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    mp_payment_id = models.CharField(max_length=40, blank=True)
    pix_copia_cola = models.TextField(blank=True)
    pix_qr_base64 = models.TextField(blank=True)
    pix_expira_em = models.DateTimeField(null=True, blank=True)
    parcelas = models.PositiveSmallIntegerField(default=1)
    cartao_final = models.CharField("4 últimos dígitos do cartão", max_length=4, blank=True)
    cartao_bandeira = models.CharField("bandeira do cartão", max_length=30, blank=True)
    tentativas = models.PositiveSmallIntegerField(default=0)

    codigo_rastreio = models.CharField(max_length=40, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    pago_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Pedido {self.numero_curto} — {self.nome}"

    @property
    def numero_curto(self):
        return f"#{self.pk:05d}" if self.pk else "#—"

    @property
    def valor_produtos(self):
        """Valor dos produtos já com descontos (base da comissão)."""
        return self.subtotal - self.desconto - self.desconto_continua

    @property
    def endereco_completo(self):
        partes = [f"{self.rua}, {self.numero}"]
        if self.complemento:
            partes.append(self.complemento)
        partes.append(self.bairro)
        partes.append(f"{self.cidade}/{self.uf}")
        return " — ".join(partes) + f" — CEP {self.cep[:5]}-{self.cep[5:]}"

    def marcar_pago(self):
        """Confirma o pagamento uma única vez: baixa estoque, gera comissão e ativa a assinatura."""
        with transaction.atomic():
            pedido = Pedido.objects.select_for_update().get(pk=self.pk)
            if pedido.status not in (self.Status.AGUARDANDO, self.Status.EXPIRADO):
                return False
            pedido.status = self.Status.PAGO
            pedido.pago_em = timezone.now()
            pedido.save(update_fields=["status", "pago_em"])
            for item in pedido.itens.all():
                if item.produto_id:
                    Produto.objects.filter(pk=item.produto_id).update(
                        estoque=Greatest(F("estoque") - item.quantidade, Value(0))
                    )
            if pedido.cupom_id and pedido.comissao_valor > 0:
                Comissao.objects.get_or_create(
                    pedido=pedido,
                    defaults={
                        "parceiro_id": pedido.cupom.parceiro_id,
                        "valor": pedido.comissao_valor,
                    },
                )
            if pedido.assinatura_id:
                ass = pedido.assinatura
                if ass.status == Assinatura.Status.PENDENTE:
                    ass.status = Assinatura.Status.ATIVA
                    ass.proxima_entrega = date.today() + timedelta(days=ass.frequencia_dias)
                    ass.save(update_fields=["status", "proxima_entrega"])
        self.refresh_from_db()
        return True


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name="itens", on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, null=True, on_delete=models.SET_NULL)
    nome = models.CharField(max_length=220)  # copia do nome no momento da compra
    preco_unitario = models.DecimalField(max_digits=8, decimal_places=2)
    quantidade = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantidade}x {self.nome}"

    @property
    def subtotal(self):
        return self.preco_unitario * self.quantidade


class Comissao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "A pagar"
        PAGA = "paga", "Paga"
        CANCELADA = "cancelada", "Cancelada"

    parceiro = models.ForeignKey(Parceiro, related_name="comissoes", on_delete=models.PROTECT)
    pedido = models.OneToOneField(Pedido, related_name="comissao", on_delete=models.PROTECT)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    criado_em = models.DateTimeField(auto_now_add=True)
    paga_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "comissão"
        verbose_name_plural = "comissões"

    def __str__(self):
        return f"{self.pedido.numero_curto} — {self.parceiro.nome} — R$ {self.valor}"


# ======================================================================
# Programa Mase Contínua (compra recorrente, sempre com o prescritor vinculado)
# ======================================================================
class Assinatura(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "Aguardando 1º pagamento"
        ATIVA = "ativa", "Ativa"
        PAUSADA = "pausada", "Pausada"
        CANCELADA = "cancelada", "Cancelada"

    FREQUENCIAS = [(30, "A cada 30 dias"), (60, "A cada 60 dias"), (90, "A cada 90 dias")]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="assinaturas", on_delete=models.CASCADE)
    cupom = models.ForeignKey(
        Cupom, related_name="assinaturas", null=True, blank=True, on_delete=models.PROTECT
    )
    origem = models.ForeignKey("Pedido", related_name="+", null=True, blank=True, on_delete=models.SET_NULL)
    frequencia_dias = models.PositiveSmallIntegerField(choices=FREQUENCIAS, default=30)
    proxima_entrega = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "assinatura Mase Contínua"
        verbose_name_plural = "assinaturas Mase Contínua"

    def __str__(self):
        return f"Assinatura #{self.pk} — {self.usuario}"


class ItemAssinatura(models.Model):
    assinatura = models.ForeignKey(Assinatura, related_name="itens", on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantidade}x {self.produto}"


# ======================================================================
# Leads / CRM
# ======================================================================
class Lead(models.Model):
    class Tipo(models.TextChoices):
        COMPRAR = "comprar", "Quero comprar produtos Mase"
        PROFISSIONAL = "profissional", "Sou profissional de saúde"
        CDMO = "cdmo", "Quero desenvolver minha marca — CDMO"
        INGREDIENTES = "ingredientes", "Quero comprar ingredientes"
        DISTRIBUIDOR = "distribuidor", "Quero representar/distribuir a Mase"
        HOSPITAL = "hospital", "Sou hospital/clínica"
        OUTROS = "outros", "Outros assuntos"

    class Status(models.TextChoices):
        NOVO = "novo", "Novo"
        EM_CONTATO = "em_contato", "Em contato"
        PROPOSTA = "proposta", "Proposta enviada"
        CONVERTIDO = "convertido", "Convertido"
        PERDIDO = "perdido", "Perdido"

    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NOVO)
    nome = models.CharField(max_length=120)
    empresa = models.CharField(max_length=120, blank=True)
    cnpj = models.CharField(max_length=14, blank=True)
    email = models.EmailField()
    telefone = models.CharField(max_length=20, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    mensagem = models.TextField(blank=True)
    dados = models.JSONField("dados do formulário", default=dict, blank=True)
    responsavel = models.CharField("consultor responsável", max_length=80, blank=True)
    notas = models.TextField("anotações internas", blank=True)
    consentimento = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.nome}"


class RotaContato(models.Model):
    """Para quem cada tipo de contato é encaminhado."""

    tipo = models.CharField(max_length=15, choices=Lead.Tipo.choices, unique=True)
    responsavel = models.CharField("responsável", max_length=80, blank=True)
    email = models.EmailField("e-mail do responsável", blank=True)

    class Meta:
        verbose_name = "rota de contato"
        verbose_name_plural = "rotas de contato"

    def __str__(self):
        return self.get_tipo_display()


# ======================================================================
# Conteúdo
# ======================================================================
class Material(models.Model):
    """Material técnico exclusivo para profissionais de saúde aprovados."""

    class Tipo(models.TextChoices):
        LITERATURA = "literatura", "Literatura científica"
        FICHA = "ficha", "Ficha técnica"
        INFO = "info", "Informação nutricional"
        PACIENTE = "paciente", "Material para pacientes"
        WEBINAR = "webinar", "Webinar"
        EVENTO = "evento", "Evento"
        AULA = "aula", "Aula"
        PROTOCOLO = "protocolo", "Protocolo educacional"

    titulo = models.CharField(max_length=160)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    descricao = models.TextField(blank=True)
    arquivo = models.FileField(upload_to="materiais/", blank=True)
    link = models.URLField("link (webinar, evento, aula)", blank=True)
    publicado = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tipo", "-criado_em"]
        verbose_name_plural = "materiais"

    def __str__(self):
        return self.titulo


class PontoVenda(models.Model):
    class Tipo(models.TextChoices):
        LOJA = "loja", "Loja especializada"
        FARMACIA = "farmacia", "Farmácia"
        CLINICA = "clinica", "Clínica"
        DISTRIBUIDOR = "distribuidor", "Distribuidor autorizado"

    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    cidade = models.CharField(max_length=80)
    uf = models.CharField(max_length=2)
    endereco = models.CharField(max_length=200, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    site = models.URLField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["uf", "cidade", "nome"]
        verbose_name = "ponto de venda"
        verbose_name_plural = "pontos de venda"

    def __str__(self):
        return f"{self.nome} — {self.cidade}/{self.uf}"


class Artigo(models.Model):
    """Conteúdo público do Mase Science (informativo geral, sem material técnico restrito)."""

    CATEGORIAS = [
        ("alergias-alimentares", "Alergias alimentares"),
        ("nutricao-clinica", "Nutrição clínica"),
        ("microbiota", "Microbiota e saúde intestinal"),
        ("obesidade-glp1", "Obesidade e GLP-1"),
        ("massa-muscular", "Massa muscular e sarcopenia"),
        ("longevidade", "Nutrição na longevidade"),
        ("oncologica", "Nutrição oncológica"),
        ("bariatrica", "Bariátrica"),
        ("ingredientes", "Ciência dos ingredientes"),
    ]

    titulo = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    categoria = models.CharField(max_length=30, choices=CATEGORIAS)
    resumo = models.CharField(max_length=300, blank=True)
    corpo = models.TextField()
    publicado = models.BooleanField(default=True)
    publicado_em = models.DateField(default=date.today)

    class Meta:
        ordering = ["-publicado_em", "-id"]

    def __str__(self):
        return self.titulo

    def get_absolute_url(self):
        return reverse("science_artigo", args=[self.slug])


class FaixaFrete(models.Model):
    """Valor de frete por estado de destino (usado quando não há cotação de transportadora)."""

    uf = models.CharField("estado (UF)", max_length=2, unique=True)
    valor = models.DecimalField("valor do frete (R$)", max_digits=8, decimal_places=2)
    prazo_dias = models.PositiveSmallIntegerField("prazo (dias úteis)", null=True, blank=True)

    class Meta:
        ordering = ["uf"]
        verbose_name = "frete por estado"
        verbose_name_plural = "frete por estado"

    def __str__(self):
        return f"{self.uf} — R$ {self.valor}"
