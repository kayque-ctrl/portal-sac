"""Área da operação (/operacao): fila, atendimento, painel e cadastros."""

import re
from collections import Counter
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from contas.convites import enviar_convite, reenviar_convite
from contas.models import Empresa, Papel, TipoPessoa, Usuario

from .. import servicos
from ..apresentacao import linha_do_tempo
from ..labels import (
    AVISO_MENSAGEM_MAX,
    AVISO_TITULO_MAX,
    PRIORIDADE_LABEL,
    STATUS_ATIVOS,
    STATUS_BLOQUEADOS,
    STATUS_ENCERRADOS,
    STATUS_LABEL,
    TIPO_LABEL,
    TIPOS_FORM,
    Prioridade,
)
from ..models import Aviso, ContatoEncaminhamento, Ocorrencia, SlaRegra
from ..planilhas import XLSX_MIME, planilha_ocorrencia, planilha_ocorrencias
from ..servicos import STATUS_OPERACAO
from ..uploads import ACCEPT_ATTR, MAX_ANEXOS
from .comum import admin_required, operacao_required, uuids_validos

PAGE_SIZE = 20

SITUACOES = [
    ("ativas", "Ativas"),
    ("concluidas", "Encerradas"),
    ("arquivadas", "Arquivadas"),
    ("lixeira", "Lixeira"),
]


# Atalhos da aba Ativas (spec 020). "Vencidas" deixa de fora quem aguarda o
# cliente: nesse status o relógio do SLA está pausado.
ATALHOS_FILA = [
    ("", "Todas"),
    ("minhas", "Minhas"),
    ("sem_responsavel", "Sem responsável"),
    ("vencidas", "Vencidas"),
]


def _atalho(qs, chave: str, user):
    if chave == "minhas":
        return qs.filter(atribuido_a=user)
    if chave == "sem_responsavel":
        return qs.filter(atribuido_a__isnull=True)
    if chave == "vencidas":
        return qs.filter(status__in=STATUS_ATIVOS, sla_prazo__lt=timezone.now())
    return qs


def sanitizar_busca(q: str | None) -> str:
    return re.sub(r"[,()%*]", "", (q or "").strip())[:80]


def paginar(request, qs):
    return Paginator(qs, PAGE_SIZE).get_page(request.GET.get("p"))


# ---------------------------------------------------------------- fila


@operacao_required
def lista(request):
    sp = request.GET
    status, tipo = sp.get("status", ""), sp.get("tipo", "")
    empresa = (uuids_validos([sp.get("empresa")]) or [""])[0]
    cliente = (uuids_validos([sp.get("cliente")]) or [""])[0]
    responsavel = (uuids_validos([sp.get("responsavel")]) or [""])[0]
    q = sanitizar_busca(sp.get("q"))

    # Lixeira (exclusão definitiva) é restrita a admin — nem a aba aparece,
    # nem uma URL direta com ?situacao=lixeira funciona para operador.
    situacoes = SITUACOES if request.user.eh_admin else [s for s in SITUACOES if s[0] != "lixeira"]
    situacao = sp.get("situacao") if sp.get("situacao") in dict(situacoes) else "ativas"

    qs = Ocorrencia.objects.select_related("cliente__empresa").order_by("-criado_em")
    if situacao == "lixeira":
        qs = qs.filter(excluida_em__isnull=False)
    else:
        qs = qs.filter(excluida_em__isnull=True)
        if situacao == "arquivadas":
            qs = qs.filter(arquivada_em__isnull=False)
        else:
            qs = qs.filter(arquivada_em__isnull=True)
            qs = qs.filter(status__in=STATUS_ENCERRADOS if situacao == "concluidas" else STATUS_ATIVOS)

    # Opções de status coerentes com a aba atual.
    if situacao == "ativas":
        status_opcoes = STATUS_ATIVOS
    elif situacao == "concluidas":
        status_opcoes = STATUS_ENCERRADOS
    else:
        status_opcoes = list(STATUS_LABEL)

    if status:
        qs = qs.filter(status=status)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if empresa:
        qs = qs.filter(cliente__empresa_id=empresa)
    if cliente:
        qs = qs.filter(cliente_id=cliente)
    if responsavel:
        qs = qs.filter(atribuido_a_id=responsavel)
    if q:
        qs = qs.filter(
            Q(protocolo__icontains=q)
            | Q(descricao__icontains=q)
            | Q(referencia__icontains=q)
            | Q(cliente__nome__icontains=q, cliente__papel=Papel.CLIENTE)
        )

    # Atalhos só fazem sentido entre as ativas; a contagem de cada um respeita
    # os outros filtros já aplicados.
    fila = sp.get("fila", "") if situacao == "ativas" and sp.get("fila") in dict(ATALHOS_FILA) else ""
    atalhos = (
        [{"chave": c, "label": l, "qtd": _atalho(qs, c, request.user).count()} for c, l in ATALHOS_FILA]
        if situacao == "ativas"
        else []
    )
    qs = _atalho(qs, fila, request.user)

    pagina = paginar(request, qs)
    abas = []
    for chave, label in situacoes:
        base = {"q": sp.get("q", ""), "tipo": tipo, "empresa": empresa, "cliente": cliente, "responsavel": responsavel}
        params = {k: v for k, v in base.items() if v}
        params["situacao"] = chave
        abas.append({"chave": chave, "label": label, "params": params})

    escolhidos = Usuario.objects.filter(pk__in=[u for u in (cliente, responsavel) if u])
    nomes = {str(pk): nome for pk, nome in escolhidos.values_list("pk", "nome")}

    return render(
        request,
        "ocorrencias/operacao/lista.html",
        {
            "pagina": pagina,
            "ids_lixeira": [str(o.pk) for o in pagina.object_list] if situacao == "lixeira" else [],
            "situacao": situacao,
            "abas": abas,
            "status": status,
            "tipo": tipo,
            "empresa": empresa,
            "empresa_nome": Empresa.objects.filter(pk=empresa).values_list("nome", flat=True).first() if empresa else None,
            "cliente": cliente,
            "cliente_nome": nomes.get(cliente),
            "responsavel": responsavel,
            "responsavel_nome": nomes.get(responsavel),
            "fila": fila,
            "atalhos": atalhos,
            "q": sp.get("q", ""),
            "tem_filtro": bool(status or tipo or empresa or cliente or responsavel or fila or q),
            "status_opcoes": [(s, STATUS_LABEL[s]) for s in status_opcoes],
            "tipos": list(TIPO_LABEL.items()),
        },
    )


@admin_required
@require_POST
def esvaziar_lixeira(request):
    ids = list(Ocorrencia.objects.filter(excluida_em__isnull=False).values_list("pk", flat=True))
    n = servicos.purgar(ids)
    messages.success(request, f"Lixeira esvaziada ({n} ocorrência(s) excluída(s) definitivamente).")
    return redirect("/operacao/?situacao=lixeira")


@admin_required
@require_POST
def excluir_selecionadas(request):
    # purgar() só apaga as que estão mesmo na lixeira (segurança).
    n = servicos.purgar(uuids_validos(request.POST.getlist("ids")))
    messages.success(request, f"{n} ocorrência(s) excluída(s) definitivamente.")
    return redirect("/operacao/?situacao=lixeira")


# ---------------------------------------------------------------- detalhe


# Abas do atendimento no celular (spec 020), na ordem em que aparecem.
# A abertura agora é o primeiro item da linha do tempo (spec 021).
ABAS_ATENDIMENTO = [("conversa", "Linha do tempo"), ("atender", "Atender")]


def _ocorrencia(pk) -> Ocorrencia:
    return get_object_or_404(Ocorrencia.objects.select_related("cliente__empresa", "aprovada_por__empresa"), pk=pk)


def _render_detalhe(request, oc, **extra):
    mensagens = list(oc.mensagens.select_related("autor"))
    cliente = oc.cliente
    rotulo_cliente = f"{cliente.nome} · {cliente.empresa.nome}" if cliente.empresa_id else cliente.nome
    contexto = {
        "oc": oc,
        "mensagens": mensagens,
        "linha": linha_do_tempo(oc, request.user, mensagens, oc.anexos.all(), rotulo_cliente),
        "itens": list(oc.itens.all()),
        "operadores": Usuario.objects.filter(papel__in=[Papel.OPERADOR, Papel.ADMIN]).order_by("nome"),
        # Já existe mensagem (não interna) da operação ao cliente? Sem isso,
        # o status não pode mudar.
        "tem_tratativa": any(not m.interna and m.autor_id != oc.cliente_id for m in mensagens),
        "status_opcoes": [(s, STATUS_LABEL[s]) for s in (STATUS_OPERACAO if oc.status in STATUS_OPERACAO else [oc.status, *STATUS_OPERACAO])],
        "prioridades": list(PRIORIDADE_LABEL.items()),
        "encerrada": oc.status in STATUS_BLOQUEADOS,
        # Responder ao cliente numa ocorrência "aberta" a move para "em tratativa".
        "avisa_bump": oc.status == "aberta",
        "accept": ACCEPT_ATTR,
        "max_anexos": MAX_ANEXOS,
        "abas_celular": ABAS_ATENDIMENTO,
        **extra,
    }
    return render(request, "ocorrencias/operacao/detalhe.html", contexto)


@operacao_required
def detalhe(request, pk):
    return _render_detalhe(request, _ocorrencia(pk))


@operacao_required
@require_POST
def atualizar(request, pk):
    oc = _ocorrencia(pk)
    r = servicos.atualizar_ocorrencia(request.user, oc, request.POST)
    if not r.ok:
        oc.refresh_from_db()
        return _render_detalhe(request, oc, controles_erro=r.erro)
    messages.success(request, "Alterações salvas.", extra_tags="controles")
    return redirect("operacao:detalhe", pk=oc.pk)


@operacao_required
@require_POST
def enviar_mensagem(request, pk):
    oc = _ocorrencia(pk)
    interna = request.POST.get("interna") == "on"
    r = servicos.adicionar_mensagem(
        request.user, oc, request.POST.get("conteudo", ""), interna, request.FILES.getlist("anexos")
    )
    if not r.ok:
        return _render_detalhe(
            request, oc, msg_erro=r.erro, msg_conteudo=request.POST.get("conteudo", ""), msg_interna=interna
        )
    if r.aviso:
        messages.warning(request, r.aviso, extra_tags="mensagem")
    return redirect("operacao:detalhe", pk=oc.pk)


@operacao_required
@require_POST
def solicitar_coleta(request, pk):
    oc = _ocorrencia(pk)
    r = servicos.solicitar_coleta(request.user, oc, request.POST.get("email_transportadora", ""))
    if not r.ok:
        return _render_detalhe(request, oc, coleta_erro=r.erro)
    messages.success(request, "Solicitação registrada.", extra_tags="coleta")
    return redirect("operacao:detalhe", pk=oc.pk)


@operacao_required
@require_POST
def ciclo_vida(request, pk, acao):
    """Arquivar / desarquivar / reabrir / excluir (lixeira, só admin) / restaurar."""
    oc = _ocorrencia(pk)
    agora = timezone.now()
    if acao == "arquivar":
        oc.arquivada_em = agora
    elif acao == "desarquivar":
        oc.arquivada_em = None
    elif acao == "excluir":
        if not request.user.eh_admin:
            raise Http404
        oc.excluida_em = agora
    elif acao == "restaurar":
        oc.excluida_em = None
    elif acao == "reabrir":
        servicos.reabrir(request.user, oc)
        return redirect("operacao:detalhe", pk=oc.pk)
    else:
        raise Http404
    oc.save(por=request.user)
    return redirect("operacao:detalhe", pk=oc.pk)


@operacao_required
def exportar(request, pk):
    oc = _ocorrencia(pk)
    resp = HttpResponse(planilha_ocorrencia(oc), content_type=XLSX_MIME)
    resp["Content-Disposition"] = f'attachment; filename="ocorrencia-{oc.protocolo}.xlsx"'
    resp["Cache-Control"] = "no-store"
    return resp


@operacao_required
def notificacoes(request):
    lista = list(request.user.notificacoes.order_by("-criado_em")[:50])
    request.user.notificacoes.filter(pk__in=[n.pk for n in lista if not n.lida]).update(lida=True)
    return render(request, "ocorrencias/notificacoes.html", {"notificacoes": lista, "voltar": "/operacao/"})


# ---------------------------------------------------------------- painel


def _filtros_painel(sp) -> dict:
    def data_valida(v):
        return v if v and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else ""

    return {
        "status": sp.get("status", "") if sp.get("status") in STATUS_LABEL else "",
        "tipo": sp.get("tipo", "") if sp.get("tipo") in TIPO_LABEL else "",
        "empresa": (uuids_validos([sp.get("empresa")]) or [""])[0],
        "de": data_valida(sp.get("de")),
        "ate": data_valida(sp.get("ate")),
    }


def _aplicar_filtros(qs, f: dict):
    if f["status"]:
        qs = qs.filter(status=f["status"])
    if f["tipo"]:
        qs = qs.filter(tipo=f["tipo"])
    if f["empresa"]:
        qs = qs.filter(cliente__empresa_id=f["empresa"])
    tz = timezone.get_current_timezone()
    if f["de"]:
        qs = qs.filter(criado_em__gte=datetime.combine(datetime.fromisoformat(f["de"]).date(), time.min, tz))
    if f["ate"]:
        fim = datetime.combine(datetime.fromisoformat(f["ate"]).date(), time.min, tz) + timedelta(days=1)
        qs = qs.filter(criado_em__lt=fim)
    return qs


@operacao_required
def painel(request):
    f = _filtros_painel(request.GET)
    linhas = list(
        _aplicar_filtros(Ocorrencia.objects.filter(excluida_em__isnull=True), f)
        .select_related("cliente__empresa")
        .order_by("criado_em")
    )

    cont_status = Counter(o.status for o in linhas)
    cont_tipo = Counter(o.tipo for o in linhas)
    cont_dia = Counter(timezone.localtime(o.criado_em).date() for o in linhas)

    por_empresa: dict = {}
    for o in linhas:
        emp = o.cliente.empresa
        chave = emp.pk if emp else None
        atual = por_empresa.setdefault(chave, {"id": chave, "nome": emp.nome if emp else "Sem empresa", "total": 0, "abertas": 0})
        atual["total"] += 1
        if o.status in STATUS_ATIVOS:
            atual["abertas"] += 1
    empresas_ordenadas = sorted(por_empresa.values(), key=lambda e: e["total"], reverse=True)

    graficos = {
        "porStatus": [{"label": STATUS_LABEL[s], "valor": cont_status.get(s, 0)} for s in STATUS_LABEL],
        "porTipo": [{"label": TIPO_LABEL[t], "valor": n} for t in TIPO_LABEL if (n := cont_tipo.get(t, 0)) > 0],
        "porTempo": [{"label": d.strftime("%d/%m"), "valor": n} for d, n in sorted(cont_dia.items())],
        "porEmpresa": [{"label": e["nome"], "valor": e["total"]} for e in empresas_ordenadas if e["id"]][:8],
    }

    query = "&".join(f"{k}={v}" for k, v in f.items() if v)
    return render(
        request,
        "ocorrencias/operacao/painel.html",
        {
            "total": len(linhas),
            "filtros": f,
            "tem_filtro": any(f.values()),
            "empresas": Empresa.objects.order_by("nome").values("id", "nome"),
            "status_labels": list(STATUS_LABEL.items()),
            "tipo_labels": list(TIPO_LABEL.items()),
            "cartoes": [
                {"label": "Total", "valor": len(linhas)},
                {"label": "Abertas", "valor": cont_status.get("aberta", 0), "destaque": True},
                {"label": "Em tratativa", "valor": cont_status.get("em_analise", 0)},
                {"label": "Aguard. aprovação", "valor": cont_status.get("resolvida", 0)},
                {"label": "Resolvidas", "valor": cont_status.get("concluida", 0)},
                {"label": "Recusadas", "valor": cont_status.get("recusada", 0)},
            ],
            "graficos": graficos,
            "graficos_titulos": [
                ("g-status", "Ocorrências por status"),
                ("g-tipo", "Por categoria"),
                ("g-tempo", "Evolução no tempo"),
                ("g-empresa", "Top empresas"),
            ],
            "empresas_ordenadas": empresas_ordenadas,
            "export_href": f"/operacao/painel/export{'?' + query if query else ''}",
        },
    )


@operacao_required
def painel_exportar(request):
    f = _filtros_painel(request.GET)
    qs = (
        _aplicar_filtros(Ocorrencia.objects.filter(excluida_em__isnull=True), f)
        .select_related("cliente__empresa")
        .order_by("-criado_em")
    )
    stamp = timezone.localdate().isoformat()
    resp = HttpResponse(planilha_ocorrencias(qs), content_type=XLSX_MIME)
    resp["Content-Disposition"] = f'attachment; filename="ocorrencias-{stamp}.xlsx"'
    resp["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- empresas


def _texto(post, campo) -> str | None:
    return (post.get(campo) or "").strip() or None


@operacao_required
def empresas(request):
    erro = None
    valores = {}
    if request.method == "POST":
        valores = request.POST
        nome = (request.POST.get("nome") or "").strip()
        if len(nome) < 2:
            erro = "Informe o nome da empresa."
        else:
            Empresa.objects.create(
                nome=nome,
                cnpj=_texto(request.POST, "cnpj"),
                contato_nome=_texto(request.POST, "contato_nome"),
                contato_email=_texto(request.POST, "contato_email"),
                telefone=_texto(request.POST, "telefone"),
            )
            return redirect("operacao:empresas")

    q = sanitizar_busca(request.GET.get("q"))
    qs = Empresa.objects.annotate(n_clientes=Count("membros")).order_by("nome")
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(cnpj__icontains=q))
    return render(
        request,
        "ocorrencias/operacao/empresas.html",
        {
            "pagina": paginar(request, qs),
            "q": request.GET.get("q", ""),
            "filtrado": bool(q),
            "erro": erro,
            "valores": valores,
            "campos_empresa": [
                ("cnpj", "CNPJ", "text"),
                ("telefone", "Telefone", "text"),
                ("contato_nome", "Contato (nome)", "text"),
                ("contato_email", "Contato (e-mail)", "email"),
            ],
        },
    )


@operacao_required
def empresa_detalhe(request, pk):
    empresa = get_object_or_404(Empresa, pk=pk)
    if request.method == "POST":
        user_id = (uuids_validos([request.POST.get("userId")]) or [None])[0]
        if user_id:
            if request.POST.get("acao") == "desvincular":
                Usuario.objects.filter(pk=user_id, empresa=empresa).update(empresa=None)
            else:
                Usuario.objects.filter(pk=user_id, papel=Papel.CLIENTE).update(empresa=empresa)
        return redirect("operacao:empresa_detalhe", pk=empresa.pk)

    clientes = list(Usuario.objects.filter(papel=Papel.CLIENTE).order_by("nome"))
    contato = " · ".join(filter(None, [empresa.cnpj, empresa.contato_nome, empresa.contato_email, empresa.telefone]))
    return render(
        request,
        "ocorrencias/operacao/empresa_detalhe.html",
        {
            "empresa": empresa,
            "contato": contato or "Sem dados de contato",
            "membros": [c for c in clientes if c.empresa_id == empresa.pk],
            "candidatos": [c for c in clientes if c.empresa_id != empresa.pk],
        },
    )


# ---------------------------------------------------------------- usuários


def _dados_usuario(request, papel: str) -> dict:
    eh_cliente = papel == Papel.CLIENTE
    tipo = request.POST.get("tipo_pessoa", "")
    empresa_id = (uuids_validos([request.POST.get("empresa_id")]) or [None])[0] if eh_cliente else None
    return {
        "tipo_pessoa": tipo if eh_cliente and tipo in TipoPessoa.values else None,
        "documento": _texto(request.POST, "documento"),
        "telefone": _texto(request.POST, "telefone"),
        "empresa_id": empresa_id if empresa_id and Empresa.objects.filter(pk=empresa_id).exists() else None,
    }


def _papel_do_form(request) -> str:
    v = request.POST.get("papel", "cliente")
    return v if v in Papel.values else Papel.CLIENTE


@operacao_required
def usuarios(request):
    erro = None
    form_aberto = False
    if request.method == "POST":
        form_aberto = True
        email = (request.POST.get("email") or "").strip().lower()
        nome = (request.POST.get("nome") or "").strip()
        papel = _papel_do_form(request)
        if papel == Papel.ADMIN and not request.user.eh_admin:
            erro = "Apenas um administrador pode conceder o papel de admin."
        elif not email or "@" not in email:
            erro = "Informe um e-mail válido."
        elif len(nome) < 2:
            erro = "Informe o nome do usuário."
        elif Usuario.objects.filter(email=email).exists():
            erro = "Já existe um usuário com esse e-mail."
        else:
            user = Usuario.objects.create_user(email, None, nome=nome, papel=papel, **_dados_usuario(request, papel))
            enviado = enviar_convite(user)
            messages.success(
                request,
                f"Convite enviado para {email}."
                if enviado
                else 'Convite criado, mas o e-mail não pôde ser enviado (confira o SMTP no .env). Use "Reenviar convite" depois de corrigir.',
                extra_tags="usuario",
            )
            return redirect("operacao:usuarios")

    q = sanitizar_busca(request.GET.get("q"))
    papel_f = request.GET.get("papel", "")
    empresa_f = (uuids_validos([request.GET.get("empresa")]) or [""])[0]
    qs = Usuario.objects.select_related("empresa").order_by("papel", "nome")
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(email__icontains=q))
    if papel_f in Papel.values:
        qs = qs.filter(papel=papel_f)
    if empresa_f:
        qs = qs.filter(empresa_id=empresa_f)

    return render(
        request,
        "ocorrencias/operacao/usuarios.html",
        {
            "pagina": paginar(request, qs),
            "q": request.GET.get("q", ""),
            "papel_f": papel_f,
            "empresa_f": empresa_f,
            "tem_filtro": bool(q or papel_f or empresa_f),
            "empresas": Empresa.objects.order_by("nome"),
            "tipos_pessoa": TipoPessoa.choices,
            "erro": erro,
            "form_aberto": form_aberto,
            "valores": request.POST if request.method == "POST" else {},
        },
    )


@operacao_required
@require_POST
def usuario_reenviar(request, pk):
    user = Usuario.objects.filter(pk=pk).first()
    if user is None:
        return JsonResponse({"error": "Usuário não encontrado."})
    if user.ativado_em:
        return JsonResponse({"error": "Esse usuário já ativou a conta."})
    if not reenviar_convite(user):
        return JsonResponse({"error": "Link gerado, mas o e-mail não pôde ser enviado (confira o SMTP no .env)."})
    return JsonResponse({"mensagem": f"Convite reenviado para {user.email}."})


def _atividade(usuario, qtd_abertas: int) -> dict:
    """Quadro "Atividade" do usuário (spec 020): o que ele abriu ou atende agora."""
    em_andamento = Ocorrencia.objects.filter(excluida_em__isnull=True, status__in=STATUS_ATIVOS)
    if usuario.eh_cliente:
        return {
            "total": qtd_abertas,
            "em_andamento": em_andamento.filter(cliente=usuario).count(),
            "filtro": f"cliente={usuario.pk}",
        }
    return {
        "total": None,
        "em_andamento": em_andamento.filter(atribuido_a=usuario).count(),
        "filtro": f"responsavel={usuario.pk}",
    }


@operacao_required
def usuario_detalhe(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    qtd = Ocorrencia.objects.filter(cliente=usuario).count()
    erro = None

    if request.method == "POST":
        nome = (request.POST.get("nome") or "").strip()
        papel = _papel_do_form(request)
        # Só admin concede/retira admin (anti-escalação de privilégio).
        if papel != usuario.papel and Papel.ADMIN in (papel, usuario.papel) and not request.user.eh_admin:
            erro = "Apenas um administrador pode conceder o papel de admin."
        elif len(nome) < 2:
            erro = "Informe o nome do usuário."
        else:
            usuario.nome = nome
            usuario.papel = papel
            for campo, valor in _dados_usuario(request, papel).items():
                setattr(usuario, campo, valor)
            usuario.save()
            messages.success(request, "Alterações salvas.", extra_tags="usuario")
            return redirect("operacao:usuario_detalhe", pk=usuario.pk)

    eu = request.user.pk == usuario.pk
    if eu:
        bloqueio = "Você não pode excluir a si mesmo."
    elif qtd:
        bloqueio = f"Possui {qtd} ocorrência(s) — não pode ser excluído."
    else:
        bloqueio = None

    return render(
        request,
        "ocorrencias/operacao/usuario_detalhe.html",
        {
            "usuario": usuario,
            "empresas": Empresa.objects.order_by("nome"),
            "tipos_pessoa": TipoPessoa.choices,
            "bloqueio_exclusao": bloqueio,
            "atividade": _atividade(usuario, qtd),
            "pode_admin": request.user.eh_admin,
            "erro": erro,
        },
    )


@operacao_required
@require_POST
def usuario_excluir(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "Você não pode excluir a si mesmo.", extra_tags="excluir")
    elif Ocorrencia.objects.filter(cliente=usuario).exists():
        messages.error(
            request,
            "Este usuário possui ocorrências e não pode ser excluído (isso apagaria registros). Considere apenas mantê-lo.",
            extra_tags="excluir",
        )
    elif usuario.eh_admin and not request.user.eh_admin:
        messages.error(request, "Apenas um administrador pode excluir outro administrador.", extra_tags="excluir")
    else:
        usuario.delete()
        return redirect("operacao:usuarios")
    return redirect("operacao:usuario_detalhe", pk=usuario.pk)


# ---------------------------------------------------------------- avisos


@operacao_required
def avisos(request):
    erro = None
    if request.method == "POST":
        titulo = (request.POST.get("titulo") or "").strip()
        mensagem = (request.POST.get("mensagem") or "").strip()
        tipo = "alerta" if request.POST.get("tipo") == "alerta" else "info"
        validade = (request.POST.get("expira_em") or "").strip()
        expira_em = None

        if len(titulo) < 2:
            erro = "Informe um título."
        elif len(mensagem) < 2:
            erro = "Informe a mensagem."
        elif len(titulo) > AVISO_TITULO_MAX:
            erro = f"O título aceita até {AVISO_TITULO_MAX} caracteres."
        elif len(mensagem) > AVISO_MENSAGEM_MAX:
            erro = f"A mensagem aceita até {AVISO_MENSAGEM_MAX} caracteres."
        elif validade:
            # Vale até o fim do dia informado, no horário de Brasília.
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", validade):
                erro = "Data de validade inválida."
            else:
                try:
                    dia = datetime.fromisoformat(validade).date()
                    expira_em = datetime.combine(dia, time(23, 59, 59), timezone.get_current_timezone())
                    if expira_em < timezone.now():
                        erro = "A validade não pode estar no passado."
                except ValueError:
                    erro = "Data de validade inválida."

        if not erro:
            Aviso.objects.create(titulo=titulo, mensagem=mensagem, tipo=tipo, expira_em=expira_em)
            return redirect("operacao:avisos")

    return render(
        request,
        "ocorrencias/operacao/avisos.html",
        {
            "avisos": Aviso.objects.order_by("-criado_em"),
            "erro": erro,
            "valores": request.POST if request.method == "POST" else {},
            "titulo_max": AVISO_TITULO_MAX,
            "mensagem_max": AVISO_MENSAGEM_MAX,
        },
    )


@operacao_required
@require_POST
def aviso_acao(request, pk, acao):
    aviso = get_object_or_404(Aviso, pk=pk)
    if acao == "alternar":
        aviso.ativo = not aviso.ativo
        aviso.save(update_fields=["ativo"])
    elif acao == "excluir":
        aviso.delete()
    return redirect("operacao:avisos")


# ---------------------------------------------------------------- contatos


@operacao_required
def contatos(request):
    erro = None
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        setor = (request.POST.get("setor") or "").strip()
        if len(email) < 5 or "@" not in email:
            erro = "Informe um e-mail válido."
        else:
            ContatoEncaminhamento.objects.create(email=email, setor=setor or None)
            return redirect("operacao:contatos")
    return render(
        request,
        "ocorrencias/operacao/contatos.html",
        {
            "contatos": ContatoEncaminhamento.objects.order_by("-criado_em"),
            "erro": erro,
            "valores": request.POST if request.method == "POST" else {},
        },
    )


@operacao_required
@require_POST
def contato_acao(request, pk, acao):
    contato = get_object_or_404(ContatoEncaminhamento, pk=pk)
    if acao == "alternar":
        contato.ativo = not contato.ativo
        contato.save(update_fields=["ativo"])
    elif acao == "excluir":
        contato.delete()
    return redirect("operacao:contatos")


# ---------------------------------------------------------------- SLA (admin)


@admin_required
def sla(request):
    erro = None
    if request.method == "POST":
        categoria = request.POST.get("categoria") or None
        prioridade = request.POST.get("prioridade") or None
        categoria = categoria if categoria in TIPOS_FORM else None
        prioridade = prioridade if prioridade in Prioridade.values else None
        try:
            horas = int(request.POST.get("horas", ""))
        except ValueError:
            horas = 0
        if horas <= 0:
            erro = "Informe o prazo em horas (maior que zero)."
        else:
            # Uma regra por combinação (upsert).
            SlaRegra.objects.update_or_create(categoria=categoria, prioridade=prioridade, defaults={"horas": horas})
            messages.success(request, "Regra salva.", extra_tags="sla")
            return redirect("operacao:sla")

    ordem = {None: -1, **{t: i for i, t in enumerate(TIPO_LABEL)}}
    ordem_p = {None: -1, "baixa": 0, "media": 1, "alta": 2}
    regras = sorted(SlaRegra.objects.all(), key=lambda r: (ordem.get(r.categoria, 99), ordem_p.get(r.prioridade, 99)))
    return render(
        request,
        "ocorrencias/operacao/sla.html",
        {
            "regras": regras,
            "erro": erro,
            "tipos_form": [(t, TIPO_LABEL[t]) for t in TIPOS_FORM],
            "prioridades": list(PRIORIDADE_LABEL.items()),
        },
    )


@admin_required
@require_POST
def sla_excluir(request, pk):
    SlaRegra.objects.filter(pk=pk).delete()
    return redirect("operacao:sla")
