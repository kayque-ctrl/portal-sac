"""
Links de acesso de uso único (convite e redefinição de senha).

Usa o gerador de tokens do Django: o token embute o hash da senha e o
last_login, então deixa de valer assim que o usuário entra pelo link (o
login atualiza last_login) ou troca a senha.
"""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from ocorrencias.emails import botao_email, enviar_email, layout_email

from .models import Usuario


def gerar_link(user: Usuario) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.SITE_URL}/auth/confirm?uid={uid}&token={token}&next=/definir-senha"


def usuario_do_token(uid: str, token: str) -> Usuario | None:
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        user = Usuario.objects.get(pk=pk, is_active=True)
    except (TypeError, ValueError, OverflowError, ValidationError, Usuario.DoesNotExist):
        return None
    return user if default_token_generator.check_token(user, token) else None


def enviar_link_de_acesso(user: Usuario, *, titulo: str, intro: str, texto_botao: str, assunto: str) -> bool:
    """Envia o link por e-mail. Retorna True se o e-mail saiu de fato."""
    html = layout_email(titulo, f"<p>{intro}</p>{botao_email(gerar_link(user), texto_botao)}")
    return enviar_email(user.email, assunto, html)


def enviar_convite(user: Usuario) -> bool:
    return enviar_link_de_acesso(
        user,
        titulo="Você foi convidado",
        intro="Você foi convidado para o Portal de Ocorrências. Clique no botão abaixo para definir sua senha e acessar:",
        texto_botao="Aceitar convite e definir senha",
        assunto="Você foi convidado — Portal de Ocorrências",
    )


def reenviar_convite(user: Usuario) -> bool:
    return enviar_link_de_acesso(
        user,
        titulo="Seu convite para o Portal de Ocorrências",
        intro="Aqui está um novo link para você definir sua senha e acessar o Portal de Ocorrências:",
        texto_botao="Definir senha e acessar",
        assunto="Convite (reenvio) — Portal de Ocorrências",
    )


def enviar_redefinicao(user: Usuario) -> bool:
    return enviar_link_de_acesso(
        user,
        titulo="Redefinir senha",
        intro="Recebemos um pedido para redefinir sua senha no Portal de Ocorrências. "
        "Clique no botão abaixo para escolher uma nova senha:</p><p>Se você não pediu isso, pode ignorar este e-mail.",
        texto_botao="Redefinir senha",
        assunto="Redefinir senha — Portal de Ocorrências",
    )
