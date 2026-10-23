"""
Cria dados de demonstração para desenvolvimento local:
empresas, usuários (admin, operador, clientes) e algumas ocorrências.

    python manage.py popular_demo

Todos os usuários de demonstração usam a senha SENHA_DEMO abaixo.
NÃO rode em produção.
"""

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from contas.models import Empresa, Papel, Usuario
from ocorrencias import servicos
from ocorrencias.models import Aviso, Ocorrencia

SENHA_DEMO = "demo12345"


class Command(BaseCommand):
    help = "Popula o banco com dados de demonstração (desenvolvimento)."

    def _usuario(self, email, nome, papel=Papel.CLIENTE, **extra):
        user, criado = Usuario.objects.get_or_create(
            email=email, defaults={"nome": nome, "papel": papel, "ativado_em": timezone.now(), **extra}
        )
        if criado:
            user.set_password(SENHA_DEMO)
            user.is_staff = papel == Papel.ADMIN
            user.is_superuser = papel == Papel.ADMIN
            user.save()
        return user

    def handle(self, *args, **options):
        acme, _ = Empresa.objects.get_or_create(nome="ACME Distribuidora", defaults={"cnpj": "12.345.678/0001-90"})
        globex, _ = Empresa.objects.get_or_create(nome="Globex Varejo")

        admin = self._usuario("admin@demo.local", "Alice Admin", Papel.ADMIN)
        operador = self._usuario("operador@demo.local", "Otto Operador", Papel.OPERADOR)
        ana = self._usuario("ana@acme.local", "Ana Souza", empresa=acme, documento="123.456.789-00", tipo_pessoa="pf")
        bruno = self._usuario("bruno@acme.local", "Bruno Lima", empresa=acme)
        self._usuario("carla@globex.local", "Carla Dias", empresa=globex)

        if not Ocorrencia.objects.exists():
            itens = [
                {"categoria": "falta", "codigo": "001", "descricao": "Camisa azul", "quantidade": 10},
                {"categoria": "sobra", "codigo": "002", "descricao": "Caneca", "quantidade": 3},
            ]
            servicos.criar_ocorrencia(
                ana,
                {"tipo": "produtos", "referencia_tipo": "nf", "referencia": "45120", "itens_json": json.dumps(itens)},
                [],
            )
            oc = servicos.criar_ocorrencia(
                ana,
                {
                    "tipo": "atraso",
                    "referencia_tipo": "pedido",
                    "referencia": "9981",
                    "descricao": "Pedido previsto para segunda e ainda não chegou.",
                },
                [],
            ).dados["ocorrencia"]
            servicos.adicionar_mensagem(operador, oc, "Olá! Já acionamos a transportadora.", False, [])
            servicos.adicionar_mensagem(operador, oc, "Transportadora prometeu entrega amanhã.", True, [])
            servicos.atualizar_ocorrencia(
                operador, oc, {"status": "resolvida", "prioridade": "alta", "atribuido_a": str(operador.pk)}
            )
            servicos.criar_ocorrencia(
                bruno,
                {"tipo": "reclamacao_sugestao", "descricao": "Sugestão: avisar por e-mail quando sair para entrega."},
                [],
            )

        if not Aviso.objects.exists():
            Aviso.objects.create(
                titulo="Feriado na sexta", mensagem="Não haverá coletas nem entregas na sexta-feira.", tipo="alerta"
            )
            Aviso.objects.create(
                titulo="Novo portal", mensagem="Novo visual: escolha o assunto e siga as etapas.", tipo="info"
            )

        self.stdout.write(self.style.SUCCESS("Dados de demonstração prontos."))
        self.stdout.write(f"Senha de todos os usuários: {SENHA_DEMO}")
        for u in (admin, operador, ana, bruno):
            self.stdout.write(f"  {u.get_papel_display():9} {u.email}")
