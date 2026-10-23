"""
Dashboard do cliente: cálculo dos KPIs (antes: função SQL kpis_cliente) e a
lógica pura de apresentação (antes: src/lib/kpis-cliente.ts).

Os números respeitam a mesma visibilidade das telas: o cliente só enxerga
ocorrências dele e dos colegas da mesma empresa.
"""

import math
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Max, Min, Sum
from django.utils import timezone

from .formato import js_round
from .labels import STATUS_ATIVOS
from .models import HistoricoStatus, OcorrenciaItem
from .permissoes import colegas_da_empresa, ocorrencias_visiveis

PERIODOS = [7, 30, 90]

# Abaixo disso, tempo médio e SLA mostram "—" (percentual enganoso).
MIN_AMOSTRA = 5


def _decimal(n: float, casas: int = 1) -> str:
    """Equivale a n.toFixed(casas) com vírgula decimal."""
    q = Decimal(1).scaleb(-casas)
    return str(Decimal(n).quantize(q, rounding=ROUND_HALF_UP)).replace(".", ",")


# ---------------------------------------------------------------- lógica pura


def parse_periodo(v) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 30
    return n if n in PERIODOS else 30


def formatar_duracao(horas) -> str:
    """0,5 → "30 min" · 5,2 → "5,2 h" · 30 → "30 h" · 72 → "3,0 d"."""
    if horas is None or not math.isfinite(horas):
        return "—"
    if horas < 1:
        return f"{max(1, js_round(horas * 60))} min"
    if horas < 10:
        return f"{_decimal(horas)} h"
    if horas < 48:
        return f"{js_round(horas)} h"
    return f"{_decimal(horas / 24)} d"


def valor_tempo_medio(horas, resolvidas: int) -> str:
    if resolvidas < MIN_AMOSTRA:
        return "—"
    return formatar_duracao(horas)


def variacao_tempo(atual, anterior, resolvidas: int):
    """Variação do tempo médio vs. período anterior (menor é melhor)."""
    if resolvidas < MIN_AMOSTRA or atual is None or anterior is None:
        return None
    diff = atual - anterior
    if abs(diff) < 0.5:
        return {"texto": "igual ao período anterior", "tom": "neutro"}
    if diff < 0:
        return {"texto": f"{formatar_duracao(-diff)} melhor que antes", "tom": "bom"}
    return {"texto": f"{formatar_duracao(diff)} pior que antes", "tom": "ruim"}


def percentual_sla(cumpridas: int, encerradas: int):
    if encerradas < MIN_AMOSTRA:
        return None
    return js_round(cumpridas / encerradas * 100)


def sub_sla(cumpridas: int, encerradas: int) -> str:
    if encerradas < MIN_AMOSTRA:
        if encerradas == 0:
            return "sem encerradas no período"
        return f"só {encerradas} encerrada{'s' if encerradas > 1 else ''} no período"
    return f"{cumpridas} de {encerradas} no prazo"


def tom_sla(pct) -> str:
    if pct is None:
        return "neutro"
    if pct >= 90:
        return "bom"
    if pct >= 75:
        return "alerta"
    return "ruim"


def barras_motivos(motivos: list[dict], modo: str) -> list[dict]:
    linhas = sorted(
        ({"categoria": m["categoria"], "valor": m[modo]} for m in motivos if m[modo] > 0),
        key=lambda m: m["valor"],
        reverse=True,
    )
    maximo = linhas[0]["valor"] if linhas else 0
    return [{**linha, "pct": max(4, js_round(linha["valor"] / maximo * 100)) if maximo > 0 else 0} for linha in linhas]


def barras_semanas(semanas: list[dict]) -> list[dict]:
    maximo = max([0] + [s["total"] for s in semanas])
    saida = []
    for s in semanas:
        _, mm, dd = s["semana"].split("-")
        saida.append(
            {
                "rotulo": f"{dd}/{mm}",
                "total": s["total"],
                "pct": js_round(s["total"] / maximo * 100) if maximo > 0 else 0,
            }
        )
    return saida


def rotulo_idade(criado_em: datetime, agora: datetime) -> str:
    """Idade curta: "agora", "5 h", "6 d"."""
    h = max(0.0, (agora - criado_em).total_seconds() / 3600)
    if h < 1:
        return "agora"
    if h < 48:
        return f"{js_round(h)} h"
    return f"{js_round(h / 24)} d"


def sem_dados(k: dict) -> bool:
    """A empresa ainda não tem ocorrências no escopo."""
    return (
        k["em_aberto"]
        + k["aguardando_aprovacao"]
        + k["novas_no_periodo"]
        + k["resolvidas_no_periodo"]
        + k["sla_encerradas"]
        == 0
    )


# ---------------------------------------------------------------- cálculo


def _segunda_feira(d) -> datetime.date:
    return d - timedelta(days=d.weekday())


def _media(valores):
    return round(sum(valores) / len(valores), 1) if valores else None


def calcular_kpis(user, dias: int) -> dict:
    dias = max(1, min(dias or 30, 365))
    agora = timezone.now()
    ini = agora - timedelta(days=dias)
    ini_ant = agora - timedelta(days=2 * dias)
    n_semanas = max(4, min(12, math.ceil(dias / 7)))

    base = ocorrencias_visiveis(user).filter(excluida_em__isnull=True)
    ocs = list(
        base.values(
            "id",
            "protocolo",
            "tipo",
            "status",
            "criado_em",
            "cliente_id",
            "sla_horas",
            "sla_prazo",
            "sla_restante_ms",
            "sla_cumprido",
        )
    )
    por_id = {o["id"]: o for o in ocs}
    ids = list(por_id)

    def vencida(o):
        return o["sla_horas"] is not None and o["sla_prazo"] is not None and o["sla_prazo"] < agora

    ativas = [o for o in ocs if o["status"] in STATUS_ATIVOS]

    # 1ª vez que cada ocorrência foi para "Aguardando aprovação" (resolvida).
    primeiras = (
        HistoricoStatus.objects.filter(ocorrencia_id__in=ids, para_status="resolvida")
        .values("ocorrencia_id")
        .annotate(em=Min("criado_em"))
    )
    resolvidas = [
        {"em": p["em"], "horas": (p["em"] - por_id[p["ocorrencia_id"]]["criado_em"]).total_seconds() / 3600}
        for p in primeiras
    ]

    # Encerradas (concluída/recusada) e quando foram encerradas pela última vez.
    ultimas = (
        HistoricoStatus.objects.filter(
            ocorrencia_id__in=[o["id"] for o in ocs if o["status"] in ("concluida", "recusada")],
            para_status__in=["concluida", "recusada"],
        )
        .values("ocorrencia_id")
        .annotate(em=Max("criado_em"))
    )
    encerradas = [{"em": u["em"], "sla_cumprido": por_id[u["ocorrencia_id"]]["sla_cumprido"]} for u in ultimas]

    # Ocorrências por semana (segunda-feira, horário de Brasília).
    seg_atual = _segunda_feira(timezone.localtime(agora).date())
    contagem_semana: dict = {}
    for o in ocs:
        s = _segunda_feira(timezone.localtime(o["criado_em"]).date())
        contagem_semana[s] = contagem_semana.get(s, 0) + 1
    semanas = []
    for i in range(n_semanas - 1, -1, -1):
        s = seg_atual - timedelta(weeks=i)
        semanas.append({"semana": s.isoformat(), "total": contagem_semana.get(s, 0)})

    # Principais motivos (categoria dos produtos) no período.
    motivos = [
        {"categoria": m["categoria"], "ocorrencias": m["ocorrencias"], "itens": m["itens"] or 0}
        for m in OcorrenciaItem.objects.filter(
            ocorrencia_id__in=[o["id"] for o in ocs if o["criado_em"] >= ini], categoria__isnull=False
        )
        .values("categoria")
        .annotate(ocorrencias=Count("ocorrencia_id", distinct=True), itens=Sum("quantidade"))
        .order_by("-ocorrencias", "-itens")
    ]

    # Precisam de atenção: SLA vencido primeiro, depois as mais antigas.
    colegas = colegas_da_empresa(user)
    atencao = []
    for o in sorted(ativas, key=lambda o: (0 if vencida(o) else 1, o["criado_em"]))[:5]:
        atencao.append(
            {
                **o,
                "autor_nome": colegas.get(o["cliente_id"]),
                "eh_minha": o["cliente_id"] == user.pk,
            }
        )

    return {
        "periodo_dias": dias,
        "em_aberto": len(ativas),
        "com_sla_vencido": sum(1 for o in ativas if vencida(o)),
        "aguardando_aprovacao": sum(1 for o in ocs if o["status"] == "resolvida"),
        "aguardando_aprovacao_minhas": sum(1 for o in ocs if o["status"] == "resolvida" and o["cliente_id"] == user.pk),
        "novas_no_periodo": sum(1 for o in ocs if o["criado_em"] >= ini),
        "resolvidas_no_periodo": sum(1 for r in resolvidas if r["em"] >= ini),
        "tempo_medio_horas": _media([r["horas"] for r in resolvidas if r["em"] >= ini]),
        "tempo_medio_horas_anterior": _media([r["horas"] for r in resolvidas if ini_ant <= r["em"] < ini]),
        "sla_encerradas": sum(1 for e in encerradas if e["em"] >= ini and e["sla_cumprido"] is not None),
        "sla_cumpridas": sum(1 for e in encerradas if e["em"] >= ini and e["sla_cumprido"] is True),
        "semanas": semanas,
        "motivos": motivos,
        "atencao": atencao,
    }
