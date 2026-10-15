"""Port de src/lib/kpis-cliente.test.ts (lógica pura do dashboard do cliente)."""

from datetime import datetime, timezone

from django.test import SimpleTestCase

from ocorrencias.kpis import (
    MIN_AMOSTRA,
    barras_motivos,
    barras_semanas,
    formatar_duracao,
    parse_periodo,
    percentual_sla,
    rotulo_idade,
    sem_dados,
    sub_sla,
    tom_sla,
    valor_tempo_medio,
    variacao_tempo,
)


class KpisPurosTests(SimpleTestCase):
    def test_parse_periodo_aceita_7_30_90(self):
        self.assertEqual(parse_periodo("7"), 7)
        self.assertEqual(parse_periodo("90"), 90)
        self.assertEqual(parse_periodo("15"), 30)
        self.assertEqual(parse_periodo(None), 30)
        self.assertEqual(parse_periodo("abc"), 30)

    def test_formatar_duracao(self):
        self.assertEqual(formatar_duracao(None), "—")
        self.assertEqual(formatar_duracao(0.5), "30 min")
        self.assertEqual(formatar_duracao(0), "1 min")
        self.assertEqual(formatar_duracao(5.25), "5,3 h")
        self.assertEqual(formatar_duracao(30), "30 h")
        self.assertEqual(formatar_duracao(48), "2,0 d")
        self.assertEqual(formatar_duracao(72), "3,0 d")

    def test_tempo_medio_com_amostra_pequena(self):
        self.assertEqual(valor_tempo_medio(48, MIN_AMOSTRA - 1), "—")
        self.assertEqual(valor_tempo_medio(48, MIN_AMOSTRA), "2,0 d")
        self.assertEqual(valor_tempo_medio(None, 10), "—")

    def test_variacao_menor_e_melhor(self):
        self.assertEqual(variacao_tempo(24, 48, 10), {"texto": "24 h melhor que antes", "tom": "bom"})
        self.assertEqual(variacao_tempo(120, 48, 10), {"texto": "3,0 d pior que antes", "tom": "ruim"})
        self.assertEqual(variacao_tempo(48.2, 48, 10)["tom"], "neutro")
        self.assertIsNone(variacao_tempo(24, None, 10))
        self.assertIsNone(variacao_tempo(24, 48, 2))

    def test_sla_percentual_e_textos(self):
        self.assertIsNone(percentual_sla(3, 4))
        self.assertEqual(percentual_sla(18, 21), 86)
        self.assertEqual(percentual_sla(5, 5), 100)
        self.assertEqual(sub_sla(0, 0), "sem encerradas no período")
        self.assertEqual(sub_sla(1, 2), "só 2 encerradas no período")
        self.assertEqual(sub_sla(1, 1), "só 1 encerrada no período")
        self.assertEqual(sub_sla(18, 21), "18 de 21 no prazo")

    def test_tom_sla(self):
        self.assertEqual(tom_sla(None), "neutro")
        self.assertEqual(tom_sla(95), "bom")
        self.assertEqual(tom_sla(80), "alerta")
        self.assertEqual(tom_sla(60), "ruim")

    def test_barras_motivos(self):
        motivos = [
            {"categoria": "falta", "ocorrencias": 1, "itens": 2},
            {"categoria": "avaria", "ocorrencias": 2, "itens": 6},
            {"categoria": "sobra", "ocorrencias": 0, "itens": 0},
        ]
        por_oc = barras_motivos(motivos, "ocorrencias")
        self.assertEqual([(b["categoria"], b["valor"], b["pct"]) for b in por_oc], [("avaria", 2, 100), ("falta", 1, 50)])
        por_item = barras_motivos(motivos, "itens")
        self.assertEqual(por_item[0]["categoria"], "avaria")
        self.assertEqual(por_item[1]["pct"], 33)
        self.assertEqual(barras_motivos([], "itens"), [])

    def test_barras_semanas(self):
        b = barras_semanas(
            [
                {"semana": "2026-09-07", "total": 2},
                {"semana": "2026-09-14", "total": 4},
                {"semana": "2026-09-21", "total": 0},
            ]
        )
        self.assertEqual([(x["rotulo"], x["total"], x["pct"]) for x in b], [("07/09", 2, 50), ("14/09", 4, 100), ("21/09", 0, 0)])
        self.assertEqual(barras_semanas([{"semana": "2026-09-07", "total": 0}])[0]["pct"], 0)

    def test_rotulo_idade(self):
        agora = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)
        self.assertEqual(rotulo_idade(datetime(2026, 9, 21, 11, 40, tzinfo=timezone.utc), agora), "agora")
        self.assertEqual(rotulo_idade(datetime(2026, 9, 21, 7, tzinfo=timezone.utc), agora), "5 h")
        self.assertEqual(rotulo_idade(datetime(2026, 9, 15, 12, tzinfo=timezone.utc), agora), "6 d")

    def test_sem_dados(self):
        vazio = {
            "em_aberto": 0,
            "aguardando_aprovacao": 0,
            "novas_no_periodo": 0,
            "resolvidas_no_periodo": 0,
            "sla_encerradas": 0,
        }
        self.assertTrue(sem_dados(vazio))
        self.assertFalse(sem_dados({**vazio, "em_aberto": 1}))
        self.assertFalse(sem_dados({**vazio, "sla_encerradas": 1}))
