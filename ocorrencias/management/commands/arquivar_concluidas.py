"""
Arquiva ocorrências resolvidas/recusadas paradas há mais de N dias
(antes: pg_cron chamando arquivar_concluidas_antigas). Agende no cron/Task
Scheduler, ex.: todo dia às 03:00 → `python manage.py arquivar_concluidas`.
"""

from django.core.management.base import BaseCommand

from ocorrencias.servicos import arquivar_concluidas_antigas


class Command(BaseCommand):
    help = "Arquiva ocorrências resolvidas/recusadas paradas há mais de N dias."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=30)

    def handle(self, *args, dias, **options):
        n = arquivar_concluidas_antigas(dias)
        self.stdout.write(self.style.SUCCESS(f"{n} ocorrência(s) arquivada(s)."))
