"""Arquivamento e lixeira (servicos.purgar, arquivar_concluidas_antigas)."""

from datetime import timedelta

from django.utils import timezone

from ocorrencias import servicos
from ocorrencias.models import Ocorrencia


def test_purgar_so_apaga_o_que_esta_na_lixeira(abrir):
    na_lixeira, ativa = abrir(), abrir()
    na_lixeira.excluida_em = timezone.now()
    na_lixeira.save()

    apagadas = servicos.purgar([na_lixeira.pk, ativa.pk])

    assert apagadas == 1
    assert not Ocorrencia.objects.filter(pk=na_lixeira.pk).exists()
    assert Ocorrencia.objects.filter(pk=ativa.pk).exists()


def test_auto_arquivamento_so_pega_encerradas_antigas(abrir, operador):
    antiga, recente, aberta = abrir(), abrir(), abrir()
    for oc in (antiga, recente):
        oc.status = "recusada"
        oc.save(por=operador)
    Ocorrencia.objects.filter(pk=antiga.pk).update(atualizado_em=timezone.now() - timedelta(days=40))

    arquivadas = servicos.arquivar_concluidas_antigas(30)

    assert arquivadas == 1
    antiga.refresh_from_db(), recente.refresh_from_db(), aberta.refresh_from_db()
    assert antiga.arquivada_em is not None
    assert recente.arquivada_em is None
    assert aberta.arquivada_em is None
