"""Spec 023: portal do cliente (cabeçalho, início, lista) e mesa da operação (3 colunas)."""

from types import SimpleNamespace

import pytest
from django.utils import timezone

from ocorrencias import servicos
from ocorrencias.models import Ocorrencia
from ocorrencias.templatetags.ocorrencias_tags import prazo, situacao, sla_info

from ..builders import foto


def corpo(resposta) -> str:
    return resposta.content.decode()


def pdf(nome="nota.pdf"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(nome, b"%PDF-1.4\n%fim\n", content_type="application/pdf")


# ---------------------------------------------------------------- casca


def test_cliente_navega_pelo_cabecalho_e_nao_tem_menu_lateral(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/"))
    assert 'class="cab"' in html and 'class="lado"' not in html
    for href, rotulo in (
        ("/portal/", "Início"),
        ("/portal/ocorrencias", "Minhas ocorrências"),
        ("/portal/dashboard", "Painel"),
    ):
        assert f'href="{href}"' in html and rotulo in html


def test_operacao_tem_menu_lateral_sem_filas(operador, entrar):
    html = corpo(entrar(operador).get("/operacao/"))
    assert 'class="lado"' in html
    # Os filtros prontos da spec 025 ficam na página da fila, nunca no menu lateral.
    menu = html[html.index('class="lado"') : html.index("</aside>")]
    assert "Sem responsável</a>" not in menu and "data-atalho" not in html


def test_lista_do_cliente_marca_o_item_do_menu(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/ocorrencias"))
    assert 'href="/portal/ocorrencias" aria-current="page"' in html


def test_abrir_ocorrencia_nao_marca_item_do_menu(cliente, entrar):
    assert entrar(cliente).get("/portal/nova").context["menu_atual"] is None


# ---------------------------------------------------------------- abertura numa página só


def test_formulario_tem_os_blocos_e_o_botao_enviar(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/nova?tipo=produtos"))
    for trecho in (
        "Referência (Nota Fiscal, Pedido ou Picking)",
        "Quais produtos tiveram problema?",
        "Fotos e documentos",
        "Conte o que aconteceu",
        "Enviar ocorrência",
    ):
        assert trecho in html
    assert "Continuar" not in html  # spec 025: as etapas avançam sozinhas, sem botão de passo


def test_formulario_oferece_tirar_foto_pela_camera(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/nova"))
    assert 'capture="environment"' in html and 'accept="image/*"' in html


# ---------------------------------------------------------------- linha do tempo: documentos como eventos


def test_cada_documento_vira_um_evento_com_o_cartao_do_arquivo(ocorrencia, cliente, entrar):
    servicos.adicionar_mensagem(
        cliente, ocorrencia, "Segue a foto do lote.", False, [foto("lote.png"), pdf("NF-1.pdf")]
    )
    html = corpo(entrar(cliente).get(f"/portal/{ocorrencia.pk}"))
    assert html.count('data-item="documento"') >= 3  # resp.png da operação + lote.png + NF-1.pdf
    assert "adicionou o documento <strong>lote.png</strong>" in html
    assert "adicionou o documento <strong>NF-1.pdf</strong>" in html
    assert html.index("Segue a foto do lote.") < html.index("lote.png</strong>")


def test_mensagem_so_com_anexo_nao_gera_balao_vazio(ocorrencia, cliente, entrar):
    servicos.adicionar_mensagem(cliente, ocorrencia, "", False, [foto("so-foto.png")])
    html = corpo(entrar(cliente).get(f"/portal/{ocorrencia.pk}"))
    assert '<div class="bal"></div>' not in html
    assert "so-foto.png</strong>" in html


def test_documento_de_comentario_interno_nao_chega_ao_cliente(ocorrencia, operador, cliente, entrar):
    servicos.adicionar_mensagem(operador, ocorrencia, "conferir", True, [foto("interno.png")])
    assert "interno.png" not in corpo(entrar(cliente).get(f"/portal/{ocorrencia.pk}"))
    html = corpo(entrar(operador).get(f"/operacao/{ocorrencia.pk}"))
    assert "interno.png</strong>" in html and "só operação" in html


# ---------------------------------------------------------------- mesa: outras da empresa


def test_atendimento_mostra_outras_ocorrencias_da_empresa(ocorrencia, abrir, colega, estranho, operador, entrar):
    da_colega, de_fora = abrir(por=colega), abrir(por=estranho)
    r = entrar(operador).get(f"/operacao/{ocorrencia.pk}")
    outras = [o.pk for o in r.context["outras_da_empresa"]]
    assert da_colega.pk in outras and de_fora.pk not in outras and ocorrencia.pk not in outras
    assert "data-outras-da-empresa" in corpo(r)


def test_cliente_sem_empresa_mostra_as_outras_dele(abrir, sem_empresa, operador, entrar):
    primeira, segunda = abrir(por=sem_empresa), abrir(por=sem_empresa)
    outras = entrar(operador).get(f"/operacao/{primeira.pk}").context["outras_da_empresa"]
    assert [o.pk for o in outras] == [segunda.pk]


def test_lixeira_nao_entra_nas_outras_da_empresa(ocorrencia, abrir, colega, operador, entrar):
    apagada = abrir(por=colega)
    Ocorrencia.objects.filter(pk=apagada.pk).update(excluida_em=timezone.now())
    outras = entrar(operador).get(f"/operacao/{ocorrencia.pk}").context["outras_da_empresa"]
    assert apagada.pk not in [o.pk for o in outras]


# ---------------------------------------------------------------- tags de apresentação


def test_situacao_com_rotulo_proprio_e_so_o_ponto():
    assert ">Aberta</span>" in situacao("aberta")
    assert ">Aguarda você</span>" in situacao("resolvida", "Aguarda você")
    so_ponto = situacao("concluida", "")
    assert 'title="Resolvida"' in so_ponto and '<span class="sr">Resolvida</span>' in so_ponto


def oc_sla(**campos):
    base = {"status": "em_analise", "sla_horas": 10, "sla_prazo": None, "sla_restante_ms": None, "sla_cumprido": None}
    return SimpleNamespace(**{**base, **campos})


@pytest.mark.parametrize(
    ("campos", "trecho"),
    [
        ({"sla_horas": None}, "sem prazo"),
        ({"status": "concluida", "sla_cumprido": None}, "—"),
        ({"sla_prazo": timezone.now() - timezone.timedelta(hours=2)}, "var(--perigo)"),
        ({"sla_prazo": timezone.now() + timezone.timedelta(hours=8)}, "Vence em 8 h"),
    ],
)
def test_prazo_em_texto(campos, trecho):
    assert trecho in prazo(oc_sla(**campos))


def test_sla_info_calcula_quanto_do_prazo_ja_foi_usado():
    info = sla_info(oc_sla(sla_prazo=timezone.now() + timezone.timedelta(hours=2, minutes=30)))
    assert info["pct"] == 75 and not info["vencido"]
    assert sla_info(oc_sla(sla_horas=None))["pct"] is None
    assert sla_info(oc_sla(sla_prazo=timezone.now() - timezone.timedelta(hours=1)))["vencido"]
