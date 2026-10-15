"""Caminhos de borda que restavam sem cobertura: admin, download, painel e mensagens."""

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from ocorrencias import servicos
from ocorrencias.models import Anexo, HistoricoStatus, Ocorrencia

from ..builders import foto


def corpo(resposta) -> str:
    return resposta.content.decode()


def test_prioridade_invalida_e_recusada(abrir, operador):
    r = servicos.atualizar_ocorrencia(operador, abrir(), {"status": "aberta", "prioridade": "urgentissima"})
    assert r.erro == "Prioridade inválida."


def test_anexo_cujo_arquivo_sumiu_do_disco_e_404(ocorrencia, cliente, entrar):
    anexo = ocorrencia.anexos.first()
    anexo.arquivo.delete(save=False)

    assert entrar(cliente).get(f"/anexos/{anexo.pk}").status_code == 404


def test_download_de_pdf_abre_no_navegador_e_planilha_baixa(ocorrencia, cliente, entrar):
    from django.core.files.uploadedfile import SimpleUploadedFile

    servicos.adicionar_mensagem(
        cliente,
        ocorrencia,
        "docs",
        False,
        [
            SimpleUploadedFile("nota.pdf", b"%PDF-1.4", content_type="application/pdf"),
            SimpleUploadedFile("itens.csv", b"a;b", content_type="text/csv"),
        ],
    )
    http = entrar(cliente)
    pdf = Anexo.objects.get(nome_arquivo="nota.pdf")
    csv = Anexo.objects.get(nome_arquivo="itens.csv")

    assert http.get(f"/anexos/{pdf.pk}")["Content-Disposition"].startswith("inline")
    assert http.get(f"/anexos/{csv.pk}")["Content-Disposition"].startswith("attachment")


def test_mensagem_do_cliente_com_anexo_que_falha_avisa(ocorrencia, cliente, entrar):
    with mock.patch.object(Anexo.objects, "create", side_effect=OSError("disco")):
        r = entrar(cliente).post(
            f"/portal/{ocorrencia.pk}/mensagem", {"conteudo": "veja", "anexos": [foto("a.png")]}, follow=True
        )
    assert "não foi possível anexar" in corpo(r)


def _resolvidas(abrir, operador, quantas, horas_para_resolver, ha_dias):
    agora = timezone.now()
    for _ in range(quantas):
        oc = abrir()
        oc.status = "resolvida"
        oc.save(por=operador)
        resolvida_em = agora - timedelta(days=ha_dias)
        Ocorrencia.objects.filter(pk=oc.pk).update(criado_em=resolvida_em - timedelta(hours=horas_para_resolver))
        HistoricoStatus.objects.filter(ocorrencia=oc, para_status="resolvida").update(criado_em=resolvida_em)


def _cartao_tempo(http):
    return {c["label"]: c for c in http.get("/portal/dashboard").context["cartoes"]}["Tempo médio de resolução"]


def test_painel_compara_com_o_periodo_anterior(abrir, operador, cliente, entrar):
    _resolvidas(abrir, operador, 5, horas_para_resolver=10, ha_dias=1)
    _resolvidas(abrir, operador, 5, horas_para_resolver=50, ha_dias=40)

    cartao = _cartao_tempo(entrar(cliente))

    assert cartao["valor"] == "10 h"
    assert (cartao["sub"], cartao["tom"]) == ("40 h melhor que antes", "bom")


def test_painel_sem_periodo_anterior_nao_mostra_comparacao(abrir, operador, cliente, entrar):
    _resolvidas(abrir, operador, 5, horas_para_resolver=10, ha_dias=1)

    cartao = _cartao_tempo(entrar(cliente))

    assert (cartao["valor"], cartao["sub"], cartao["tom"]) == ("10 h", "", "neutro")


def test_admin_do_django_registra_quem_alterou(ocorrencia, admin, client):
    admin.is_staff = admin.is_superuser = True
    admin.save()
    client.force_login(admin)
    url = f"/admin/ocorrencias/ocorrencia/{ocorrencia.pk}/change/"
    form = client.get(url).context["adminform"].form
    dados = {k: v for k, v in form.initial.items() if v is not None and not hasattr(v, "pk")}
    dados.update(
        {
            "cliente": str(ocorrencia.cliente_id),
            "status": "recusada",
            "motivo_recusa": "Teste pelo admin",
            "criado_em_0": timezone.localtime(ocorrencia.criado_em).strftime("%d/%m/%Y"),
            "criado_em_1": timezone.localtime(ocorrencia.criado_em).strftime("%H:%M:%S"),
            "itens-TOTAL_FORMS": "0",
            "itens-INITIAL_FORMS": "0",
            "historico-TOTAL_FORMS": "0",
            "historico-INITIAL_FORMS": "0",
        }
    )

    client.post(url, dados)

    assert HistoricoStatus.objects.filter(ocorrencia=ocorrencia, para_status="recusada", alterado_por=admin).exists()
