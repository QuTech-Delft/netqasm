"""BroadcastChannel implementation using ThreadSockets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Type

from ..broadcast_channel import BroadcastChannelBySockets
from .socket import ThreadSocket

if TYPE_CHECKING:
    from .. import socket


class ThreadBroadcastChannel(BroadcastChannelBySockets):
    _socket_class: Type[socket.Socket] = ThreadSocket
