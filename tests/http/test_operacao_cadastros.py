"""Operação: empresas, usuários, avisos, contatos e regras de SLA."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from contas.models import Empresa, Usuario
from ocorrencias.models import Aviso, ContatoEncaminhamento, SlaRegra


def corpo(resposta) -> str:
    return resposta.content.decode()


# ---------------------------------------------------------------- empresas


def test_empresa_com_nome_curto_e_recusada(operador, entrar):
    r = entrar(operador).post("/operacao/empresas", {"nome": "A"})
    assert "Informe o nome da empresa." in corpo(r)
    assert not Empresa.objects.filter(nome="A").exists()


def test_empresa_guarda_so_os_campos_preenchidos(operador, entrar):
    entrar(operador).post("/operacao/empresas", {"nome": "Initech", "cnpj": " 00.000.000/0001-00 ", "telefone": "  "})
    empresa = Empresa.objects.get(nome="Initech")
    assert empresa.cnpj == "00.000.000/0001-00"
    assert empresa.telefone is None


def test_empresas_filtra_por_nome_ou_cnpj(empresa, outra_empresa, operador, entrar):
    empresa.cnpj = "11.111.111/0001-11"
    empresa.save()
    http = entrar(operador)

    assert "Globex" not in corpo(http.get("/operacao/empresas?q=acme"))
    assert "ACME" in corpo(http.get("/operacao/empresas?q=11.111"))


def test_vincular_e_desvincular_cliente_da_empresa(empresa, outra_empresa, estranho, operador, entrar):
    http = entrar(operador)

    http.post(f"/operacao/empresas/{empresa.pk}", {"userId": str(estranho.pk)})
    estranho.refresh_from_db()
    assert estranho.empresa == empresa

    http.post(f"/operacao/empresas/{empresa.pk}", {"userId": str(estranho.pk), "acao": "desvincular"})
    estranho.refresh_from_db()
    assert estranho.empresa is None


def test_so_cliente_pode_ser_vinculado_a_empresa(empresa, operador, admin, entrar):
    entrar(operador).post(f"/operacao/empresas/{empresa.pk}", {"userId": str(admin.pk)})
    admin.refresh_from_db()
    assert admin.empresa is None


def test_vinculo_com_id_invalido_nao_faz_nada(empresa, operador, entrar):
    r = entrar(operador).post(f"/operacao/empresas/{empresa.pk}", {"userId": "lixo"})
    assert r.status_code == 302


# ---------------------------------------------------------------- usuários


@pytest.mark.parametrize(
    ("dados", "erro"),
    [
        ({"nome": "Nova Pessoa", "email": "sem-arroba"}, "Informe um e-mail válido."),
        ({"nome": "N", "email": "n@x.com"}, "Informe o nome do usuário."),
        ({"nome": "Outra Ana", "email": "cliente@acme.com"}, "Já existe um usuário com esse e-mail."),
    ],
)
def test_validacoes_do_cadastro_de_usuario(cliente, operador, entrar, dados, erro):
    assert erro in corpo(entrar(operador).post("/operacao/usuarios", dados))


def test_admin_pode_criar_admin(admin, entrar):
    entrar(admin).post("/operacao/usuarios", {"nome": "Novo Admin", "email": "novo@x.com", "papel": "admin"})
    assert Usuario.objects.get(email="novo@x.com").papel == "admin"


def test_papel_desconhecido_vira_cliente(operador, entrar):
    entrar(operador).post("/operacao/usuarios", {"nome": "Fulano", "email": "f@x.com", "papel": "superuser"})
    assert Usuario.objects.get(email="f@x.com").papel == "cliente"


def test_operador_nao_tem_empresa_nem_documento_vinculados(operador, empresa, entrar):
    entrar(operador).post(
        "/operacao/usuarios",
        {"nome": "Outro Op", "email": "o@x.com", "papel": "operador", "empresa_id": str(empresa.pk), "tipo_pessoa": "pf"},
    )
    novo = Usuario.objects.get(email="o@x.com")
    assert (novo.empresa, novo.tipo_pessoa) == (None, None)


def test_cliente_novo_guarda_tipo_documento_e_empresa(operador, empresa, entrar):
    entrar(operador).post(
        "/operacao/usuarios",
        {
            "nome": "Cli Novo",
            "email": "c@x.com",
            "empresa_id": str(empresa.pk),
            "tipo_pessoa": "pj",
            "documento": "12.345.678/0001-90",
            "telefone": "11 99999-0000",
        },
    )
    novo = Usuario.objects.get(email="c@x.com")
    assert (novo.empresa, novo.tipo_pessoa, novo.documento) == (empresa, "pj", "12.345.678/0001-90")


def test_empresa_inexistente_no_cadastro_e_ignorada(operador, entrar):
    import uuid

    entrar(operador).post("/operacao/usuarios", {"nome": "Cli Novo", "email": "c@x.com", "empresa_id": str(uuid.uuid4())})
    assert Usuario.objects.get(email="c@x.com").empresa is None


def test_convite_sem_smtp_avisa_que_o_email_nao_saiu(operador, entrar, settings):
    settings.SMTP_CONFIGURADO = False
    r = entrar(operador).post("/operacao/usuarios", {"nome": "Cli Novo", "email": "c@x.com"}, follow=True)
    assert "o e-mail não pôde ser enviado" in corpo(r)


def test_lista_de_usuarios_filtra(cliente, colega, operador, empresa, entrar):
    http = entrar(operador)
    assert "Bruno Colega" in corpo(http.get("/operacao/usuarios?q=bruno"))
    assert "Bruno Colega" not in corpo(http.get("/operacao/usuarios?papel=operador"))
    assert "Bruno Colega" in corpo(http.get(f"/operacao/usuarios?empresa={empresa.pk}&papel=cliente"))


def test_reenviar_convite_pendente(operador, entrar, settings):
    settings.SMTP_CONFIGURADO = True
    pendente = Usuario.objects.create_user("p@x.com", None, nome="Pendente")
    r = entrar(operador).post(f"/operacao/usuarios/{pendente.pk}/reenviar").json()
    assert r == {"mensagem": "Convite reenviado para p@x.com."}
    assert mail.outbox[-1].to == ["p@x.com"]


def test_reenviar_convite_de_quem_ja_ativou(cliente, operador, entrar):
    cliente.ativado_em = timezone.now()
    cliente.save()
    assert entrar(operador).post(f"/operacao/usuarios/{cliente.pk}/reenviar").json() == {"error": "Esse usuário já ativou a conta."}


def test_reenviar_convite_de_usuario_inexistente(operador, entrar):
    import uuid

    assert entrar(operador).post(f"/operacao/usuarios/{uuid.uuid4()}/reenviar").json() == {"error": "Usuário não encontrado."}


def test_reenvio_sem_smtp_informa_a_falha(operador, entrar, settings):
    settings.SMTP_CONFIGURADO = False
    pendente = Usuario.objects.create_user("p@x.com", None, nome="Pendente")
    r = entrar(operador).post(f"/operacao/usuarios/{pendente.pk}/reenviar").json()
    assert "e-mail não pôde ser enviado" in r["error"]


def test_editar_usuario(cliente, outra_empresa, operador, entrar):
    r = entrar(operador).post(
        f"/operacao/usuarios/{cliente.pk}",
        {"nome": "Ana Renomeada", "papel": "cliente", "empresa_id": str(outra_empresa.pk), "tipo_pessoa": "pf"},
    )
    assert r.url == f"/operacao/usuarios/{cliente.pk}"
    cliente.refresh_from_db()
    assert (cliente.nome, cliente.empresa) == ("Ana Renomeada", outra_empresa)


def test_editar_usuario_com_nome_curto(cliente, operador, entrar):
    r = entrar(operador).post(f"/operacao/usuarios/{cliente.pk}", {"nome": "A", "papel": "cliente"})
    assert "Informe o nome do usuário." in corpo(r)


def test_operador_nao_rebaixa_admin(admin, operador, entrar):
    r = entrar(operador).post(f"/operacao/usuarios/{admin.pk}", {"nome": "Alice Admin", "papel": "cliente"})
    assert "Apenas um administrador pode conceder o papel de admin." in corpo(r)
    admin.refresh_from_db()
    assert admin.papel == "admin"


def test_detalhe_explica_por_que_nao_pode_excluir(cliente, ocorrencia, operador, entrar):
    http = entrar(operador)
    assert "Possui 1 ocorrência(s)" in corpo(http.get(f"/operacao/usuarios/{cliente.pk}"))
    assert "Você não pode excluir a si mesmo." in corpo(http.get(f"/operacao/usuarios/{operador.pk}"))


def test_nao_exclui_a_si_mesmo(operador, entrar):
    entrar(operador).post(f"/operacao/usuarios/{operador.pk}/excluir")
    assert Usuario.objects.filter(pk=operador.pk).exists()


def test_operador_nao_exclui_admin(admin, operador, entrar):
    entrar(operador).post(f"/operacao/usuarios/{admin.pk}/excluir")
    assert Usuario.objects.filter(pk=admin.pk).exists()


def test_admin_exclui_outro_admin(admin, entrar):
    outro = Usuario.objects.create_user("a2@x.com", "senha-forte-1", nome="Outro Admin", papel="admin")
    entrar(admin).post(f"/operacao/usuarios/{outro.pk}/excluir")
    assert not Usuario.objects.filter(pk=outro.pk).exists()


# ---------------------------------------------------------------- avisos


@pytest.mark.parametrize(
    ("dados", "erro"),
    [
        ({"titulo": "x", "mensagem": "Teste"}, "Informe um título."),
        ({"titulo": "Título", "mensagem": "x"}, "Informe a mensagem."),
        ({"titulo": "T" * 61, "mensagem": "Teste"}, "O título aceita até 60 caracteres."),
        ({"titulo": "Título", "mensagem": "M" * 161}, "A mensagem aceita até 160 caracteres."),
        ({"titulo": "Título", "mensagem": "Teste", "expira_em": "31/12/2099"}, "Data de validade inválida."),
        ({"titulo": "Título", "mensagem": "Teste", "expira_em": "2099-02-31"}, "Data de validade inválida."),
        ({"titulo": "Título", "mensagem": "Teste", "expira_em": "2000-01-01"}, "A validade não pode estar no passado."),
    ],
)
def test_validacoes_do_aviso(operador, entrar, dados, erro):
    assert erro in corpo(entrar(operador).post("/operacao/avisos", dados))
    assert not Aviso.objects.exists()


def test_aviso_vale_ate_o_fim_do_dia_informado(operador, entrar):
    amanha = (timezone.localdate() + timedelta(days=1)).isoformat()
    entrar(operador).post("/operacao/avisos", {"titulo": "Aviso", "mensagem": "Teste", "tipo": "alerta", "expira_em": amanha})

    aviso = Aviso.objects.get()
    assert aviso.tipo == "alerta"
    assert timezone.localtime(aviso.expira_em).strftime("%H:%M:%S") == "23:59:59"


def test_tipo_de_aviso_desconhecido_vira_info(operador, entrar):
    entrar(operador).post("/operacao/avisos", {"titulo": "Aviso", "mensagem": "Teste", "tipo": "xx"})
    assert Aviso.objects.get().tipo == "info"


def test_alternar_e_excluir_aviso(operador, entrar):
    aviso = Aviso.objects.create(titulo="Aviso", mensagem="Teste")
    http = entrar(operador)

    http.post(f"/operacao/avisos/{aviso.pk}/alternar")
    aviso.refresh_from_db()
    assert not aviso.ativo

    http.post(f"/operacao/avisos/{aviso.pk}/excluir")
    assert not Aviso.objects.exists()


# ---------------------------------------------------------------- contatos


def test_contato_com_email_invalido(operador, entrar):
    assert "Informe um e-mail válido." in corpo(entrar(operador).post("/operacao/contatos", {"email": "abc"}))
    assert not ContatoEncaminhamento.objects.exists()


def test_alternar_e_excluir_contato(operador, entrar):
    contato = ContatoEncaminhamento.objects.create(email="q@empresa.com")
    http = entrar(operador)

    http.post(f"/operacao/contatos/{contato.pk}/alternar")
    contato.refresh_from_db()
    assert not contato.ativo

    http.post(f"/operacao/contatos/{contato.pk}/excluir")
    assert not ContatoEncaminhamento.objects.exists()


# ---------------------------------------------------------------- SLA


@pytest.mark.parametrize("horas", ["", "0", "-3", "abc"])
def test_sla_exige_horas_positivas(admin, entrar, horas):
    r = entrar(admin).post("/operacao/sla", {"categoria": "atraso", "horas": horas})
    assert "Informe o prazo em horas (maior que zero)." in corpo(r)


def test_sla_com_categoria_e_prioridade_invalidas_vira_regra_geral(admin, entrar):
    entrar(admin).post("/operacao/sla", {"categoria": "avaria", "prioridade": "urgente", "horas": "10"})
    assert SlaRegra.objects.filter(categoria=None, prioridade=None, horas=10).exists()


def test_admin_exclui_regra_de_sla(admin, entrar):
    regra = SlaRegra.objects.create(categoria="atraso", prioridade=None, horas=5)
    entrar(admin).post(f"/operacao/sla/{regra.pk}/excluir")
    assert not SlaRegra.objects.filter(pk=regra.pk).exists()


def test_operador_nao_exclui_regra_de_sla(operador, entrar):
    regra = SlaRegra.objects.create(categoria="atraso", prioridade=None, horas=5)
    entrar(operador).post(f"/operacao/sla/{regra.pk}/excluir")
    assert SlaRegra.objects.filter(pk=regra.pk).exists()
