from django.apps import AppConfig


class OcorrenciasConfig(AppConfig):
    name = "ocorrencias"

    def ready(self):
        from . import checks  # noqa: F401  (registra os system checks)
