"""Regras de negócio (antes: triggers, RLS e Server Actions)."""

import tempfile
from datetime import timedelta
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from ocorrencias import servicos
from ocorrencias.models import HistoricoStatus, Mensagem, Notificacao, Ocorrencia, SlaRegra
from ocorrencias.permissoes import mensagens_visiveis, ocorrencias_visiveis, pode_agir, pode_ver
from ocorrencias.sla import calcular_sla

from .base import Fabrica, foto


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RegrasTests(Fabrica, TestCase):
    def setUp(self):
        self.criar_elenco()

    def abrir(self, **kw):
        r = servicos.criar_ocorrencia(self.cliente, self.dados_atraso(**kw), [])
        self.assertTrue(r.ok, r.erro)
        return r.dados["ocorrencia"]

    def responder(self, oc, por=None):
        r = servicos.adicionar_mensagem(por or self.operador, oc, "Estamos verificando.", False, [])
        self.assertTrue(r.ok, r.erro)
        oc.refresh_from_db()

    # ----- criação -----

    def test_criacao_gera_protocolo_sla_historico_e_notifica_operacao(self):
        oc = self.abrir()
        ano = timezone.localtime().year
        self.assertRegex(oc.protocolo, rf"^{ano}-\d{{6}}$")
        self.assertEqual(oc.status, "aberta")
        self.assertEqual(oc.sla_horas, 72)  # padrão: prioridade média
        self.assertAlmostEqual(
            (oc.sla_prazo - oc.criado_em).total_seconds(), 72 * 3600, delta=5
        )
        self.assertEqual(HistoricoStatus.objects.filter(ocorrencia=oc).count(), 1)
        destinatarios = set(Notificacao.objects.filter(ocorrencia=oc).values_list("destinatario_id", flat=True))
        self.assertEqual(destinatarios, {self.operador.pk, self.admin.pk})

    def test_protocolos_sao_sequenciais(self):
        a, b = self.abrir(), self.abrir()
        self.assertEqual(int(b.protocolo.split("-")[1]), int(a.protocolo.split("-")[1]) + 1)

    def test_regra_mais_especifica_vence(self):
        SlaRegra.objects.create(categoria="atraso", prioridade="media", horas=10)
        SlaRegra.objects.create(categoria="atraso", prioridade=None, horas=20)
        self.assertEqual(SlaRegra.horas_para("atraso", "media"), 10)
        self.assertEqual(SlaRegra.horas_para("atraso", "alta"), 24)  # prioridade pesa mais
        self.assertEqual(SlaRegra.horas_para("produtos", "baixa"), 120)

    def test_somente_cliente_abre(self):
        r = servicos.criar_ocorrencia(self.operador, self.dados_atraso(), [])
        self.assertEqual(r.erro, "Apenas clientes podem abrir ocorrências.")

    def test_validacoes_de_abertura(self):
        casos = [
            ({"tipo": "outro"}, "Selecione um tipo válido."),
            ({"descricao": "curta"}, "Descreva a ocorrência com pelo menos 10 caracteres."),
            ({"referencia_tipo": ""}, "Escolha se vai informar Nota Fiscal ou Pedido."),
            ({"referencia": ""}, "Informe o número da Nota Fiscal ou do Pedido."),
        ]
        for extra, erro in casos:
            with self.subTest(erro=erro):
                r = servicos.criar_ocorrencia(self.cliente, self.dados_atraso(**extra), [])
                self.assertEqual(r.erro, erro)

    def test_produtos_exigem_itens_e_foto_quando_avaria(self):
        r = servicos.criar_ocorrencia(self.cliente, self.dados_produtos(itens_json="[]"), [])
        self.assertEqual(r.erro, "Adicione ao menos um produto (com código).")

        r = servicos.criar_ocorrencia(self.cliente, self.dados_produtos("avaria"), [])
        self.assertIn("Anexe pelo menos uma foto", r.erro)

        r = servicos.criar_ocorrencia(self.cliente, self.dados_produtos("avaria"), [foto()])
        self.assertTrue(r.ok, r.erro)
        oc = r.dados["ocorrencia"]
        self.assertEqual(oc.itens.count(), 1)
        self.assertEqual(oc.anexos.count(), 1)

    def test_troca_de_volume_dispensa_codigo_e_quantidade(self):
        dados = self.dados_produtos(
            itens_json='[{"categoria": "troca_volume", "codigo": "", "descricao": "", "quantidade": ""}]'
        )
        r = servicos.criar_ocorrencia(self.cliente, dados, [foto()])
        self.assertTrue(r.ok, r.erro)
        item = r.dados["ocorrencia"].itens.get()
        self.assertEqual((item.descricao, item.quantidade), ("Troca de volume", 1))

    def test_imagem_falsa_e_recusada(self):
        falsa = SimpleUploadedFile("x.png", b"isto nao e imagem", content_type="image/png")
        r = servicos.criar_ocorrencia(self.cliente, self.dados_atraso(), [falsa])
        self.assertEqual(r.erro, '"x.png" não parece uma imagem válida.')

    def test_reclamacao_avisa_contatos(self):
        from ocorrencias.models import ContatoEncaminhamento

        ContatoEncaminhamento.objects.create(email="qualidade@empresa.com")
        ContatoEncaminhamento.objects.create(email="inativo@empresa.com", ativo=False)
        with mock.patch("ocorrencias.emails.enviar_email") as enviar:
            r = servicos.criar_ocorrencia(
                self.cliente, {"tipo": "reclamacao_sugestao", "descricao": "Atendimento demorado demais."}, []
            )
        self.assertTrue(r.ok, r.erro)
        self.assertEqual([c.args[0] for c in enviar.call_args_list], ["qualidade@empresa.com"])

    # ----- mensagens -----

    def test_resposta_da_operacao_move_para_tratativa_e_notifica(self):
        oc = self.abrir()
        Notificacao.objects.all().delete()
        self.responder(oc)
        self.assertEqual(oc.status, "em_analise")
        self.assertTrue(Notificacao.objects.filter(destinatario=self.cliente, mensagem__contains="Nova resposta").exists())

    def test_nota_interna_nao_movimenta_nem_aparece_para_cliente(self):
        oc = self.abrir()
        Notificacao.objects.all().delete()
        r = servicos.adicionar_mensagem(self.operador, oc, "só nós", True, [])
        self.assertTrue(r.ok)
        oc.refresh_from_db()
        self.assertEqual(oc.status, "aberta")
        self.assertFalse(Notificacao.objects.filter(destinatario=self.cliente).exists())
        self.assertEqual(mensagens_visiveis(self.cliente, oc).count(), 0)
        self.assertEqual(mensagens_visiveis(self.operador, oc).count(), 1)

    def test_cliente_nao_marca_nota_interna(self):
        oc = self.abrir()
        servicos.adicionar_mensagem(self.cliente, oc, "oi", True, [])
        self.assertFalse(Mensagem.objects.get(ocorrencia=oc).interna)

    def test_colega_nao_responde_e_conversa_encerrada_bloqueia(self):
        oc = self.abrir()
        r = servicos.adicionar_mensagem(self.colega, oc, "oi", False, [])
        self.assertEqual(r.erro, "Só quem abriu esta ocorrência pode enviar mensagens.")
        oc.status = "recusada"
        oc.save(por=self.operador)
        r = servicos.adicionar_mensagem(self.cliente, oc, "oi", False, [])
        self.assertEqual(r.erro, "Esta ocorrência está encerrada. Reabra para enviar mensagens.")
        # Nota interna continua possível.
        self.assertTrue(servicos.adicionar_mensagem(self.operador, oc, "registro", True, []).ok)

    # ----- operação -----

    def test_mudar_status_exige_responsavel_e_tratativa(self):
        oc = self.abrir()
        dados = {"status": "resolvida", "prioridade": "media", "atribuido_a": ""}
        r = servicos.atualizar_ocorrencia(self.operador, oc, dados)
        self.assertEqual(
            r.erro,
            "Não é possível mudar o status: falta um responsável definido e pelo menos uma mensagem registrada para o cliente.",
        )
        self.responder(oc)
        r = servicos.atualizar_ocorrencia(self.operador, oc, {**dados, "atribuido_a": str(self.operador.pk)})
        self.assertTrue(r.ok, r.erro)
        oc.refresh_from_db()
        self.assertEqual(oc.status, "resolvida")

    def test_recusa_exige_motivo_e_operacao_nao_conclui(self):
        oc = self.abrir()
        base = {"prioridade": "media", "atribuido_a": str(self.operador.pk)}
        self.assertEqual(servicos.atualizar_ocorrencia(self.operador, oc, {**base, "status": "concluida"}).erro, "Status inválido.")
        self.assertEqual(
            servicos.atualizar_ocorrencia(self.operador, oc, {**base, "status": "recusada"}).erro,
            "Informe o motivo da recusa.",
        )

    def test_sla_pausa_ao_aguardar_cliente_e_marca_cumprido(self):
        oc = self.abrir()
        self.responder(oc)
        oc.status = "resolvida"
        oc.save(por=self.operador)
        self.assertIsNone(oc.sla_prazo)
        self.assertGreater(oc.sla_restante_ms, 0)
        self.assertEqual(calcular_sla(oc).estado, "pausado")

        # Cliente reabre: o relógio volta de onde parou.
        self.assertTrue(servicos.reabrir(self.cliente, oc))
        self.assertIsNotNone(oc.sla_prazo)
        self.assertIsNone(oc.sla_restante_ms)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.operador, mensagem__contains="reaberta pelo cliente").exists()
        )

        oc.status = "resolvida"
        oc.save(por=self.operador)
        self.assertTrue(servicos.aprovar_resolucao(self.cliente, oc))
        oc.refresh_from_db()
        self.assertEqual(oc.status, "concluida")
        self.assertTrue(oc.sla_cumprido)
        self.assertEqual(oc.aprovada_por, self.cliente)
        self.assertEqual(calcular_sla(oc).estado, "cumprido")

    def test_sla_estourado(self):
        oc = self.abrir()
        Ocorrencia.objects.filter(pk=oc.pk).update(sla_prazo=timezone.now() - timedelta(hours=1))
        oc.refresh_from_db()
        self.assertEqual(calcular_sla(oc).estado, "vencido")
        oc.status = "recusada"
        oc.motivo_recusa = "Fora do prazo"
        oc.save(por=self.operador)
        self.assertFalse(oc.sla_cumprido)

    def test_so_quem_abriu_aprova(self):
        oc = self.abrir()
        oc.status = "resolvida"
        oc.save(por=self.operador)
        self.assertFalse(servicos.aprovar_resolucao(self.colega, oc))
        self.assertFalse(servicos.aprovar_resolucao(self.operador, oc))
        self.assertTrue(servicos.aprovar_resolucao(self.cliente, oc))
        # Segunda aprovação não "mente": nada muda.
        self.assertFalse(servicos.aprovar_resolucao(self.cliente, oc))

    def test_historico_registra_cada_troca(self):
        oc = self.abrir()
        self.responder(oc)
        para = list(oc.historico.values_list("de_status", "para_status"))
        self.assertEqual(para, [(None, "aberta"), ("aberta", "em_analise")])

    def test_coleta_registra_nota_interna(self):
        oc = self.abrir()
        r = servicos.solicitar_coleta(self.operador, oc, "transp@exemplo.com")
        self.assertTrue(r.ok)
        msg = Mensagem.objects.get(ocorrencia=oc)
        self.assertTrue(msg.interna)
        self.assertIn("transp@exemplo.com", msg.conteudo)

    def test_purgar_so_apaga_da_lixeira(self):
        a, b = self.abrir(), self.abrir()
        a.excluida_em = timezone.now()
        a.save()
        self.assertEqual(servicos.purgar([a.pk, b.pk]), 1)
        self.assertFalse(Ocorrencia.objects.filter(pk=a.pk).exists())
        self.assertTrue(Ocorrencia.objects.filter(pk=b.pk).exists())

    def test_auto_arquivamento(self):
        oc = self.abrir()
        oc.status = "recusada"
        oc.save(por=self.operador)
        Ocorrencia.objects.filter(pk=oc.pk).update(atualizado_em=timezone.now() - timedelta(days=40))
        self.assertEqual(servicos.arquivar_concluidas_antigas(30), 1)

    # ----- visibilidade (antes: RLS) -----

    def test_visibilidade_por_empresa(self):
        oc = self.abrir()
        self.assertTrue(pode_ver(self.colega, oc))
        self.assertFalse(pode_agir(self.colega, oc))
        self.assertFalse(pode_ver(self.estranho, oc))
        self.assertTrue(pode_agir(self.operador, oc))
        self.assertEqual(list(ocorrencias_visiveis(self.estranho)), [])
        self.assertEqual(list(ocorrencias_visiveis(self.colega)), [oc])

    def test_sem_empresa_ve_so_as_proprias(self):
        from contas.models import Usuario

        solo = Usuario.objects.create_user("solo@x.com", "senha-forte-1", nome="Solo")
        sem_empresa = Usuario.objects.create_user("solo2@x.com", "senha-forte-1", nome="Solo 2")
        r = servicos.criar_ocorrencia(solo, self.dados_atraso(), [])
        self.assertTrue(pode_ver(solo, r.dados["ocorrencia"]))
        self.assertFalse(pode_ver(sem_empresa, r.dados["ocorrencia"]))

    def test_duplicata_avisa_quem_abriu(self):
        self.abrir()
        self.assertEqual(servicos.verificar_duplicata(self.cliente, "987")["abertaPor"], None)
        self.assertEqual(servicos.verificar_duplicata(self.colega, "987")["abertaPor"], "Ana Cliente")
        self.assertIsNone(servicos.verificar_duplicata(self.estranho, "987"))
