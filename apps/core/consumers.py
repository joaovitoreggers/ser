from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .realtime import restaurante_group


class EventosConsumer(AsyncJsonWebsocketConsumer):
    """Recebe os eventos de servidor (§3B/§3C) e os repassa ao navegador.

    Cada usuário entra no grupo do seu restaurante; ``notify()`` faz group_send
    com type ``sgr.event`` → Channels chama ``sgr_event`` aqui."""

    group_name: str | None = None

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close()
            return

        restaurante_id = await self._get_restaurante_id(user)
        if restaurante_id is None:
            await self.close()
            return

        self.group_name = restaurante_group(restaurante_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def sgr_event(self, message: dict):
        """Handler do type ``sgr.event``: encaminha {event, payload} ao cliente."""
        await self.send_json(
            {"event": message.get("event"), "payload": message.get("payload", {})}
        )

    @database_sync_to_async
    def _get_restaurante_id(self, user):
        perfil = getattr(user, "perfil", None)
        return perfil.restaurante_id if perfil is not None else None
