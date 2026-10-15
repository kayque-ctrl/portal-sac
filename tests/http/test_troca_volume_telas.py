"""Spec 004 nas telas: formulário, erro devolvido e exibição do sinal."""

import json

from ocorrencias.models import Ocorrencia

from ..builders import dados_produtos, foto


def corpo(resposta) -> str:
    return resposta.content.decode()


def troca(sinal):
    return [{"categoria": "troca_volume", "codigo": "", "descricao": "", "quantidade": 2, "sinal_volume": sinal}]


def test_formulario_oferece_falta_e_sobra(cliente, entrar):
    r = entrar(cliente).get("/portal/nova")

    config = r.context["config"]
    assert config["comSinalVolume"] == ["troca_volume"]
    assert [s["valor"] for s in config["sinaisVolume"]] == ["falta", "sobra"]
    assert "O volume está faltando ou sobrando?" in corpo(r)


def test_abrir_troca_de_volume_pelo_formulario(cliente, entrar):
    dados = {**dados_produtos(itens_json=json.dumps(troca("sobra"))), "anexos": [foto()]}

    r = entrar(cliente).post("/portal/nova", dados)

    assert r.status_code == 302
    assert Ocorrencia.objects.get().itens.get().sinal_volume == "sobra"


def test_troca_sem_sinal_volta_ao_formulario_com_o_erro_e_os_itens(cliente, entrar):
    dados = {**dados_produtos(itens_json=json.dumps(troca(None))), "anexos": [foto()]}

    r = entrar(cliente).post("/portal/nova", dados)

    assert "Na troca de volume, informe se o volume está faltando ou sobrando." in corpo(r)
    assert r.context["inicial"]["itens"] == troca(None)
    assert not Ocorrencia.objects.exists()


def test_detalhe_mostra_rotulo_e_sinal_negativo_da_falta(cliente, operador, entrar):
    entrar(cliente).post("/portal/nova", {**dados_produtos(itens_json=json.dumps(troca("falta"))), "anexos": [foto()]})
    oc = Ocorrencia.objects.get()

    for usuario, url in ((cliente, f"/portal/{oc.pk}"), (operador, f"/operacao/{oc.pk}")):
        html = corpo(entrar(usuario).get(url))
        assert "Troca de volume (falta)" in html
        assert "-2</span>" in html


def test_detalhe_mostra_sinal_positivo_da_sobra(cliente, entrar):
    http = entrar(cliente)
    http.post("/portal/nova", {**dados_produtos(itens_json=json.dumps(troca("sobra"))), "anexos": [foto()]})

    html = corpo(http.get(f"/portal/{Ocorrencia.objects.get().pk}"))

    assert "Troca de volume (sobra)" in html
    assert "+2</span>" in html


def test_importacao_de_planilha_com_troca_de_volume(cliente, entrar):
    from django.core.files.uploadedfile import SimpleUploadedFile

    csv = "codigo;nome;categoria;quantidade;sinal\n;;Troca de volume;1;Falta\n"
    arquivo = SimpleUploadedFile("p.csv", csv.encode(), content_type="text/csv")

    r = entrar(cliente).post("/portal/nova/importar", {"file": arquivo}).json()

    assert r["itens"][0]["sinal_volume"] == "falta"
