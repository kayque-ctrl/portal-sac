"""Spec 025: telas no estilo GLPI e os pontos do cliente que aparecem na tela."""

from datetime import timedelta

import pytest
from django.utils import timezone

from ocorrencias.models import Ocorrencia, SlaRegra


def corpo(resposta) -> str:
    return resposta.content.decode()


# ---------------------------------------------------------------- abertura (pontos 1 a 9)


@pytest.fixture
def formulario(cliente, entrar):
    return corpo(entrar(cliente).get("/portal/nova"))


def test_passo_um_pede_para_selecionar_uma_opcao(formulario):
    assert "Selecione uma opção abaixo" in formulario
    assert "O que aconteceu?" not in formulario


def test_etapas_aparecem_no_topo(formulario):
    assert 'class="etapas"' in formulario
    for etapa in ("Assunto", "Detalhes", "Enviar"):
        assert f'<span class="txt">{etapa}</span>' in formulario


def test_escolher_a_referencia_leva_ao_campo_estreito(formulario):
    assert 'class="in in-ref mono"' in formulario
    assert 'x-init="$el.focus()"' in formulario


def test_resumo_fica_atras_de_um_botao(formulario):
    assert "Confira antes de enviar" not in formulario
    assert "Ver resumo antes de enviar" in formulario
    assert 'id="resumo-envio" x-show="verResumo"' in formulario


def test_sem_importar_planilha(formulario):
    assert "Importar planilha" not in formulario
    assert "Baixar modelo" not in formulario
    assert "importar" not in formulario.lower().split("data-anexos-limite")[1].split("</form>")[0]


def test_categoria_virou_motivo(formulario):
    assert '<label for="categoria-produto">Motivo' in formulario
    assert "Selecione o motivo" in formulario
    assert "Selecione a categoria" not in formulario


def test_codigo_descricao_e_quantidade_na_mesma_linha_embaixo_do_motivo(formulario):
    motivo = formulario.index('id="categoria-produto"')
    linha = formulario.index('class="linha-produto"')
    assert motivo < linha
    trecho = formulario[linha : formulario.index('</div>\n            <p x-show="dispensaDadosProduto"', linha)]
    assert trecho.index("codigo-produto") < trecho.index("descricao-produto") < trecho.index("quantidade-produto")


def test_comentario_em_produtos_fica_atras_de_um_botao(formulario):
    assert "Adicionar comentário" in formulario
    assert '<template x-if="categoriaComProduto && !comentarioAberto">' in formulario


# ---------------------------------------------------------------- prioridade (ponto 12)


def test_atendimento_sem_prioridade(ocorrencia, operador, entrar):
    html = corpo(entrar(operador).get(f"/operacao/{ocorrencia.pk}"))
    assert 'name="prioridade"' not in html
    assert ">Prioridade<" not in html


def test_fila_sem_coluna_de_prioridade(ocorrencia, operador, entrar):
    assert ">Prioridade</th>" not in corpo(entrar(operador).get("/operacao/"))


def test_sla_sem_campo_de_prioridade(admin, entrar):
    html = corpo(entrar(admin).get("/operacao/sla"))
    assert 'name="prioridade"' not in html


def test_sla_mostra_regra_antiga_por_prioridade(admin, entrar):
    # A migration 0007 (spec 026) já converte as regras padrão; uma regra por
    # prioridade só existe se alguém criar pelo admin do Django.
    SlaRegra.objects.create(categoria=None, prioridade="alta", horas=4)

    html = corpo(entrar(admin).get("/operacao/sla"))

    assert "Prioridade (antiga)" in html
    assert 'só valem para "Média"' in html


def test_sla_sem_regra_antiga_nao_mostra_a_coluna(admin, entrar):
    SlaRegra.objects.all().delete()
    SlaRegra.objects.create(categoria="atraso", prioridade=None, horas=24)
    assert "Prioridade (antiga)" not in corpo(entrar(admin).get("/operacao/sla"))


# ---------------------------------------------------------------- fila da operação


def test_fila_tem_contadores_e_filtros_prontos(abrir, operador, entrar):
    abrir(), abrir()

    r = entrar(operador).get("/operacao/")

    contadores = {c["chave"]: c["n"] for c in r.context["contadores"]}
    assert contadores == {"aberta": 2, "em_analise": 0, "resolvida": 0, "vencido": 0}
    assert [p[0] for p in r.context["prontos"]] == ["Comigo", "Sem responsável", "Prazo vencido", "Todas ativas"]
    assert 'href="?responsavel=eu"' in corpo(r)


def test_filtro_prazo_vencido(abrir, operador, entrar):
    vencida, em_dia = abrir(), abrir()
    Ocorrencia.objects.filter(pk=vencida.pk).update(sla_prazo=timezone.now() - timedelta(hours=1))
    Ocorrencia.objects.filter(pk=em_dia.pk).update(sla_prazo=timezone.now() + timedelta(hours=5))

    html = corpo(entrar(operador).get("/operacao/?prazo=vencido"))

    assert vencida.protocolo in html and em_dia.protocolo not in html


@pytest.mark.parametrize("valor", ["lixo", "", "VENCIDO"])
def test_filtro_de_prazo_malformado_e_ignorado(abrir, operador, entrar, valor):
    oc = abrir()

    r = entrar(operador).get(f"/operacao/?prazo={valor}")

    assert r.status_code == 200
    assert r.context["prazo"] == ""
    assert oc.protocolo in corpo(r)


def test_contador_de_aprovacao_leva_para_encerradas(operador, entrar):
    r = entrar(operador).get("/operacao/")
    aprovacao = next(c for c in r.context["contadores"] if c["chave"] == "resolvida")
    assert aprovacao["url"] == "?situacao=concluidas&status=resolvida"


# ---------------------------------------------------------------- início e lista do cliente


def test_inicio_tem_busca_e_contadores(abrir, cliente, entrar):
    abrir()

    html = corpo(entrar(cliente).get("/portal/"))

    # Spec 030: a busca saiu da faixa escura e foi para a barra do topo (no celular, na página).
    assert 'class="heroi"' not in html
    assert html.count('action="/portal/ocorrencias"') == 2
    assert 'href="/portal/ocorrencias?status=aberta"' in html
    assert 'href="/portal/ocorrencias?filtro=aprovar"' in html


def test_inicio_sem_ocorrencias_nao_mostra_contadores(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/"))
    assert "data-contadores" not in html
    assert html.count('action="/portal/ocorrencias"') == 1  # só a busca do topo


def test_lista_comeca_com_o_filtro_do_contador(cliente, entrar):
    r = entrar(cliente).get("/portal/ocorrencias?status=em_analise&q=NF 123")
    assert r.context["inicial"] == {"status": "em_analise", "q": "NF 123"}


@pytest.mark.parametrize("status", ["lixo", "", "<script>"])
def test_lista_ignora_status_malformado(cliente, entrar, status):
    r = entrar(cliente).get(f"/portal/ocorrencias?status={status}")
    assert r.status_code == 200
    assert r.context["inicial"]["status"] == "todas"


def test_busca_longa_e_cortada(cliente, entrar):
    r = entrar(cliente).get("/portal/ocorrencias?q=" + "x" * 300)
    assert len(r.context["inicial"]["q"]) == 80


# ---------------------------------------------------------------- visual


def test_operacao_tem_menu_lateral_e_fonte_ibm_plex(operador, entrar):
    # Spec 030: a fonte passou a ser IBM Plex Sans / Mono.
    html = corpo(entrar(operador).get("/operacao/"))
    assert "family=IBM+Plex+Sans" in html
    assert 'class="lado"' in html
