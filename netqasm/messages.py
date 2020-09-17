import ctypes
from enum import Enum

from netqasm.parsing.binary import deserialize as deserialize_subroutine

# This module defines the messages that the host can send to
# the backend/QNodeOS

MESSAGE_TYPE = ctypes.c_uint8
APP_ID = ctypes.c_uint32
NUM_QUBITS = ctypes.c_uint8
EPR_SOCKET_ID = ctypes.c_uint32
NODE_ID = ctypes.c_uint32
SIGNAL = ctypes.c_uint8

MESSAGE_TYPE_BYTES = len(bytes(MESSAGE_TYPE()))  # type: ignore


class MessageType(Enum):
    INIT_NEW_APP = 0x00
    OPEN_EPR_SOCKET = 0x01
    SUBROUTINE = 0x02
    STOP_APP = 0x03
    SIGNAL = 0x04


class Message(ctypes.Structure):
    _pack = 1
    _fields_ = [
        ('type', MESSAGE_TYPE),
    ]

    @classmethod
    def deserialize_from(cls, raw: bytes, flavour=None):
        return cls.from_buffer_copy(raw)


class InitNewAppMessage(Message):
    _fields_ = [
        ('app_id', APP_ID),  # type: ignore
        ('max_qubits', NUM_QUBITS),
    ]

    TYPE = MessageType.INIT_NEW_APP.value

    def __init__(self, app_id, max_qubits):
        super().__init__(self.TYPE)
        self.app_id = app_id
        self.max_qubits = max_qubits


class OpenEPRSocketMessage(Message):
    _fields_ = [
        ("epr_socket_id", EPR_SOCKET_ID),  # type: ignore
        ("remote_node_id", NODE_ID),  # type: ignore
        ("remote_epr_socket_id", EPR_SOCKET_ID),  # type: ignore
    ]

    TYPE = MessageType.OPEN_EPR_SOCKET.value

    def __init__(self, epr_socket_id, remote_node_id, remote_epr_socket_id):
        super().__init__(self.TYPE)
        self.epr_socket_id = epr_socket_id
        self.remote_node_id = remote_node_id
        self.remote_epr_socket_id = remote_epr_socket_id


class SubroutineMessage:

    TYPE = MessageType.SUBROUTINE.value

    def __init__(self, subroutine):
        """
        NOTE this message does not subclass from Message since it contains
        a subroutine which is defined separately and not as a `ctype` for now.
        Still this class defines the methods `__bytes__` and `deserialize_from`
        so that it can be packed and unpacked.
        """
        self.type = self.TYPE
        self.subroutine = subroutine

    def __bytes__(self):
        return bytes(MESSAGE_TYPE(self.type)) + bytes(self.subroutine)

    @classmethod
    def deserialize_from(cls, raw: bytes, flavour=None):
        subroutine = deserialize_subroutine(data=raw[MESSAGE_TYPE_BYTES:], flavour=flavour)
        return cls(subroutine=subroutine)


class StopAppMessage(Message):
    _fields_ = [
        ('app_id', APP_ID),  # type: ignore
    ]

    TYPE = MessageType.STOP_APP.value

    def __init__(self, app_id):
        super().__init__(self.TYPE)
        self.app_id = app_id


class Signal(Enum):
    STOP = 0


class SignalMessage(Message):
    _fields_ = [
        ("signal", SIGNAL),
    ]

    TYPE = MessageType.SIGNAL.value

    def __init__(self, signal: Signal):
        super().__init__(self.TYPE)
        self.signal = signal.value


MESSAGE_CLASSES = {
    MessageType.INIT_NEW_APP: InitNewAppMessage,
    MessageType.OPEN_EPR_SOCKET: OpenEPRSocketMessage,
    MessageType.SUBROUTINE: SubroutineMessage,
    MessageType.STOP_APP: StopAppMessage,
    MessageType.SIGNAL: SignalMessage,
}


def deserialize(raw: bytes, flavour=None) -> Message:
    message_type = MessageType(MESSAGE_TYPE.from_buffer_copy(raw[:MESSAGE_TYPE_BYTES]).value)
    message_class = MESSAGE_CLASSES[message_type]
    return message_class.deserialize_from(raw, flavour=flavour)  # type: ignore
