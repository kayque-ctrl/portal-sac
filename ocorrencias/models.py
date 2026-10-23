"""
Modelos do domínio.

No projeto original boa parte das regras vivia em triggers do Postgres
(protocolo, SLA, histórico de status, notificações). Aqui elas ficam no
`save()` dos modelos, para valer em qualquer caminho de escrita da aplicação
(views, admin, shell). Por isso: NÃO altere `status` com `QuerySet.update()`
— use `ocorrencia.save(por=usuario)`.
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from .labels import (
    STATUS_ATIVOS,
    AvisoTipo,
    EventoTipo,
    ItemCategoria,
    OcorrenciaTipo,
    Prioridade,
    ReferenciaTipo,
    SinalVolume,
    Status,
)


class ProtocoloSeq(models.Model):
    """Contador único do protocolo (substitui a sequence protocolo_seq)."""

    valor = models.BigIntegerField(default=0)

    @classmethod
    def proximo(cls) -> int:
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(pk=1)
            cls.objects.filter(pk=1).update(valor=F("valor") + 1)
            seq.refresh_from_db()
            return seq.valor


class SlaRegra(models.Model):
    """
    Prazo (horas) por empresa, categoria e/ou prioridade. Nulo = qualquer;
    empresa nula = padrão de todas as empresas (spec 026).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        "contas.Empresa", on_delete=models.CASCADE, null=True, blank=True, related_name="regras_sla"
    )
    categoria = models.CharField(max_length=24, choices=OcorrenciaTipo.choices, null=True, blank=True)
    prioridade = models.CharField(max_length=8, choices=Prioridade.choices, null=True, blank=True)
    horas = models.PositiveIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "regra de SLA"
        verbose_name_plural = "regras de SLA"

    def __str__(self) -> str:
        base = f"{self.categoria or 'qualquer'} / {self.prioridade or 'qualquer'}: {self.horas} h"
        return f"{self.empresa} / {base}" if self.empresa_id else base

    @staticmethod
    def horas_para(tipo: str, prioridade: str, empresa_id=None) -> int | None:
        """
        Regra mais específica vence: a da empresa pesa mais que o padrão,
        depois a prioridade, depois a categoria (spec 026).
        """
        candidatas = SlaRegra.objects.filter(
            models.Q(empresa_id=empresa_id) | models.Q(empresa__isnull=True),
            models.Q(categoria=tipo) | models.Q(categoria__isnull=True),
            models.Q(prioridade=prioridade) | models.Q(prioridade__isnull=True),
        )
        melhor = sorted(
            candidatas,
            key=lambda r: (r.empresa_id is not None, r.prioridade is not None, r.categoria is not None),
            reverse=True,
        )
        return melhor[0].horas if melhor else None


# Campos cuja mudança vira evento na linha do tempo (spec 021).
CAMPOS_COM_EVENTO = ("atribuido_a_id", "prioridade", "arquivada_em", "excluida_em")


class Ocorrencia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    protocolo = models.CharField(max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ocorrencias")
    tipo = models.CharField(max_length=24, choices=OcorrenciaTipo.choices)
    titulo = models.CharField(max_length=200, null=True, blank=True)
    descricao = models.TextField(blank=True, default="")
    referencia = models.CharField(max_length=80, null=True, blank=True)
    referencia_tipo = models.CharField(max_length=8, choices=ReferenciaTipo.choices, null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTA, db_index=True)
    prioridade = models.CharField(max_length=8, choices=Prioridade.choices, default=Prioridade.MEDIA)
    atribuido_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_atribuidas",
    )
    motivo_recusa = models.TextField(null=True, blank=True)
    aprovada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_aprovadas",
    )
    aprovada_em = models.DateTimeField(null=True, blank=True)

    # SLA: mantidos pelo save() (antes: triggers sla_ao_criar / sla_ao_atualizar).
    sla_horas = models.PositiveIntegerField(null=True, blank=True)
    sla_prazo = models.DateTimeField(null=True, blank=True)
    sla_restante_ms = models.BigIntegerField(null=True, blank=True)
    sla_cumprido = models.BooleanField(null=True, blank=True)

    criado_em = models.DateTimeField(default=timezone.now, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    arquivada_em = models.DateTimeField(null=True, blank=True, db_index=True)
    excluida_em = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "ocorrência"
        indexes = [models.Index(fields=["status", "arquivada_em", "excluida_em"])]

    def __str__(self) -> str:
        return self.protocolo

    # ----- rastreio do status anterior (para detectar mudanças no save) -----

    @classmethod
    def from_db(cls, db, field_names, values, **kwargs):
        # **kwargs repassa o `fetch_mode` que o Django 6.1+ passa a enviar.
        obj = super().from_db(db, field_names, values, **kwargs)
        obj._status_original = obj.__dict__.get("status")
        obj._originais = {c: obj.__dict__.get(c) for c in CAMPOS_COM_EVENTO}
        return obj

    @property
    def status_original(self) -> str | None:
        return getattr(self, "_status_original", None)

    # ----- regras que eram triggers -----

    def _sla_ao_criar(self, agora):
        self.sla_horas = SlaRegra.horas_para(self.tipo, self.prioridade, self.cliente.empresa_id)
        if self.sla_horas is not None:
            self.sla_prazo = agora + timedelta(hours=self.sla_horas)

    def _sla_ao_atualizar(self, de: str, agora):
        """
        Ajusta o relógio nas trocas de status:
          ativo → aguardando cliente: pausa (guarda o tempo restante)
          aguardando cliente → ativo: retoma
          → concluída/recusada: marca se cumpriu
          reabertura de terminal → ativo: reinicia o prazo
        """
        para = self.status
        ativo_de = de in STATUS_ATIVOS
        ativo_para = para in STATUS_ATIVOS

        if ativo_de and para == Status.RESOLVIDA:
            if self.sla_prazo is not None:
                restante = (self.sla_prazo - agora).total_seconds() * 1000
                self.sla_restante_ms = max(0, int(restante))
            self.sla_prazo = None
        elif de == Status.RESOLVIDA and ativo_para:
            if self.sla_restante_ms is not None:
                self.sla_prazo = agora + timedelta(milliseconds=self.sla_restante_ms)
            elif self.sla_horas is not None:
                self.sla_prazo = agora + timedelta(hours=self.sla_horas)
            self.sla_restante_ms = None
        elif para in (Status.CONCLUIDA, Status.RECUSADA):
            if de == Status.RESOLVIDA:
                self.sla_cumprido = (self.sla_restante_ms or 0) > 0
            else:
                self.sla_cumprido = self.sla_prazo is not None and agora <= self.sla_prazo
        elif de in (Status.CONCLUIDA, Status.RECUSADA) and ativo_para:
            self.sla_cumprido = None
            self.sla_restante_ms = None
            if self.sla_horas is not None:
                self.sla_prazo = agora + timedelta(hours=self.sla_horas)

    def save(self, *args, por=None, observacao=None, **kwargs):
        """
        `por` = quem fez a alteração (antes: auth.uid() nos triggers).
        `observacao` = texto da troca de status (ex.: resumo da resolução, spec 025).
        """
        from . import notificacoes

        agora = timezone.now()
        criando = self._state.adding
        de = self.status_original
        mudou_status = not criando and de is not None and de != self.status

        if criando:
            if not self.protocolo:
                self.protocolo = f"{timezone.localtime(agora).year}-{ProtocoloSeq.proximo():06d}"
            self._sla_ao_criar(agora)
        elif mudou_status:
            self._sla_ao_atualizar(de, agora)

        with transaction.atomic():
            super().save(*args, **kwargs)

            if criando:
                HistoricoStatus.objects.create(
                    ocorrencia=self, de_status=None, para_status=self.status, alterado_por=self.cliente
                )
                notificacoes.nova_ocorrencia(self)
            elif mudou_status:
                HistoricoStatus.objects.create(
                    ocorrencia=self, de_status=de, para_status=self.status, alterado_por=por, observacao=observacao
                )
                notificacoes.mudanca_status(self, por)
            if not criando:
                self._registrar_eventos(por)

        self._status_original = self.status
        self._originais = {c: self.__dict__.get(c) for c in CAMPOS_COM_EVENTO}

    def _registrar_eventos(self, por):
        """Responsável, prioridade e ciclo de vida viram eventos (spec 021)."""
        antes = getattr(self, "_originais", None)
        if antes is None:  # instância que não veio do banco: nada a comparar
            return
        eventos = []

        if antes["atribuido_a_id"] != self.atribuido_a_id:
            from contas.models import Usuario

            nomes = dict(
                Usuario.objects.filter(pk__in=[antes["atribuido_a_id"], self.atribuido_a_id]).values_list("pk", "nome")
            )
            eventos.append((EventoTipo.RESPONSAVEL, nomes.get(antes["atribuido_a_id"]), nomes.get(self.atribuido_a_id)))
        if antes["prioridade"] != self.prioridade:
            eventos.append((EventoTipo.PRIORIDADE, antes["prioridade"], self.prioridade))
        if (antes["arquivada_em"] is None) != (self.arquivada_em is None):
            eventos.append((EventoTipo.ARQUIVADA if self.arquivada_em else EventoTipo.DESARQUIVADA, None, None))
        if (antes["excluida_em"] is None) != (self.excluida_em is None):
            eventos.append((EventoTipo.EXCLUIDA if self.excluida_em else EventoTipo.RESTAURADA, None, None))

        EventoOcorrencia.objects.bulk_create(
            [EventoOcorrencia(ocorrencia=self, tipo=t, de=de, para=para, autor=por) for t, de, para in eventos]
        )

    # ----- utilidades de exibição -----

    @property
    def bloqueada(self) -> bool:
        return self.status in (Status.RESOLVIDA, Status.CONCLUIDA, Status.RECUSADA)

    @property
    def referencia_formatada(self) -> str:
        from .labels import formatar_referencia

        return formatar_referencia(self.referencia_tipo, self.referencia)


class OcorrenciaItem(models.Model):
    """Produto lançado numa ocorrência do tipo "produtos"."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ocorrencia = models.ForeignKey(Ocorrencia, on_delete=models.CASCADE, related_name="itens")
    categoria = models.CharField(max_length=14, choices=ItemCategoria.choices, null=True, blank=True)
    codigo = models.CharField(max_length=80, blank=True, default="")
    descricao = models.CharField(max_length=300)
    quantidade = models.PositiveIntegerField()
    # Só na troca de volume: o volume falta ou sobra (spec 004). Nulo nas demais
    # categorias e nos itens lançados antes desta regra.
    sinal_volume = models.CharField(max_length=5, choices=SinalVolume.choices, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]
        verbose_name = "item da ocorrência"
        verbose_name_plural = "itens da ocorrência"

    def __str__(self) -> str:
        return f"{self.descricao} ({self.quantidade})"

    @property
    def sinal(self) -> str:
        """neg / pos / neutro, para o sinal e a cor da quantidade."""
        from .labels import sinal_item

        return sinal_item(self.categoria, self.sinal_volume)

    @property
    def rotulo_categoria(self) -> str:
        from .labels import rotulo_item

        return rotulo_item(self.categoria, self.sinal_volume)


class Mensagem(models.Model):
    """Conversa entre cliente e operação. `interna` = só a operação vê."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ocorrencia = models.ForeignKey(Ocorrencia, on_delete=models.CASCADE, related_name="mensagens")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mensagens")
    conteudo = models.TextField(blank=True, default="")
    interna = models.BooleanField(default=False)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["criado_em"]
        verbose_name_plural = "mensagens"

    def save(self, *args, **kwargs):
        from . import notificacoes

        criando = self._state.adding
        super().save(*args, **kwargs)
        if criando and not self.interna:
            notificacoes.nova_mensagem(self)


def caminho_anexo(instance: Anexo, filename: str) -> str:
    from .uploads import sanitizar_nome

    return f"anexos/{instance.ocorrencia_id}/{uuid.uuid4()}-{sanitizar_nome(filename)}"


class Anexo(models.Model):
    """Arquivo da ocorrência (abertura) ou de uma mensagem da conversa."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ocorrencia = models.ForeignKey(Ocorrencia, on_delete=models.CASCADE, related_name="anexos")
    mensagem = models.ForeignKey(Mensagem, on_delete=models.SET_NULL, null=True, blank=True, related_name="anexos")
    arquivo = models.FileField(upload_to=caminho_anexo, max_length=300)
    nome_arquivo = models.CharField(max_length=255)
    tipo_mime = models.CharField(max_length=120, blank=True, null=True)
    tamanho_bytes = models.BigIntegerField(null=True, blank=True)
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]

    def __str__(self) -> str:
        return self.nome_arquivo


class HistoricoStatus(models.Model):
    """Auditoria das trocas de status (alimenta a consulta pública e os KPIs)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ocorrencia = models.ForeignKey(Ocorrencia, on_delete=models.CASCADE, related_name="historico")
    de_status = models.CharField(max_length=12, choices=Status.choices, null=True, blank=True)
    para_status = models.CharField(max_length=12, choices=Status.choices)
    alterado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Ao ir para "Aguardando aprovação": o resumo da resolução, que o cliente vê (spec 025).
    observacao = models.TextField(null=True, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["criado_em"]
        verbose_name = "histórico de status"
        verbose_name_plural = "históricos de status"


class EventoOcorrencia(models.Model):
    """
    O que acontece na ocorrência além das mensagens e do status (spec 021):
    troca de responsável e de prioridade, arquivamento e lixeira. Gravado pelo
    `Ocorrencia.save(por=...)`. Só a operação vê. `autor` nulo = o sistema
    (ex.: arquivamento automático).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ocorrencia = models.ForeignKey(Ocorrencia, on_delete=models.CASCADE, related_name="eventos")
    tipo = models.CharField(max_length=14, choices=EventoTipo.choices)
    de = models.CharField(max_length=200, null=True, blank=True)
    para = models.CharField(max_length=200, null=True, blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["criado_em"]
        verbose_name = "evento da ocorrência"
        verbose_name_plural = "eventos da ocorrência"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} ({self.criado_em:%d/%m %H:%M})"


class Notificacao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificacoes")
    ocorrencia = models.ForeignKey(
        Ocorrencia, on_delete=models.CASCADE, null=True, blank=True, related_name="notificacoes"
    )
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "notificação"
        verbose_name_plural = "notificações"
        indexes = [models.Index(fields=["destinatario", "lida", "-criado_em"])]


class Aviso(models.Model):
    """Aviso da operação exibido no topo do portal do cliente."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=60)
    mensagem = models.CharField(max_length=160)
    tipo = models.CharField(max_length=8, choices=AvisoTipo.choices, default=AvisoTipo.INFO)
    ativo = models.BooleanField(default=True, db_index=True)
    # Fim da validade. Nulo = vale até a operação desativar.
    expira_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.titulo

    @property
    def expirado(self) -> bool:
        return self.expira_em is not None and self.expira_em < timezone.now()

    @classmethod
    def vigentes(cls):
        """Ativos e dentro da validade (o que o cliente vê)."""
        return cls.objects.filter(ativo=True).filter(
            models.Q(expira_em__isnull=True) | models.Q(expira_em__gt=timezone.now())
        )


class ContatoEncaminhamento(models.Model):
    """E-mails avisados quando uma reclamação/sugestão é aberta."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    setor = models.CharField(max_length=100, null=True, blank=True)
    ativo = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "contato de encaminhamento"
        verbose_name_plural = "contatos de encaminhamento"

    def __str__(self) -> str:
        return self.email


class Transportadora(models.Model):
    """
    Transportadora que faz as coletas (spec 025). Ligada às empresas que ela
    atende, para a coleta já sugerir o e-mail certo.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=120)
    email = models.EmailField()
    telefone = models.CharField(max_length=40, null=True, blank=True)
    ativa = models.BooleanField(default=True, db_index=True)
    empresas = models.ManyToManyField("contas.Empresa", blank=True, related_name="transportadoras")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome
