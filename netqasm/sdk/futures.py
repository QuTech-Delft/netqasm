"""Abstractions for classical runtime values.

This module contains the `BaseFuture` class and its subclasses.
"""


from __future__ import annotations

import abc
from typing import TYPE_CHECKING, List, Optional, Union

from netqasm.lang import operand
from netqasm.lang.ir import GenericInstr, ICmd, Symbols
from netqasm.lang.operand import Address, ArrayEntry
from netqasm.lang.parsing import parse_address, parse_register
from netqasm.typedefs import T_Cmd
from netqasm.util.log import HostLine

if TYPE_CHECKING:
    from netqasm.lang import ir
    from netqasm.sdk import connection as sdkconn
    from netqasm.sdk.builder import Builder, SdkForEachContext, SdkIfContext

# Generic type for classical values (that may only get a value at runtime).
T_CValue = Union[int, "Future", "RegFuture"]


# Error types.
class NoValueError(RuntimeError):
    pass


class NonConstantIndexError(RuntimeError):
    pass


def as_int_when_value(cls):
    """A decorator for the `BaseFuture` class which makes is behave like an `int`
    when the property `value` is not `None`.
    """

    def wrap_method(method_name):
        """Return a new method for the class given a method name"""
        int_method = getattr(int, method_name)

        def new_method(self, *args, **kwargs):
            """Check if the value is set, otherwise raise an error"""
            value = self.value
            if value is None:
                raise NoValueError(
                    f"The object '{repr(self)}' has no value yet, "
                    "consider flusing the current subroutine"
                )
            try:
                if isinstance(*args, Future):
                    raise RuntimeError(
                        "Cannot directly do a binary operation on two Futures. "
                        "Convert them to `int`s first."
                    )
            except TypeError:
                pass
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
    """Base class for Future-like objects.

    A Future represents a classical value that becomes available at some point
    in the future. At the moment, a Future always represents an integer value.

    Futures have a `value` property that is either `None` (when the value is not yet
    available), or has a concrete integer value.
    Executing a subroutine on the quantum node controller makes the value property go
    from `None` to a concrete value, granted that the subroutine sets the value of
    whatever the Future represents.
    When the `value` property has a concrete value, the Future behaves like an `int`
    and can then also be used in Python expressions just like integers.

    Typically, a Future instance is obtained as the result of an SDK function, and not
    directly instantiated in application code.
    For example, calling `measure()` on a Qubit returns a Future representing the
    measurement outcome. Only after the subroutine containing the operations has been
    executed by the quantum node controller (by flushing the subroutine), the
    measurement outcome will have an actual value, and the Future can be resolved into
    an `int`.
    """

    @classmethod
    def __new__(cls, *args, **kwargs):
        return int.__new__(cls, 0)

    def __init__(self, connection: sdkconn.BaseNetQASMConnection):
        self._value: Optional[int] = None
        self._connection: sdkconn.BaseNetQASMConnection = connection

    def __repr__(self):
        return f"{self.__class__} with value={self.value}"

    @property
    def builder(self) -> Builder:
        return self._connection.builder

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
        """Add another value to this Future's value.

        The result is stored in this Future.

        Let the quantum node controller add a value to the value represented by this
        Future. The addition operation is compiled into a subroutine and is fully
        executed by the quantum node controller.
        This avoids the need to wait for a subroutine result (which resolves the
        Future's `value`) and then doing the addition on the Host.

        :param other: value to add to this Future's value
        :param mod: do the addition modulo `mod`
        """
        raise NotImplementedError(
            f"add is not implemented for {self.__class__.__name__}"
        )

    def if_eq(self, other: Optional[T_CValue]) -> SdkIfContext:
        return self.builder.sdk_new_if_context(
            condition=GenericInstr.BEQ, op0=self, op1=other
        )

    def if_ne(self, other: Optional[T_CValue]) -> SdkIfContext:
        return self.builder.sdk_new_if_context(
            condition=GenericInstr.BNE, op0=self, op1=other
        )

    def if_lt(self, other: Optional[T_CValue]) -> SdkIfContext:
        return self.builder.sdk_new_if_context(
            condition=GenericInstr.BLT, op0=self, op1=other
        )

    def if_ge(self, other: Optional[T_CValue]) -> SdkIfContext:
        return self.builder.sdk_new_if_context(
            condition=GenericInstr.BGE, op0=self, op1=other
        )

    def if_ez(self) -> SdkIfContext:
        return self.builder.sdk_new_if_context(
            condition=GenericInstr.BEZ, op0=self, op1=None
        )

    def if_nz(self) -> SdkIfContext:
        return self.builder.sdk_new_if_context(
            condition=GenericInstr.BNZ, op0=self, op1=None
        )


class Future(BaseFuture):
    """Represents a single array entry value that will become available in the future.

    See `BaseFuture` for more explanation about Futures.
    """

    @classmethod
    def __new__(cls, *args, **kwargs):
        return int.__new__(cls, 0)

    def __init__(
        self,
        connection: sdkconn.BaseNetQASMConnection,
        address: int,
        index: Union[int, Future, operand.Register, RegFuture],
    ):
        """Future constructor. Typically not used directly.

        :param connection: connection through which subroutines are sent that contain
            the array entry corresponding to this Future
        :param address: address of the array
        :param index: index in the array
        """
        super().__init__(connection=connection)
        self._address: int = address
        self._index: Union[int, Future, operand.Register, RegFuture] = index

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
        tmp_register = self.builder._mem_mgr.get_inactive_register(activate=True)
        load_commands = self.get_load_commands(tmp_register)
        store_commands = self._get_store_commands(tmp_register)

        other_tmp_register: Optional[operand.Register] = None
        other_operand: Union[int, operand.Register]  # empty declaration for type hints

        # If other is a Future, also load this into a temporary register
        if isinstance(other, Future):
            other_operand = self.builder._mem_mgr.get_inactive_register(activate=True)
            other_tmp_register = other_operand
            load_commands += other.get_load_commands(other_tmp_register)
            store_commands += other._get_store_commands(other_tmp_register)
        elif isinstance(other, operand.Register) or isinstance(other, int):
            other_operand = other
        else:
            raise NotImplementedError("for type {type(other)}")

        add_operands: List[ir.T_OperandUnion] = [
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

        self.builder._mem_mgr.remove_active_register(tmp_register)
        if other_tmp_register is not None:
            self.builder._mem_mgr.remove_active_register(other_tmp_register)

        self.builder.subrt_add_pending_commands(commands)

    def get_load_commands(self, register: operand.Register) -> List[T_Cmd]:
        """Return a list of PreSubroutine commands for loading this Future into
        the specified register."""
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
            tmp_register = self.builder._mem_mgr.get_inactive_register()
            # NOTE this might be many commands if the index is a future with a future index etc
            with self.builder._activate_register(tmp_register):
                access_index_cmds = self._index._get_access_commands(
                    instruction=GenericInstr.LOAD,
                    register=tmp_register,
                )
            commands += access_index_cmds
            index: Union[int, operand.Register] = tmp_register
        elif isinstance(self._index, RegFuture):
            assert (
                self._index.reg is not None
            ), "Trying to use RegFuture that has no value yet"
            index = self._index.reg
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

    def get_address_entry(self) -> ArrayEntry:
        """Convert this Future to an ArrayEntry object to be used an instruction
        operand."""
        if isinstance(self._index, RegFuture):
            assert self._index.reg is not None, (
                f"cannot use RegFuture {self._index} as array index since "
                f"it does not yet have a value"
            )
            return ArrayEntry(Address(self._address), self._index.reg)
        elif isinstance(self._index, int) or isinstance(self._index, operand.Register):
            return ArrayEntry(Address(self._address), self._index)
        else:
            assert False, f"index type {self._index} not supported"


class RegFuture(BaseFuture):
    """Represents a single register value that will become available in the future.

    See `BaseFuture` for more explanation about Futures.
    """

    def __init__(
        self,
        connection: sdkconn.BaseNetQASMConnection,
        reg: Optional[operand.Register] = None,
    ):
        """RegFuture constructor. Typically not used directly.

        :param connection: connection through which subroutines are sent that contain
            the array entry corresponding to this Future
        :param reg: specific NetQASM register that will hold the Future's value.
            If None, a suitable register is automatically used.
        """
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
            other_operand = self.builder._mem_mgr.get_inactive_register(activate=True)
            other_tmp_register = other_operand
            load_commands += other.get_load_commands(other_tmp_register)
            store_commands += other._get_store_commands(other_tmp_register)
        elif isinstance(other, operand.Register) or isinstance(other, int):
            other_operand = other
        else:
            raise NotImplementedError("for type {type(other)}")

        add_operands: List[ir.T_OperandUnion] = [
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
            self.builder._mem_mgr.remove_active_register(other_tmp_register)

        self.builder.subrt_add_pending_commands(commands)


class Array:
    """Wrapper around an array in Shared Memory.

    An `Array` instance provides methods to inspect and operate on an array that
    exists in shared memory.
    They are typically obtained as return values to certain SDK methods.

    Elements or slices of the array can be captured as Futures.
    """

    def __init__(
        self,
        connection: sdkconn.BaseNetQASMConnection,
        length: int,
        address: int,
        init_values: Optional[List[Optional[int]]] = None,
        lineno: Optional[HostLine] = None,
    ):
        """Array constructor. Typically not used directly.

        :param connection: connection of the application this array is part of
        :param length: length of the array
        :param address: address of the array
        :param init_values: initial values of the array. Must have length `length`.
        :param lineno: line number where the array is created in the Python source code
        """
        if init_values is not None:
            if not all((isinstance(x, int) or x is None) for x in init_values):
                raise TypeError("Array needs to consist of int's or None's")
            length = len(init_values)
        assert isinstance(length, int) and length > 0, f"{length} is not a valid length"
        self._connection: sdkconn.BaseNetQASMConnection = connection
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

    @property
    def builder(self) -> Builder:
        return self._connection.builder

    def get_future_index(
        self, index: Union[int, str, operand.Register, RegFuture]
    ) -> Future:
        """Get a Future representing a particular array element"""
        if isinstance(index, str):
            index = parse_register(index)
        return Future(
            connection=self._connection,
            address=self._address,
            index=index,
        )

    def get_future_slice(self, s: slice) -> List[Future]:
        """Get a list of Futures each representing one element in a particular
        array slice"""
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

    def foreach(self) -> SdkForEachContext:
        """Create a context of code that gets called for each element in the array.

        Returns a future of the array value at the current index.

        Code inside the context *must* be compilable to NetQASM, that is,
        it should only contain quantum operations and/or classical values that are
        are stored in shared memory (arrays and registers).
        No classical communication is allowed.

        Example:

        .. code-block::

            with NetQASMConnection(app_name="alice") as alice:
                outcomes = alice.new_array(10)
                values = alice.new_array(
                    10,
                    init_values=[random.randint(0, 1) for _ in range(10)]
                )
                with values.foreach() as v:
                    q = Qubit(alice)
                    with v.if_eq(1):
                        q.H()
                    q.measure(future=outcomes.get_future_index(i))
        """
        return self.builder.sdk_new_foreach_context(array=self, return_index=False)

    def enumerate(self) -> SdkForEachContext:
        """Create a context of code that gets called for each element in the array
        and includes a counter.

        Returns a tuple (`index`, `future`) where `future` is a Future of the array
        value at the current index.

        Code inside the context *must* be compilable to NetQASM, that is,
        it should only contain quantum operations and/or classical values that are
        are stored in shared memory (arrays and registers).
        No classical communication is allowed.

        Example:

        .. code-block::

            with NetQASMConnection(app_name="alice") as alice:
                outcomes = alice.new_array(10)
                values = alice.new_array(
                    10,
                    init_values=[random.randint(0, 1) for _ in range(10)]
                )
                with values.enumerate() as (i, v):
                    q = Qubit(alice)
                    with v.if_eq(1):
                        q.H()
                    q.measure(future=outcomes.get_future_index(i))
        """
        return self.builder.sdk_new_foreach_context(array=self, return_index=True)

    def undefine(self) -> None:
        """Undefine (i.e. set to 'None') all elements in the array."""
        self.builder._build_cmds_undefine_array(self)
