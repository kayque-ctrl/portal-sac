"""Fluxos completos pelo cliente HTTP: formulário → serviço → banco → tela."""

from django.core.files.uploadedfile import SimpleUploadedFile

from contas.models import Usuario
from ocorrencias.models import Aviso, ContatoEncaminhamento, Ocorrencia, SlaRegra

from ..builders import dados_atraso, foto


def test_login_roteia_cada_papel_para_a_sua_area(cliente, operador, client):
    client.force_login(cliente)
    assert client.get("/apos-login").url == "/portal/"
    client.force_login(operador)
    assert client.get("/apos-login").url == "/operacao/"


def test_abrir_ocorrencia_pelo_formulario(cliente, entrar):
    r = entrar(cliente).post("/portal/nova", dados_atraso())

    oc = Ocorrencia.objects.get(tipo="atraso")
    assert r.url == f"/portal/?nova={oc.protocolo}"


def test_importar_planilha_csv(cliente, entrar):
    csv = "codigo;nome;categoria;quantidade\n001;Camisa;Avaria;1\n002;Caneca;Pré-vencido;3\n;sem código;Falta;1\n"
    arquivo = SimpleUploadedFile("p.csv", csv.encode(), content_type="text/csv")

    r = entrar(cliente).post("/portal/nova/importar", {"file": arquivo}).json()

    assert r["total"] == 2
    assert r["ignoradas"] == 1
    assert r["itens"][1]["categoria"] == "pre_vencido"


def test_endpoint_de_duplicata_avisa_o_colega(ocorrencia, colega, entrar):
    r = entrar(colega).get("/portal/nova/duplicata?referencia=12345").json()
    assert r["duplicata"]["protocolo"] == ocorrencia.protocolo


def test_operador_resolve_e_cliente_aprova(ocorrencia, operador, cliente, entrar):
    r = entrar(operador).post(
        f"/operacao/{ocorrencia.pk}/atualizar",
        {"status": "resolvida", "prioridade": "alta", "atribuido_a": str(operador.pk)},
    )
    assert r.url == f"/operacao/{ocorrencia.pk}"
    ocorrencia.refresh_from_db()
    assert ocorrencia.status == "resolvida"

    r = entrar(cliente).post(f"/portal/{ocorrencia.pk}/aprovar", follow=True)

    assert "Ocorrência aprovada!" in r.content.decode()
    ocorrencia.refresh_from_db()
    assert ocorrencia.status == "concluida"


def test_cliente_envia_mensagem_com_anexo(ocorrencia, cliente, entrar):
    r = entrar(cliente).post(f"/portal/{ocorrencia.pk}/mensagem", {"conteudo": "Segue foto", "anexos": [foto()]})

    assert r.url == f"/portal/{ocorrencia.pk}"
    assert ocorrencia.mensagens.filter(autor=cliente).count() == 1


def test_admin_move_para_a_lixeira_e_exclui_definitivamente(ocorrencia, admin, entrar):
    http = entrar(admin)

    http.post(f"/operacao/{ocorrencia.pk}/ciclo/excluir")
    ocorrencia.refresh_from_db()
    assert ocorrencia.excluida_em is not None

    http.post("/operacao/lixeira/excluir", {"ids": [str(ocorrencia.pk)]})
    assert not Ocorrencia.objects.filter(pk=ocorrencia.pk).exists()


def test_cadastros_da_operacao(operador, entrar):
    http = entrar(operador)

    http.post("/operacao/empresas", {"nome": "Initech", "cnpj": "00.000.000/0001-00"})
    http.post("/operacao/contatos", {"email": "q@empresa.com", "setor": "Qualidade"})
    http.post("/operacao/avisos", {"titulo": "Novo", "mensagem": "Teste", "tipo": "info", "expira_em": "2099-01-01"})

    assert ContatoEncaminhamento.objects.filter(setor="Qualidade").exists()
    assert Aviso.objects.filter(titulo="Novo", expira_em__isnull=False).exists()


def test_aviso_respeita_o_limite_de_titulo(operador, entrar):
    r = entrar(operador).post("/operacao/avisos", {"titulo": "x" * 61, "mensagem": "Teste"})
    assert "O título aceita até 60 caracteres." in r.content.decode()


def test_operador_comum_nao_configura_sla_mas_admin_sim(operador, admin, entrar):
    assert entrar(operador).get("/operacao/sla").status_code == 302

    http = entrar(admin)
    http.post("/operacao/sla", {"categoria": "atraso", "prioridade": "", "horas": "48"})
    http.post("/operacao/sla", {"categoria": "atraso", "prioridade": "", "horas": "36"})

    assert SlaRegra.objects.get(categoria="atraso", prioridade=None).horas == 36


def test_operacao_cadastra_cliente_novo(operador, empresa, entrar):
    entrar(operador).post(
        "/operacao/usuarios",
        {"nome": "Nova Pessoa", "email": "nova@acme.com", "papel": "cliente", "empresa_id": str(empresa.pk)},
    )
    assert Usuario.objects.get(email="nova@acme.com").empresa == empresa
