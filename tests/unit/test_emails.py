"""E-mail best-effort (emails.py): nunca lança exceção."""

from unittest import mock

from django.core import mail

from ocorrencias import emails


def test_sem_destinatario_nao_envia():
    assert emails.enviar_email("", "assunto", "<p>x</p>") is False
    assert mail.outbox == []


def test_sem_smtp_envia_para_o_console_e_devolve_false(settings):
    settings.SMTP_CONFIGURADO = False
    assert emails.enviar_email("a@x.com", "assunto", "<p>x</p>") is False
    assert mail.outbox[0].subject == "assunto"
    assert mail.outbox[0].content_subtype == "html"


def test_com_smtp_devolve_true(settings):
    settings.SMTP_CONFIGURADO = True
    assert emails.enviar_email("a@x.com", "assunto", "<p>x</p>") is True


def test_erro_de_envio_nao_quebra_o_fluxo():
    with mock.patch("ocorrencias.emails.EmailMessage.send", side_effect=OSError("smtp fora do ar")):
        assert emails.enviar_email("a@x.com", "assunto", "<p>x</p>") is False


def test_layout_escapa_o_titulo_e_monta_o_link(settings):
    settings.SITE_URL = "https://portal.exemplo.com"

    html = emails.layout_email("<b>Oi</b>", "<p>corpo</p>", "/portal/1")

    assert "&lt;b&gt;Oi&lt;/b&gt;" in html
    assert 'href="https://portal.exemplo.com/portal/1"' in html


def test_layout_sem_cta_nao_tem_botao():
    assert "Ver no portal" not in emails.layout_email("t", "c")
