"""Spec 021: responsável, prioridade, arquivamento e lixeira viram eventos no save()."""

from datetime import timedelta

from django.utils import timezone

from ocorrencias import servicos
from ocorrencias.labels import EventoTipo
from ocorrencias.models import EventoOcorrencia, Ocorrencia


def eventos(oc):
    return list(EventoOcorrencia.objects.filter(ocorrencia=oc).values_list("tipo", "de", "para", "autor_id"))


def recarregar(oc):
    return Ocorrencia.objects.get(pk=oc.pk)


def test_abrir_nao_gera_evento(abrir):
    assert eventos(abrir()) == []


def test_salvar_sem_mudanca_nao_gera_evento(abrir, operador):
    oc = recarregar(abrir())
    oc.descricao = "Só o texto mudou."
    oc.save(por=operador)
    assert eventos(oc) == []


def test_definir_trocar_e_remover_responsavel(abrir, operador, admin):
    oc = recarregar(abrir())

    oc.atribuido_a = operador
    oc.save(por=admin)
    oc.atribuido_a = admin
    oc.save(por=admin)
    oc.atribuido_a = None
    oc.save(por=operador)

    assert eventos(oc) == [
        (EventoTipo.RESPONSAVEL, None, operador.nome, admin.pk),
        (EventoTipo.RESPONSAVEL, operador.nome, admin.nome, admin.pk),
        (EventoTipo.RESPONSAVEL, admin.nome, None, operador.pk),
    ]


def test_prioridade(abrir, operador):
    oc = recarregar(abrir())
    oc.prioridade = "alta"
    oc.save(por=operador)
    assert eventos(oc) == [(EventoTipo.PRIORIDADE, "media", "alta", operador.pk)]


def test_arquivar_desarquivar_excluir_e_restaurar(abrir, admin):
    oc = recarregar(abrir())
    for campo, valor in (
        ("arquivada_em", timezone.now()),
        ("arquivada_em", None),
        ("excluida_em", timezone.now()),
        ("excluida_em", None),
    ):
        setattr(oc, campo, valor)
        oc.save(por=admin)

    assert [t for t, *_ in eventos(oc)] == [
        EventoTipo.ARQUIVADA,
        EventoTipo.DESARQUIVADA,
        EventoTipo.EXCLUIDA,
        EventoTipo.RESTAURADA,
    ]


def test_mudancas_seguidas_na_mesma_instancia_comparam_com_o_ultimo_save(abrir, operador):
    oc = abrir()  # instância recém-criada, não lida do banco
    oc.prioridade = "alta"
    oc.save(por=operador)
    oc.prioridade = "alta"
    oc.save(por=operador)
    assert eventos(oc) == [(EventoTipo.PRIORIDADE, "media", "alta", operador.pk)]


def test_instancia_montada_a_mao_nao_gera_evento(abrir, operador):
    oc = recarregar(abrir())
    del oc._originais  # sem os valores do banco, não há com o que comparar
    oc.prioridade = "alta"
    oc.save(por=operador)
    assert eventos(oc) == []


def test_atendimento_pela_operacao_registra_responsavel_e_prioridade(abrir, operador, responder):
    oc = responder(recarregar(abrir()))
    r = servicos.atualizar_ocorrencia(
        operador, oc, {"status": oc.status, "prioridade": "baixa", "atribuido_a": str(operador.pk)}
    )
    assert r.ok
    assert {t for t, *_ in eventos(oc)} == {EventoTipo.RESPONSAVEL, EventoTipo.PRIORIDADE}


def test_arquivamento_automatico_vira_evento_do_sistema(abrir):
    oc = abrir()
    antigo = timezone.now() - timedelta(days=40)
    Ocorrencia.objects.filter(pk=oc.pk).update(status="recusada", atualizado_em=antigo)

    assert servicos.arquivar_concluidas_antigas() == 1
    assert eventos(oc) == [(EventoTipo.ARQUIVADA, None, None, None)]


def test_evento_se_descreve_pelo_tipo(abrir, operador):
    oc = recarregar(abrir())
    oc.prioridade = "alta"
    oc.save(por=operador)
    assert str(EventoOcorrencia.objects.get(ocorrencia=oc)).startswith("Prioridade (")
