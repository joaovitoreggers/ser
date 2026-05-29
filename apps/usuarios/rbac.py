"""RBAC central (§5): perfis, grupos Django, permissões e redirects pós-login."""

from __future__ import annotations

# Perfil -> URL name de redirecionamento pós-login (§5).
PERFIL_REDIRECT: dict[str, str] = {
    "admin": "relatorios:dashboard",
    "gerente": "relatorios:dashboard",
    "garcom": "pedidos:mesas",
    "cozinheiro": "pedidos:kds",
    "caixa": "pedidos:caixa",
    "almoxarife": "estoque:home",
}

_CRUD = ["add", "change", "delete", "view"]
_RW = ["add", "change", "view"]
_VIEW = ["view"]

# Grupo -> lista de (app_label, model, [actions]). "*" em model = todos os models do app.
GROUP_PERMISSIONS: dict[str, list[tuple[str, str, list[str]]]] = {
    "admin": [
        ("core", "*", _CRUD),
        ("usuarios", "*", _CRUD),
        ("estoque", "*", _CRUD),
        ("fichas", "*", _CRUD),
        ("cardapio", "*", _CRUD),
        ("pedidos", "*", _CRUD),
        ("financeiro", "*", _CRUD),
    ],
    "gerente": [
        ("estoque", "*", _CRUD),
        ("fichas", "*", _CRUD),
        ("cardapio", "*", _CRUD),
        ("financeiro", "*", _CRUD),
        ("pedidos", "*", _RW),
        ("usuarios", "perfilusuario", _VIEW),
    ],
    "garcom": [
        ("cardapio", "prato", _VIEW),
        ("cardapio", "categoriaprato", _VIEW),
        ("pedidos", "pedido", _RW),
        ("pedidos", "itempedido", _RW),
        ("pedidos", "mesa", _VIEW),
    ],
    "cozinheiro": [
        ("pedidos", "itempedido", ["view", "change"]),
        ("pedidos", "pedido", _VIEW),
    ],
    "caixa": [
        ("financeiro", "turnocaixa", _RW),
        ("financeiro", "movimentacaocaixa", _RW),
        ("financeiro", "pagamento", _RW),
        ("pedidos", "pedido", ["view", "change"]),
        ("pedidos", "itempedido", _VIEW),
    ],
    "almoxarife": [
        ("estoque", "ingrediente", _RW),
        ("estoque", "entradaestoque", _RW),
        ("estoque", "ajusteestoque", _RW),
        ("estoque", "fornecedor", _RW),
        ("estoque", "categoriaingrediente", _RW),
    ],
}

# Perfis autorizados a aprovar operações sensíveis via PIN (§4.4).
PERFIS_APROVADORES = ("admin", "gerente")


def sync_groups(apps=None) -> None:
    """Cria/atualiza os grupos e suas permissões. Idempotente.

    Aceita o `apps` de uma migração (state apps) ou usa o registry global.
    """
    if apps is None:
        from django.apps import apps as global_apps

        apps = global_apps

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    for group_name, specs in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        perms = []
        for app_label, model, actions in specs:
            cts = ContentType.objects.filter(app_label=app_label)
            if model != "*":
                cts = cts.filter(model=model)
            for ct in cts:
                for action in actions:
                    codename = f"{action}_{ct.model}"
                    perm = Permission.objects.filter(
                        content_type=ct, codename=codename
                    ).first()
                    if perm:
                        perms.append(perm)
        group.permissions.set(perms)
