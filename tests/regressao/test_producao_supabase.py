"""Protege: spec 015 (produção na Vercel + Supabase).

- Anexos no bucket privado: a permissão continua sendo conferida antes da URL
  assinada (mesmas regras da spec 012).
- O migrate nunca roda fora do schema `django` (o `public` é exposto pela API).
- A rota do cron só responde com o segredo correto.
- A soma dos anexos respeita o limite da Vercel.
"""

from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from ocorrencias import checks, servicos
from ocorrencias.models import Ocorrencia

from ..builders import foto

URL_ASSINADA = "https://ref.supabase.co/storage/v1/s3/anexos-django/x.png?X-Amz-Signature=abc"


# ---------------------------------------------------------------- anexos remotos


@pytest.fixture
def bucket_remoto(settings):
    settings.ANEXOS_REMOTOS = True
    with mock.patch(
        "django.db.models.fields.files.FieldFile.url", new_callable=mock.PropertyMock, return_value=URL_ASSINADA
    ):
        yield


def test_quem_pode_ver_e_redirecionado_para_a_url_assinada(ocorrencia, colega, entrar, bucket_remoto):
    anexo = ocorrencia.anexos.first()

    r = entrar(colega).get(f"/anexos/{anexo.pk}")

    assert r.status_code == 302
    assert r.url == URL_ASSINADA


def test_outra_empresa_nao_recebe_url_assinada(ocorrencia, estranho, entrar, bucket_remoto):
    r = entrar(estranho).get(f"/anexos/{ocorrencia.anexos.first().pk}")
    assert r.status_code == 404


def test_cliente_nao_recebe_url_de_anexo_de_nota_interna(ocorrencia, operador, cliente, entrar, bucket_remoto):
    servicos.adicionar_mensagem(operador, ocorrencia, "interna", True, [foto("i.png")])
    interno = ocorrencia.anexos.get(mensagem__interna=True)

    assert entrar(cliente).get(f"/anexos/{interno.pk}").status_code == 404
    assert entrar(operador).get(f"/anexos/{interno.pk}").status_code == 302


def test_anonimo_nao_recebe_url_assinada(ocorrencia, client, bucket_remoto):
    r = client.get(f"/anexos/{ocorrencia.anexos.first().pk}")
    assert r.status_code == 302
    assert r.url.startswith("/login")


# ---------------------------------------------------------------- schema


def _conexao(vendor, schema):
    conexao = mock.MagicMock(vendor=vendor)
    conexao.cursor.return_value.__enter__.return_value.fetchone.return_value = (schema,)
    return conexao


def test_check_bloqueia_postgres_fora_do_schema_django(settings):
    settings.DB_SCHEMA = "django"
    with mock.patch.object(checks, "connections", {"default": _conexao("postgresql", "public")}):
        erros = checks.schema_do_banco(None, databases=["default"])

    assert [e.id for e in erros] == ["ocorrencias.E001"]
    assert "'public'" in erros[0].msg


def test_check_bloqueia_schema_inexistente(settings):
    """search_path apontando para um schema que não existe: current_schema() é NULL."""
    with mock.patch.object(checks, "connections", {"default": _conexao("postgresql", None)}):
        assert checks.schema_do_banco(None, databases=["default"])


def test_check_aceita_o_schema_django(settings):
    settings.DB_SCHEMA = "django"
    with mock.patch.object(checks, "connections", {"default": _conexao("postgresql", "django")}):
        assert checks.schema_do_banco(None, databases=["default"]) == []


def test_check_ignora_sqlite_e_quando_nao_ha_banco_para_checar():
    with mock.patch.object(checks, "connections", {"default": _conexao("sqlite", None)}):
        assert checks.schema_do_banco(None, databases=["default"]) == []
    assert checks.schema_do_banco(None, databases=None) == []


# ---------------------------------------------------------------- cron


@pytest.fixture
def encerrada_antiga(abrir, operador):
    from datetime import timedelta

    from django.utils import timezone

    oc = abrir()
    oc.status = "recusada"
    oc.save(por=operador)
    Ocorrencia.objects.filter(pk=oc.pk).update(atualizado_em=timezone.now() - timedelta(days=40))
    return oc


@pytest.mark.parametrize("cabecalho", [None, "Bearer errado", "segredo-do-cron", "Bearer segredo-do-cron "])
def test_cron_sem_o_segredo_correto_e_404(client, settings, encerrada_antiga, cabecalho):
    settings.CRON_SECRET = "segredo-do-cron"
    extra = {"HTTP_AUTHORIZATION": cabecalho} if cabecalho else {}

    assert client.get("/cron/arquivar", **extra).status_code == 404
    encerrada_antiga.refresh_from_db()
    assert encerrada_antiga.arquivada_em is None


def test_cron_desligado_sem_segredo_configurado(client, settings, db):
    settings.CRON_SECRET = ""
    assert client.get("/cron/arquivar", HTTP_AUTHORIZATION="Bearer ").status_code == 404


def test_cron_com_o_segredo_arquiva(client, settings, encerrada_antiga):
    settings.CRON_SECRET = "segredo-do-cron"

    r = client.get("/cron/arquivar", HTTP_AUTHORIZATION="Bearer segredo-do-cron")

    assert r.json() == {"arquivadas": 1}
    encerrada_antiga.refresh_from_db()
    assert encerrada_antiga.arquivada_em is not None


def test_cron_so_aceita_get(client, settings, db):
    settings.CRON_SECRET = "segredo-do-cron"
    assert client.post("/cron/arquivar", HTTP_AUTHORIZATION="Bearer segredo-do-cron").status_code == 405


# ---------------------------------------------------------------- limite de upload


def _arquivo(nome, tamanho):
    a = SimpleUploadedFile(nome, b"%PDF", content_type="application/pdf")
    a.size = tamanho
    return a


def test_soma_dos_anexos_acima_do_limite_e_recusada(settings, cliente, abrir):
    settings.UPLOAD_MAX_TOTAL_BYTES = 4 * 1024 * 1024
    arquivos = [_arquivo("a.pdf", 3 * 1024 * 1024), _arquivo("b.pdf", 2 * 1024 * 1024)]

    r = servicos.adicionar_mensagem(cliente, abrir(), "segue", False, arquivos)

    assert r.erro == "Os anexos somam 5,0 MB; o limite por envio é 4,0 MB. Envie em mais de uma mensagem."


def test_soma_dentro_do_limite_passa(settings, cliente, abrir):
    settings.UPLOAD_MAX_TOTAL_BYTES = 4 * 1024 * 1024
    r = servicos.adicionar_mensagem(cliente, abrir(), "segue", False, [_arquivo("a.pdf", 1024)])
    assert r.ok


def test_formularios_informam_o_limite_ao_navegador(ocorrencia, cliente, entrar, settings):
    settings.UPLOAD_MAX_TOTAL_BYTES = 4 * 1024 * 1024
    http = entrar(cliente)

    for url in ("/portal/nova", f"/portal/{ocorrencia.pk}"):
        html = http.get(url).content.decode()
        assert f'data-anexos-limite="{4 * 1024 * 1024}"' in html
        # A compressão das fotos acontece no componente da lista de anexos (spec 017).
        assert f"listaAnexos({{ max: 5, limite: {4 * 1024 * 1024} }})" in html
        assert "data-erro-upload" in html
