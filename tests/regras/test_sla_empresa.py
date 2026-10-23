"""Spec 026: prazo (SLA) padrão e por empresa."""

import pytest

from ocorrencias.models import SlaRegra


@pytest.fixture
def so_padrao(db):
    """Só o padrão geral de 72 h (o que a migration 0007 deixa)."""
    SlaRegra.objects.exclude(empresa=None, categoria=None, prioridade=None).delete()
    return SlaRegra.objects.get(empresa=None, categoria=None, prioridade=None)


def test_migration_deixa_o_padrao_geral(db):
    regras = list(SlaRegra.objects.values_list("empresa_id", "categoria", "prioridade", "horas"))
    assert regras == [(None, None, None, 72)]


def test_regra_da_empresa_vence_o_padrao(so_padrao, empresa, abrir):
    SlaRegra.objects.create(empresa=empresa, horas=8)

    assert abrir().sla_horas == 8


def test_outra_empresa_usa_o_padrao(so_padrao, empresa, outra_empresa, abrir, estranho):
    SlaRegra.objects.create(empresa=empresa, horas=8)

    assert abrir(por=estranho).sla_horas == 72


def test_cliente_sem_empresa_usa_o_padrao(so_padrao, empresa, abrir, sem_empresa):
    SlaRegra.objects.create(empresa=empresa, horas=8)

    assert abrir(por=sem_empresa).sla_horas == 72


def test_ordem_de_escolha(so_padrao, empresa):
    """empresa + tipo → empresa → padrão do tipo → padrão geral."""
    SlaRegra.objects.create(categoria="atraso", horas=48)
    assert SlaRegra.horas_para("atraso", "media", empresa.pk) == 48

    SlaRegra.objects.create(empresa=empresa, horas=24)
    assert SlaRegra.horas_para("atraso", "media", empresa.pk) == 24

    SlaRegra.objects.create(empresa=empresa, categoria="atraso", horas=6)
    assert SlaRegra.horas_para("atraso", "media", empresa.pk) == 6

    assert SlaRegra.horas_para("produtos", "media", empresa.pk) == 24
    assert SlaRegra.horas_para("atraso", "media", None) == 48
    assert SlaRegra.horas_para("produtos", "media", None) == 72


def test_sem_nenhuma_regra_fica_sem_prazo(db, abrir):
    SlaRegra.objects.all().delete()
    assert abrir().sla_horas is None


def test_excluir_a_empresa_exclui_as_regras_dela(so_padrao, empresa):
    SlaRegra.objects.create(empresa=empresa, horas=8)

    empresa.delete()

    assert not SlaRegra.objects.exclude(empresa=None).exists()


def test_regra_da_empresa_aparece_com_o_nome(empresa):
    assert str(SlaRegra(empresa=empresa, categoria=None, horas=8)) == "ACME / qualquer / qualquer: 8 h"
