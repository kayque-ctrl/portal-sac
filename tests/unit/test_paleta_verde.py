"""Spec 031: paleta com verde como cor principal (opção A, verde floresta + grafite)."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CSS = (RAIZ / "static" / "css" / "sac.css").read_text(encoding="utf-8")


def token(bloco: str, nome: str) -> str:
    inicio = CSS.index(bloco + " {")
    corpo = CSS[inicio : CSS.index("\n}", inicio)]
    return re.search(rf"\n  --{nome}: ([^;]+);", corpo).group(1)


def contraste(a: str, b: str) -> float:
    def lum(h: str) -> float:
        c = [int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    claro, escuro = sorted([lum(a), lum(b)], reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def test_cor_de_acao_e_o_verde_floresta():
    assert token(":root", "preto") == "#1f7a4d"
    assert token(".dark", "preto") == "#3fae74"
    assert token(":root", "lado") == "#1b2320"  # menu grafite


def test_botao_verde_tem_contraste_de_leitura_nos_dois_temas():
    assert contraste(token(":root", "preto"), token(":root", "preto-txt")) >= 4.5
    assert contraste(token(".dark", "preto"), token(".dark", "preto-txt")) >= 4.5
    assert contraste(token(":root", "lado-selo"), "#ffffff") >= 4.5  # selo e "Abrir" no menu


def test_resolvida_e_grafite_para_nao_parecer_botao():
    assert token(":root", "s-resolvida") == "#4b5563"
    assert token(".dark", "s-resolvida") == "#9aa3ad"
    assert token(":root", "s-resolvida") != token(":root", "preto")


def test_sem_o_azul_antigo():
    for cor in ("#2b5797", "#234a82", "#6e9be0", "#1f2a3c", "#c8cfdb"):
        assert cor not in CSS


def test_email_usa_o_verde_da_marca():
    emails = (RAIZ / "ocorrencias" / "emails.py").read_text(encoding="utf-8")
    assert "background:#1f7a4d;color:#fff;" in emails
