from __future__ import annotations

from apps.core.models import LogAuditoria
from apps.usuarios.models import PerfilUsuario
from apps.usuarios.rbac import PERFIS_APROVADORES


def validar_pin_aprovador(restaurante, pin: str) -> PerfilUsuario | None:
    """Retorna o PerfilUsuario aprovador (gerente/admin do tenant) cujo PIN bate,
    ou None se nenhum aprovador validar o PIN (§4.4)."""
    if not pin:
        return None
    aprovadores = PerfilUsuario.objects.for_tenant(restaurante).filter(
        perfil__in=PERFIS_APROVADORES
    )
    for aprovador in aprovadores:
        if aprovador.check_pin(pin):
            return aprovador
    return None


def registrar_log(
    *,
    restaurante,
    usuario,
    acao: str,
    entidade: str,
    entidade_id=None,
    dados_antes: dict | None = None,
    dados_depois: dict | None = None,
) -> LogAuditoria:
    """Cria um registro em LogAuditoria (§4.4 — cancelamentos e fechamentos)."""
    return LogAuditoria.objects.create(
        restaurante=restaurante,
        usuario=usuario,
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id,
        dados_antes=dados_antes or {},
        dados_depois=dados_depois or {},
    )
