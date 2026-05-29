from __future__ import annotations

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from apps.core.realtime import restaurante_group
from apps.core.routing import websocket_urlpatterns
from channels.routing import URLRouter

pytestmark = pytest.mark.django_db(transaction=True)


def _build_communicator(user=None):
    app = URLRouter(websocket_urlpatterns)
    communicator = WebsocketCommunicator(app, "/ws/eventos/")
    # AuthMiddlewareStack normalmente popula scope["user"]; aqui injetamos direto.
    communicator.scope["user"] = user
    return communicator


def test_consumer_recusa_anonimo():
    """Sem usuário autenticado a conexão deve ser fechada."""
    from django.contrib.auth.models import AnonymousUser

    async def _run():
        communicator = _build_communicator(AnonymousUser())
        connected, _ = await communicator.connect()
        await communicator.disconnect()
        return connected

    connected = async_to_sync(_run)()
    assert connected is False


def test_consumer_recebe_evento_do_grupo(make_perfil, restaurante):
    """Usuário autenticado entra no grupo do restaurante e recebe o evento."""
    user = make_perfil("gerente")

    async def _run():
        communicator = _build_communicator(user)
        connected, _ = await communicator.connect()
        assert connected is True

        layer = get_channel_layer()
        await layer.group_send(
            restaurante_group(restaurante.id),
            {
                "type": "sgr.event",
                "event": "estoque_alerta",
                "payload": {
                    "ingrediente": "Carne Moída",
                    "estoque_atual": "100",
                    "estoque_minimo": "500",
                },
            },
        )

        data = await communicator.receive_json_from(timeout=2)
        await communicator.disconnect()
        return data

    data = async_to_sync(_run)()
    assert data["event"] == "estoque_alerta"
    assert data["payload"]["ingrediente"] == "Carne Moída"
