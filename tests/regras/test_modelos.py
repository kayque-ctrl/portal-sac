"""Modelos: representações, propriedades e o relógio do SLA em casos de borda."""

from datetime import timedelta

import pytest
from django.utils import timezone

from contas.models import Papel, Usuario
from ocorrencias import servicos
from ocorrencias.models import (
    Anexo,
    Aviso,
    ContatoEncaminhamento,
    Mensagem,
    OcorrenciaItem,
    SlaRegra,
)

from ..builders import dados_produtos, foto

# ---------------------------------------------------------------- usuários


def test_usuario_sem_email_e_recusado(db):
    with pytest.raises(ValueError, match="e-mail é obrigatório"):
        Usuario.objects.create_user("", "senha")


def test_email_e_normalizado_em_minusculas(db):
    assert Usuario.objects.create_user("Ana@ACME.com", "senha-forte-1").email == "ana@acme.com"


def test_usuario_nasce_cliente_por_padrao(db):
    assert Usuario.objects.create_user("a@x.com", "senha-forte-1").papel == Papel.CLIENTE


def test_usuario_sem_senha_nao_consegue_logar(db):
    assert not Usuario.objects.create_user("a@x.com").has_usable_password()


def test_superusuario_nasce_admin_ativado(db):
    u = Usuario.objects.create_superuser("root@x.com", "senha-forte-1")
    assert (u.papel, u.is_staff, u.is_superuser) == (Papel.ADMIN, True, True)
    assert u.ativado_em is not None
    assert u.eh_admin and u.eh_operacao and not u.eh_cliente


@pytest.mark.parametrize(
    ("papel", "operacao", "admin", "cliente"),
    [("cliente", False, False, True), ("operador", True, False, False), ("admin", True, True, False)],
)
def test_propriedades_de_papel(db, papel, operacao, admin, cliente):
    u = Usuario.objects.create_user(f"{papel}@x.com", "senha-forte-1", papel=papel)
    assert (u.eh_operacao, u.eh_admin, u.eh_cliente) == (operacao, admin, cliente)


def test_representacoes_em_texto(db, ocorrencia, empresa, cliente):
    Mensagem.objects.create(ocorrencia=ocorrencia, autor=cliente, conteudo="oi")
    assert str(empresa) == "ACME"
    assert str(cliente) == "Ana Cliente"
    assert str(Usuario(email="sem-nome@x.com", nome="")) == "sem-nome@x.com"
    assert str(ocorrencia) == ocorrencia.protocolo
    assert str(ocorrencia.itens.get()) == "Camisa (2)"
    assert str(ocorrencia.anexos.first()) == "foto.png"
    assert str(Aviso(titulo="Feriado")) == "Feriado"
    assert str(ContatoEncaminhamento(email="a@x.com")) == "a@x.com"
    assert str(SlaRegra(categoria=None, prioridade="alta", horas=4)) == "qualquer / alta: 4 h"


# ---------------------------------------------------------------- ocorrência


def test_bloqueada_conforme_o_status(abrir):
    oc = abrir()
    assert not oc.bloqueada
    for status in ("resolvida", "concluida", "recusada"):
        oc.status = status
        assert oc.bloqueada


def test_referencia_formatada(abrir):
    assert abrir().referencia_formatada == "Pedido 987"


def test_status_original_acompanha_o_banco(abrir, operador):
    oc = abrir()
    oc.status = "recusada"
    assert oc.status_original == "aberta"
    oc.save(por=operador)
    assert oc.status_original == "recusada"


def test_aviso_expirado(db):
    agora = timezone.now()
    assert not Aviso(titulo="a", mensagem="b").expirado
    assert not Aviso(titulo="a", mensagem="b", expira_em=agora + timedelta(days=1)).expirado
    assert Aviso(titulo="a", mensagem="b", expira_em=agora - timedelta(days=1)).expirado


def test_avisos_vigentes_escondem_os_vencidos_e_os_inativos(db):
    agora = timezone.now()
    Aviso.objects.create(titulo="ok", mensagem="m")
    Aviso.objects.create(titulo="com validade", mensagem="m", expira_em=agora + timedelta(days=1))
    Aviso.objects.create(titulo="vencido", mensagem="m", expira_em=agora - timedelta(days=1))
    Aviso.objects.create(titulo="inativo", mensagem="m", ativo=False)

    assert {a.titulo for a in Aviso.vigentes()} == {"ok", "com validade"}


# ---------------------------------------------------------------- SLA


def test_retomar_sem_tempo_guardado_reinicia_pelas_horas_da_regra(abrir, operador, cliente):
    """Aguardando aprovação sem sla_restante_ms (dado antigo): retoma com o prazo cheio."""
    oc = abrir()
    oc.status = "resolvida"
    oc.sla_restante_ms = None
    oc.save(por=operador)
    oc.sla_restante_ms = None

    assert servicos.reabrir(cliente, oc)

    assert (oc.sla_prazo - timezone.now()).total_seconds() == pytest.approx(oc.sla_horas * 3600, abs=10)


def test_reabrir_encerrada_reinicia_o_prazo(abrir, operador, cliente):
    oc = abrir()
    oc.status = "recusada"
    oc.motivo_recusa = "x"
    oc.save(por=operador)

    assert servicos.reabrir(cliente, oc)

    assert oc.sla_cumprido is None
    assert oc.sla_prazo is not None


def test_sem_regra_nao_ha_sla(db, cliente):
    SlaRegra.objects.all().delete()
    oc = servicos.criar_ocorrencia(cliente, {"tipo": "reclamacao_sugestao", "descricao": "Algo bem longo aqui."}, []).dados["ocorrencia"]
    assert oc.sla_horas is None and oc.sla_prazo is None


# ---------------------------------------------------------------- reabrir


def test_reabrir_recusado_para_quem_nao_e_dono_ou_operacao(abrir, colega, operador):
    oc = abrir()
    oc.status = "recusada"
    oc.save(por=operador)
    assert not servicos.reabrir(colega, oc)


def test_nao_reabre_ocorrencia_na_lixeira(abrir, cliente):
    oc = abrir()
    oc.excluida_em = timezone.now()
    assert not servicos.reabrir(cliente, oc)


def test_reabrir_desarquiva(abrir, operador):
    oc = abrir()
    oc.status = "recusada"
    oc.arquivada_em = timezone.now()
    oc.save(por=operador)

    assert servicos.reabrir(operador, oc)

    assert oc.arquivada_em is None and oc.status == "em_analise"


def test_exclusao_do_item_acompanha_a_ocorrencia(cliente):
    oc = servicos.criar_ocorrencia(cliente, dados_produtos("avaria"), [foto()]).dados["ocorrencia"]
    oc.delete()
    assert not OcorrenciaItem.objects.exists()
    assert not Anexo.objects.exists()
