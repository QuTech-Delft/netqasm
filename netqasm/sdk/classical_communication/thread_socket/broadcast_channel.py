from __future__ import annotations
from typing import Type
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..socket import Socket

from ..broadcast_channel import BroadcastChannelBySockets
from .socket import ThreadSocket


class ThreadBroadcastChannel(BroadcastChannelBySockets):
    _socket_class: Type[Socket] = ThreadSocket
