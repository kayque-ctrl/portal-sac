"""Regras de SLA padrão por prioridade (o admin ajusta depois em /operacao/sla)."""

from django.db import migrations

PADRAO = [("alta", 24), ("media", 72), ("baixa", 120)]


def criar(apps, schema_editor):
    SlaRegra = apps.get_model("ocorrencias", "SlaRegra")
    for prioridade, horas in PADRAO:
        SlaRegra.objects.get_or_create(categoria=None, prioridade=prioridade, defaults={"horas": horas})


def remover(apps, schema_editor):
    SlaRegra = apps.get_model("ocorrencias", "SlaRegra")
    for prioridade, horas in PADRAO:
        SlaRegra.objects.filter(categoria=None, prioridade=prioridade, horas=horas).delete()


class Migration(migrations.Migration):
    dependencies = [("ocorrencias", "0001_initial")]

    operations = [migrations.RunPython(criar, remover)]
