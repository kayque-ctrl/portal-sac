"""Spec 016 nas telas: opção Picking no formulário e exibição no detalhe."""

from ocorrencias.models import Ocorrencia

from ..builders import dados_atraso


def test_formulario_oferece_nota_pedido_e_picking(cliente, entrar):
    r = entrar(cliente).get("/portal/nova")

    assert r.context["referencias"] == [("nf", "Nota Fiscal"), ("pedido", "Pedido"), ("picking", "Picking")]
    assert r.context["config"]["referencias"]["picking"]["exemplo"] == "Ex.: 004512"
    assert "Referência (Nota Fiscal, Pedido ou Picking)" in r.content.decode()


def test_abrir_com_picking_pela_tela_e_ver_no_detalhe(cliente, operador, entrar):
    entrar(cliente).post("/portal/nova", dados_atraso(referencia_tipo="picking", referencia="004512"))
    oc = Ocorrencia.objects.get()

    for usuario, url in ((cliente, f"/portal/{oc.pk}"), (operador, f"/operacao/{oc.pk}")):
        assert "Picking 004512" in entrar(usuario).get(url).content.decode()


def test_operacao_acha_pelo_numero_do_picking(abrir, operador, entrar):
    oc = abrir(referencia_tipo="picking", referencia="004512")
    assert oc.protocolo in entrar(operador).get("/operacao/?q=004512").content.decode()
