from .models import Produto

SESSION_KEY = "carrinho"
CUPOM_KEY = "cupom"


class Carrinho:
    """Carrinho guardado na sessão: {slug: quantidade}. Preços sempre vêm do banco."""

    def __init__(self, request):
        self.session = request.session
        bruto = self.session.get(SESSION_KEY, {})
        self.dados = bruto if isinstance(bruto, dict) else {}

    def _salvar(self):
        self.session[SESSION_KEY] = self.dados
        self.session.modified = True

    @property
    def total_itens(self):
        return sum(int(q) for q in self.dados.values())

    def quantidade_de(self, slug):
        return int(self.dados.get(slug, 0))

    def definir(self, slug, quantidade):
        if quantidade <= 0:
            self.dados.pop(slug, None)
        else:
            self.dados[slug] = int(quantidade)
        self._salvar()

    def remover(self, slug):
        self.definir(slug, 0)

    def limpar(self):
        self.dados = {}
        self._salvar()
        self.remover_cupom()

    # ---- cupom aplicado ----
    @property
    def cupom_codigo(self):
        return self.session.get(CUPOM_KEY, "")

    def definir_cupom(self, codigo):
        self.session[CUPOM_KEY] = codigo
        self.session.modified = True

    def remover_cupom(self):
        self.session.pop(CUPOM_KEY, None)
        self.session.modified = True

    def itens(self):
        produtos = {p.slug: p for p in Produto.objects.filter(slug__in=list(self.dados), ativo=True)}
        resultado = []
        for slug, qtd in self.dados.items():
            p = produtos.get(slug)
            if not p:
                continue
            qtd = int(qtd)
            resultado.append(
                {
                    "produto": p,
                    "quantidade": qtd,
                    "subtotal": p.preco * qtd,
                    "indisponivel": qtd > p.estoque,
                }
            )
        return resultado
