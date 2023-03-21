from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Union

from netqasm.lang import encoding
from netqasm.lang.encoding import RegisterName
from netqasm.lang.symbols import Symbols


class Operand:
    pass


@dataclass(eq=True, frozen=True)
class Immediate(Operand):
    value: int

    def __str__(self):
        return str(self.value)


class RegisterMeta:
    @classmethod
    def prefixes(cls) -> List[str]:
        return ["R", "C", "Q", "M"]

    @classmethod
    def parse(cls, name: str) -> Tuple[RegisterName, int]:
        assert len(name) >= 2
        assert name[0] in cls.prefixes()
        group = RegisterName[name[0]]
        index = int(name[1:])
        assert index < 16
        return group, index


@dataclass(eq=True, frozen=True)
class Register(Operand):
    name: RegisterName
    index: int

    def _assert_types(self):
        assert isinstance(self.name, RegisterName)
        assert isinstance(self.index, int)

    def __str__(self):
        return f"{self.name.name}{self.index}"

    @classmethod
    def from_str(cls, name: str) -> Register:
        reg_name, index = RegisterMeta.parse(name)
        return Register(reg_name, index)

    @property
    def cstruct(self):
        self._assert_types()
        return encoding.Register(self.name.value, self.index)

    def __bytes__(self):
        return bytes(self.cstruct)

    @classmethod
    def from_raw(cls, raw: encoding.Register):
        reg_name = RegisterName(raw.register_name)
        return cls(name=reg_name, index=raw.register_index)


@dataclass(eq=True, frozen=True)
class Address(Operand):
    address: Union[int, str]

    def _assert_types(self):
        assert isinstance(self.address, int)

    def __str__(self):
        return f"{Symbols.ADDRESS_START}{self.address}"

    @property
    def cstruct(self):
        self._assert_types()
        return encoding.Address(self.address)

    def __bytes__(self):
        return bytes(self.cstruct)

    @classmethod
    def from_raw(cls, raw: encoding.Address):
        return cls(address=raw.address)


@dataclass
class ArrayEntry(Operand):
    address: Address
    index: Union[Register, int]  # Can ONLY be int when in a "ProtoSubroutine"

    def __post_init__(self):
        if isinstance(self.address, int):
            self.address = Address(self.address)

    def _assert_types(self):
        assert isinstance(self.address, Address)
        assert isinstance(self.index, Register)

    def __str__(self):
        index = f"{Symbols.INDEX_BRACKETS[0]}{self.index}{Symbols.INDEX_BRACKETS[1]}"
        return f"{self.address}{index}"

    @property
    def cstruct(self):
        self._assert_types()
        return encoding.ArrayEntry(
            self.address.cstruct,
            self.index.cstruct,
        )

    def __bytes__(self):
        return bytes(self.cstruct)

    @classmethod
    def from_raw(cls, raw: encoding.ArrayEntry):
        addr = Address.from_raw(raw.address)
        index = Register.from_raw(raw.index)
        entry = cls(address=addr, index=index)
        return entry


@dataclass
class ArraySlice(Operand):
    address: Address
    start: Union[Register, int]  # Can ONLY be int when in a "ProtoSubroutine"
    stop: Union[Register, int]  # Can ONLY be int when in a "ProtoSubroutine"

    def __post_init__(self):
        if isinstance(self.address, int):
            self.address = Address(self.address)

    def _assert_types(self):
        assert isinstance(self.address, Address)
        assert isinstance(self.start, Register)
        assert isinstance(self.stop, Register)

    def __str__(self):
        index = f"{Symbols.INDEX_BRACKETS[0]}{self.start}{Symbols.SLICE_DELIM}{self.stop}{Symbols.INDEX_BRACKETS[1]}"
        return f"{self.address}{index}"

    @property
    def cstruct(self):
        self._assert_types()
        return encoding.ArraySlice(
            self.address.cstruct,
            self.start.cstruct,
            self.stop.cstruct,
        )

    def __bytes__(self):
        return bytes(self.cstruct)

    @classmethod
    def from_raw(cls, raw: encoding.ArraySlice):
        addr = Address.from_raw(raw.address)
        start = Register.from_raw(raw.start)
        stop = Register.from_raw(raw.stop)
        return cls(address=addr, start=start, stop=stop)


@dataclass(eq=True, frozen=True)
class Label:
    name: str

    def _assert_types(self):
        assert isinstance(self.name, str)

    def __str__(self):
        return self.name


@dataclass(eq=True, frozen=True)
class Template(Operand):
    """An operand that does not have a concrete value (it can be filled in later)."""

    name: str

    def _assert_types(self):
        assert isinstance(self.name, str)

    def __str__(self):
        return "{" + self.name + "}"
