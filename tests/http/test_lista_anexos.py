"""Spec 017: lista de anexos que acumula, permite remover e aceita PDF.

O comportamento no navegador (acumular, remover, comprimir) é do componente
Alpine `listaAnexos`; aqui se garante que os formulários o usam corretamente e
que o servidor aceita o que a lista envia (vários arquivos, PDF).
"""

import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from ocorrencias import servicos
from ocorrencias.models import Ocorrencia

from ..builders import dados_atraso, dados_produtos, foto

APP_JS = (Path(__file__).resolve().parents[2] / "static" / "js" / "app.js").read_text(encoding="utf-8")


def pdf(nome="nota.pdf", tamanho=1024 * 1024):
    return SimpleUploadedFile(nome, b"%PDF-1.4" + b"0" * (tamanho - 8), content_type="application/pdf")


class Inputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag == "input" and dict(attrs).get("type") == "file":
            self.inputs.append(dict(attrs))


def inputs_de_arquivo(html):
    p = Inputs()
    p.feed(html)
    return p.inputs


@pytest.fixture
def paginas(ocorrencia, cliente, operador, entrar):
    return {
        "abertura": entrar(cliente).get("/portal/nova").content.decode(),
        "conversa do cliente": entrar(cliente).get(f"/portal/{ocorrencia.pk}").content.decode(),
        "conversa da operação": entrar(operador).get(f"/operacao/{ocorrencia.pk}").content.decode(),
    }


@pytest.mark.parametrize("pagina", ["abertura", "conversa do cliente", "conversa da operação"])
def test_formularios_usam_a_lista_de_anexos(paginas, pagina):
    html = paginas[pagina]
    arquivos = [i for i in inputs_de_arquivo(html) if "importar" not in (i.get("x-ref") or "")]

    enviados = [i for i in arquivos if i.get("name") == "anexos"]
    seletores = [i for i in arquivos if i.get("x-ref") == "escolher"]

    assert "data-lista-anexos" in html
    assert len(enviados) == 1 and len(seletores) == 1
    # O seletor fica fora do formulário: escolher de novo nunca apaga a lista enviada.
    assert seletores[0].get("form") == "sem-form" and "name" not in seletores[0]
    assert ".pdf" in seletores[0]["accept"]


def test_componente_acumula_remove_e_comprime():
    for trecho in (
        'Alpine.data("listaAnexos"',
        "this.arquivos.push(",
        "remover(i) {",
        "this.arquivos.splice(i, 1);",
        "escolhidos.map(comprimirImagem)",
        "new DataTransfer()",
        "o mesmo arquivo duas vezes",
        "Remova algum para adicionar outro.",
        "o limite por envio é",
    ):
        assert trecho in APP_JS, trecho


def test_seletor_de_arquivo_antigo_foi_removido():
    assert "data-comprimir" not in APP_JS
    assert "limparArquivos" not in APP_JS


# ---------------------------------------------------------------- servidor


def test_abertura_aceita_varios_arquivos_e_pdf(cliente, entrar):
    r = entrar(cliente).post("/portal/nova", {**dados_atraso(), "anexos": [pdf(), foto(), pdf("planilha.pdf", 2048)]})

    assert r.status_code == 302
    nomes = sorted(Ocorrencia.objects.get().anexos.values_list("nome_arquivo", flat=True))
    assert nomes == ["foto.png", "nota.pdf", "planilha.pdf"]


def test_conversa_aceita_pdf(ocorrencia, cliente, entrar):
    entrar(cliente).post(f"/portal/{ocorrencia.pk}/mensagem", {"conteudo": "segue a nota", "anexos": [pdf()]})
    assert ocorrencia.anexos.filter(nome_arquivo="nota.pdf", tipo_mime="application/pdf").exists()


def test_pdf_sozinho_em_avaria_explica_que_falta_a_foto(cliente):
    itens = json.dumps([{"categoria": "avaria", "codigo": "1", "descricao": "X", "quantidade": 1}])
    r = servicos.criar_ocorrencia(cliente, dados_produtos(itens_json=itens), [pdf()])

    assert r.erro.startswith("Anexe pelo menos uma foto")
    assert "PDF e planilha podem ir junto, mas não substituem a foto." in r.erro


def test_pdf_junto_com_foto_em_avaria_e_aceito(cliente):
    r = servicos.criar_ocorrencia(cliente, dados_produtos("avaria"), [foto(), pdf()])
    assert r.ok, r.erro
    assert r.dados["ocorrencia"].anexos.count() == 2


def test_pdf_acima_do_limite_explica_tamanho_e_limite(settings, ocorrencia, cliente):
    settings.UPLOAD_MAX_TOTAL_BYTES = 4 * 1024 * 1024
    r = servicos.adicionar_mensagem(cliente, ocorrencia, "segue", False, [pdf(tamanho=5 * 1024 * 1024)])
    assert r.erro == "Os anexos somam 5,0 MB; o limite por envio é 4,0 MB. Envie em mais de uma mensagem."
