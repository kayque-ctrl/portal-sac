"""Protege: bug 027 (produção fora do ar: 500 FUNCTION_INVOCATION_FAILED na Vercel).

A Vercel roda o app em Python 3.12 (a versão padrão, já que o projeto não
fixa outra), mas a CI e as máquinas usam 3.14. Com `target-version = "py314"`,
o ruff reescreveu `except (A, B):` como `except A, B:` (só existe no 3.14) e
tirou as aspas de uma anotação que aponta para uma classe definida depois
(no 3.12 a anotação é avaliada na hora: NameError). A função quebrava ao
importar e a Vercel devolvia 500 antes de o Django responder.

O teste lê todo o código com a gramática do 3.12. A semântica (como a
anotação) é coberta pela CI, que roda a suíte também em Python 3.12.
"""

import ast
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTAS = ("api", "config", "contas", "ocorrencias", "tests")
ARQUIVOS = sorted(p for pasta in PASTAS for p in (RAIZ / pasta).rglob("*.py")) + [RAIZ / "manage.py"]


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda p: str(p.relative_to(RAIZ)))
def test_codigo_le_com_a_gramatica_do_python_312(arquivo):
    ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo), feature_version=(3, 12))


def test_ruff_mira_a_versao_da_producao():
    """Com alvo acima de 3.12, o ruff volta a usar sintaxe que a Vercel não roda."""
    config = tomllib.loads((RAIZ / "ruff.toml").read_text(encoding="utf-8"))
    assert config["target-version"] == "py312"
