"""Comandos de manutenção (manage.py)."""

from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.utils import timezone

from contas.models import Usuario
from ocorrencias import servicos
from ocorrencias.models import Ocorrencia


def test_arquivar_concluidas_informa_quantas_arquivou(abrir, operador):
    oc = abrir()
    oc.status = "recusada"
    oc.save(por=operador)
    Ocorrencia.objects.filter(pk=oc.pk).update(atualizado_em=timezone.now() - timedelta(days=45))
    saida = StringIO()

    call_command("arquivar_concluidas", "--dias", "30", stdout=saida)

    assert "1 ocorrência(s) arquivada(s)." in saida.getvalue()
    oc.refresh_from_db()
    assert oc.arquivada_em is not None


def test_arquivar_concluidas_sem_nada_a_arquivar(db):
    saida = StringIO()
    call_command("arquivar_concluidas", stdout=saida)
    assert "0 ocorrência(s) arquivada(s)." in saida.getvalue()


def test_popular_demo_cria_ambiente_navegavel_e_e_idempotente(db):
    call_command("popular_demo", stdout=StringIO())
    usuarios, ocorrencias = Usuario.objects.count(), Ocorrencia.objects.count()

    call_command("popular_demo", stdout=StringIO())

    assert usuarios >= 5 and ocorrencias >= 2
    assert Usuario.objects.count() == usuarios
    assert Ocorrencia.objects.count() == ocorrencias
    assert Usuario.objects.get(email="admin@demo.local").eh_admin


def test_purgar_continua_mesmo_se_o_arquivo_nao_puder_ser_removido(ocorrencia):
    ocorrencia.excluida_em = timezone.now()
    ocorrencia.save()

    with mock.patch("django.db.models.fields.files.FieldFile.delete", side_effect=OSError("em uso")):
        apagadas = servicos.purgar([ocorrencia.pk])

    assert apagadas == 1
    assert not Ocorrencia.objects.filter(pk=ocorrencia.pk).exists()
