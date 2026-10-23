"""Protege: bug 028 (produção fora do ar: "No module named 'django'" na Vercel).

A Vercel instala as dependências do `pyproject.toml` quando ele existe, no
lugar do `requirements.txt`. O commit que adotou o ruff criou um
`pyproject.toml` só com a configuração do ruff (sem dependências): a função
subia sem o Django e quebrava ao importar. A configuração do ruff fica em
`ruff.toml`, e as dependências de produção, só no `requirements.txt`.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def test_sem_pyproject_a_vercel_usa_o_requirements():
    assert not (RAIZ / "pyproject.toml").exists()
    assert not (RAIZ / "Pipfile").exists()


def test_requirements_tem_o_django():
    linhas = (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert any(linha.lower().startswith("django>=") for linha in linhas)


def test_configuracao_do_ruff_fica_no_ruff_toml():
    assert (RAIZ / "ruff.toml").exists()
