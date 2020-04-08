from enum import Enum, auto
import ctypes


FIELD_TYPE = ctypes.c_uint8
FIELD_BYTES = len(bytes(FIELD_TYPE()))
NUM_FIELDS = 5
COMMAND_BYTES = FIELD_BYTES * (NUM_FIELDS + 1)

# Num bits in field
_FIELD_BITS = 8 * FIELD_BYTES
# Num bits in tp of value
_TP_BITS = 1
# Num bits in register name
_REG_NAME_BITS = 2
# Num bits in register index
_REG_INDEX_BITS = 4


class ValueType(Enum):
    CONSTANT = 0
    REGISTER = 1


# CONSTANT = ctypes.c_int32


class Constant(ctypes.Structure):
    _fields_ = [
        ('tp', FIELD_TYPE, _TP_BITS),
        ('value', FIELD_TYPE, _FIELD_BITS - _TP_BITS),
    ]

    TP = ValueType.CONSTANT

    def __init__(self, value=0):
        super().__init__(self.__class__.TP.value)
        self.value = value


class RegisterName(Enum):
    # Standard register
    R = 0
    # Register for constants
    C = auto()
    # Qubit addresses
    Q = auto()
    # Measurment outcomes
    M = auto()


class Register(ctypes.Structure):
    _fields_ = [
        ('tp', FIELD_TYPE, _TP_BITS),
        ('register_name', FIELD_TYPE, _REG_NAME_BITS),
        ('register_index', FIELD_TYPE, _REG_INDEX_BITS),
        ('padding', FIELD_TYPE, _FIELD_BITS - _TP_BITS - _REG_NAME_BITS - _REG_INDEX_BITS),
    ]

    TP = ValueType.REGISTER

    def __init__(self, register_name=0, register_index=0):
        super().__init__(self.__class__.TP.value)
        self.register_name = register_name
        self.register_index = register_index


class Value(ctypes.Structure):
    # A constant or register
    _fields_ = [
        ('tp', FIELD_TYPE, _TP_BITS),
        ('value', FIELD_TYPE, _FIELD_BITS - _TP_BITS),
    ]

    def __init__(self, value=None):
        if value is None:
            value = Constant()
        self._assert_type(value)
        value = int.from_bytes(bytes(value), 'little', signed=False)
        super().__init__(value)

    def _assert_type(self, value):
        if not (isinstance(value, Constant) or
                isinstance(value, Register) or
                isinstance(value, Value)):
            raise TypeError(f"expected Constant or Register, got {type(value)}")

    def to_tp(self):
        value_type = ValueType(self.tp)
        if value_type == ValueType.CONSTANT:
            return Constant.from_buffer_copy(bytes(self))
        else:
            return Register.from_buffer_copy(bytes(self))


class Address(ctypes.Structure):
    _fields_ = [
        ('read_index', ctypes.c_bool),
        ('address', Value),
        ('index', Value),
    ]


class Command(ctypes.Structure):
    _fields_ = [
        ('id', FIELD_TYPE),
    ]

    ID = 0

    # Number of args (non-operands)
    num_args = 0

    def __init__(self, *args, **kwargs):
        super().__init__(self.ID, *args, **kwargs)


PADDING_FIELD = 'padding'


def add_padding(fields):
    """Used to add correct amount of padding for commands to make them fixed-length"""
    current_num_bytes = len(bytes(Command()))
    current_num_bytes += sum(len(bytes(field[1]())) for field in fields)
    total_num_bytes = COMMAND_BYTES
    pad_num_bytes = total_num_bytes - current_num_bytes
    assert pad_num_bytes >= 0
    new_fields = fields + [
        (PADDING_FIELD, ctypes.c_uint8 * pad_num_bytes)
    ]
    return new_fields


class SingleQubitCommand(Command):
    _fields_ = add_padding([
        ('qubit', Value),
    ])


class TwoQubitCommand(Command):
    _fields_ = add_padding([
        ('qubit1', Value),
        ('qubit2', Value),
    ])


class MeasCommand(Command):
    _fields_ = add_padding([
        ('qubit', Value),
        ('outcome', Value),
    ])


class RotationCommand(Command):
    _fields_ = add_padding([
        ('angle', Value),
        ('qubit', Value),
    ])

    num_args = 1


class ClassicalOpCommand(Command):
    _fields_ = add_padding([
        ('out', Value),
        ('a', Value),
        ('b', Value),
    ])


class ClassicalOpModCommand(Command):
    _fields_ = add_padding([
        ('mod', Value),
        ('out', Value),
        ('a', Value),
        ('b', Value),
    ])

    num_args = 1


class BranchCommand(Command):
    _fields_ = add_padding([
        ('a', Value),
        ('b', Value),
        ('line', Value),
    ])


class SetCommand(Command):
    _fields_ = add_padding([
        ('register', Value),
        ('value', Value),
    ])


class RegisterAddressCommand(Command):
    _fields_ = add_padding([
        ('register', Value),
        ('address', Address),
    ])


class SingleAddressCommand(Command):
    _fields_ = add_padding([
        ('address', Value),
    ])


class ArrayCommand(Command):
    _fields_ = add_padding([
        ('size', Value),
        ('address', Value),
    ])

    num_args = 1


class CreateEPRCommand(Command):
    _fields_ = add_padding([
        ('remote_node_id', Value),
        ('purpose_id', Value),
        ('qubit_address_array', Value),
        ('arg_array', Value),
        ('ent_info_array', Value),
    ])

    num_args = 2


class RecvEPRCommand(Command):
    _fields_ = add_padding([
        ('remote_node_id', Value),
        ('purpose_id', Value),
        ('qubit_address_array', Value),
        ('ent_info_array', Value),
    ])

    num_args = 2


COMMANDS = [
    SingleQubitCommand,
    TwoQubitCommand,
    MeasCommand,
    RotationCommand,
    ClassicalOpCommand,
    BranchCommand,
    SetCommand,
    RegisterAddressCommand,
    SingleAddressCommand,
    ArrayCommand,
    CreateEPRCommand,
    RecvEPRCommand,
]


def test_command_length():
    for command_class in COMMANDS:
        length = len(bytes(command_class()))
        print(f"{command_class.__name__}: {len(bytes(command_class()))}")
        field_width = len(bytes(FIELD_TYPE()))
        assert length == field_width * (NUM_FIELDS + 1)


def test_constant_register_length():
    len_constant = len(bytes(Constant()))
    len_register = len(bytes(Register()))
    assert len_constant == len_register
