"""Portal do cliente: lista, painel, detalhe, formulário e consulta pública."""

import json
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from ocorrencias import servicos
from ocorrencias.models import Aviso, Ocorrencia

from ..builders import dados_atraso, dados_produtos


def corpo(resposta) -> str:
    return resposta.content.decode()


# ---------------------------------------------------------------- lista


def test_lista_mostra_colegas_com_o_nome_de_quem_abriu(ocorrencia, colega, entrar):
    html = corpo(entrar(colega).get("/portal/"))
    assert ocorrencia.protocolo in html
    assert "Ana Cliente" in html


def test_lista_conta_so_as_minhas_aguardando_aprovacao(abrir, operador, cliente, colega, entrar):
    for autor in (cliente, colega):
        oc = abrir(por=autor)
        oc.status = "resolvida"
        oc.save(por=operador)

    # Lista completa conta; o início mostra cada uma que espera o cliente.
    assert entrar(cliente).get("/portal/ocorrencias").context["pendentes"] == 1
    assert len(entrar(cliente).get("/portal/").context["pendentes"]) == 1


def test_lista_ordena_alertas_antes_dos_avisos_informativos(cliente, entrar):
    Aviso.objects.create(titulo="Info", mensagem="m", tipo="info")
    Aviso.objects.create(titulo="Alerta", mensagem="m", tipo="alerta")

    avisos = entrar(cliente).get("/portal/").context["avisos"]

    assert [a.tipo for a in avisos] == ["alerta", "info"]


def test_lista_nao_mostra_avisos_vencidos(cliente, entrar):
    Aviso.objects.create(titulo="Velho", mensagem="m", expira_em=timezone.now() - timedelta(days=1))
    assert "Velho" not in corpo(entrar(cliente).get("/portal/"))


def test_lista_aceita_filtro_inicial(cliente, entrar):
    assert entrar(cliente).get("/portal/ocorrencias?filtro=aprovar").context["filtro_inicial"] == "aprovar"


def test_inicio_mostra_o_retorno_da_abertura(cliente, entrar):
    r = entrar(cliente).get("/portal/?nova=2026-000001&anexosFalha=2")
    assert r.context["nova"] == "2026-000001"
    assert r.context["anexos_falha"] == 2


def test_lista_ignora_anexos_falha_invalido(cliente, entrar):
    assert entrar(cliente).get("/portal/?anexosFalha=abc").context["anexos_falha"] == 0


def test_lixeira_nao_aparece_para_o_cliente(ocorrencia, cliente, entrar):
    Ocorrencia.objects.filter(pk=ocorrencia.pk).update(excluida_em=timezone.now())
    assert ocorrencia.protocolo not in corpo(entrar(cliente).get("/portal/"))
    assert entrar(cliente).get(f"/portal/{ocorrencia.pk}").status_code == 404


# ---------------------------------------------------------------- painel


def test_painel_vazio_mostra_estado_vazio(cliente, entrar):
    r = entrar(cliente).get("/portal/dashboard")
    assert r.context["sem_dados"] is True


def test_painel_com_sla_vencido_destaca_o_cartao(abrir, cliente, entrar):
    oc = abrir()
    Ocorrencia.objects.filter(pk=oc.pk).update(sla_prazo=timezone.now() - timedelta(hours=2))

    cartoes = {c["label"]: c for c in entrar(cliente).get("/portal/dashboard").context["cartoes"]}

    assert cartoes["Em aberto"]["sub"] == "1 com SLA vencido"
    assert cartoes["Em aberto"]["tom"] == "ruim"


def test_painel_sem_vencidas_mostra_tom_bom(abrir, cliente, entrar):
    abrir()
    cartoes = {c["label"]: c for c in entrar(cliente).get("/portal/dashboard").context["cartoes"]}
    assert (cartoes["Em aberto"]["sub"], cartoes["Em aberto"]["tom"]) == ("nenhuma com SLA vencido", "bom")


def test_painel_aguardando_aprovacao_diferencia_minhas_das_de_colegas(abrir, operador, cliente, colega, entrar):
    do_colega = abrir(por=colega)
    do_colega.status = "resolvida"
    do_colega.save(por=operador)
    http = entrar(cliente)

    sub = {c["label"]: c for c in http.get("/portal/dashboard").context["cartoes"]}["Aguardando aprovação"]
    assert (sub["sub"], sub["tom"]) == ("de outros usuários da empresa", "neutro")

    minha = abrir(por=cliente)
    minha.status = "resolvida"
    minha.save(por=operador)
    sub = {c["label"]: c for c in http.get("/portal/dashboard").context["cartoes"]}["Aguardando aprovação"]
    assert (sub["sub"], sub["tom"]) == ("1 é sua", "alerta")


def test_painel_tempo_medio_explica_amostra_pequena(abrir, operador, cliente, entrar):
    http = entrar(cliente)
    tempo = lambda: {c["label"]: c for c in http.get("/portal/dashboard").context["cartoes"]}["Tempo médio de resolução"]  # noqa: E731

    assert tempo()["sub"] == "sem resolvidas no período"

    oc = abrir()
    oc.status = "resolvida"
    oc.save(por=operador)
    assert tempo()["sub"] == "só 1 resolvida no período"


def test_painel_com_historico_longo_reduz_rotulos_das_semanas(abrir, cliente, entrar):
    abrir()
    semanas = entrar(cliente).get("/portal/dashboard?dias=90").context["semanas"]
    assert len(semanas) == 12
    assert semanas[-1]["mostrar"] is True
    assert semanas[-1]["altura"] >= 4


# ---------------------------------------------------------------- detalhe


def test_detalhe_do_autor_nao_e_somente_leitura(ocorrencia, cliente, entrar):
    r = entrar(cliente).get(f"/portal/{ocorrencia.pk}")
    assert r.context["somente_leitura"] is False
    assert "Somente Ana Cliente pode responder" not in corpo(r)


def test_detalhe_de_colega_sem_nome_conhecido_usa_texto_generico(ocorrencia, colega, entrar):
    from contas.models import Papel

    ocorrencia.cliente.papel = Papel.OPERADOR  # sai da lista de "colegas" por papel
    ocorrencia.cliente.save()

    r = entrar(colega).get(f"/portal/{ocorrencia.pk}")

    assert r.context["responsavel_nome"] == "um colega da empresa"


def test_cliente_reabre_a_propria_ocorrencia(ocorrencia, operador, cliente, entrar):
    ocorrencia.status = "resolvida"
    ocorrencia.save(por=operador)

    entrar(cliente).post(f"/portal/{ocorrencia.pk}/reabrir")

    ocorrencia.refresh_from_db()
    assert ocorrencia.status == "em_analise"


def test_exportar_ocorrencia_de_colega_e_permitido_so_na_empresa(ocorrencia, colega, estranho, entrar):
    assert entrar(colega).get(f"/portal/{ocorrencia.pk}/export").content.startswith(b"PK")
    assert entrar(estranho).get(f"/portal/{ocorrencia.pk}/export").status_code == 404


def test_mensagem_com_anexo_invalido_mostra_o_erro_e_preserva_o_texto(ocorrencia, cliente, entrar):
    from django.core.files.uploadedfile import SimpleUploadedFile

    ruim = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/x-msdownload")

    r = entrar(cliente).post(f"/portal/{ocorrencia.pk}/mensagem", {"conteudo": "meu texto", "anexos": [ruim]})

    assert "formato não permitido" in corpo(r)
    assert "meu texto" in corpo(r)


def test_notificacoes_do_cliente_sao_marcadas_como_lidas(ocorrencia, responder, cliente, entrar):
    responder(ocorrencia)
    assert cliente.notificacoes.filter(lida=False).exists()

    entrar(cliente).get("/portal/notificacoes")

    assert not cliente.notificacoes.filter(lida=False).exists()


# ---------------------------------------------------------------- formulário


def test_abertura_com_anexo_que_falha_avisa_na_lista(cliente, entrar):
    from unittest import mock

    from ocorrencias.models import Anexo

    from ..builders import foto

    with mock.patch.object(Anexo.objects, "create", side_effect=OSError("disco")):
        r = entrar(cliente).post("/portal/nova", {**dados_produtos("avaria"), "anexos": [foto()]})

    assert r.url.endswith("&anexosFalha=1")


def test_erro_de_abertura_preserva_os_itens_enviados(cliente, entrar):
    itens = [{"categoria": "falta", "codigo": "9", "descricao": "Item", "quantidade": 1}]

    r = entrar(cliente).post("/portal/nova", dados_produtos(itens_json=json.dumps(itens), tipo="outro"))

    assert r.context["inicial"]["itens"] == itens


@pytest.mark.parametrize("itens_json", ["isto nao e json", '{"a": 1}'])
def test_erro_de_abertura_com_itens_malformados_nao_quebra_o_formulario(cliente, entrar, itens_json):
    r = entrar(cliente).post("/portal/nova", dados_produtos(itens_json=itens_json, tipo="outro"))
    assert r.status_code == 200
    assert r.context["inicial"]["itens"] == []


def test_duplicata_sem_referencia(cliente, entrar):
    assert entrar(cliente).get("/portal/nova/duplicata").json() == {"duplicata": None}


def test_duplicata_so_aceita_get(cliente, entrar):
    assert entrar(cliente).post("/portal/nova/duplicata").status_code == 405


def test_importar_so_aceita_post_e_exige_arquivo(cliente, entrar):
    http = entrar(cliente)
    assert http.get("/portal/nova/importar").status_code == 405
    assert http.post("/portal/nova/importar").json()["erro"] == "Arquivo inválido."


def test_operacao_nao_abre_ocorrencia_pelo_formulario(operador, entrar):
    r = entrar(operador).post("/portal/nova", dados_atraso())
    assert r.status_code == 302 and r.url == "/operacao/"
    assert not Ocorrencia.objects.exists()


# ---------------------------------------------------------------- consulta pública


def test_consulta_exige_protocolo_e_documento(client):
    r = client.post("/consulta", {"protocolo": "", "documento": ""})
    assert "Informe o protocolo e o documento." in corpo(r)


def test_consulta_nao_revela_ocorrencia_na_lixeira(ocorrencia, client):
    Ocorrencia.objects.filter(pk=ocorrencia.pk).update(excluida_em=timezone.now())
    r = client.post("/consulta", {"protocolo": ocorrencia.protocolo, "documento": "12345678900"})
    assert "Protocolo não encontrado ou documento não confere." in corpo(r)


def test_consulta_de_cliente_sem_documento_nunca_confere(abrir, client, sem_empresa):
    oc = servicos.criar_ocorrencia(sem_empresa, dados_atraso(), []).dados["ocorrencia"]
    r = client.post("/consulta", {"protocolo": oc.protocolo, "documento": ""})
    assert "Informe o protocolo e o documento." in corpo(r)
    r = client.post("/consulta", {"protocolo": oc.protocolo, "documento": "000"})
    assert "Protocolo não encontrado ou documento não confere." in corpo(r)


def test_consulta_aceita_documento_com_ou_sem_pontuacao(ocorrencia, client):
    for doc in ("123.456.789-00", "12345678900"):
        r = client.post("/consulta", {"protocolo": ocorrencia.protocolo, "documento": doc})
        assert r.context["r"]["protocolo"] == ocorrencia.protocolo


def test_consulta_nao_vaza_dados_sensiveis(ocorrencia, client):
    r = client.post("/consulta", {"protocolo": ocorrencia.protocolo, "documento": "12345678900"})
    assert set(r.context["r"]) == {"protocolo", "tipo", "status", "historico"}
    assert "Ana Cliente" not in corpo(r)
    assert "cliente@acme.com" not in corpo(r)


def test_ocorrencia_inexistente_na_consulta(client, db):
    r = client.post("/consulta", {"protocolo": str(uuid.uuid4()), "documento": "1"})
    assert "Protocolo não encontrado" in corpo(r)


# ---------------------------------------------------------------- spec 023: início e lista


def test_inicio_tem_os_cartoes_de_tipo_que_levam_ao_formulario(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/"))
    for tipo in ("produtos", "atraso", "reclamacao_sugestao"):
        assert f'href="/portal/nova?tipo={tipo}"' in html


def test_inicio_mostra_so_o_que_esta_em_andamento(abrir, cliente, operador, entrar):
    andamento, encerrada = abrir(), abrir()
    encerrada.status = "recusada"
    encerrada.motivo_recusa = "fora do prazo"
    encerrada.save(por=operador)
    r = entrar(cliente).get("/portal/")
    assert [o.pk for o in r.context["andamento"]] == [andamento.pk]
    assert encerrada.protocolo in corpo(entrar(cliente).get("/portal/ocorrencias"))


def test_inicio_poe_primeiro_o_que_aguarda_o_cliente(abrir, cliente, operador, entrar):
    abrir()
    aguardando = abrir()
    aguardando.status = "resolvida"
    aguardando.save(por=operador)
    assert entrar(cliente).get("/portal/").context["andamento"][0].pk == aguardando.pk


def test_formulario_aceita_o_tipo_vindo_do_cartao(cliente, entrar):
    assert entrar(cliente).get("/portal/nova?tipo=atraso").context["tipo_inicial"] == "atraso"
    assert entrar(cliente).get("/portal/nova?tipo=inventado").context["tipo_inicial"] == ""
