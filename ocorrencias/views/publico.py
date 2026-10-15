"""Páginas públicas: início e consulta de protocolo sem login."""

import re

from django.shortcuts import render

from ..models import Ocorrencia


def inicio(request):
    return render(request, "ocorrencias/inicio.html")


def _so_digitos(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def consulta(request):
    """
    Protocolo + CPF/CNPJ de quem abriu. Devolve SÓ campos não sensíveis
    (tipo, status e linha do tempo) e ignora ocorrências na lixeira.
    """
    erro = resultado = None
    if request.method == "POST":
        protocolo = request.POST.get("protocolo", "").strip()
        documento = request.POST.get("documento", "").strip()
        if not protocolo or not documento:
            erro = "Informe o protocolo e o documento."
        else:
            oc = (
                Ocorrencia.objects.select_related("cliente")
                .filter(protocolo=protocolo, excluida_em__isnull=True)
                .first()
            )
            doc_cliente = _so_digitos(oc.cliente.documento) if oc else ""
            if oc and doc_cliente and doc_cliente == _so_digitos(documento):
                resultado = {
                    "protocolo": oc.protocolo,
                    "tipo": oc.tipo,
                    "status": oc.status,
                    "historico": list(oc.historico.order_by("criado_em").values("para_status", "criado_em")),
                }
            else:
                # Mensagem genérica de propósito (não revela qual campo falhou).
                erro = "Protocolo não encontrado ou documento não confere."
    return render(request, "ocorrencias/consulta.html", {"erro": erro, "r": resultado})
