"""Telas e fluxos HTTP (renderização, acesso por papel, formulários)."""

import re
import tempfile

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from contas.models import Usuario
from ocorrencias import servicos
from ocorrencias.models import Aviso, ContatoEncaminhamento, Ocorrencia, SlaRegra

from .base import Fabrica, foto


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TelasTests(Fabrica, TestCase):
    def setUp(self):
        self.criar_elenco()
        r = servicos.criar_ocorrencia(self.cliente, self.dados_produtos("avaria"), [foto()])
        self.oc = r.dados["ocorrencia"]
        servicos.adicionar_mensagem(self.operador, self.oc, "Olá, vamos verificar.", False, [foto("resp.png")])
        Aviso.objects.create(titulo="Feriado", mensagem="Sem coleta na sexta.", tipo="alerta")

    def entrar(self, user):
        self.client.force_login(user)

    def test_paginas_publicas(self):
        for nome in ["publico:inicio", "publico:consulta", "contas:login", "contas:esqueci_senha", "contas:definir_senha"]:
            with self.subTest(nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)

    def test_areas_exigem_login_e_papel(self):
        self.assertRedirects(self.client.get("/portal/"), "/login?next=/portal/", fetch_redirect_response=False)
        self.entrar(self.cliente)
        self.assertRedirects(self.client.get("/operacao/"), "/portal/", fetch_redirect_response=False)
        self.entrar(self.operador)
        self.assertRedirects(self.client.get("/portal/"), "/operacao/", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/operacao/sla"), "/operacao/", fetch_redirect_response=False)

    def test_telas_do_cliente(self):
        self.entrar(self.cliente)
        for url in ["/portal/", "/portal/dashboard", "/portal/dashboard?dias=7", "/portal/nova", "/portal/notificacoes", f"/portal/{self.oc.pk}"]:
            with self.subTest(url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
        r = self.client.get("/portal/")
        self.assertContains(r, self.oc.protocolo)
        self.assertContains(r, "Feriado")

    def test_telas_da_operacao(self):
        self.entrar(self.admin)
        urls = [
            "/operacao/",
            "/operacao/?situacao=concluidas",
            "/operacao/?situacao=arquivadas",
            "/operacao/?situacao=lixeira",
            f"/operacao/?q={self.oc.protocolo}",
            "/operacao/?q=Ana",
            "/operacao/painel",
            f"/operacao/painel?empresa={self.empresa.pk}&de=2020-01-01&ate=2099-12-31",
            "/operacao/empresas",
            f"/operacao/empresas/{self.empresa.pk}",
            "/operacao/usuarios",
            f"/operacao/usuarios/{self.cliente.pk}",
            "/operacao/avisos",
            "/operacao/contatos",
            "/operacao/sla",
            "/operacao/notificacoes",
            f"/operacao/{self.oc.pk}",
        ]
        for url in urls:
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(f"/operacao/?q={self.oc.protocolo}"), self.oc.protocolo)

    def test_exportacoes_xlsx(self):
        self.entrar(self.cliente)
        r = self.client.get(f"/portal/{self.oc.pk}/export")
        self.assertEqual(r["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(r.content.startswith(b"PK"))
        self.entrar(self.operador)
        r = self.client.get("/operacao/painel/export?status=aberta")
        self.assertTrue(r.content.startswith(b"PK"))

    def test_anexo_respeita_visibilidade(self):
        anexo = self.oc.anexos.first()
        self.entrar(self.colega)
        self.assertEqual(self.client.get(f"/anexos/{anexo.pk}").status_code, 200)
        self.entrar(self.estranho)
        self.assertEqual(self.client.get(f"/anexos/{anexo.pk}").status_code, 404)

    def test_estranho_nao_ve_ocorrencia(self):
        self.entrar(self.estranho)
        self.assertEqual(self.client.get(f"/portal/{self.oc.pk}").status_code, 404)

    def test_colega_ve_em_modo_leitura(self):
        self.entrar(self.colega)
        r = self.client.get(f"/portal/{self.oc.pk}")
        self.assertContains(r, "Somente Ana Cliente pode responder")

    def test_login_e_roteamento(self):
        r = self.client.post("/login", {"email": "cliente@acme.com", "password": "errada"})
        self.assertContains(r, "E-mail ou senha inválidos.")
        r = self.client.post("/login", {"email": "CLIENTE@acme.com", "password": "senha-forte-1"})
        self.assertRedirects(r, "/apos-login", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/apos-login"), "/portal/", fetch_redirect_response=False)

    def test_abrir_ocorrencia_pelo_formulario(self):
        self.entrar(self.cliente)
        r = self.client.post("/portal/nova", self.dados_atraso())
        oc = Ocorrencia.objects.filter(tipo="atraso").get()
        self.assertRedirects(r, f"/portal/?nova={oc.protocolo}", fetch_redirect_response=False)
        # Erro volta ao formulário com o que foi preenchido.
        r = self.client.post("/portal/nova", self.dados_atraso(descricao="curta"))
        self.assertContains(r, "Descreva a ocorrência com pelo menos 10 caracteres.")
        self.assertContains(r, '"referencia": "987"')

    def test_importar_planilha_csv(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.entrar(self.cliente)
        csv = "codigo;nome;categoria;quantidade\n001;Camisa;Avaria;1\n002;Caneca;Pré-vencido;3\n;sem código;Falta;1\n"
        arq = SimpleUploadedFile("p.csv", csv.encode(), content_type="text/csv")
        r = self.client.post("/portal/nova/importar", {"file": arq}).json()
        self.assertEqual(r["total"], 2)
        self.assertEqual(r["ignoradas"], 1)
        self.assertEqual(r["itens"][1]["categoria"], "pre_vencido")

    def test_duplicata_endpoint(self):
        self.entrar(self.colega)
        r = self.client.get("/portal/nova/duplicata?referencia=12345").json()
        self.assertEqual(r["duplicata"]["protocolo"], self.oc.protocolo)

    def test_fluxo_operador_resolve_e_cliente_aprova(self):
        self.entrar(self.operador)
        r = self.client.post(
            f"/operacao/{self.oc.pk}/atualizar",
            {"status": "resolvida", "prioridade": "alta", "atribuido_a": str(self.operador.pk)},
        )
        self.assertRedirects(r, f"/operacao/{self.oc.pk}", fetch_redirect_response=False)
        self.oc.refresh_from_db()
        self.assertEqual(self.oc.status, "resolvida")

        self.entrar(self.cliente)
        r = self.client.post(f"/portal/{self.oc.pk}/aprovar", follow=True)
        self.assertContains(r, "Ocorrência aprovada!")
        self.oc.refresh_from_db()
        self.assertEqual(self.oc.status, "concluida")

    def test_erro_nos_controles_aparece_na_tela(self):
        self.entrar(self.operador)
        r = self.client.post(
            f"/operacao/{self.oc.pk}/atualizar", {"status": "resolvida", "prioridade": "media", "atribuido_a": ""}
        )
        self.assertContains(r, "Não é possível mudar o status: falta um responsável definido.")

    def test_mensagem_com_anexo_pela_tela(self):
        self.entrar(self.cliente)
        r = self.client.post(f"/portal/{self.oc.pk}/mensagem", {"conteudo": "Segue foto", "anexos": [foto()]})
        self.assertRedirects(r, f"/portal/{self.oc.pk}", fetch_redirect_response=False)
        self.assertEqual(self.oc.mensagens.filter(autor=self.cliente).count(), 1)

    def test_lixeira_so_admin(self):
        self.entrar(self.operador)
        self.client.post(f"/operacao/{self.oc.pk}/ciclo/excluir")
        self.oc.refresh_from_db()
        self.assertIsNone(self.oc.excluida_em)
        self.entrar(self.admin)
        self.client.post(f"/operacao/{self.oc.pk}/ciclo/excluir")
        self.oc.refresh_from_db()
        self.assertIsNotNone(self.oc.excluida_em)
        self.client.post("/operacao/lixeira/excluir", {"ids": [str(self.oc.pk)]})
        self.assertFalse(Ocorrencia.objects.filter(pk=self.oc.pk).exists())

    def test_cadastros(self):
        self.entrar(self.operador)
        self.client.post("/operacao/empresas", {"nome": "Initech", "cnpj": "00.000.000/0001-00"})
        self.client.post("/operacao/contatos", {"email": "q@empresa.com", "setor": "Qualidade"})
        self.client.post("/operacao/avisos", {"titulo": "Novo", "mensagem": "Teste", "tipo": "info", "expira_em": "2099-01-01"})
        r = self.client.post("/operacao/avisos", {"titulo": "x" * 61, "mensagem": "Teste"})
        self.assertContains(r, "O título aceita até 60 caracteres.")
        self.assertTrue(ContatoEncaminhamento.objects.filter(setor="Qualidade").exists())
        self.assertTrue(Aviso.objects.filter(titulo="Novo", expira_em__isnull=False).exists())
        self.assertEqual(self.client.get("/operacao/sla").status_code, 302)  # operador comum não configura SLA
        self.entrar(self.admin)
        self.client.post("/operacao/sla", {"categoria": "atraso", "prioridade": "", "horas": "48"})
        self.client.post("/operacao/sla", {"categoria": "atraso", "prioridade": "", "horas": "36"})
        self.assertEqual(SlaRegra.objects.get(categoria="atraso", prioridade=None).horas, 36)

    def test_consulta_publica(self):
        r = self.client.post("/consulta", {"protocolo": self.oc.protocolo, "documento": "12345678900"})
        self.assertContains(r, "Linha do tempo")
        r = self.client.post("/consulta", {"protocolo": self.oc.protocolo, "documento": "000"})
        self.assertContains(r, "Protocolo não encontrado ou documento não confere.")


class ConviteTests(Fabrica, TestCase):
    def setUp(self):
        self.criar_elenco()

    def test_convite_define_senha_e_ativa(self):
        self.client.force_login(self.operador)
        r = self.client.post(
            "/operacao/usuarios",
            {"nome": "Nova Pessoa", "email": "nova@acme.com", "papel": "cliente", "empresa_id": str(self.empresa.pk)},
        )
        self.assertRedirects(r, "/operacao/usuarios", fetch_redirect_response=False)
        novo = Usuario.objects.get(email="nova@acme.com")
        self.assertIsNone(novo.ativado_em)
        self.assertEqual(novo.empresa, self.empresa)
        self.assertFalse(novo.has_usable_password())

        link = re.search(r'href="([^"]+/auth/confirm[^"]+)"', mail.outbox[-1].body).group(1).replace("&amp;", "&")
        caminho = link.split("localhost:8000", 1)[1]
        self.client.logout()

        # GET só mostra o botão (não consome o token).
        self.assertContains(self.client.get(caminho), "Confirmar acesso")
        r = self.client.post("/auth/confirm", dict(p.split("=", 1) for p in caminho.split("?", 1)[1].split("&")))
        self.assertRedirects(r, "/definir-senha", fetch_redirect_response=False)

        r = self.client.post("/definir-senha", {"senha": "nova-senha-123", "confirma": "nova-senha-123"})
        self.assertRedirects(r, "/apos-login", fetch_redirect_response=False)
        novo.refresh_from_db()
        self.assertIsNotNone(novo.ativado_em)
        self.assertTrue(novo.check_password("nova-senha-123"))

        # O link é de uso único.
        self.client.logout()
        r = self.client.post("/auth/confirm", dict(p.split("=", 1) for p in caminho.split("?", 1)[1].split("&")))
        self.assertRedirects(r, "/login?erro=convite", fetch_redirect_response=False)

    def test_operador_nao_concede_admin(self):
        self.client.force_login(self.operador)
        r = self.client.post("/operacao/usuarios", {"nome": "X", "email": "x@x.com", "papel": "admin"})
        self.assertContains(r, "Apenas um administrador pode conceder o papel de admin.")
        r = self.client.post(f"/operacao/usuarios/{self.cliente.pk}", {"nome": "Ana", "papel": "admin"})
        self.assertContains(r, "Apenas um administrador pode conceder o papel de admin.")
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.papel, "cliente")

    def test_esqueci_senha_nao_revela_existencia(self):
        r1 = self.client.post("/esqueci-senha", {"email": "cliente@acme.com"})
        r2 = self.client.post("/esqueci-senha", {"email": "ninguem@acme.com"})
        self.assertContains(r1, "Se esse e-mail estiver cadastrado")
        self.assertContains(r2, "Se esse e-mail estiver cadastrado")
        self.assertEqual(len(mail.outbox), 1)

    def test_nao_exclui_usuario_com_ocorrencias(self):
        servicos.criar_ocorrencia(self.cliente, self.dados_atraso(), [])
        self.client.force_login(self.operador)
        self.client.post(f"/operacao/usuarios/{self.cliente.pk}/excluir")
        self.assertTrue(Usuario.objects.filter(pk=self.cliente.pk).exists())
        self.client.post(f"/operacao/usuarios/{self.colega.pk}/excluir")
        self.assertFalse(Usuario.objects.filter(pk=self.colega.pk).exists())
