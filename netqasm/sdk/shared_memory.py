"""Abstractions for the classical memory shared between the Host and
the quantum node controller.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from netqasm.lang import operand
from netqasm.lang.encoding import ADDRESS_BITS, REG_INDEX_BITS, RegisterName
from netqasm.lang.ir import Symbols
from netqasm.lang.parsing import parse_address, parse_register
from netqasm.runtime.settings import get_is_using_hardware


def _assert_within_width(value: int, width: int) -> None:
    if not get_is_using_hardware():
        # in simulation, don't care about overflow
        return
    min_value = -(2 ** (width - 1))
    max_value = 2 ** (width - 1) - 1
    if not min_value <= value <= max_value:
        raise OverflowError(f"value {value} does not fit into {width} bits")


class RegisterGroup:
    """A register group (like "R", or "Q") in shared memory."""

    def __init__(self):
        self._size: int = 2 ** REG_INDEX_BITS
        self._register: Dict[int, Optional[int]] = {}

    def __len__(self) -> int:
        return self._size

    def __str__(self) -> str:
        return str(self._register)

    def __setitem__(self, index: int, value: int) -> None:
        self._assert_within_length(index)
        _assert_within_width(value, ADDRESS_BITS)
        self._register[index] = value

    def __getitem__(self, index: int) -> Optional[int]:
        self._assert_within_length(index)
        return self._register.get(index)

    def _assert_within_length(self, index: int) -> None:
        if not (0 <= index < len(self)):
            raise IndexError(f"index {index} is not within 0 and {len(self)}")

    def _get_active_values(self) -> List[Tuple[int, int]]:
        return [
            (index, value)
            for index, value in self._register.items()
            if value is not None
        ]


def setup_registers() -> Dict[RegisterName, RegisterGroup]:
    return {reg_name: RegisterGroup() for reg_name in RegisterName}


class Arrays:
    def __init__(self):
        self._arrays: Dict[int, List[Optional[int]]] = {}

    # TODO add test for this
    def _get_active_values(self) -> List[Tuple[operand.ArrayEntry, int]]:
        values = []
        for address, array in self._arrays.items():
            for index, value in enumerate(array):
                if value is None:
                    continue
                address_entry = parse_address(
                    f"{Symbols.ADDRESS_START}{address}"
                    f"{Symbols.INDEX_BRACKETS[0]}{index}{Symbols.INDEX_BRACKETS[1]}"
                )
                if not isinstance(address_entry, operand.ArrayEntry):
                    raise RuntimeError(
                        f"Something went wrong: address_entry should be "
                        f"ArrayEntry but it is {type(address_entry)}"
                    )
                values.append((address_entry, value))
        return values

    def __str__(self) -> str:
        return str(self._arrays)

    def __setitem__(
        self,
        key: Tuple[int, Union[int, slice]],
        value: Union[None, int, List[Optional[int]]],
    ) -> None:
        address, index = self._extract_key(key)
        if isinstance(index, int):
            if isinstance(value, int):
                _assert_within_width(value, ADDRESS_BITS)
                _assert_within_width(index, ADDRESS_BITS)
        elif isinstance(index, slice):
            self._assert_list(value)
            if index.start is not None:
                _assert_within_width(index.start, ADDRESS_BITS)
            if index.stop is not None:
                _assert_within_width(index.stop, ADDRESS_BITS)
        else:
            raise TypeError(f"Cannot use {key} of type {type(key)} as an index")
        array = self._get_array(address)
        try:
            if isinstance(index, slice):
                assert isinstance(value, list)
                assert len(array[index]) == len(value), "value not of correct length"
            array[index] = value  # type: ignore
        except IndexError:
            raise IndexError(
                f"index {index} is out of range for array with address {address}"
            )

    def __getitem__(
        self, key: Tuple[int, Union[int, slice]]
    ) -> Union[None, int, List[Optional[int]]]:
        address, index = self._extract_key(key)
        try:
            array = self._get_array(address)
        except IndexError:
            return None

        try:
            value = array[index]
        except IndexError:
            raise IndexError(
                f"index {index} is out of range for array with address {address}"
            )
        return value

    def _get_array(self, address: int) -> List[Optional[int]]:
        if address not in self._arrays:
            raise IndexError(f"No array with address {address}")
        return self._arrays[address]

    def _set_array(self, address: int, array: List[Optional[int]]) -> None:
        if address not in self._arrays:
            raise IndexError(f"No array with address {address}")
        self._assert_list(array)
        self._arrays[address] = array

    def has_array(self, address: int) -> bool:
        return address in self._arrays

    @staticmethod
    def _extract_key(
        key: Tuple[int, Union[int, slice]]
    ) -> Tuple[int, Union[int, slice]]:
        try:
            address, index = key
        except (TypeError, ValueError):
            raise ValueError(
                "Can only access entries and slices of arrays, not the full array"
            )
        _assert_within_width(address, ADDRESS_BITS)
        return address, index

    @staticmethod
    def _assert_list(value: Any) -> None:
        if not isinstance(value, list):
            raise TypeError(f"expected 'list', not {type(value)}")
        for x in value:
            if x is not None:
                _assert_within_width(x, ADDRESS_BITS)
        _assert_within_width(len(value), ADDRESS_BITS)

    def init_new_array(self, address: int, length: int) -> None:
        # TODO, is it okay to overwrite the array if it exists?
        _assert_within_width(address, ADDRESS_BITS)
        self._arrays[address] = [None] * length


class SharedMemory:
    """Representation of the classical memory that is shared between the Host
    and the quantum node controller.

    Each application is associated with a single `SharedMemory`.
    Although the name contains "shared", it is typically only used in one "direction":
    the quantum node controller writes to it, and the Host reads from it.

    Shared memory consists of two types of memory: registers and arrays.
    The quantum node controller writes to the shared memory if it executes a "return"
    NetQASM instruction (`ret_reg` or `ret_arr`). This is typically done at the end
    of a subroutine. The Host can then read the values from the shared memory, which
    means that the Host effectively receives the returned values.

    When trying to use a value represented by a `Future`, it will try to get the value
    from the shared memory. So, *only* after the quantum node controller has executed
    a subroutine containing the relevant `ret_reg` or `ret_arr` NetQASM instruction,
    the shared memory is updated and the value from the Future can be used.

    The specific runtime context determines how a shared memory is implemented and
    by which component it is controlled. In the case of a physical setup, where the
    Host and the quantum node controller may be separate devices, "writing to the
    shared memory" may simply be "sending values from the quantum node controller to
    the Host". On the other hand, a simulator that runs the Host and the quantum node
    controller in the same process might e.g. use a global shared object.
    """

    def __init__(self):
        self._registers: Dict[RegisterName, RegisterGroup] = setup_registers()
        self._arrays: Arrays = Arrays()

    def __getitem__(
        self, key: Union[operand.Register, Tuple[int, Union[int, slice]], int]
    ) -> Union[None, int, List[Optional[int]]]:
        if isinstance(key, operand.Register):
            return self.get_register(key)
        elif isinstance(key, tuple):
            address, index = key
            return self.get_array_part(address, index)
        elif isinstance(key, int):
            return self._get_array(key)

    def get_register(self, register: Union[str, operand.Register]) -> Optional[int]:
        if isinstance(register, str):
            reg = parse_register(register)
        else:
            reg = register
        return self._registers[reg.name][reg.index]

    def set_register(self, register: Union[str, operand.Register], value: int) -> None:
        if isinstance(register, str):
            reg = parse_register(register)
        else:
            reg = register
        self._registers[reg.name][reg.index] = value

    def get_array_part(
        self, address: int, index: Union[int, slice]
    ) -> Union[None, int, List[Optional[int]]]:
        return self._arrays[address, index]

    def set_array_part(
        self,
        address: int,
        index: Union[int, slice],
        value: Union[None, int, List[Optional[int]]],
    ):
        self._arrays[address, index] = value

    def _get_array(self, address: int) -> List[Optional[int]]:
        return self._arrays._get_array(address)

    def init_new_array(
        self,
        address: int,
        length: int = 1,
        new_array: Optional[List[Optional[int]]] = None,
    ) -> None:
        if new_array is not None:
            length = len(new_array)
        self._arrays.init_new_array(address, length)
        if new_array is not None:
            self._arrays._set_array(address, new_array)

    def _get_active_values(
        self,
    ) -> List[Union[Tuple[operand.Register, int], Tuple[operand.ArrayEntry, int]]]:
        all_values: List[
            Union[Tuple[operand.Register, int], Tuple[operand.ArrayEntry, int]]
        ] = []
        for reg_name, reg in self._registers.items():
            act_reg_values = reg._get_active_values()
            reg_values = [
                (parse_register(f"{reg_name.name}{index}"), value)
                for index, value in act_reg_values
            ]
            all_values += reg_values
        all_values += self._arrays._get_active_values()
        return all_values


class SharedMemoryManager:
    """Global object that manages shared memories. Typically used by simulators.

    This class can be used as a global object that stores `SharedMemory` objects.
    Simulators that simulate Hosts and the quantum node controllers in the same
    process may use this to have a single location for creating and accessing shared
    memories.
    """

    _MEMORIES: Dict[Tuple[str, Optional[int]], Optional[SharedMemory]] = {}

    @classmethod
    def create_shared_memory(
        cls, node_name: str, key: Optional[int] = None
    ) -> SharedMemory:
        absolute_key = (node_name, key)
        if cls._MEMORIES.get(absolute_key) is not None:
            raise RuntimeError(
                f"Shared memory for (node, key): ({node_name}, {key}) already exists."
            )
        memory = SharedMemory()
        cls._MEMORIES[absolute_key] = memory
        return memory

    @classmethod
    def get_shared_memory(
        cls, node_name: str, key: Optional[int] = None
    ) -> Optional[SharedMemory]:
        absolute_key = (node_name, key)
        memory = cls._MEMORIES.get(absolute_key)
        return memory

    @classmethod
    def reset_memories(cls) -> None:
        for key in list(cls._MEMORIES.keys()):
            cls._MEMORIES.pop(key)
