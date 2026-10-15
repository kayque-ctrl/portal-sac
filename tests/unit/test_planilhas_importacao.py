"""Importação de produtos (planilhas.importar_produtos): CSV e XLSX, sem banco."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from ocorrencias import planilhas


def csv_file(texto, nome="p.csv", codificacao="utf-8"):
    return SimpleUploadedFile(nome, texto.encode(codificacao), content_type="text/csv")


def xlsx_file(linhas, nome="p.xlsx"):
    wb = Workbook()
    for linha in linhas:
        wb.active.append(linha)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(nome, buf.getvalue())


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Avaria", "avaria"),
        ("  FALTA ", "falta"),
        ("Sobra", "sobra"),
        ("Troca de volume", "troca_volume"),
        ("Pré-vencido", "pre_vencido"),
        ("pre vencido", "pre_vencido"),
        ("Vencido", "vencido"),
        ("Outra coisa", None),
        ("", None),
    ],
)
def test_normalizar_categoria(texto, esperado):
    assert planilhas.normalizar_categoria(texto) == esperado


def test_csv_com_ponto_e_virgula():
    r = planilhas.importar_produtos(csv_file("codigo;nome;categoria;quantidade\n001;Camisa;Avaria;2\n"))
    assert r["itens"] == [{"categoria": "avaria", "codigo": "001", "descricao": "Camisa", "quantidade": 2, "sinal_volume": None}]
    assert (r["total"], r["ignoradas"]) == (1, 0)


def test_csv_com_virgula_e_cabecalhos_alternativos():
    r = planilhas.importar_produtos(csv_file("SKU,Descrição,Tipo,Qtd\nA1,Caneca,Vencido,5\n"))
    assert r["itens"][0]["categoria"] == "vencido"


def test_csv_em_latin1():
    r = planilhas.importar_produtos(csv_file("código;nome;categoria;quantidade\n1;Pão;Falta;1\n", codificacao="latin-1"))
    assert r["itens"][0]["descricao"] == "Pão"


def test_linhas_invalidas_sao_contadas_como_ignoradas():
    r = planilhas.importar_produtos(
        csv_file("codigo;nome;categoria;quantidade\n;sem codigo;Falta;1\n2;sem categoria;Xyz;1\n3;qtd zero;Falta;0\n4;ok;Falta;1\n")
    )
    assert (r["total"], r["ignoradas"]) == (1, 3)


def test_xlsx_converte_inteiros_lidos_como_float():
    r = planilhas.importar_produtos(xlsx_file([["codigo", "nome", "categoria", "quantidade"], [10.0, "Camisa", "Sobra", 3.0]]))
    assert r["itens"] == [{"categoria": "sobra", "codigo": "10", "descricao": "Camisa", "quantidade": 3, "sinal_volume": None}]


def test_arquivo_vazio():
    assert planilhas.importar_produtos(None)["erro"] == "Arquivo inválido."
    assert planilhas.importar_produtos(csv_file(""))["erro"] == "Arquivo inválido."


def test_csv_so_com_linhas_em_branco():
    r = planilhas.importar_produtos(csv_file("\n   \n\n"))
    assert r["erro"] == "Planilha vazia ou sem linhas de produto."


def test_so_cabecalho():
    r = planilhas.importar_produtos(csv_file("codigo;nome;categoria;quantidade\n"))
    assert r["erro"] == "Planilha vazia ou sem linhas de produto."


def test_colunas_obrigatorias():
    r = planilhas.importar_produtos(csv_file("codigo;nome\n1;x\n"))
    assert r["erro"] == "Colunas esperadas: código, nome, categoria, quantidade."


def test_arquivo_ilegivel():
    r = planilhas.importar_produtos(SimpleUploadedFile("p.xlsx", b"nao e xlsx"))
    assert r["erro"] == "Não foi possível ler o arquivo. Use o modelo (.xlsx ou .csv)."


def test_limite_de_linhas_nao_trunca_em_silencio():
    linhas = "\n".join(f"{i};P{i};Falta;1" for i in range(planilhas.MAX_LINHAS + 1))
    r = planilhas.importar_produtos(csv_file("codigo;nome;categoria;quantidade\n" + linhas))
    assert f"mais de {planilhas.MAX_LINHAS} produtos" in r["erro"]
    assert r["itens"] == []


# ---------------------------------------------------------------- troca de volume (spec 004)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("Falta", "falta"), ("faltando", "falta"), ("-", "falta"), ("Sobra", "sobra"), ("+", "sobra"), ("", None), ("x", None)],
)
def test_normalizar_sinal(texto, esperado):
    assert planilhas.normalizar_sinal(texto) == esperado


def test_troca_de_volume_com_coluna_sinal_dispensa_codigo_e_descricao():
    r = planilhas.importar_produtos(csv_file("codigo;nome;categoria;quantidade;sinal\n;;Troca de volume;;Sobra\n"))
    assert r["itens"] == [
        {"categoria": "troca_volume", "codigo": "", "descricao": "Troca de volume", "quantidade": 1, "sinal_volume": "sobra"}
    ]


def test_troca_de_volume_com_sinal_no_texto_da_categoria():
    r = planilhas.importar_produtos(csv_file("codigo;nome;categoria;quantidade\n7;Volume 2;Troca de volume - falta;2\n"))
    assert r["itens"][0]["sinal_volume"] == "falta"


def test_troca_de_volume_sem_sinal_e_ignorada():
    r = planilhas.importar_produtos(csv_file("codigo;nome;categoria;quantidade;sinal\n7;V;Troca de volume;1;\n8;Ok;Falta;1;\n"))
    assert (r["total"], r["ignoradas"]) == (1, 1)


def test_sinal_e_ignorado_nas_outras_categorias():
    r = planilhas.importar_produtos(csv_file("codigo;nome;categoria;quantidade;sinal\n8;Ok;Avaria;1;Sobra\n"))
    assert r["itens"][0]["sinal_volume"] is None
