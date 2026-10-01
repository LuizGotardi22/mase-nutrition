from django.urls import path

from . import views, views_conta, views_site

urlpatterns = [
    # institucional
    path("", views_site.home, name="index"),
    path("quem-somos/", views_site.quem_somos, name="quem_somos"),
    path("allergen-free/", views_site.allergen_free, name="allergen_free"),
    path("clinical-care/", views_site.clinical_care, name="clinical_care"),
    path("clinical-care/<slug:slug>/", views_site.linha, name="linha"),
    path("cdmo/", views_site.cdmo, name="cdmo"),
    path("cdmo/desenvolver-minha-marca/", views_site.cdmo_proposta, name="cdmo_proposta"),
    path("onde-encontrar/", views_site.onde_encontrar, name="onde_encontrar"),
    path("science/", views_site.science, name="science"),
    path("science/<slug:slug>/", views_site.science_artigo, name="science_artigo"),
    path("contato/", views_site.contato, name="contato"),
    path("mase-continua/", views_site.mase_continua, name="mase_continua"),
    # profissionais de saúde
    path("profissionais/", views_site.profissionais, name="profissionais"),
    path("profissionais/area/", views_site.profissionais_area, name="profissionais_area"),
    path("profissionais/material/<int:pk>/", views_site.material_abrir, name="material_abrir"),
    path("profissionais/cadastro/", views_conta.parceiro_cadastro, name="parceiro_cadastro"),
    path("profissionais/painel/", views_conta.parceiro_painel, name="parceiro_painel"),
    path("profissionais/cupons/novo/", views_conta.parceiro_cupom_criar, name="parceiro_cupom_criar"),
    path("profissionais/cupons/<int:pk>/alternar/", views_conta.parceiro_cupom_alternar, name="parceiro_cupom_alternar"),
    # conta
    path("entrar/", views_conta.entrada, name="entrada"),
    path("criar-conta/", views_conta.criar_conta, name="criar_conta"),
    path("sair/", views_conta.sair, name="sair"),
    path("conta/", views_conta.minha_conta, name="minha_conta"),
    path("conta/assinaturas/<int:pk>/<str:acao>/", views_conta.assinatura_acao, name="assinatura_acao"),
    # loja
    path("loja/", views.loja, name="loja"),
    path("produto/<slug:slug>/", views.produto, name="produto"),
    path("carrinho/", views.carrinho, name="carrinho"),
    path("carrinho/adicionar/<slug:slug>/", views.carrinho_adicionar, name="carrinho_adicionar"),
    path("carrinho/atualizar/<slug:slug>/", views.carrinho_atualizar, name="carrinho_atualizar"),
    path("carrinho/remover/<slug:slug>/", views.carrinho_remover, name="carrinho_remover"),
    path("carrinho/cupom/", views.cupom_aplicar, name="cupom_aplicar"),
    path("carrinho/cupom/remover/", views.cupom_remover, name="cupom_remover"),
    path("checkout/", views.checkout, name="checkout"),
    path("frete/", views.frete_calcular, name="frete_calcular"),
    path("pedido/<uuid:codigo>/", views.pedido, name="pedido"),
    path("pedido/<uuid:codigo>/status/", views.pedido_status, name="pedido_status"),
    path("pedido/<uuid:codigo>/novo-pix/", views.pedido_novo_pix, name="pedido_novo_pix"),
    path("pedido/<uuid:codigo>/pagar-cartao/", views.cartao_pagar, name="cartao_pagar"),
    path("pedido/<uuid:codigo>/simular/", views.pedido_simular_pagamento, name="pedido_simular"),
    path("webhooks/mercadopago/", views.webhook_mercadopago, name="webhook_mp"),
]
