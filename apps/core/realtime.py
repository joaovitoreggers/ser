from __future__ import annotations

from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def restaurante_group(restaurante_id) -> str:
    return f"restaurante_{restaurante_id}"


def notify(restaurante_id, event: str, payload: dict[str, Any]) -> None:
    """Broadcast a server event to a restaurante's WebSocket group.

    Safe no-op if no channel layer is configured.
    """
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        restaurante_group(restaurante_id),
        {"type": "sgr.event", "event": event, "payload": payload},
    )
