import json

from django.core.files.uploadedfile import SimpleUploadedFile

from contas.models import Empresa, Papel, Usuario

# Menor PNG válido (1x1) — passa na checagem de magic bytes.
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def foto(nome="foto.png"):
    return SimpleUploadedFile(nome, PNG_1X1, content_type="image/png")


class Fabrica:
    """Cria o elenco padrão dos testes."""

    def criar_elenco(self):
        self.empresa = Empresa.objects.create(nome="ACME")
        self.outra_empresa = Empresa.objects.create(nome="Globex")
        self.cliente = Usuario.objects.create_user(
            "cliente@acme.com", "senha-forte-1", nome="Ana Cliente", empresa=self.empresa, documento="123.456.789-00"
        )
        self.colega = Usuario.objects.create_user(
            "colega@acme.com", "senha-forte-1", nome="Bruno Colega", empresa=self.empresa
        )
        self.estranho = Usuario.objects.create_user(
            "x@globex.com", "senha-forte-1", nome="Carla Globex", empresa=self.outra_empresa
        )
        self.operador = Usuario.objects.create_user(
            "op@empresa.com", "senha-forte-1", nome="Otto Operador", papel=Papel.OPERADOR
        )
        self.admin = Usuario.objects.create_user(
            "admin@empresa.com", "senha-forte-1", nome="Alice Admin", papel=Papel.ADMIN
        )

    def dados_produtos(self, categoria="falta", **extra):
        itens = [{"categoria": categoria, "codigo": "001", "descricao": "Camisa", "quantidade": 2}]
        return {
            "tipo": "produtos",
            "referencia_tipo": "nf",
            "referencia": "12345",
            "descricao": "",
            "itens_json": json.dumps(itens),
            **extra,
        }

    def dados_atraso(self, **extra):
        return {
            "tipo": "atraso",
            "referencia_tipo": "pedido",
            "referencia": "987",
            "descricao": "A entrega atrasou três dias.",
            **extra,
        }
