from ..broadcast_channel import BroadcastChannelBySockets
from .socket import ThreadSocket


class ThreadBroadcastChannel(BroadcastChannelBySockets):
    _socket_class = ThreadSocket
