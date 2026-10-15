"""Spec 006: cor de fonte por categoria (Avaria, Pré-vencido, Vencido)."""

import re

import pytest

from ocorrencias import labels
from ocorrencias.templatetags import ocorrencias_tags as tags

# Tons do Tailwind usados no texto (hex de referência da paleta). Se ITEM_TEXTO
# passar a usar outro tom, acrescente-o aqui: o teste de contraste exige.
TONS = {
    "amber-700": "#b45309",
    "orange-700": "#c2410c",
    "rose-700": "#be123c",
    "zinc-800": "#27272a",
    "amber-400": "#fbbf24",
    "orange-400": "#fb923c",
    "rose-400": "#fb7185",
    "zinc-200": "#e4e4e7",
}
FUNDO_CLARO = "#ffffff"  # cartões no tema claro
FUNDO_ESCURO = "#18181b"  # zinc-900, cartões no tema escuro
WCAG_AA = 4.5


def _luminancia(hex_cor: str) -> float:
    canais = [int(hex_cor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(a: str, b: str) -> float:
    claro, escuro = sorted([_luminancia(a), _luminancia(b)], reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def _tons(classes: str) -> tuple[str, str]:
    """('amber-700', 'amber-400') a partir de 'text-amber-700 dark:text-amber-400'."""
    claro = re.search(r"(?<!:)text-([a-z]+-\d+)", classes).group(1)
    escuro = re.search(r"dark:text-([a-z]+-\d+)", classes).group(1)
    return claro, escuro


def test_so_as_tres_categorias_do_card_tem_cor_propria():
    assert set(labels.ITEM_TEXTO) == {"avaria", "pre_vencido", "vencido"}


def test_cores_sao_distintas_entre_si():
    assert len({_tons(c) for c in labels.ITEM_TEXTO.values()}) == 3


def test_cor_segue_o_tom_da_etiqueta():
    """Consistência visual: a fonte usa a mesma família de cor do badge."""
    for categoria, classes in labels.ITEM_TEXTO.items():
        familia = _tons(classes)[0].split("-")[0]
        assert f"bg-{familia}-" in labels.ITEM_BADGE[categoria]


@pytest.mark.parametrize("classes", [*labels.ITEM_TEXTO.values(), labels.ITEM_TEXTO_PADRAO])
def test_contraste_wcag_aa_nos_dois_temas(classes):
    claro, escuro = _tons(classes)
    assert contraste(TONS[claro], FUNDO_CLARO) >= WCAG_AA, claro
    assert contraste(TONS[escuro], FUNDO_ESCURO) >= WCAG_AA, escuro


@pytest.mark.parametrize("categoria", ["avaria", "pre_vencido", "vencido"])
def test_tag_item_texto_nas_categorias_com_cor(categoria):
    assert tags.item_texto(categoria) == labels.ITEM_TEXTO[categoria]


@pytest.mark.parametrize("categoria", ["falta", "sobra", "troca_volume", None, "xyz"])
def test_demais_categorias_seguem_o_texto_padrao(categoria):
    assert tags.item_texto(categoria) == labels.ITEM_TEXTO_PADRAO
