# MASE NUTRITION — site institucional + loja (Django)

Implementa o briefing do site: home institucional, Clinical Care (linhas), CDMO (formulário de qualificação),
Ingredients, Allergen Free, área de profissionais de saúde (acesso controlado), Mase Science, Onde comprar,
contato com encaminhamento de leads, e loja com Pix, cupom do prescritor e Programa Mase Contínua.

## Rodar (Windows)

```
venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations loja
python manage.py migrate
python manage.py seed_produtos
python manage.py runserver
```
Primeira vez: `python manage.py createsuperuser` (usuário do painel). Site: http://127.0.0.1:8000 · Painel: /painel/

## Onde editar cada coisa (painel /painel/)

| Quero mexer em | Onde |
|---|---|
| Produtos, preço, estoque, seções da página do produto, kits | Produtos |
| Linhas (Neurocare, Immunocare...) e status "em desenvolvimento/lançada" | Linhas |
| Aprovar profissional (conferir CRM/CRN no site do conselho) | Profissionais de saúde > ação "Aprovar" |
| Desconto do paciente e comissão de cada profissional | Profissionais de saúde (comissão começa em 0) |
| Materiais técnicos exclusivos (PDF, links de webinar) | Materiais |
| Pontos de venda (Onde encontrar) | Pontos de venda |
| Artigos do Mase Science | Artigos |
| Leads (CDMO, ingredientes, distribuidor...), status do funil, exportar CSV | Leads |
| Quem recebe cada tipo de contato (nome + e-mail) | Rotas de contato |
| Pedidos, comissões, assinaturas | Pedidos / Comissões / Assinaturas Mase Contínua |

## Imagens
Coloque as fotos em `static/img/` (nomes em `static/img/LEIA-ME.txt`). Sem foto, o site mostra um fundo em degradê azul.

## Regras configuráveis (.env)
- `PRESCRITOR_OBRIGATORIO=False` (padrão): compra livre. `True` exige o cupom do profissional de saúde (briefing).
- `LOGIN_OBRIGATORIO=False` (padrão): site público, como a Vitafor. `True` exige login para ver qualquer página.
- `CONTINUA_BENEFICIO_PERCENTUAL=5`: benefício do Mase Contínua (valor de exemplo).
- `EMAIL_COMERCIAL` e `EMAIL_HOST...`: avisos de novos leads/cadastros. Sem isso, os e-mails aparecem no terminal.
- `SOCIAL_*`: links das redes (aparecem só as preenchidas).

## Mase Contínua (renovações)
`python manage.py gerar_assinaturas` cria o pedido (com Pix) das entregas que vencem e avisa o cliente por e-mail.
Em produção, agende para rodar 1x por dia. O Pix não é cobrança automática: o cliente paga cada renovação.

## Pix (Mercado Pago)
Ver `MP_ACCESS_TOKEN` no `.env.example`. Sem token e com `DEBUG=True`, o Pix é simulado.

## Contas de clientes (JSON)
As contas ficam em `data/contas.json` (senha só como hash). Faça backup desse arquivo junto com o `db.sqlite3`.
`python manage.py migrar_contas_para_json` copia para o JSON as contas criadas antes desta versão.
O administrador do painel (`/painel/`) continua no banco.

## Frete
- O frete é calculado pelo **CEP** na tela de finalizar compra (o servidor recalcula ao fechar o pedido).
- Padrão: tabela **Frete por estado** em `/painel/` (valores de exemplo, ajuste os seus). `FRETE_GRATIS_ACIMA` no `.env` ativa frete grátis.
- Opcional: cotação real das transportadoras pelo Melhor Envio. Preencha `CEP_ORIGEM` e `MELHOR_ENVIO_TOKEN` no `.env`
  (peso e medidas dos produtos vêm do cadastro). Se a cotação falhar, o sistema usa a tabela por estado.

## Publicar na Vercel
1. Suba o projeto para o GitHub (com a pasta `loja/migrations/` incluída; `.env`, `venv`, `db.sqlite3` e `data/` ficam de fora pelo `.gitignore`).
2. Na Vercel: **Add New > Project**, importe o repositório (ela detecta o Django pelo `manage.py`).
3. **Storage / Marketplace**: conecte um Postgres (Neon ou Supabase). A Vercel cria `DATABASE_URL` sozinha.
4. **Settings > Environment Variables**: `SECRET_KEY` (obrigatória), `MP_ACCESS_TOKEN`, `WHATSAPP_NUMBER`, `EMAIL_COMERCIAL`, `EMAIL_HOST...`,
   `CEP_ORIGEM`, etc. (as mesmas do `.env.example`). Faça isso **antes** do primeiro deploy.
5. Deploy. Depois crie as tabelas no banco de produção: coloque o `DATABASE_URL` no seu `.env` local e rode
   `python manage.py migrate`, `seed_produtos` e `createsuperuser` (depois remova o `DATABASE_URL` do `.env`).
6. Mercado Pago: cadastre `https://SEU-DOMINIO/webhooks/mercadopago/` em Suas integrações > Webhooks.

Na Vercel o disco não é permanente: as contas ficam no banco (não no JSON), e anexos de "Materiais" não persistem
(use o campo *link* nos materiais). O `gerar_assinaturas` precisa de um agendador (Vercel Cron).

### Sem GitHub (Vercel CLI)
Instale o Node.js (nodejs.org), depois: `npm install -g vercel`, `vercel login`, `vercel link` (cria o projeto),
configure Postgres e variáveis no painel da Vercel e rode `vercel --prod`. A cada atualização, rode `vercel --prod` de novo.
O arquivo `.vercelignore` impede o envio de `venv`, `.env` e `db.sqlite3`.

## Pagamento com cartão (crédito e débito)
O formulário de cartão fica **embutido na tela do pedido** (número, validade, CVV, parcelas) — o cliente não sai
do site. O número do cartão e o CVV vão direto do navegador para o Mercado Pago (campos seguros/iframe do
`MercadoPago.js`); seu servidor só recebe um token, nunca os dados do cartão.

1. Em mercadopago.com.br > o seu negócio > credenciais, pegue o **Access Token** e a **Public Key** (comece
   pelos de teste, que começam com `TEST-`).
2. Coloque os dois no `.env`: `MP_ACCESS_TOKEN` e `MP_PUBLIC_KEY`.
3. Sem as duas chaves preenchidas, a tela do pedido mostra o botão **"Simular pagamento aprovado"**, como no Pix.
4. Com as chaves de teste, use os [cartões de teste do Mercado Pago](https://www.mercadopago.com.br/developers/pt/docs/checkout-api/additional-content/your-integrations/test/cards)
   para simular aprovação, recusa, etc.

Depois de mexer nisso, rode `python manage.py makemigrations loja` e `migrate` — o pedido passou a guardar
parcelas, bandeira e os 4 últimos dígitos do cartão.
