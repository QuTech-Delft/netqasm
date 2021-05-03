"""
Definitions of messages between the Host and the quantum node controller.
"""

import ctypes
from enum import Enum
from typing import Union

from netqasm.lang.encoding import INTEGER, Address, OptionalInt, Register
from netqasm.lang.subroutine import Subroutine

# C types for serialization
MESSAGE_TYPE = ctypes.c_uint8
MESSAGE_ID = ctypes.c_uint32
APP_ID = ctypes.c_uint32
NUM_QUBITS = ctypes.c_uint8
EPR_SOCKET_ID = INTEGER
EPR_FIDELITY = ctypes.c_uint8
NODE_ID = INTEGER
SIGNAL = ctypes.c_uint8

MESSAGE_TYPE_BYTES = len(bytes(MESSAGE_TYPE()))  # type: ignore


class MessageHeader(ctypes.Structure):
    _fields_ = [
        ("id", MESSAGE_ID),
        ("length", ctypes.c_uint32),
    ]

    @classmethod
    def len(cls):
        return len(bytes(cls()))

    def __str__(self):
        return f"{self.__class__.__name__}(id={self.id}, length={self.length})"


class MessageType(Enum):
    INIT_NEW_APP = 0x00
    OPEN_EPR_SOCKET = 0x01
    SUBROUTINE = 0x02
    STOP_APP = 0x03
    SIGNAL = 0x04


class Message(ctypes.Structure):
    _pack = 1
    _fields_ = [
        ("type", MESSAGE_TYPE),
    ]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        return cls.from_buffer_copy(raw)

    def __str__(self):
        to_print = f"{self.__class__.__name__}("
        for field_name, _ in self._fields_:
            to_print += f"{field_name}={getattr(self, field_name)}, "
        to_print = to_print[:-2] + ")"
        return to_print

    def __len__(self):
        return len(bytes(self))


class InitNewAppMessage(Message):
    """Message sent to the quantum node controller to register a new application."""

    _fields_ = [
        ("app_id", APP_ID),  # type: ignore
        ("max_qubits", NUM_QUBITS),
    ]

    TYPE = MessageType.INIT_NEW_APP

    def __init__(self, app_id=0, max_qubits=0):
        super().__init__(self.TYPE.value)
        self.app_id = app_id
        self.max_qubits = max_qubits


class OpenEPRSocketMessage(Message):
    """Message sent to the quantum node controller to open an EPR socket."""

    _fields_ = [
        ("app_id", APP_ID),  # type: ignore
        ("epr_socket_id", EPR_SOCKET_ID),  # type: ignore
        ("remote_node_id", NODE_ID),  # type: ignore
        ("remote_epr_socket_id", EPR_SOCKET_ID),  # type: ignore
        ("min_fidelity", EPR_FIDELITY),  # type: ignore
    ]

    TYPE = MessageType.OPEN_EPR_SOCKET

    def __init__(
        self,
        app_id=0,
        epr_socket_id=0,
        remote_node_id=0,
        remote_epr_socket_id=0,
        min_fidelity=100,
    ):
        super().__init__(self.TYPE.value)
        self.app_id = app_id
        self.epr_socket_id = epr_socket_id
        self.remote_node_id = remote_node_id
        self.remote_epr_socket_id = remote_epr_socket_id
        self.min_fidelity = min_fidelity


class SubroutineMessage:
    """Message sent to the quantum node controller to execute a subroutine."""

    TYPE = MessageType.SUBROUTINE

    def __init__(self, subroutine: Union[bytes, Subroutine]):
        """
        NOTE this message does not subclass from `Message` since it contains
        a subroutine which is defined separately and not as a `ctype` for now.
        Still this class defines the methods `__bytes__` and `deserialize_from`
        so that it can be packed and unpacked.
        The packed form of the message is:

        .. code-block:: text

            | TYP | SUBROUTINE ... |

        """
        self.type = self.TYPE.value
        if isinstance(subroutine, Subroutine):
            self.subroutine = bytes(subroutine)
        elif isinstance(subroutine, bytes):
            self.subroutine = subroutine
        else:
            raise TypeError(
                f"subroutine should be Subroutine or bytes, not {type(subroutine)}"
            )

    def __bytes__(self):
        return bytes(MESSAGE_TYPE(self.type)) + bytes(self.subroutine)

    def __len__(self):
        return len(bytes(self))

    @classmethod
    def deserialize_from(cls, raw: bytes):
        # NOTE we don't deserialize the subroutine here, since we need to know which flavour
        # is being used
        return cls(subroutine=raw[MESSAGE_TYPE_BYTES:])


class StopAppMessage(Message):
    """Message sent to the quantum node controller to stop/finish an application."""

    _fields_ = [
        ("app_id", APP_ID),  # type: ignore
    ]

    TYPE = MessageType.STOP_APP

    def __init__(self, app_id=0):
        super().__init__(self.TYPE.value)
        self.app_id = app_id


class Signal(Enum):
    STOP = 0


class SignalMessage(Message):
    """Message sent to the quantum node controller with a specific signal.

    Currently only used with the SquidASM simulator backend.
    """

    _fields_ = [
        ("signal", SIGNAL),
    ]

    TYPE = MessageType.SIGNAL

    def __init__(self, signal: Signal = Signal.STOP):
        super().__init__(self.TYPE.value)
        self.signal = signal.value


MESSAGE_CLASSES = {
    MessageType.INIT_NEW_APP: InitNewAppMessage,
    MessageType.OPEN_EPR_SOCKET: OpenEPRSocketMessage,
    MessageType.SUBROUTINE: SubroutineMessage,
    MessageType.STOP_APP: StopAppMessage,
    MessageType.SIGNAL: SignalMessage,
}


def deserialize_host_msg(raw: bytes) -> Message:
    """Convert a serialized message into a `Message` object

    :param raw: serialized message (string of bytes)
    :return: deserialized message object
    """
    message_type = MessageType(
        MESSAGE_TYPE.from_buffer_copy(raw[:MESSAGE_TYPE_BYTES]).value
    )
    message_class = MESSAGE_CLASSES[message_type]
    return message_class.deserialize_from(raw)  # type: ignore


class ReturnMessage(Message):
    """Base class for messages from the quantum node controller to the Host."""

    pass


class ReturnMessageType(Enum):
    DONE = 0x00
    ERR = 0x01
    RET_ARR = 0x02
    RET_REG = 0x03


class MsgDoneMessage(ReturnMessage):
    """Message to the Host that a subroutine has finished."""

    _fields_ = [
        ("msg_id", MESSAGE_ID),  # type: ignore
    ]

    TYPE = ReturnMessageType.DONE

    def __init__(self, msg_id=0):
        super().__init__(self.TYPE.value)
        self.msg_id = msg_id


class ErrorCode(Enum):
    GENERAL = 0x00
    NO_QUBIT = 0x01
    UNSUPP = 0x02


class ErrorMessage(ReturnMessage):
    """Message to the Host that an error occurred at the quantum node controller."""

    _fields_ = [
        ("err_code", ctypes.c_uint8),
    ]

    TYPE = ReturnMessageType.ERR

    def __init__(self, err_code):
        super().__init__(self.TYPE.value)
        self.err_code = err_code.value


class ReturnArrayMessageHeader(ctypes.Structure):
    """Header for a message with a returned array coming from the quantum node
    controller.
    """

    _pack = 1
    _fields_ = [
        ("address", Address),
        ("length", INTEGER),
    ]

    @classmethod
    def len(cls):
        return len(bytes(cls()))


class ReturnArrayMessage:
    """Message with a returned array coming from the quantum node controller."""

    TYPE = ReturnMessageType.RET_ARR

    def __init__(self, address, values):
        """NOTE this message does not subclass from `ReturnMessage` since
        the values is of variable length.
        Still this class defines the methods `__bytes__` and `deserialize_from`
        so that it can be packed and unpacked.

        The packed form of the message is:

        .. code-block:: text

            | ADDRESS | LENGTH | VALUES ... |

        """
        self.type = self.TYPE.value
        self.address = address
        self.values = values

    def __bytes__(self):
        array_type = OptionalInt * len(self.values)
        payload = array_type(*(OptionalInt(v) for v in self.values))
        hdr = ReturnArrayMessageHeader(
            address=Address(self.address),
            length=len(self.values),
        )
        return bytes(MESSAGE_TYPE(self.type)) + bytes(hdr) + bytes(payload)

    def __str__(self):
        return (
            f"{self.__class__.__name__}(address={self.address}, values={self.values})"
        )

    def __len__(self):
        return len(bytes(self))

    @classmethod
    def deserialize_from(cls, raw: bytes):
        raw = raw[MESSAGE_TYPE_BYTES:]
        hdr = ReturnArrayMessageHeader.from_buffer_copy(raw)
        array_type = OptionalInt * hdr.length
        raw = raw[ReturnArrayMessageHeader.len() :]
        values = list(v.value for v in array_type.from_buffer_copy(raw))
        return cls(address=hdr.address.address, values=values)


class ReturnRegMessage(ReturnMessage):
    """Message with a returned register coming from the quantum node controller."""

    _fields_ = [
        ("register", Register),  # type: ignore
        ("value", INTEGER),  # type: ignore
    ]

    TYPE = ReturnMessageType.RET_REG

    def __init__(self, register, value):
        super().__init__(self.TYPE.value)
        self.register = register
        self.value = value


RETURN_MESSAGE_CLASSES = {
    ReturnMessageType.DONE: MsgDoneMessage,
    ReturnMessageType.ERR: ErrorMessage,
    ReturnMessageType.RET_REG: ReturnRegMessage,
    ReturnMessageType.RET_ARR: ReturnArrayMessage,
}


def deserialize_return_msg(raw: bytes) -> Message:
    """Convert a serialized 'return' message into a `Message` object

    :param raw: serialized message (string of bytes)
    :return: deserialized message object
    """
    message_type = ReturnMessageType(
        MESSAGE_TYPE.from_buffer_copy(raw[:MESSAGE_TYPE_BYTES]).value
    )
    message_class = RETURN_MESSAGE_CLASSES[message_type]
    return message_class.deserialize_from(raw)  # type: ignore
