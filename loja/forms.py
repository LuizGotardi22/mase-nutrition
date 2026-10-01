import re

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from . import contas_json
from .models import Assinatura, Cupom, Lead, Parceiro, Pedido
from .utils import cnpj_valido, cpf_valido, so_digitos

User = get_user_model()

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]
ESTADOS = [("", "Selecione")] + [(u, u) for u in UFS]


def _texto(auto="", **extra):
    return forms.TextInput(attrs={"autocomplete": auto, **extra})


def _consentimento():
    return forms.BooleanField(
        label="Autorizo a Mase Nutrition a entrar em contato e a tratar os meus dados para esta finalidade.",
        error_messages={"required": "É necessário autorizar para enviar."},
    )


# ======================================================================
# Checkout
# ======================================================================
class CheckoutForm(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=120, widget=_texto("name"))
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    telefone = forms.CharField(label="Celular com DDD", max_length=20, widget=_texto("tel", inputmode="tel"))
    cpf = forms.CharField(label="CPF", max_length=14, widget=_texto("off", inputmode="numeric"))

    cep = forms.CharField(label="CEP", max_length=9, widget=_texto("postal-code", inputmode="numeric"))
    rua = forms.CharField(label="Rua", max_length=150, widget=_texto("address-line1"))
    numero = forms.CharField(label="Número", max_length=20, widget=_texto("off"))
    complemento = forms.CharField(label="Complemento (opcional)", max_length=80, required=False, widget=_texto("address-line2"))
    bairro = forms.CharField(label="Bairro", max_length=80, widget=_texto("off"))
    cidade = forms.CharField(label="Cidade", max_length=80, widget=_texto("address-level2"))
    uf = forms.CharField(label="UF", max_length=2, widget=_texto("address-level1"))

    forma_pagamento = forms.ChoiceField(
        label="Forma de pagamento", choices=Pedido.FormaPagamento.choices,
        initial=Pedido.FormaPagamento.PIX, widget=forms.RadioSelect,
    )

    # Programa Mase Contínua
    assinar = forms.BooleanField(required=False, label="Quero receber com entrega programada (Programa Mase Contínua)")
    frequencia = forms.TypedChoiceField(
        label="Frequência da entrega", choices=Assinatura.FREQUENCIAS, coerce=int, required=False,
    )

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if len(nome.split()) < 2:
            raise forms.ValidationError("Informe nome e sobrenome.")
        return nome

    def clean_telefone(self):
        tel = so_digitos(self.cleaned_data["telefone"])
        if len(tel) not in (10, 11):
            raise forms.ValidationError("Informe o DDD e o número. Ex: (11) 99999-9999.")
        return tel

    def clean_cpf(self):
        cpf = so_digitos(self.cleaned_data["cpf"])
        if not cpf_valido(cpf):
            raise forms.ValidationError("CPF inválido. Confira os números.")
        return cpf

    def clean_cep(self):
        cep = so_digitos(self.cleaned_data["cep"])
        if len(cep) != 8:
            raise forms.ValidationError("CEP deve ter 8 números.")
        return cep

    def clean_uf(self):
        uf = self.cleaned_data["uf"].strip().upper()
        if uf not in UFS:
            raise forms.ValidationError("UF inválida. Ex: SP.")
        return uf


# ======================================================================
# Conta
# ======================================================================
class LoginForm(forms.Form):
    identificador = forms.CharField(
        label="E-mail", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    senha = forms.CharField(
        label="Senha", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )


class CadastroForm(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=120, widget=_texto("name"))
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    senha2 = forms.CharField(label="Repita a senha", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if len(nome.split()) < 2:
            raise forms.ValidationError("Informe nome e sobrenome.")
        return nome

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existe = User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists()
        if settings.CONTAS_EM_JSON:
            try:
                existe = existe or contas_json.buscar(email) is not None
            except contas_json.ContasJsonErro:
                raise forms.ValidationError("Não foi possível verificar as contas agora. Tente novamente em instantes.")
        if existe:
            raise forms.ValidationError("Já existe uma conta com este e-mail. Tente entrar.")
        return email

    def clean(self):
        dados = super().clean()
        senha, senha2 = dados.get("senha"), dados.get("senha2")
        if senha and senha2 and senha != senha2:
            self.add_error("senha2", "As senhas não conferem.")
        elif senha:
            provisorio = User(
                username=dados.get("email", ""), email=dados.get("email", ""),
                first_name=dados.get("nome", "")[:150],
            )
            try:
                validate_password(senha, provisorio)
            except forms.ValidationError as erro:
                self.add_error("senha", erro)
        return dados


# ======================================================================
# Profissionais de saúde e cupons
# ======================================================================
class ProfissionalForm(forms.ModelForm):
    consentimento = _consentimento()

    class Meta:
        model = Parceiro
        fields = [
            "tipo", "conselho", "registro_profissional", "registro_uf",
            "cnpj", "instituicao", "telefone", "sobre",
        ]
        labels = {
            "tipo": "Profissão / especialidade",
            "conselho": "Conselho profissional",
            "registro_profissional": "Número do registro (CRM ou CRN)",
            "registro_uf": "UF do registro",
            "cnpj": "CNPJ do hospital ou clínica (opcional)",
            "instituicao": "Nome do hospital ou clínica (opcional)",
            "telefone": "Celular com DDD (WhatsApp)",
            "sobre": "Área de atuação (opcional)",
        }
        widgets = {"sobre": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["conselho"].required = True
        self.fields["registro_profissional"].required = True
        self.fields["registro_uf"].required = True
        self.fields["conselho"].choices = [("", "Selecione")] + list(Parceiro.Conselho.choices)
        self.fields["tipo"].choices = [("", "Selecione")] + list(Parceiro.Tipo.choices)

    def clean_telefone(self):
        tel = so_digitos(self.cleaned_data["telefone"])
        if len(tel) not in (10, 11):
            raise forms.ValidationError("Informe o DDD e o número. Ex: (11) 99999-9999.")
        return tel

    def clean_registro_uf(self):
        uf = self.cleaned_data["registro_uf"].strip().upper()
        if uf not in UFS:
            raise forms.ValidationError("UF inválida. Ex: SP.")
        return uf

    def clean_cnpj(self):
        cnpj = so_digitos(self.cleaned_data.get("cnpj", ""))
        if cnpj and not cnpj_valido(cnpj):
            raise forms.ValidationError("CNPJ inválido. Confira os números.")
        return cnpj


class CupomForm(forms.Form):
    codigo = forms.CharField(
        label="Código do cupom", max_length=20,
        widget=forms.TextInput(attrs={"autocomplete": "off", "placeholder": "Ex: DRANA10"}),
    )

    def clean_codigo(self):
        codigo = re.sub(r"\s", "", self.cleaned_data["codigo"]).upper()
        if not re.fullmatch(r"[A-Z0-9]{4,20}", codigo):
            raise forms.ValidationError("Use de 4 a 20 letras ou números, sem espaços, acentos ou símbolos.")
        if Cupom.objects.filter(codigo=codigo).exists():
            raise forms.ValidationError("Este código já está em uso. Escolha outro.")
        return codigo


# ======================================================================
# Leads: contato por interesse e formulário CDMO
# ======================================================================
class ContatoForm(forms.Form):
    assunto = forms.ChoiceField(label="Como podemos ajudar?", choices=Lead.Tipo.choices)
    nome = forms.CharField(label="Nome", max_length=120, widget=_texto("name"))
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    telefone = forms.CharField(label="Telefone / WhatsApp", max_length=20, required=False, widget=_texto("tel", inputmode="tel"))
    empresa = forms.CharField(label="Empresa, hospital ou clínica (se houver)", max_length=120, required=False, widget=_texto("organization"))
    mensagem = forms.CharField(label="Mensagem", widget=forms.Textarea(attrs={"rows": 4}))
    consentimento = _consentimento()

    def clean_telefone(self):
        tel = so_digitos(self.cleaned_data.get("telefone", ""))
        if tel and len(tel) not in (10, 11):
            raise forms.ValidationError("Informe o DDD e o número.")
        return tel


class CdmoForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=120, widget=_texto("name"))
    empresa = forms.CharField(label="Empresa", max_length=120, widget=_texto("organization"))
    cnpj = forms.CharField(label="CNPJ", max_length=18, widget=_texto("off", inputmode="numeric"))
    telefone = forms.CharField(label="Telefone / WhatsApp", max_length=20, widget=_texto("tel", inputmode="tel"))
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    estado = forms.ChoiceField(label="Estado", choices=ESTADOS)
    segmento = forms.CharField(label="Segmento de atuação", max_length=120, widget=_texto("off"))
    produto_desejado = forms.CharField(label="Produto desejado", max_length=160, widget=_texto("off"))
    forma_farmaceutica = forms.ChoiceField(
        label="Forma farmacêutica",
        choices=[("", "Selecione"), ("Pó", "Pó"), ("Cápsula", "Cápsula"), ("Comprimido", "Comprimido"),
                 ("Líquido", "Líquido"), ("Sachê", "Sachê / stick"), ("Barra", "Barra"), ("Outra", "Outra / não sei")],
    )
    quantidade_inicial = forms.CharField(label="Quantidade inicial estimada", max_length=80, widget=_texto("off"))
    possui_formulacao = forms.ChoiceField(
        label="Possui formulação?",
        choices=[("", "Selecione"), ("Sim", "Sim"), ("Não", "Não"), ("Em desenvolvimento", "Em desenvolvimento")],
    )
    possui_marca = forms.ChoiceField(
        label="Possui marca?",
        choices=[("", "Selecione"), ("Sim", "Sim"), ("Não", "Não"), ("Em criação", "Em criação")],
    )
    prazo = forms.ChoiceField(
        label="Prazo estimado do projeto",
        choices=[("", "Selecione"), ("Até 3 meses", "Até 3 meses"), ("3 a 6 meses", "3 a 6 meses"),
                 ("6 a 12 meses", "6 a 12 meses"), ("Acima de 12 meses", "Acima de 12 meses"),
                 ("Ainda não definido", "Ainda não definido")],
    )
    mensagem = forms.CharField(label="Quer contar mais? (opcional)", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    consentimento = _consentimento()

    def clean_cnpj(self):
        cnpj = so_digitos(self.cleaned_data["cnpj"])
        if not cnpj_valido(cnpj):
            raise forms.ValidationError("CNPJ inválido. Confira os números.")
        return cnpj

    def clean_telefone(self):
        tel = so_digitos(self.cleaned_data["telefone"])
        if len(tel) not in (10, 11):
            raise forms.ValidationError("Informe o DDD e o número.")
        return tel
