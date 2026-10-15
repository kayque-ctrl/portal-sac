from django.contrib import admin
from django.urls import include, path

from ocorrencias.urls import operacao_urls, portal_urls, publico_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("contas.urls")),
    path("", include((publico_urls, "publico"))),
    path("portal/", include(portal_urls)),
    path("operacao/", include(operacao_urls)),
]
