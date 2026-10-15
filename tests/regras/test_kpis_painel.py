"""Painel do cliente com banco (spec 011): escopo por empresa e cálculos."""

from datetime import timedelta

import pytest
from django.utils import timezone

from ocorrencias import kpis, servicos
from ocorrencias.models import HistoricoStatus, Ocorrencia

from ..builders import dados_produtos


@pytest.fixture
def resolver(operador):
    """Leva a ocorrência a 'resolvida' e ajusta quando foi aberta e quando foi resolvida."""

    def _resolver(oc, aberta_ha_horas, resolvida_ha_horas):
        agora = timezone.now()
        oc.status = "resolvida"
        oc.save(por=operador)
        Ocorrencia.objects.filter(pk=oc.pk).update(criado_em=agora - timedelta(hours=aberta_ha_horas))
        HistoricoStatus.objects.filter(ocorrencia=oc, para_status="resolvida").update(
            criado_em=agora - timedelta(hours=resolvida_ha_horas)
        )
        oc.refresh_from_db()
        return oc

    return _resolver


def vencer(oc):
    Ocorrencia.objects.filter(pk=oc.pk).update(sla_prazo=timezone.now() - timedelta(hours=1))


def test_colegas_da_mesma_empresa_veem_os_mesmos_numeros(abrir, cliente, colega):
    abrir(por=cliente)
    abrir(por=colega)

    do_cliente, do_colega = kpis.calcular_kpis(cliente, 30), kpis.calcular_kpis(colega, 30)

    assert do_cliente["em_aberto"] == do_colega["em_aberto"] == 2
    assert do_cliente["novas_no_periodo"] == do_colega["novas_no_periodo"] == 2


def test_outra_empresa_nunca_entra_na_conta(abrir, cliente, estranho):
    abrir(por=cliente)
    abrir(por=estranho)

    assert kpis.calcular_kpis(cliente, 30)["em_aberto"] == 1
    assert kpis.calcular_kpis(estranho, 30)["em_aberto"] == 1


def test_usuario_sem_empresa_conta_so_as_proprias(abrir, cliente, sem_empresa):
    abrir(por=cliente)
    abrir(por=sem_empresa)
    assert kpis.calcular_kpis(sem_empresa, 30)["em_aberto"] == 1


def test_aguardando_aprovacao_separa_as_minhas_das_da_empresa(abrir, resolver, cliente, colega):
    resolver(abrir(por=cliente), 5, 1)
    resolver(abrir(por=colega), 5, 1)

    k = kpis.calcular_kpis(cliente, 30)

    assert k["aguardando_aprovacao"] == 2
    assert k["aguardando_aprovacao_minhas"] == 1
    assert kpis.calcular_kpis(colega, 30)["aguardando_aprovacao_minhas"] == 1


def test_ocorrencia_na_lixeira_nao_conta(abrir, cliente):
    oc = abrir()
    oc.excluida_em = timezone.now()
    oc.save()
    assert kpis.calcular_kpis(cliente, 30)["em_aberto"] == 0


def test_sla_vencido_so_conta_as_ativas(abrir, resolver, cliente):
    ativa, aguardando = abrir(), abrir()
    resolver(aguardando, 5, 1)
    vencer(ativa)
    vencer(aguardando)

    assert kpis.calcular_kpis(cliente, 30)["com_sla_vencido"] == 1


def test_tempo_medio_de_resolucao_e_comparacao_com_periodo_anterior(abrir, resolver, cliente):
    resolver(abrir(), aberta_ha_horas=20, resolvida_ha_horas=10)  # 10 h depois de aberta
    resolver(abrir(), aberta_ha_horas=40, resolvida_ha_horas=10)  # 30 h
    # Resolvida no período anterior (entre 30 e 60 dias atrás): 100 h para resolver.
    resolver(abrir(), aberta_ha_horas=24 * 40 + 100, resolvida_ha_horas=24 * 40)

    k = kpis.calcular_kpis(cliente, 30)

    assert k["resolvidas_no_periodo"] == 2
    assert k["tempo_medio_horas"] == pytest.approx(20.0, abs=0.1)
    assert k["tempo_medio_horas_anterior"] == pytest.approx(100.0, abs=0.1)


def test_sla_cumprido_das_encerradas_no_periodo(abrir, responder, operador, cliente):
    no_prazo, estourada = abrir(), abrir()
    responder(no_prazo)
    no_prazo.status = "resolvida"
    no_prazo.save(por=operador)
    assert servicos.aprovar_resolucao(cliente, no_prazo)
    vencer(estourada)
    estourada.refresh_from_db()
    estourada.status = "recusada"
    estourada.motivo_recusa = "Fora do prazo"
    estourada.save(por=operador)

    k = kpis.calcular_kpis(cliente, 30)

    assert (k["sla_encerradas"], k["sla_cumpridas"]) == (2, 1)


def test_motivos_contam_ocorrencias_e_itens(cliente):
    servicos.criar_ocorrencia(cliente, dados_produtos("falta"), [])
    servicos.criar_ocorrencia(cliente, dados_produtos("falta"), [])
    sobra = dados_produtos("sobra")
    servicos.criar_ocorrencia(cliente, sobra, [])

    por_categoria = {m["categoria"]: m for m in kpis.calcular_kpis(cliente, 30)["motivos"]}

    assert por_categoria["falta"] == {"categoria": "falta", "ocorrencias": 2, "itens": 4}
    assert por_categoria["sobra"]["ocorrencias"] == 1


def test_atencao_poe_sla_vencido_primeiro_e_identifica_o_autor(abrir, cliente, colega):
    antiga = abrir(por=cliente)
    vencida = abrir(por=colega)
    Ocorrencia.objects.filter(pk=antiga.pk).update(criado_em=timezone.now() - timedelta(days=5))
    vencer(vencida)

    atencao = kpis.calcular_kpis(cliente, 30)["atencao"]

    assert [a["id"] for a in atencao] == [vencida.pk, antiga.pk]
    assert (atencao[0]["autor_nome"], atencao[0]["eh_minha"]) == ("Bruno Colega", False)
    assert (atencao[1]["autor_nome"], atencao[1]["eh_minha"]) == ("Ana Cliente", True)


def test_atencao_mostra_no_maximo_cinco(abrir, cliente):
    for _ in range(7):
        abrir()
    assert len(kpis.calcular_kpis(cliente, 30)["atencao"]) == 5


def test_serie_semanal_tem_entre_4_e_12_semanas(abrir, cliente):
    abrir()
    assert len(kpis.calcular_kpis(cliente, 7)["semanas"]) == 4
    assert len(kpis.calcular_kpis(cliente, 90)["semanas"]) == 12
    ultima = kpis.calcular_kpis(cliente, 30)["semanas"][-1]
    assert ultima["total"] == 1


@pytest.mark.parametrize(("pedido", "esperado"), [(0, 30), (-5, 1), (1000, 365)])
def test_periodo_e_limitado(cliente, pedido, esperado):
    assert kpis.calcular_kpis(cliente, pedido)["periodo_dias"] == esperado
