import re


def so_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def cpf_valido(cpf):
    """Valida CPF (11 dígitos, dígitos verificadores corretos)."""
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in (9, 10):
        soma = sum(int(cpf[n]) * ((i + 1) - n) for n in range(i))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[i]):
            return False
    return True


def cnpj_valido(cnpj):
    """Valida CNPJ (14 dígitos, dígitos verificadores corretos)."""
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    def digito(base):
        pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] if len(base) == 12 else [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)

    return cnpj[12] == digito(cnpj[:12]) and cnpj[13] == digito(cnpj[:13])


# Faixas de CEP por estado (tabela dos Correios). Usado para achar o estado do CEP sem depender de internet.
_FAIXAS_CEP = [
    (1000000, 19999999, "SP"), (20000000, 28999999, "RJ"), (29000000, 29999999, "ES"),
    (30000000, 39999999, "MG"), (40000000, 48999999, "BA"), (49000000, 49999999, "SE"),
    (50000000, 56999999, "PE"), (57000000, 57999999, "AL"), (58000000, 58999999, "PB"),
    (59000000, 59999999, "RN"), (60000000, 63999999, "CE"), (64000000, 64999999, "PI"),
    (65000000, 65999999, "MA"), (66000000, 68899999, "PA"), (68900000, 68999999, "AP"),
    (69000000, 69299999, "AM"), (69300000, 69399999, "RR"), (69400000, 69899999, "AM"),
    (69900000, 69999999, "AC"), (70000000, 72799999, "DF"), (72800000, 72999999, "GO"),
    (73000000, 73699999, "DF"), (73700000, 76799999, "GO"), (76800000, 76999999, "RO"),
    (77000000, 77999999, "TO"), (78000000, 78899999, "MT"), (78900000, 78999999, "RO"),
    (79000000, 79999999, "MS"), (80000000, 87999999, "PR"), (88000000, 89999999, "SC"),
    (90000000, 99999999, "RS"),
]


def uf_do_cep(cep):
    """Estado (UF) de um CEP de 8 dígitos, ou "" se não reconhecer."""
    digitos = so_digitos(cep)
    if len(digitos) != 8:
        return ""
    numero = int(digitos)
    for inicio, fim, uf in _FAIXAS_CEP:
        if inicio <= numero <= fim:
            return uf
    return ""
