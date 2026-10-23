"""Protege: spec 025, ponto 10 (o "x" de remover anexo não fazia nada).

O `lucide.createIcons()` procura `[data-lucide]`, o que inclui os <svg> já
desenhados (eles mantêm o atributo). Chamado pelo MutationObserver a cada
mudança no DOM, ele trocava todos os SVGs, o que disparava o observer de novo:
um laço a cada quadro. O ícone sob o cursor era trocado entre o mousedown e o
mouseup, e o clique nos botões só de ícone (como o "x" do anexo) se perdia.

O comportamento é do navegador; aqui se garante que `desenharIcones` só troca
os <i data-lucide> ainda não desenhados e nunca chama o createIcons global.
"""

import re
from pathlib import Path

APP_JS = (Path(__file__).resolve().parents[2] / "static" / "js" / "app.js").read_text(encoding="utf-8")


def _corpo_desenhar_icones() -> str:
    m = re.search(r"function desenharIcones\(\) \{(.*?)\n\}", APP_JS, re.S)
    assert m, "desenharIcones não encontrada em app.js"
    return m.group(1)


def test_desenhar_icones_so_troca_os_i_novos():
    corpo = _corpo_desenhar_icones()

    assert "createIcons(" not in corpo
    assert 'querySelectorAll("i[data-lucide]")' in corpo
