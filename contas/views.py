from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .convites import enviar_redefinicao, usuario_do_token
from .models import Usuario


def login_view(request):
    # Já logado abrindo /login → manda para o roteador pós-login.
    if request.user.is_authenticated:
        return redirect("contas:apos_login")

    erro = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        senha = request.POST.get("password", "")
        if not email or not senha:
            erro = "Preencha e-mail e senha."
        else:
            user = authenticate(request, username=email, password=senha)
            if user is None:
                erro = "E-mail ou senha inválidos."
            else:
                login(request, user)
                return redirect("contas:apos_login")
    elif request.GET.get("erro") == "convite":
        erro = "Link inválido ou expirado. Peça um novo convite à operação."

    return render(request, "contas/login.html", {"erro": erro})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("contas:login")


@login_required
def apos_login(request):
    """Rota de trânsito: decide a área conforme o papel."""
    return redirect("operacao:lista" if request.user.eh_operacao else "portal:inicio")


def esqueci_senha(request):
    ok = erro = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if not email or "@" not in email:
            erro = "Informe um e-mail válido."
        else:
            # Nunca revela se o e-mail existe (evita enumeração de usuários).
            user = Usuario.objects.filter(email=email, is_active=True).first()
            if user:
                enviar_redefinicao(user)
            ok = True
    return render(request, "contas/esqueci_senha.html", {"ok": ok, "erro": erro})


def confirmar_acesso(request):
    """
    O token só é consumido no POST (clique no botão), nunca num GET. Assim
    scanners de e-mail que pré-visitam links (ex.: Safe Links do Outlook) não
    gastam o link de uso único antes do usuário real.
    """
    dados = request.POST if request.method == "POST" else request.GET
    uid, token = dados.get("uid", ""), dados.get("token", "")
    proximo = dados.get("next", "/")
    if not url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}) or not proximo.startswith("/"):
        proximo = "/"

    if not uid or not token:
        return redirect("/login?erro=convite")

    if request.method == "POST":
        user = usuario_do_token(uid, token)
        if user is None:
            return redirect("/login?erro=convite")
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect(proximo)

    return render(request, "contas/confirmar.html", {"uid": uid, "token": token, "next": proximo})


def definir_senha(request):
    erro = None
    if request.method == "POST":
        senha = request.POST.get("senha", "")
        confirma = request.POST.get("confirma", "")
        if len(senha) < 8:
            erro = "A senha precisa ter ao menos 8 caracteres."
        elif senha != confirma:
            erro = "As senhas não conferem."
        elif not request.user.is_authenticated:
            erro = "Link inválido ou expirado. Peça um novo convite à operação."
        else:
            user = request.user
            user.set_password(senha)
            # Marca o perfil como ativo (convite aceito / senha definida).
            if user.ativado_em is None:
                user.ativado_em = timezone.now()
            user.save(update_fields=["password", "ativado_em"])
            update_session_auth_hash(request, user)
            return redirect("contas:apos_login")
    return render(request, "contas/definir_senha.html", {"erro": erro})
