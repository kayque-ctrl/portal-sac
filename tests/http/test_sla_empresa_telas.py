"""Spec 026: telas do prazo (SLA) padrão e por empresa."""

import pytest

from ocorrencias.models import SlaRegra


def corpo(resposta) -> str:
    return resposta.content.decode()


def test_cadastra_regra_da_empresa(admin, empresa, entrar):
    r = entrar(admin).post("/operacao/sla", {"empresa": str(empresa.pk), "categoria": "", "horas": "8"})

    assert r.url == f"/operacao/sla?empresa={empresa.pk}"
    assert SlaRegra.objects.get(empresa=empresa).horas == 8


def test_salvar_de_novo_atualiza(admin, empresa, entrar):
    http = entrar(admin)
    http.post("/operacao/sla", {"empresa": str(empresa.pk), "categoria": "atraso", "horas": "8"})
    http.post("/operacao/sla", {"empresa": str(empresa.pk), "categoria": "atraso", "horas": "6"})

    assert list(SlaRegra.objects.filter(empresa=empresa).values_list("horas", flat=True)) == [6]


def test_padrao_continua_sem_empresa(admin, entrar):
    entrar(admin).post("/operacao/sla", {"empresa": "", "categoria": "", "horas": "48"})

    assert SlaRegra.objects.get(empresa=None, categoria=None, prioridade=None).horas == 48


@pytest.mark.parametrize("valor", ["lixo", "00000000-0000-0000-0000-000000000000"])
def test_empresa_invalida_e_recusada_sem_virar_padrao(admin, entrar, valor):
    antes = list(SlaRegra.objects.values_list("pk", "horas"))

    r = entrar(admin).post("/operacao/sla", {"empresa": valor, "categoria": "", "horas": "1"})

    assert r.status_code == 200
    assert "Escolha uma empresa válida." in corpo(r)
    assert list(SlaRegra.objects.values_list("pk", "horas")) == antes


def test_tela_agrupa_padrao_e_empresas(admin, empresa, entrar):
    SlaRegra.objects.create(empresa=empresa, horas=8)

    html = corpo(entrar(admin).get("/operacao/sla"))

    assert html.index('data-grupo-sla="padrao"') < html.index(f'data-grupo-sla="{empresa.pk}"')
    assert "Padrão (todas as empresas)" in html


def test_link_da_empresa_deixa_ela_marcada(admin, empresa, entrar):
    html = corpo(entrar(admin).get(f"/operacao/sla?empresa={empresa.pk}"))
    assert f'<option value="{empresa.pk}" selected>' in html


@pytest.mark.parametrize("valor", ["lixo", "", "00000000-0000-0000-0000-000000000000"])
def test_empresa_malformada_na_url_e_ignorada(admin, entrar, valor):
    r = entrar(admin).get(f"/operacao/sla?empresa={valor}")
    assert r.status_code == 200
    assert r.context["empresa_marcada"] is None


def test_operador_nao_cria_regra(operador, empresa, entrar):
    entrar(operador).post("/operacao/sla", {"empresa": str(empresa.pk), "horas": "1"})
    assert not SlaRegra.objects.filter(empresa=empresa).exists()


def test_empresa_mostra_o_prazo_que_vale(admin, operador, empresa, entrar):
    SlaRegra.objects.create(empresa=empresa, categoria="atraso", horas=6)

    html_admin = corpo(entrar(admin).get(f"/operacao/empresas/{empresa.pk}"))
    html_op = corpo(entrar(operador).get(f"/operacao/empresas/{empresa.pk}"))

    prazo = html_admin[html_admin.index("data-prazo-empresa") :]
    assert "6 h</strong>" in prazo and "desta empresa" in prazo
    assert "72 h</strong>" in prazo and "padrão" in prazo
    assert "Configurar prazo desta empresa" in html_admin
    assert "Configurar prazo desta empresa" not in html_op
