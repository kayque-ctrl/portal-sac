"""
Autorização — substitui as policies de RLS do Supabase.

Regras (ver 0024_visibilidade_empresa no projeto original):
- LEITURA: operação vê tudo; cliente vê as próprias e as de colegas da MESMA
  empresa (empresa nula nunca casa: sem empresa, só as próprias).
- ESCRITA (mensagem, anexo, aprovar, reabrir): operação ou quem abriu.
- Notas internas nunca aparecem para o cliente.
"""

from django.db.models import Q

from .models import Mensagem, Ocorrencia


def ocorrencias_visiveis(user):
    qs = Ocorrencia.objects.all()
    if user.eh_operacao:
        return qs
    filtro = Q(cliente=user)
    if user.empresa_id:
        filtro |= Q(cliente__empresa_id=user.empresa_id)
    return qs.filter(filtro)


def pode_ver(user, oc: Ocorrencia) -> bool:
    if user.eh_operacao or oc.cliente_id == user.pk:
        return True
    return bool(user.empresa_id) and oc.cliente.empresa_id == user.empresa_id


def pode_agir(user, oc: Ocorrencia) -> bool:
    return user.eh_operacao or oc.cliente_id == user.pk


def mensagens_visiveis(user, oc: Ocorrencia):
    qs = Mensagem.objects.filter(ocorrencia=oc)
    if not user.eh_operacao:
        qs = qs.filter(interna=False)
    return qs


def colegas_da_empresa(user) -> dict:
    """Nome dos colegas (clientes) da mesma empresa: id → nome."""
    from contas.models import Papel, Usuario

    if not user.empresa_id:
        return {}
    return dict(Usuario.objects.filter(empresa_id=user.empresa_id, papel=Papel.CLIENTE).values_list("id", "nome"))
