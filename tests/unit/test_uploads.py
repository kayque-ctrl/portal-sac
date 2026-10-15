"""Regras de upload (uploads.py): tipo, tamanho e conteúdo."""

from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from ocorrencias import uploads

from ..builders import PNG_1X1

ASSINATURAS = {
    "jpeg": b"\xff\xd8\xff\xe0" + b"0" * 8,
    "png": PNG_1X1,
    "gif": b"GIF89a" + b"0" * 6,
    "bmp": b"BM" + b"0" * 10,
    "webp": b"RIFF\x00\x00\x00\x00WEBP",
}


def arquivo(nome="a.png", conteudo=PNG_1X1, tipo="image/png"):
    return SimpleUploadedFile(nome, conteudo, content_type=tipo)


@pytest.mark.parametrize("formato", list(ASSINATURAS))
def test_assinatura_de_imagem_valida(formato):
    assert uploads.conteudo_imagem_confere(arquivo(conteudo=ASSINATURAS[formato]))


def test_imagem_falsa_nao_confere():
    assert not uploads.conteudo_imagem_confere(arquivo(conteudo=b"isto nao e imagem"))


def test_nao_imagem_nao_e_checada():
    assert uploads.conteudo_imagem_confere(arquivo("a.pdf", b"qualquer", "application/pdf"))


def test_arquivo_ilegivel_nao_bloqueia():
    quebrado = mock.Mock(content_type="image/png")
    quebrado.tell.side_effect = OSError
    assert uploads.conteudo_imagem_confere(quebrado)


@pytest.mark.parametrize(
    ("nome", "mime", "esperado"),
    [
        ("a.png", "image/png", True),
        ("dados.csv", "application/octet-stream", True),  # MIME inconsistente, extensão ok
        ("planilha.XLSX", "", True),
        ("virus.exe", "application/x-msdownload", False),
        ("semextensao", "", False),
    ],
)
def test_anexo_permitido(nome, mime, esperado):
    assert uploads.anexo_permitido(nome, mime) is esperado


def test_limite_de_quantidade():
    erro = uploads.validar_arquivos([arquivo()] * (uploads.MAX_ANEXOS + 1))
    assert erro == f"Envie no máximo {uploads.MAX_ANEXOS} anexos."


def test_limite_de_tamanho():
    grande = arquivo()
    grande.size = uploads.MAX_TAMANHO_BYTES + 1
    assert uploads.validar_arquivos([grande]) == '"a.png" excede o limite de 10 MB.'


def test_formato_nao_permitido():
    erro = uploads.validar_arquivos([arquivo("virus.exe", b"MZ", "application/x-msdownload")])
    assert erro == '"virus.exe" tem um formato não permitido.'


def test_arquivos_validos_passam():
    assert uploads.validar_arquivos([arquivo(), arquivo("b.pdf", b"%PDF", "application/pdf")]) is None


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Relatório final (1).PDF", "Relat_rio_final__1_.pdf"),
        ("sem_ext", "sem_ext"),
        (".env", "_env"),
        ("###", "___"),
    ],
)
def test_sanitizar_nome(nome, esperado):
    assert uploads.sanitizar_nome(nome) == esperado


@pytest.mark.parametrize("nome", ["../../etc/passwd", r"..\..\windows\system32", "a/b/../c.png"])
def test_sanitizar_nome_nunca_deixa_sair_da_pasta(nome):
    seguro = uploads.sanitizar_nome(nome)
    assert "/" not in seguro
    assert "\\" not in seguro
    assert ".." not in seguro
