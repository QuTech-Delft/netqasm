from enum import Enum
import ctypes

############
# METADATA #
############
NETQASM_VERSION = ctypes.c_uint8 * 2
APP_ID = ctypes.c_uint16


class Metadata(ctypes.Structure):
    _fields_ = [
        ('netqasm_version', NETQASM_VERSION),
        ('app_id', APP_ID),
    ]


METADATA_BYTES = len(bytes(Metadata()))


########
# BODY #
########
INTEGER = ctypes.c_int32
INTEGER_BITS = len(bytes(INTEGER())) * 8  # type: ignore
IMMEDIATE = ctypes.c_uint8
IMMEDIATE_BITS = len(bytes(IMMEDIATE())) * 8  # type: ignore

ADDRESS = INTEGER
ADDRESS_BITS = len(bytes(ADDRESS())) * 8  # type: ignore

INSTR_ID = ctypes.c_uint8

REG_TYPE = ctypes.c_uint8
REG_BITS = len(bytes(REG_TYPE())) * 8  # type: ignore
# Num bits in register name
REG_NAME_BITS = 2
# Num bits in register index
REG_INDEX_BITS = 4

COMMAND_BYTES = 7

PADDING_FIELD = 'padding'


class OptionalInt(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint8),
        ('value', INTEGER),
    ]

    _NULL_TYPE = 0x00
    _INT_TYPE = 0x01

    def __init__(self, value):
        if value is None:
            self.type = self._NULL_TYPE
            self.value = 0
        else:
            self.type = self._INT_TYPE
            self.value = value

    def value(self):
        if self.type == self._NULL_TYPE:
            return None
        elif self.type == self._INT_TYPE:
            return self.value
        else:
            raise TypeError(f"Unknown type {self.type}")


class RegisterName(Enum):
    # Standard register
    R = 0
    # Register for constants
    C = 1
    # Qubit addresses
    Q = 2
    # Measurment outcomes
    M = 3


class Register(ctypes.Structure):
    _fields_ = [
        ('register_name', REG_TYPE, REG_NAME_BITS),
        ('register_index', REG_TYPE, REG_INDEX_BITS),
        (PADDING_FIELD, REG_TYPE, REG_BITS - REG_NAME_BITS - REG_INDEX_BITS),
    ]


class Address(ctypes.Structure):
    _fields_ = [
        ('address', ADDRESS),
    ]


class ArrayEntry(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('address', Address),
        ('index', Register),
    ]


class ArraySlice(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('address', Address),
        ('start', Register),
        ('stop', Register),
    ]


class Command(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('id', INSTR_ID),
    ]

    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except TypeError as err:
            raise TypeError(f"command {self.__class__.__name__} could not be created, since: {err}")


def add_padding(fields):
    """Used to add correct amount of padding for commands to make them fixed-length"""
    # TODO better way?
    class TmpCommand(Command):
        pass
    TmpCommand._fields_ = fields
    current_num_bytes = len(bytes(TmpCommand()))
    total_num_bytes = COMMAND_BYTES
    pad_num_bytes = total_num_bytes - current_num_bytes
    assert pad_num_bytes >= 0
    new_fields = fields + [
        (PADDING_FIELD, ctypes.c_uint8 * pad_num_bytes)
    ]
    return new_fields


class RegCommand(Command):
    _fields_ = add_padding([
        ('reg', Register),
    ])


class RegRegCommand(Command):
    _fields_ = add_padding([
        ('reg0', Register),
        ('reg1', Register),
    ])


class MeasCommand(Command):
    _fields_ = add_padding([
        ('qubit', Register),
        ('outcome', Register),
    ])


class RegImmImmCommand(Command):
    _fields_ = add_padding([
        ('reg', Register),
        ('imm0', IMMEDIATE),
        ('imm1', IMMEDIATE),
    ])


class RegRegImmImmCommand(Command):
    _fields_ = add_padding([
        ('reg0', Register),
        ('reg1', Register),
        ('imm0', IMMEDIATE),
        ('imm1', IMMEDIATE),
    ])


class RegRegRegCommand(Command):
    _fields_ = add_padding([
        ('reg0', Register),
        ('reg1', Register),
        ('reg2', Register),
    ])


class RegRegRegRegCommand(Command):
    _fields_ = add_padding([
        ('reg0', Register),
        ('reg1', Register),
        ('reg2', Register),
        ('reg3', Register),
    ])


class ImmCommand(Command):
    _fields_ = add_padding([
        ('imm', INTEGER),
    ])


class RegRegImmCommand(Command):
    _fields_ = add_padding([
        ('reg0', Register),
        ('reg1', Register),
        ('imm', INTEGER),
    ])


class RegImmCommand(Command):
    _fields_ = add_padding([
        ('reg', Register),
        ('imm', INTEGER),
    ])


class RegEntryCommand(Command):
    _fields_ = add_padding([
        ('reg', Register),
        ('entry', ArrayEntry),
    ])


class RegAddrCommand(Command):
    _fields_ = add_padding([
        ('reg', Register),
        ('addr', Address),
    ])


class ArrayEntryCommand(Command):
    _fields_ = add_padding([
        ('entry', ArrayEntry),
    ])


class ArraySliceCommand(Command):
    _fields_ = add_padding([
        ('slice', ArraySlice),
    ])


class SingleRegisterCommand(Command):
    _fields_ = add_padding([
        ('register', Register),
    ])


class ArrayCommand(Command):
    _fields_ = add_padding([
        ('size', Register),
        ('address', Address),
    ])


class AddrCommand(Command):
    _fields_ = add_padding([
        ('addr', Address),
    ])


class Reg5Command(Command):
    _fields_ = add_padding([
        ('reg0', Register),
        ('reg1', Register),
        ('reg2', Register),
        ('reg3', Register),
        ('reg4', Register),
    ])


class RecvEPRCommand(Command):
    _fields_ = add_padding([
        ('remote_node_id', Register),
        ('epr_socket_id', Register),
        ('qubit_address_array', Register),
        ('ent_info_array', Register),
    ])


COMMANDS = [
    RegCommand,
    RegRegCommand,
    MeasCommand,
    RegImmImmCommand,
    RegRegImmImmCommand,
    RegRegRegCommand,
    ImmCommand,
    RegImmCommand,
    RegRegImmCommand,
    RegEntryCommand,
    ArrayEntryCommand,
    ArraySliceCommand,
    SingleRegisterCommand,
    ArrayCommand,
    Reg5Command,
]
