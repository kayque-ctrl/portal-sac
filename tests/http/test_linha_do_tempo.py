"""Spec 021: a conversa vira linha do tempo nas duas áreas."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from ocorrencias import servicos
from ocorrencias.apresentacao import _texto_evento
from ocorrencias.formato import dia_da_conversa, formatar_hora
from ocorrencias.labels import EventoTipo
from ocorrencias.models import Mensagem, Ocorrencia

from ..builders import foto


def corpo(resposta) -> str:
    return resposta.content.decode()


def pdf(nome="nota.pdf"):
    return SimpleUploadedFile(nome, b"%PDF-1.4\n%fim\n", content_type="application/pdf")


@pytest.fixture
def atendida(ocorrencia, operador):
    """Ocorrência com comentário interno (com foto), troca de prioridade e de responsável."""
    servicos.adicionar_mensagem(operador, ocorrencia, "Pedir foto do lote ao CD.", True, [foto("interna.png")])
    oc = Ocorrencia.objects.get(pk=ocorrencia.pk)
    oc.prioridade = "alta"
    oc.atribuido_a = operador
    oc.save(por=operador)
    return oc


def test_operacao_ve_a_historia_inteira_em_ordem(atendida, operador, entrar):
    html = corpo(entrar(operador).get(f"/operacao/{atendida.pk}"))

    marcos = [
        'data-item="abertura"',
        "Olá, vamos verificar.",
        "Status: Aberta → Em tratativa",
        "Pedir foto do lote ao CD.",
        f"Responsável: {operador.nome}",
        "Prioridade: Média → Alta",
    ]
    posicoes = [html.index(m) for m in marcos]
    assert posicoes == sorted(posicoes)
    assert "Comentário interno · só a operação vê" in html
    assert html.count('data-item="evento-interno"') == 2


def test_operacao_ve_o_nome_de_quem_respondeu(atendida, operador, admin, entrar):
    html = corpo(entrar(admin).get(f"/operacao/{atendida.pk}"))
    assert f"<strong>{operador.nome}</strong>" in html


def test_cliente_ve_abertura_mensagens_e_status(atendida, cliente, entrar):
    html = corpo(entrar(cliente).get(f"/portal/{atendida.pk}"))
    assert 'data-item="abertura"' in html and "Você</strong> abriu a ocorrência" in html
    assert "Olá, vamos verificar." in html
    assert "Status: Aberta → Em tratativa" in html
    assert "<strong>Operação</strong>" in html


def test_abertura_vem_primeiro_e_o_mais_novo_por_ultimo(atendida, cliente, entrar):
    Mensagem.objects.create(ocorrencia=atendida, autor=cliente, conteudo="Mensagem mais nova.")
    html = corpo(entrar(cliente).get(f"/portal/{atendida.pk}"))
    itens = html.index('data-item="abertura"'), html.index("Olá, vamos verificar."), html.index("Mensagem mais nova.")
    assert itens == tuple(sorted(itens))
    assert html.index("Mensagem mais nova.") > html.rindex('data-item="evento"')


def test_separador_de_dia(ocorrencia, cliente, entrar):
    Ocorrencia.objects.filter(pk=ocorrencia.pk).update(criado_em=timezone.now() - timedelta(days=1))
    html = corpo(entrar(cliente).get(f"/portal/{ocorrencia.pk}"))
    assert html.index(">Ontem<") < html.index(">Hoje<")
    assert html.count('data-item="dia"') == 2


def test_foto_vira_miniatura_e_pdf_vira_arquivo(cliente, entrar):
    from ..builders import dados_produtos

    r = servicos.criar_ocorrencia(cliente, dados_produtos("avaria"), [foto("caixa.png"), pdf()])
    html = corpo(entrar(cliente).get(f"/portal/{r.dados['ocorrencia'].pk}"))
    assert 'data-anexo="foto"' in html and 'alt="Foto caixa.png"' in html and 'loading="lazy"' in html
    assert 'data-anexo="arquivo"' in html and "nota.pdf" in html


def test_detalhe_nao_tem_mais_o_quadro_separado_da_abertura(ocorrencia, cliente, operador, entrar):
    # Spec 030: "Linha do tempo" nas duas áreas, como no protótipo.
    for url, user, titulo in (
        (f"/portal/{ocorrencia.pk}", cliente, "Linha do tempo"),
        (f"/operacao/{ocorrencia.pk}", operador, "Linha do tempo"),
    ):
        html = corpo(entrar(user).get(url))
        assert html.count(ocorrencia.descricao or "Camisa") >= 1
        assert html.count('data-item="abertura"') == 1
        assert f">{titulo}</h2>" in html


# ---------------------------------------------------------------- formatação


@pytest.mark.parametrize(("dias", "esperado"), [(0, "Hoje"), (1, "Ontem")])
def test_dia_da_conversa_hoje_e_ontem(dias, esperado):
    assert dia_da_conversa(timezone.now() - timedelta(days=dias)) == esperado


def test_dia_da_conversa_mais_antigo_e_vazio():
    antigo = timezone.now() - timedelta(days=10)
    assert dia_da_conversa(antigo) == timezone.localtime(antigo).strftime("%d/%m/%Y")
    assert dia_da_conversa(None) == "" and formatar_hora(None) == ""


def evento(tipo, de=None, para=None):
    rotulos = dict(EventoTipo.choices)
    return SimpleNamespace(tipo=tipo, de=de, para=para, get_tipo_display=lambda: rotulos[tipo])


@pytest.mark.parametrize(
    ("e", "texto"),
    [
        (evento(EventoTipo.RESPONSAVEL, None, "Otto"), "Responsável: Otto"),
        (evento(EventoTipo.RESPONSAVEL, "Otto", "Alice"), "Responsável: Otto → Alice"),
        (evento(EventoTipo.RESPONSAVEL, "Otto", None), "Removeu o responsável (Otto)"),
        (evento(EventoTipo.RESPONSAVEL, None, None), "Removeu o responsável (usuário removido)"),
        (evento(EventoTipo.PRIORIDADE, "baixa", "alta"), "Prioridade: Baixa → Alta"),
        (evento(EventoTipo.ARQUIVADA), "Arquivada"),
        (evento(EventoTipo.EXCLUIDA), "Enviada para a lixeira"),
        (evento(EventoTipo.RESTAURADA), "Restaurada da lixeira"),
        (evento(EventoTipo.DESARQUIVADA), "Desarquivada"),
    ],
)
def test_texto_de_cada_evento(e, texto):
    assert _texto_evento(e)[1] == texto


def test_evento_do_sistema_aparece_como_sistema(ocorrencia, operador, entrar):
    Ocorrencia.objects.filter(pk=ocorrencia.pk).update(
        status="recusada", atualizado_em=timezone.now() - timedelta(days=40)
    )
    servicos.arquivar_concluidas_antigas()
    html = corpo(entrar(operador).get(f"/operacao/{ocorrencia.pk}"))
    assert ">Sistema</strong> · Arquivada" in html
