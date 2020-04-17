from copy import copy

from netqasm.encoding import REG_INDEX_BITS
from netqasm.parsing import parse_register, parse_address
from netqasm.subroutine import Constant, Symbols, Command
from netqasm.instructions import Instruction


class NoValueError(RuntimeError):
    pass


class NonConstantIndexError(RuntimeError):
    pass


def as_int_when_value(cls):
    """A decorator for the class `Future` which makes is behave like an `int`
    when the property `value` is not `None`.
    """
    def wrap_method(method_name):
        """Returns a new method for the class given a method name"""
        int_method = getattr(int, method_name)

        def new_method(self, *args, **kwargs):
            """Checks if the value is set, other raises an error"""
            value = self.value
            if value is None:
                raise NoValueError(f"The object '{repr(self)}' has no value yet, "
                                   "consider flusing the current subroutine")
            return int_method(value, *args, **kwargs)

        return new_method

    method_names = [
        "__abs__",
        "__add__",
        "__and__",
        "__bool__",
        "__ceil__",
        "__divmod__",
        "__eq__",
        "__float__",
        "__floor__",
        "__floordiv__",
        "__ge__",
        "__gt__",
        "__hash__",
        "__int__",
        "__invert__",
        "__le__",
        "__lshift__",
        "__lt__",
        "__mod__",
        "__mul__",
        "__ne__",
        "__neg__",
        "__or__",
        "__pos__",
        "__pow__",
        "__radd__",
        "__rand__",
        "__rdivmod__",
        "__rfloordiv__",
        "__rlshift__",
        "__rmod__",
        "__rmul__",
        "__ror__",
        "__round__",
        "__rpow__",
        "__rrshift__",
        "__rshift__",
        "__rsub__",
        "__rtruediv__",
        "__rxor__",
        "__sub__",
        "__truediv__",
        "__xor__",
        "bit_length",
        "conjugate",
        "denominator",
        "imag",
        "numerator",
        "real",
        "to_bytes",
    ]
    for method_name in method_names:
        setattr(cls, method_name, wrap_method(method_name))
    return cls


@as_int_when_value
class Future(int):
    @classmethod
    def __new__(cls, *args, **kwargs):
        return int.__new__(cls, 0)

    def __init__(self, connection, address, index):
        self._value = None
        self._connection = connection
        self._address = address
        self._index = index

    def __str__(self):
        value = self.value
        if value is None:
            return (f"{self.__class__.__name__} to be stored in array with address "
                    f"{self._address} at index {self._index}.\n"
                    "To access the value, the subroutine must first be executed which can be done by flushing.")
        else:
            return str(value)

    def __repr__(self):
        return f"{self.__class__} with value={self.value}"

    @property
    def value(self):
        if self._value is not None:
            return self._value
        # TODO
        # if self._address is None:
        #     raise NoValueError(f"{self.__class__.__name__} was not assigned an array address, "
        #                        "to for example use a measure outcome give it an address and index "
        #                        "when calling measure, e.g.:\n"
        #                        "\tarray = connection.new_array(1)"
        #                        "\tm = q.measure(address=array.address, index=0)")
        if not isinstance(self._index, int):
            raise NonConstantIndexError("index is not constant and cannot be resolved")
        value = self._connection._shared_memory.get_array_part(address=self._address, index=self._index)
        if value is not None:
            self._value = value
        return value

    def add(self, other, mod=None):
        if not isinstance(other, int):
            raise NotImplementedError
        tmp_register = parse_register(f"R{2 ** REG_INDEX_BITS - 1}")
        address_entry = parse_address(f"{Symbols.ADDRESS_START}{self._address}[{self._index}]")
        add_operands = [
            tmp_register,
            tmp_register,
            Constant(other),
        ]
        if mod is None:
            add_instr = Instruction.ADD
        else:
            if not isinstance(mod, int):
                raise NotImplementedError
            add_instr = Instruction.ADDM
            add_operands.append(Constant(mod))

        commands = [
            Command(
                instruction=Instruction.LOAD,
                operands=[
                    tmp_register,
                    address_entry,
                ],
            ),
            Command(
                instruction=add_instr,
                operands=add_operands
            ),
            Command(
                instruction=Instruction.STORE,
                operands=[
                    tmp_register,
                    copy(address_entry),
                ],
            ),
        ]
        self._connection.put_commands(commands)


class Array:
    def __init__(self, connection, length, address):
        assert isinstance(length, int) and length > 0, f"{length} is not a valid length"
        self._connection = connection
        self._length = length
        self._address = address

    def __len__(self):
        return self._length

    def __getitem__(self, index):
        return self._connection._shared_memory.get_array_part(address=self._address, index=index)

    @property
    def address(self):
        return self._address
