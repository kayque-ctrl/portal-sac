"""Construtores de dados de teste: funções puras, sem fixtures nem banco.

Use-os para montar o *input* de um serviço ou de um POST. Objetos que precisam
do banco (usuários, ocorrências) vêm das fixtures de `conftest.py`.
"""

import json

from django.core.files.uploadedfile import SimpleUploadedFile

SENHA = "senha-forte-1"

# Menor PNG válido (1x1): passa na checagem de magic bytes de uploads.py.
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def foto(nome: str = "foto.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, PNG_1X1, content_type="image/png")


def dados_produtos(categoria: str = "falta", **extra) -> dict:
    """Formulário de abertura do tipo "produtos" com um item."""
    itens = [{"categoria": categoria, "codigo": "001", "descricao": "Camisa", "quantidade": 2}]
    return {
        "tipo": "produtos",
        "referencia_tipo": "nf",
        "referencia": "12345",
        "descricao": "",
        "itens_json": json.dumps(itens),
        **extra,
    }


def dados_atraso(**extra) -> dict:
    """Formulário de abertura do tipo "atraso" (referência 987)."""
    return {
        "tipo": "atraso",
        "referencia_tipo": "pedido",
        "referencia": "987",
        "descricao": "A entrega atrasou três dias.",
        **extra,
    }


def dados_reclamacao(**extra) -> dict:
    return {"tipo": "reclamacao_sugestao", "descricao": "Atendimento demorado demais.", **extra}
