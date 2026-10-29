
from django.urls import path

from . import views_site

urlpatterns = [
    # Institucional
    path("", views_site.home, name="index"),
    path("quem-somos/", views_site.quem_somos, name="quem_somos"),
    path("allergen-free/", views_site.allergen_free, name="allergen_free"),
    path("clinical-care/", views_site.clinical_care, name="clinical_care"),
    path("clinical-care/<slug:slug>/", views_site.linha, name="linha"),
    path("cdmo/", views_site.cdmo, name="cdmo"),
    path(
        "cdmo/desenvolver-minha-marca/",
        views_site.cdmo_proposta,
        name="cdmo_proposta",
    ),
    path("onde-encontrar/", views_site.onde_encontrar, name="onde_encontrar"),
    path("science/", views_site.science, name="science"),
    path("science/<slug:slug>/", views_site.science_artigo, name="science_artigo"),
    path("contato/", views_site.contato, name="contato"),

    # Profissionais de saúde — área informativa
    path("profissionais/", views_site.profissionais, name="profissionais"),
]
