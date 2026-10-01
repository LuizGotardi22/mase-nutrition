from decimal import Decimal

from django.core.management.base import BaseCommand

from loja.models import FaixaFrete, Lead, Linha, Produto, RotaContato

LINHAS = [
    dict(
        slug="neurocare", nome="Neurocare",
        foco="Nutrição especializada para necessidades neurológicas.",
        descricao="A linha Neurocare reúne fórmulas pensadas para pacientes com necessidades neurológicas, "
                   "como disfagia e demandas específicas de consistência e densidade calórica. Desenvolvida com "
                   "rigoroso controle de alergênicos e composição adequada ao acompanhamento nutricional desses pacientes.",
    ),
    dict(
        slug="immunocare", nome="Immunocare",
        foco="Nutrição especializada para necessidades imunológicas.",
        descricao="A linha Immunocare foi desenvolvida para apoiar pacientes com alergias e intolerâncias alimentares, "
                   "com fórmulas isentas dos alergênicos mais comuns e voltadas ao suporte nutricional em quadros "
                   "de restrição imunológica, sempre sob a plataforma de segurança Allergen Free.",
    ),
    dict(
        slug="oncocare", nome="Oncocare",
        foco="Nutrição especializada para pacientes oncológicos.",
        descricao="A linha Oncocare atende às necessidades nutricionais de pacientes em tratamento oncológico, "
                   "com fórmulas hipercalóricas e hiperproteicas voltadas à manutenção de peso e massa muscular "
                   "durante o tratamento, desenvolvidas em conjunto com a equipe de nutrição clínica.",
    ),
    dict(
        slug="bariacare", nome="Bariacare",
        foco="Nutrição especializada para o paciente bariátrico.",
        descricao="A linha Bariacare acompanha o paciente bariátrico nas diferentes fases do pós-operatório, com "
                   "fórmulas de alta densidade proteica e baixo volume, adequadas às restrições digestivas típicas "
                   "dessa fase de tratamento.",
    ),
    dict(
        slug="metabolicare", nome="Metabolicare",
        foco="Nutrição especializada para necessidades metabólicas.",
        descricao="A linha Metabolicare foi desenvolvida para necessidades metabólicas específicas, como diabetes "
                   "e síndrome metabólica, com controle de carga glicêmica e perfil nutricional adequado ao "
                   "acompanhamento desses pacientes.",
    ),
    dict(
        slug="seniorcare", nome="Seniorcare",
        foco="Nutrição especializada para a longevidade.",
        descricao="A linha Seniorcare foi criada para apoiar a nutrição do paciente idoso, com foco na prevenção "
                   "e no manejo da sarcopenia, oferecendo alta densidade proteica em porções reduzidas, mais "
                   "fáceis de consumir por quem tem baixo apetite.",
    ),
]

# ATENÇÃO: preços, estoque, peso e dimensões são EXEMPLOS. Ajuste no painel (/painel/).
PRODUTOS_POR_LINHA = [
    dict(slug="neurocare-espessante", nome="Espessante Alimentar Neurocare", sabor="300g · Sem sabor",
         linha="neurocare", cor1="#0D2356", cor2="#1B4A9C",
         selos="Sem lactose, Sem glúten", objetivo="Disfagia",
         descricao="Espessante instantâneo para ajuste de consistência de líquidos e alimentos em pacientes com disfagia, sem alterar o sabor.",
         composicao="Amido modificado de milho, goma xantana.",
         apresentacao="Pote de 300g, com colher medidora.",
         modo_uso="Adicione aos poucos até atingir a consistência recomendada pelo profissional de saúde (néctar, mel ou pudim). Misture bem e aguarde 1 a 2 minutos.",
         alergenicos="Não contém lactose nem glúten.",
         diferenciais="Não altera cor nem sabor do alimento. Dilui sem formar grumos.",
         preco="79.90", peso="0.300", dim=(9, 12, 9)),
    dict(slug="immunocare-formula-livre", nome="Immunocare Fórmula Livre", sabor="Baunilha · 400g",
         linha="immunocare", cor1="#12306F", cor2="#2F6FBF",
         selos="Sem lactose, Sem glúten, Sem soja, Sem ovo", objetivo="Alergia alimentar",
         descricao="Fórmula nutricional isenta dos alergênicos mais comuns, para suporte nutricional em quadros de restrição imunológica e alergia alimentar múltipla.",
         composicao="Proteína isolada de ervilha, maltodextrina, óleos vegetais, vitaminas e minerais.",
         apresentacao="Lata de 400g.",
         modo_uso="Diluir conforme orientação do profissional de saúde. Uso sob acompanhamento nutricional.",
         alergenicos="Formulado sem os alergênicos alimentares mais comuns (leite, glúten, soja, ovo).",
         diferenciais="Cada lote é testado em laboratório terceirizado antes da liberação.",
         preco="129.90", peso="0.400", dim=(10, 15, 10)),
    dict(slug="oncocare-hiperproteico", nome="Oncocare Hiperproteico", sabor="Baunilha · 380g",
         linha="oncocare", cor1="#0D2356", cor2="#24508F",
         selos="Sem lactose, Sem glúten", objetivo="Suporte oncológico",
         descricao="Fórmula hipercalórica e hiperproteica para suporte nutricional durante o tratamento oncológico, voltada à manutenção de peso e massa muscular.",
         composicao="Proteína isolada, maltodextrina, óleos vegetais (TCM), vitaminas e minerais.",
         apresentacao="Lata de 380g.",
         modo_uso="Uso conforme orientação do profissional de saúde responsável pelo acompanhamento oncológico.",
         alergenicos="Sem lactose e sem glúten.",
         diferenciais="Alta densidade calórica em baixo volume, para menor esforço na ingestão.",
         preco="139.90", peso="0.380", dim=(10, 15, 10)),
    dict(slug="bariacare-proteina", nome="Bariacare Proteína Concentrada", sabor="Neutro · 300g",
         linha="bariacare", cor1="#12306F", cor2="#1B4A9C",
         selos="Sem lactose, Sem glúten, Baixo volume", objetivo="Pós-bariátrica",
         descricao="Proteína concentrada de baixo volume para as diferentes fases do pós-operatório bariátrico, adequada às restrições digestivas desse período.",
         composicao="Proteína isolada do soro do leite (whey isolado) ou blend vegetal, conforme apresentação.",
         apresentacao="Pote de 300g, com colher medidora.",
         modo_uso="Diluir 1 dose em água ou líquido de preferência, conforme orientação nutricional da fase pós-cirúrgica.",
         alergenicos="Sem glúten. Confira a apresentação para presença de derivados do leite.",
         diferenciais="Alta concentração proteica em pequeno volume, adequada à capacidade gástrica reduzida.",
         preco="119.90", peso="0.300", dim=(9, 13, 9)),
    dict(slug="metabolicare-diabetes", nome="Metabolicare Controle Glicêmico", sabor="Chocolate · 380g",
         linha="metabolicare", cor1="#0D2356", cor2="#2F6FBF",
         selos="Sem lactose, Sem glúten, Baixo índice glicêmico", objetivo="Diabetes / síndrome metabólica",
         descricao="Fórmula nutricional com controle de carga glicêmica, desenvolvida para pacientes com diabetes e síndrome metabólica.",
         composicao="Carboidratos de absorção lenta, proteína isolada, fibras, vitaminas e minerais.",
         apresentacao="Lata de 380g.",
         modo_uso="Uso conforme orientação do profissional de saúde, considerando o plano alimentar individual.",
         alergenicos="Sem lactose e sem glúten.",
         diferenciais="Perfil de carboidratos formulado para menor impacto glicêmico.",
         preco="134.90", peso="0.380", dim=(10, 15, 10)),
    dict(slug="seniorcare-antissarcopenia", nome="Seniorcare Proteína Sênior", sabor="Baunilha · 350g",
         linha="seniorcare", cor1="#12306F", cor2="#24508F",
         selos="Sem lactose, Sem glúten, Alta proteína", objetivo="Prevenção da sarcopenia",
         descricao="Fórmula com alta densidade proteica em porções reduzidas, desenvolvida para apoiar a prevenção e o manejo da sarcopenia em pacientes idosos com baixo apetite.",
         composicao="Proteína isolada, leucina, vitamina D, cálcio.",
         apresentacao="Pote de 350g, com colher medidora.",
         modo_uso="Diluir 1 dose em água, suco ou outro líquido de preferência, entre as refeições.",
         alergenicos="Sem lactose e sem glúten.",
         diferenciais="Enriquecido com leucina e vitamina D para apoio à massa muscular.",
         preco="124.90", peso="0.350", dim=(9, 14, 9)),
]

PRODUTOS = [
    dict(slug="whey-iso-baunilha", nome="Whey Isolado Zero Lactose", sabor="Baunilha", categoria="whey",
         cor1="#0D2356", cor2="#1B4A9C", selos="Sem lactose, Sem glúten",
         descricao="Whey protein isolado com processo de filtração que remove praticamente toda a lactose — feito para quem sente desconforto com whey comum.",
         preco="149.90", peso="0.950", dim=(12, 20, 12)),
    dict(slug="whey-iso-chocolate", nome="Whey Isolado Zero Lactose", sabor="Chocolate", categoria="whey",
         cor1="#0D2356", cor2="#1B4A9C", selos="Sem lactose, Sem glúten",
         descricao="Mesma fórmula do isolado zero lactose, no sabor chocolate. 25g de proteína por dose, sem adição de corantes artificiais.",
         preco="149.90", peso="0.950", dim=(12, 20, 12)),
    dict(slug="whey-vegano-neutro", nome="Whey Vegano Ervilha + Arroz", sabor="Sabor Neutro", categoria="whey",
         cor1="#12306F", cor2="#2F6FBF", selos="Sem soja, Sem lactose, Vegano",
         descricao="Blend de proteína de ervilha e arroz para quem tem restrição a soja e derivados do leite. Perfil de aminoácidos completo.",
         preco="139.90", peso="0.950", dim=(12, 20, 12)),
    dict(slug="creatina-pura", nome="Creatina Monohidratada Pura", sabor="300g · Sem sabor", categoria="creatina",
         cor1="#0D2356", cor2="#24508F", selos="Ingrediente único, Sem aditivos",
         descricao="Creatina monohidratada micronizada, sem misturas nem excipientes — só o ativo, testado em laboratório terceirizado.",
         preco="89.90", peso="0.400", dim=(10, 14, 10)),
    dict(slug="creatina-capsulas", nome="Creatina em Cápsulas", sabor="120 cápsulas", categoria="creatina",
         cor1="#12306F", cor2="#2F6FBF", selos="Sem corantes, Fácil de viajar",
         descricao="Mesma creatina monohidratada pura, encapsulada sem corantes ou conservantes — prática para quem viaja ou treina fora de casa.",
         preco="99.90", peso="0.200", dim=(8, 12, 8)),
    dict(slug="colageno-neutro", nome="Colágeno Hidrolisado", sabor="Sabor Neutro", categoria="colageno",
         cor1="#0D2356", cor2="#1B4A9C", selos="Sem glúten, Sem lactose",
         descricao="Peptídeos de colágeno hidrolisado, solúveis a frio, sem sabor residual. Livre de glúten e lactose.",
         preco="79.90", peso="0.450", dim=(10, 16, 10)),
    dict(slug="multivitaminico", nome="Multivitamínico Diário", sabor="60 cápsulas", categoria="colageno",
         cor1="#12306F", cor2="#2F6FBF", selos="Sem corantes artificiais, Sem glúten",
         descricao="Combinação de vitaminas e minerais essenciais, formulada sem corantes artificiais para quem tem sensibilidade a aditivos.",
         preco="69.90", peso="0.150", dim=(7, 11, 7)),
    dict(slug="bcaa-limao", nome="BCAA 2:1:1", sabor="Limão", categoria="outros",
         cor1="#0D2356", cor2="#24508F", selos="Sem soja, Sem corantes",
         descricao="Aminoácidos de cadeia ramificada na proporção 2:1:1, adoçado com estévia, sem derivados de soja na fórmula.",
         preco="74.90", peso="0.350", dim=(10, 14, 10)),
    dict(slug="barra-proteica", nome="Barra Proteica", sabor="Caixa com 12 un.", categoria="outros",
         cor1="#12306F", cor2="#1B4A9C", selos="Sem glúten, Sem lactose",
         descricao="Barra de 20g de proteína, sem glúten e sem lactose, adoçada naturalmente — boa opção de lanche pós-treino.",
         preco="89.90", peso="0.350", dim=(20, 8, 15)),
]


# Frete por estado: valores de EXEMPLO (origem supondo São Paulo). Ajuste em /painel/ > Frete por estado.
FRETE_ESTADOS = {
    "SP": ("14.90", 3),
    "RJ": ("19.90", 4), "MG": ("19.90", 4), "ES": ("21.90", 5),
    "PR": ("24.90", 5), "SC": ("24.90", 5), "RS": ("26.90", 6),
    "DF": ("27.90", 6), "GO": ("27.90", 6), "MT": ("29.90", 7), "MS": ("27.90", 6),
    "BA": ("32.90", 8), "SE": ("32.90", 8), "AL": ("32.90", 8), "PE": ("32.90", 8), "PB": ("32.90", 8),
    "RN": ("34.90", 9), "CE": ("34.90", 9), "PI": ("34.90", 9), "MA": ("34.90", 9),
    "PA": ("39.90", 10), "AM": ("44.90", 12), "AC": ("44.90", 12), "RO": ("42.90", 11),
    "RR": ("44.90", 12), "AP": ("44.90", 12), "TO": ("37.90", 9),
}


class Command(BaseCommand):
    help = "Cadastra linhas, rotas de contato e os produtos de exemplo (não sobrescreve o que você já editou)."

    def handle(self, *args, **options):
        # Linhas Clinical Care
        novas = 0
        linha_por_slug = {}
        for ordem, dados in enumerate(LINHAS):
            linha, criada = Linha.objects.get_or_create(
                slug=dados["slug"],
                defaults=dict(
                    nome=dados["nome"], foco=dados["foco"], descricao=dados["descricao"],
                    status=Linha.Status.LANCADA, ordem=ordem,
                ),
            )
            linha_por_slug[dados["slug"]] = linha
            novas += int(criada)

        # Rotas de contato (o responsável e o e-mail são preenchidos no painel)
        for valor, _rotulo in Lead.Tipo.choices:
            RotaContato.objects.get_or_create(tipo=valor)

        # Frete por estado (não sobrescreve o que você já editou)
        for uf, (valor, prazo) in FRETE_ESTADOS.items():
            FaixaFrete.objects.get_or_create(uf=uf, defaults={"valor": Decimal(valor), "prazo_dias": prazo})

        # Produtos das linhas Clinical Care (um exemplo por linha, com todas as seções preenchidas)
        criados_linha = 0
        for ordem, dados in enumerate(PRODUTOS_POR_LINHA):
            dados = dict(dados)
            largura, altura, comprimento = dados.pop("dim")
            slug = dados.pop("slug")
            preco, peso = Decimal(dados.pop("preco")), Decimal(dados.pop("peso"))
            linha_slug = dados.pop("linha")
            _, novo = Produto.objects.get_or_create(
                slug=slug,
                defaults=dict(
                    **dados, linha=linha_por_slug[linha_slug], preco=preco, peso_kg=peso,
                    largura_cm=largura, altura_cm=altura, comprimento_cm=comprimento,
                    estoque=15, ordem=ordem,
                ),
            )
            criados_linha += int(novo)

        # Produtos de exemplo (loja geral)
        criados = 0
        for ordem, dados in enumerate(PRODUTOS):
            dados = dict(dados)
            largura, altura, comprimento = dados.pop("dim")
            slug = dados.pop("slug")
            preco, peso = Decimal(dados.pop("preco")), Decimal(dados.pop("peso"))
            produto, novo = Produto.objects.get_or_create(
                slug=slug,
                defaults=dict(
                    **dados, preco=preco, peso_kg=peso, largura_cm=largura, altura_cm=altura,
                    comprimento_cm=comprimento, estoque=20, ordem=ordem + len(PRODUTOS_POR_LINHA),
                    alergenicos=f"Formulado {dados['selos'].lower()}.",
                ),
            )
            criados += int(novo)
            if not novo and not produto.alergenicos:  # completa produtos criados antes
                produto.alergenicos = f"Formulado {produto.selos.lower()}."
                produto.save(update_fields=["alergenicos"])
        self.stdout.write(self.style.SUCCESS(
            f"{novas} linha(s), {criados_linha} produto(s) de linha e {criados} produto(s) gerais criado(s)."
        ))
