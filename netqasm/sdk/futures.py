"""TODO write about futures"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING, List, Optional, Union

from netqasm.lang import operand
from netqasm.lang.ir import BranchLabel, GenericInstr, ICmd, Symbols
from netqasm.lang.parsing import parse_address, parse_register
from netqasm.util.log import HostLine

if TYPE_CHECKING:
    from netqasm.lang.ir import T_OperandUnion
    from netqasm.sdk.connection import BaseNetQASMConnection

T_Cmd = Union[ICmd, BranchLabel]
T_CValue = Union[int, "Future", "RegFuture"]


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
                raise NoValueError(
                    f"The object '{repr(self)}' has no value yet, "
                    "consider flusing the current subroutine"
                )
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
class BaseFuture(int):
    @classmethod
    def __new__(cls, *args, **kwargs):
        return int.__new__(cls, 0)

    def __init__(self, connection: BaseNetQASMConnection):
        self._value: Optional[int] = None
        self._connection: BaseNetQASMConnection = connection

    def __repr__(self):
        return f"{self.__class__} with value={self.value}"

    @property
    def value(self) -> Optional[int]:
        """Get the value of the future.
        If it's not set yet, `None` is returned."""
        if self._value is not None:
            return self._value
        else:
            return self._try_get_value()

    @abc.abstractmethod
    def _try_get_value(self) -> Optional[int]:
        raise NotImplementedError

    def add(
        self,
        other: Union[int, str, operand.Register, BaseFuture],
        mod: Optional[int] = None,
    ) -> None:
        """Adds another integer to this by appending to appropriate instruction to
        the current subroutine.
        Note that `self` does not need to have a value yet.
        """
        raise NotImplementedError(f"add is not implement for {self.__class__.__name__}")

    def if_eq(self, other: Optional[T_CValue]) -> _IfContext:
        return _IfContext(
            connection=self._connection,
            condition=GenericInstr.BEQ,
            a=self,
            b=other,
        )

    def if_ne(self, other: Optional[T_CValue]) -> _IfContext:
        return _IfContext(
            connection=self._connection,
            condition=GenericInstr.BNE,
            a=self,
            b=other,
        )

    def if_lt(self, other: Optional[T_CValue]) -> _IfContext:
        return _IfContext(
            connection=self._connection,
            condition=GenericInstr.BLT,
            a=self,
            b=other,
        )

    def if_ge(self, other: Optional[T_CValue]) -> _IfContext:
        return _IfContext(
            connection=self._connection,
            condition=GenericInstr.BGE,
            a=self,
            b=other,
        )

    def if_ez(self) -> _IfContext:
        return _IfContext(
            connection=self._connection,
            condition=GenericInstr.BEZ,
            a=self,
            b=None,
        )

    def if_nz(self) -> _IfContext:
        return _IfContext(
            connection=self._connection,
            condition=GenericInstr.BNZ,
            a=self,
            b=None,
        )


class Future(BaseFuture):
    @classmethod
    def __new__(cls, *args, **kwargs):
        return int.__new__(cls, 0)

    def __init__(
        self,
        connection: BaseNetQASMConnection,
        address: int,
        index: Union[int, Future, operand.Register],
    ):
        """
        Future(connection, address, index)
        TODO write doc-string
        """
        super().__init__(connection=connection)
        self._address: int = address
        self._index: Union[int, Future, operand.Register] = index

    def __str__(self) -> str:
        value = self.value
        if value is None:
            return (
                f"{self.__class__.__name__} to be stored in array with address "
                f"{self._address} at index {self._index}.\n"
                "To access the value, the subroutine must first be executed which can be done by flushing."
            )
        else:
            return str(value)

    def _try_get_value(self) -> Optional[int]:
        if not isinstance(self._index, int):
            raise NonConstantIndexError("index is not constant and cannot be resolved")
        value = self._connection.shared_memory.get_array_part(
            address=self._address, index=self._index
        )
        if not isinstance(value, int) and value is not None:
            raise RuntimeError(
                f"Something went wrong: future value {value} is not an int or None"
            )
        if value is not None:
            self._value = value
        return value

    def add(
        self,
        other: Union[int, str, operand.Register, BaseFuture],
        mod: Optional[int] = None,
    ) -> None:
        if isinstance(other, str):
            other = parse_register(other)

        # Store self in a temporary register
        tmp_register = self._connection._builder._get_inactive_register(activate=True)
        load_commands = self._get_load_commands(tmp_register)
        store_commands = self._get_store_commands(tmp_register)

        other_tmp_register: Optional[operand.Register] = None
        other_operand: Union[int, operand.Register]  # empty declaration for type hints

        # If other is a Future, also load this into a temporary register
        if isinstance(other, Future):
            other_operand = self._connection._builder._get_inactive_register(
                activate=True
            )
            other_tmp_register = other_operand
            load_commands += other._get_load_commands(other_tmp_register)
            store_commands += other._get_store_commands(other_tmp_register)
        elif isinstance(other, operand.Register) or isinstance(other, int):
            other_operand = other
        else:
            raise NotImplementedError("for type {type(other)}")

        add_operands: List[T_OperandUnion] = [
            tmp_register,
            tmp_register,
            other_operand,
        ]
        if mod is None:
            add_instr = GenericInstr.ADD
        else:
            if not isinstance(mod, int):
                raise NotImplementedError
            add_instr = GenericInstr.ADDM
            add_operands.append(mod)

        commands = (
            load_commands
            + [
                ICmd(
                    instruction=add_instr,
                    operands=add_operands,
                )
            ]
            + store_commands
        )

        self._connection._builder._remove_active_register(tmp_register)
        if other_tmp_register is not None:
            self._connection._builder._remove_active_register(other_tmp_register)

        self._connection._builder.add_pending_commands(commands)

    def _get_load_commands(self, register: operand.Register) -> List[T_Cmd]:
        return self._get_access_commands(GenericInstr.LOAD, register)

    def _get_store_commands(self, register: operand.Register) -> List[T_Cmd]:
        return self._get_access_commands(GenericInstr.STORE, register)

    def _get_access_commands(
        self, instruction: GenericInstr, register: operand.Register
    ) -> List[T_Cmd]:
        assert (
            instruction == GenericInstr.LOAD or instruction == GenericInstr.STORE
        ), "Not an access instruction"
        commands = []
        if isinstance(self._index, Future):
            if self._connection is not self._index._connection:
                raise RuntimeError(
                    "Future-index must be from the same connection as the future itself"
                )
            tmp_register = self._connection._builder._get_inactive_register()
            # NOTE this might be many commands if the index is a future with a future index etc
            with self._connection._builder._activate_register(tmp_register):
                access_index_cmds = self._index._get_access_commands(
                    instruction=GenericInstr.LOAD,
                    register=tmp_register,
                )
            commands += access_index_cmds
            index: Union[int, operand.Register] = tmp_register
        elif isinstance(self._index, int) or isinstance(self._index, operand.Register):
            index = self._index
        else:
            raise TypeError(
                f"Cannot use type {type(self._index)} as index to load future"
            )
        address_entry = parse_address(
            f"{Symbols.ADDRESS_START}{self._address}[{index}]"
        )
        access_cmd = ICmd(
            instruction=instruction,
            operands=[
                register,
                address_entry,
            ],
        )
        commands.append(access_cmd)
        return commands


class RegFuture(BaseFuture):
    def __init__(
        self, connection: BaseNetQASMConnection, reg: Optional[operand.Register] = None
    ):
        """RegFuture(connection, reg=None)
        TODO doc-string"""
        super().__init__(connection=connection)
        self._reg: Optional[operand.Register] = reg

    @property
    def reg(self) -> Optional[operand.Register]:
        return self._reg

    @reg.setter
    def reg(self, new_val: operand.Register) -> None:
        self._reg = new_val

    def __str__(self) -> str:
        assert self.reg is not None
        value = self.value
        if value is None:
            return (
                f"{self.__class__.__name__} to be stored in reg {self.reg} "
                "To access the value, the subroutine must first be executed which can be done by flushing."
            )
        else:
            return str(value)

    def _try_get_value(self) -> Optional[int]:
        assert self.reg is not None
        try:
            value = self._connection.shared_memory.get_register(self.reg)
        except KeyError:
            return None
        if value is not None:
            self._value = value
        return value

    def add(
        self,
        other: Union[int, str, operand.Register, BaseFuture],
        mod: Optional[int] = None,
    ) -> None:
        assert self.reg is not None
        if isinstance(other, str):
            other = parse_register(other)

        # Store self in a temporary register
        load_commands = []
        store_commands = []

        other_tmp_register: Optional[operand.Register] = None
        other_operand: Union[int, operand.Register]  # empty declaration for type hints

        # If other is a Future, also load this into a temporary register
        if isinstance(other, Future):
            other_operand = self._connection._builder._get_inactive_register(
                activate=True
            )
            other_tmp_register = other_operand
            load_commands += other._get_load_commands(other_tmp_register)
            store_commands += other._get_store_commands(other_tmp_register)
        elif isinstance(other, operand.Register) or isinstance(other, int):
            other_operand = other
        else:
            raise NotImplementedError("for type {type(other)}")

        add_operands: List[T_OperandUnion] = [
            self.reg,
            self.reg,
            other_operand,
        ]
        if mod is None:
            add_instr = GenericInstr.ADD
        else:
            if not isinstance(mod, int):
                raise NotImplementedError
            add_instr = GenericInstr.ADDM
            add_operands.append(mod)

        commands = (
            load_commands
            + [
                ICmd(
                    instruction=add_instr,
                    operands=add_operands,
                )
            ]
            + store_commands
        )

        if other_tmp_register is not None:
            self._connection._builder._remove_active_register(other_tmp_register)

        self._connection._builder.add_pending_commands(commands)


class Array:
    def __init__(
        self,
        connection: BaseNetQASMConnection,
        length: int,
        address: int,
        init_values: Optional[List[Optional[int]]] = None,
        lineno: Optional[HostLine] = None,
    ):
        """Array(connection, length, address, init_values=None, lineno=None)
        TODO write doc-string
        """
        if init_values is not None:
            if not all((isinstance(x, int) or x is None) for x in init_values):
                raise TypeError("Array needs to consist of int's or None's")
            length = len(init_values)
        assert isinstance(length, int) and length > 0, f"{length} is not a valid length"
        self._connection: BaseNetQASMConnection = connection
        self._length: int = length
        self._address: int = address
        self._init_values: Optional[List[Optional[int]]] = init_values
        self._lineno: Optional[HostLine] = lineno

    @property
    def lineno(self) -> Optional[HostLine]:
        """What line in host application file initiated this array"""
        return self._lineno

    def __len__(self) -> int:
        return self._length

    def __getitem__(
        self, index: Union[int, slice]
    ) -> Union[None, int, List[Optional[int]]]:
        return self._connection.shared_memory.get_array_part(
            address=self._address, index=index
        )

    @property
    def address(self) -> int:
        return self._address

    def get_future_index(self, index: Union[int, str, operand.Register]) -> Future:
        """TODO doc-string"""
        if isinstance(index, str):
            index = parse_register(index)
        return Future(
            connection=self._connection,
            address=self._address,
            index=index,
        )

    def get_future_slice(self, s: slice) -> List[Future]:
        """TODO doc-string"""
        range_args = []
        for attr in ["start", "stop", "step"]:
            x = getattr(s, attr)
            if x is not None:
                if not isinstance(x, int):
                    raise NotImplementedError(
                        "Future slices can only be specified by integers at this point, "
                        f"not {type(x)}"
                    )
                range_args.append(x)
        return [self.get_future_index(index) for index in range(*range_args)]

    def foreach(self) -> _ForEachContext:
        """TODO doc-string"""
        return _ForEachContext(
            connection=self._connection,
            array=self,
            return_index=False,
        )

    def enumerate(self) -> _ForEachContext:
        """TODO doc-string"""
        return _ForEachContext(
            connection=self._connection,
            array=self,
            return_index=True,
        )


class _Context:

    next_id: int = 0

    @property
    @abc.abstractmethod
    def ENTER_METH(self):
        pass

    @property
    @abc.abstractmethod
    def EXIT_METH(self):
        pass

    def __init__(self, connection: BaseNetQASMConnection, **kwargs):
        self._id: int = self._get_id()
        self._connection: BaseNetQASMConnection = connection
        self._kwargs = kwargs

    def _get_id(self) -> int:
        _Context.next_id += 1
        return _Context.next_id - 1

    def __enter__(self):
        return getattr(self._connection._builder, self.ENTER_METH)(
            context_id=self._id,
            **self._kwargs,
        )

    def __exit__(self, *args, **kwargs):
        getattr(self._connection._builder, self.EXIT_METH)(
            context_id=self._id,
            **self._kwargs,
        )


class _IfContext(_Context):

    ENTER_METH = "_enter_if_context"
    EXIT_METH = "_exit_if_context"

    def __init__(
        self,
        connection: BaseNetQASMConnection,
        condition: GenericInstr,
        a: Optional[T_CValue],
        b: Optional[T_CValue],
    ):
        super().__init__(
            connection=connection,
            condition=condition,
            a=a,
            b=b,
        )


class _ForEachContext(_Context):

    ENTER_METH = "_enter_foreach_context"
    EXIT_METH = "_exit_foreach_context"

    def __init__(
        self, connection: BaseNetQASMConnection, array: Array, return_index: bool
    ):
        super().__init__(
            connection=connection,
            array=array,
            return_index=return_index,
        )
