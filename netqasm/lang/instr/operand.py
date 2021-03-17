from dataclasses import dataclass

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


@dataclass(eq=True, frozen=True)
class Register(Operand):
    name: RegisterName
    index: int

    def _assert_types(self):
        assert isinstance(self.name, RegisterName)
        assert isinstance(self.index, int)

    def __str__(self):
        return f"{self.name.name}{self.index}"

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
    address: int

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
    index: Register

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
    start: Register
    stop: Register

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
