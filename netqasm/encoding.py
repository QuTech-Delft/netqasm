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
INTEGER_BITS = len(bytes(INTEGER())) * 8
IMMEDIATE = ctypes.c_uint8
IMMEDIATE_BITS = len(bytes(IMMEDIATE())) * 8

ADDRESS = ctypes.c_uint32
ADDRESS_BITS = len(bytes(ADDRESS())) * 8

INSTR_ID = ctypes.c_uint8

REG_TYPE = ctypes.c_uint8
REG_BITS = len(bytes(REG_TYPE())) * 8
# Num bits in register name
REG_NAME_BITS = 2
# Num bits in register index
REG_INDEX_BITS = 4

COMMAND_BYTES = 7

PADDING_FIELD = 'padding'


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


class SingleQubitCommand(Command):
    _fields_ = add_padding([
        ('qubit', Register),
    ])


class TwoQubitCommand(Command):
    _fields_ = add_padding([
        ('qubit1', Register),
        ('qubit2', Register),
    ])


class MeasCommand(Command):
    _fields_ = add_padding([
        ('qubit', Register),
        ('outcome', Register),
    ])


class RotationCommand(Command):
    _fields_ = add_padding([
        ('qubit', Register),
        # An angle specified as `m * pi / n`
        ('angle_numerator', IMMEDIATE),
        ('angle_denominator', IMMEDIATE),
    ])


class ClassicalOpCommand(Command):
    _fields_ = add_padding([
        ('out', Register),
        ('a', Register),
        ('b', Register),
    ])


class ClassicalOpModCommand(Command):
    _fields_ = add_padding([
        ('out', Register),
        ('a', Register),
        ('b', Register),
        ('mod', Register),
    ])


class JumpCommand(Command):
    _fields_ = add_padding([
        ('line', INTEGER),
    ])


class BranchUnaryCommand(Command):
    _fields_ = add_padding([
        ('a', Register),
        ('line', INTEGER),
    ])


class BranchBinaryCommand(Command):
    _fields_ = add_padding([
        ('a', Register),
        ('b', Register),
        ('line', INTEGER),
    ])


class SetCommand(Command):
    _fields_ = add_padding([
        ('register', Register),
        ('value', INTEGER),
    ])


class LoadStoreCommand(Command):
    _fields_ = add_padding([
        ('register', Register),
        ('entry', ArrayEntry),
    ])


class LeaCommand(Command):
    _fields_ = add_padding([
        ('register', Register),
        ('address', Address),
    ])


class SingleArrayEntryCommand(Command):
    _fields_ = add_padding([
        ('array_entry', ArrayEntry),
    ])


class SingleArraySliceCommand(Command):
    _fields_ = add_padding([
        ('array_slice', ArraySlice),
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


class RetArrCommand(Command):
    _fields_ = add_padding([
        ('address', Address),
    ])


class CreateEPRCommand(Command):
    _fields_ = add_padding([
        ('remote_node_id', Register),
        ('epr_socket_id', Register),
        ('qubit_address_array', Register),
        ('arg_array', Register),
        ('ent_info_array', Register),
    ])


class RecvEPRCommand(Command):
    _fields_ = add_padding([
        ('remote_node_id', Register),
        ('epr_socket_id', Register),
        ('qubit_address_array', Register),
        ('ent_info_array', Register),
    ])


COMMANDS = [
    SingleQubitCommand,
    TwoQubitCommand,
    MeasCommand,
    RotationCommand,
    ClassicalOpCommand,
    JumpCommand,
    BranchUnaryCommand,
    BranchBinaryCommand,
    SetCommand,
    LoadStoreCommand,
    SingleArrayEntryCommand,
    SingleArraySliceCommand,
    SingleRegisterCommand,
    ArrayCommand,
    CreateEPRCommand,
    RecvEPRCommand,
]
