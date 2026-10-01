from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("painel/", admin.site.urls),
    path("", include("loja.urls")),
]
