from enum import Enum, auto
from collections import namedtuple

Message = namedtuple("Message", ["type", "msg"])
InitNewAppMessage = namedtuple("InitNewAppMessage", ["app_id", "max_qubits"])
StopAppMessage = namedtuple("StopAppMessage", ["app_id"])
OpenEPRSocketMessage = namedtuple("OpenEPRSocketMessage", ["epr_socket_id", "remote_node_id", "remote_epr_socket_id"])


class Signal(Enum):
    STOP = auto()


class MessageType(Enum):
    SUBROUTINE = auto()
    SIGNAL = auto()
    INIT_NEW_APP = auto()
    STOP_APP = auto()
    OPEN_EPR_SOCKET = auto()
