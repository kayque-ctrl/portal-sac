"""Spec 020: atalhos da fila, atividade do usuário, marcar todas e abas do atendimento."""

from datetime import timedelta

import pytest
from django.utils import timezone

from contas.models import Usuario
from ocorrencias.models import Notificacao, Ocorrencia


def corpo(resposta) -> str:
    return resposta.content.decode()


# ---------------------------------------------------------------- atalhos da fila


@pytest.fixture
def fila(abrir, operador, admin):
    """Três ativas: uma do operador, uma do admin e uma sem responsável e vencida."""
    minha, do_admin, solta = abrir(), abrir(), abrir()
    Ocorrencia.objects.filter(pk=minha.pk).update(atribuido_a=operador)
    Ocorrencia.objects.filter(pk=do_admin.pk).update(atribuido_a=admin)
    Ocorrencia.objects.filter(pk=solta.pk).update(sla_horas=4, sla_prazo=timezone.now() - timedelta(hours=1))
    return minha, do_admin, solta


@pytest.mark.parametrize(
    ("valor", "esperadas"),
    [("eu", [0]), ("ninguem", [2])],
)
def test_filtro_de_responsavel_comigo_e_sem_responsavel(fila, operador, entrar, valor, esperadas):
    """Spec 023: no lugar dos atalhos, o filtro de responsável (comigo / sem responsável)."""
    html = corpo(entrar(operador).get(f"/operacao/?responsavel={valor}"))
    for i, oc in enumerate(fila):
        assert (oc.protocolo in html) == (i in esperadas)


def test_topo_avisa_quantas_ativas_estao_com_prazo_vencido(fila, operador, entrar):
    assert "1 com prazo vencido" in corpo(entrar(operador).get("/operacao/"))


def test_filtros_mudados_mantem_a_aba_de_situacao(operador, entrar):
    html = corpo(entrar(operador).get("/operacao/?situacao=concluidas"))
    assert '<input type="hidden" name="situacao" value="concluidas">' in html


# ---------------------------------------------------------------- filtros por pessoa


def test_fila_filtra_por_cliente_e_mostra_o_nome(abrir, cliente, estranho, operador, entrar):
    da_ana, da_carla = abrir(), abrir(por=estranho)
    html = corpo(entrar(operador).get(f"/operacao/?cliente={cliente.pk}"))
    assert da_ana.protocolo in html and da_carla.protocolo not in html
    assert "Aberta por:" in html and cliente.nome in html


def test_fila_filtra_por_um_responsavel_e_deixa_ele_escolhido(fila, operador, entrar):
    minha, do_admin, _ = fila
    html = corpo(entrar(operador).get(f"/operacao/?responsavel={operador.pk}"))
    assert minha.protocolo in html and do_admin.protocolo not in html
    assert f'<option value="{operador.pk}" selected>{operador.nome}</option>' in html


def test_filtro_por_pessoa_inexistente_nao_quebra(operador, entrar):
    r = entrar(operador).get("/operacao/?cliente=00000000-0000-0000-0000-000000000000")
    assert r.status_code == 200
    assert "usuário removido" in corpo(r)


def test_abas_de_situacao_mantem_o_filtro_por_pessoa(cliente, operador, entrar):
    html = corpo(entrar(operador).get(f"/operacao/?cliente={cliente.pk}"))
    assert f"cliente={cliente.pk}&amp;situacao=concluidas" in html


# ---------------------------------------------------------------- atividade do usuário


def test_atividade_do_cliente(abrir, cliente, operador, entrar):
    abrir()
    encerrada = abrir()
    Ocorrencia.objects.filter(pk=encerrada.pk).update(status="concluida")

    html = corpo(entrar(operador).get(f"/operacao/usuarios/{cliente.pk}"))

    assert 'data-atividade="total">2<' in html
    assert 'data-atividade="andamento">1<' in html
    assert f"/operacao/?cliente={cliente.pk}" in html


def test_atividade_do_operador_conta_o_que_esta_com_ele(fila, operador, admin, entrar):
    html = corpo(entrar(admin).get(f"/operacao/usuarios/{operador.pk}"))
    assert 'data-atividade="andamento">1<' in html
    assert 'data-atividade="total"' not in html
    assert f"/operacao/?responsavel={operador.pk}" in html


def test_ultimo_acesso_e_convite_pendente(cliente, operador, admin, entrar):
    agora = timezone.now()
    Usuario.objects.filter(pk=operador.pk).update(last_login=agora - timedelta(minutes=5), ativado_em=agora)
    http = entrar(admin)

    html_cliente = corpo(http.get(f"/operacao/usuarios/{cliente.pk}"))
    html_operador = corpo(http.get(f"/operacao/usuarios/{operador.pk}"))

    assert "Nunca entrou" in html_cliente and "Convite pendente" in html_cliente
    assert "Nunca entrou" not in html_operador and "Convite pendente" not in html_operador


# ---------------------------------------------------------------- marcar todas como lidas


def test_marcar_todas_marca_so_as_do_proprio_usuario(cliente, colega, entrar):
    # Mais do que as 6 que o sino mostra: as de fora da lista também contam.
    minhas = [Notificacao.objects.create(destinatario=cliente, mensagem=str(i)) for i in range(8)]
    do_colega = Notificacao.objects.create(destinatario=colega, mensagem="c")

    resposta = entrar(cliente).post("/notificacoes/marcar-todas")

    assert resposta.json() == {"ok": True, "naoLidas": 0}
    assert not Notificacao.objects.filter(pk__in=[n.pk for n in minhas], lida=False).exists()
    do_colega.refresh_from_db()
    assert not do_colega.lida


def test_marcar_todas_exige_login_e_post(client, cliente):
    assert client.post("/notificacoes/marcar-todas").status_code == 302
    client.force_login(cliente)
    assert client.get("/notificacoes/marcar-todas").status_code == 405


def test_sino_tem_o_botao_marcar_todas(cliente, entrar):
    assert "data-marcar-todas" in corpo(entrar(cliente).get("/portal/"))


# ---------------------------------------------------------------- atendimento no celular


def test_atendimento_tem_as_abas_e_os_paineis(ocorrencia, operador, entrar):
    # Desde a spec 021 a abertura é o 1º item da linha do tempo: sem aba "Detalhes".
    html = corpo(entrar(operador).get(f"/operacao/{ocorrencia.pk}"))
    for chave, rotulo in (("conversa", "Linha do tempo"), ("atender", "Atender")):
        assert f'id="aba-{chave}"' in html and f">{rotulo}</button>" in html
        assert f'id="painel-{chave}" role="tabpanel"' in html
    assert 'id="aba-detalhes"' not in html
