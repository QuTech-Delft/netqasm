from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from netqasm.lang import encoding
from netqasm.lang.operand import (
    Address,
    ArrayEntry,
    ArraySlice,
    Immediate,
    Operand,
    Register,
)
from netqasm.util.log import HostLine
from netqasm.util.string import rspaces

# Abstract base instruction types. Should not be instantiated directly.


@dataclass  # type: ignore
class NetQASMInstruction(ABC):
    """
    Base NetQASM instruction class.
    """

    id: int = -1
    mnemonic: str = ""
    lineno: Optional[HostLine] = None

    @property
    @abstractmethod
    def operands(self) -> List[Operand]:
        pass

    @classmethod
    @abstractmethod
    def deserialize_from(cls, raw: bytes) -> "NetQASMInstruction":
        pass

    @abstractmethod
    def serialize(self) -> bytes:
        pass

    @classmethod
    @abstractmethod
    def from_operands(cls, operands: List[Operand]) -> "NetQASMInstruction":
        pass

    def writes_to(self) -> List[Register]:
        """Returns a list of Registers that this instruction writes to"""
        return []

    def __str__(self):
        return self._build_str(show_lineno=False)

    @property
    def debug_str(self):
        return self._build_str(show_lineno=True)

    def _get_lineno_str(self):
        if self.lineno is None:
            lineno = "()"
        else:
            lineno = f"({self.lineno})"
        return f"{rspaces(lineno, min_chars=5)} "

    def _build_str(self, show_lineno=False):
        if show_lineno:
            lineno_str = self._get_lineno_str()
        else:
            lineno_str = ""
        return f"{lineno_str}{self._pretty_print()}"

    def _pretty_print(self):
        return f"{self.__class__}"


@dataclass
class NoOperandInstruction(NetQASMInstruction):
    """
    An instruction with no operands.
    """

    @property
    def operands(self) -> List[Operand]:
        return []

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.NoOperandCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        return cls(id=cls.id)

    def serialize(self) -> bytes:
        c_struct = encoding.NoOperandCommand(id=self.id)
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 0
        return cls(id=cls.id)

    def _pretty_print(self):
        return f"{self.mnemonic}"


@dataclass
class RegInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand.
    """

    reg: Register = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.reg)
        return cls(id=cls.id, reg=reg)

    def serialize(self) -> bytes:
        c_struct = encoding.RegCommand(id=self.id, reg=self.reg.cstruct)
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 1
        reg = operands[0]
        assert isinstance(reg, Register)
        return cls(id=cls.id, reg=reg)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)}"


@dataclass
class RegRegInstruction(NetQASMInstruction):
    """
    An instruction with 2 Register operands.
    """

    reg0: Register = None  # type: ignore
    reg1: Register = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegRegCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg0 = Register.from_raw(c_struct.reg0)
        reg1 = Register.from_raw(c_struct.reg1)
        return cls(reg0=reg0, reg1=reg1)

    def serialize(self) -> bytes:
        c_struct = encoding.RegRegCommand(
            id=self.id, reg0=self.reg0.cstruct, reg1=self.reg1.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 2
        reg0, reg1 = operands
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        return cls(reg0=reg0, reg1=reg1)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg0)} {str(self.reg1)}"


@dataclass
class RegImmImmInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand followed by 2 Immediate operands.
    """

    reg: Register = None  # type: ignore
    imm0: Immediate = None  # type: ignore
    imm1: Immediate = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.imm0, self.imm1]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegImmImmCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.reg)
        imm0 = Immediate(value=c_struct.imm0)
        imm1 = Immediate(value=c_struct.imm1)
        return cls(reg=reg, imm0=imm0, imm1=imm1)

    def serialize(self) -> bytes:
        c_struct = encoding.RegImmImmCommand(
            id=self.id, reg=self.reg.cstruct, imm0=self.imm0.value, imm1=self.imm1.value
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 3
        reg, imm0, imm1 = operands
        assert isinstance(reg, Register)
        assert isinstance(imm0, int)
        assert isinstance(imm1, int)
        return cls(reg=reg, imm0=Immediate(value=imm0), imm1=Immediate(value=imm1))

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.imm0)} {str(self.imm1)}"


@dataclass
class RegRegImmImmInstruction(NetQASMInstruction):
    """
    An instruction with 2 Register operands followed by 2 Immediate operands.
    """

    reg0: Register = None  # type: ignore
    reg1: Register = None  # type: ignore
    imm0: Immediate = None  # type: ignore
    imm1: Immediate = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1, self.imm0, self.imm1]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegRegImmImmCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg0 = Register.from_raw(c_struct.reg0)
        reg1 = Register.from_raw(c_struct.reg1)
        imm0 = Immediate(value=c_struct.imm0)
        imm1 = Immediate(value=c_struct.imm1)
        return cls(reg0=reg0, reg1=reg1, imm0=imm0, imm1=imm1)

    def serialize(self) -> bytes:
        c_struct = encoding.RegRegImmImmCommand(
            id=self.id,
            reg0=self.reg0.cstruct,
            reg1=self.reg1.cstruct,
            imm0=self.imm0.value,
            imm1=self.imm1.value,
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 4
        reg0, reg1, imm0, imm1 = operands
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        assert isinstance(imm0, int)
        assert isinstance(imm1, int)
        return cls(
            reg0=reg0, reg1=reg1, imm0=Immediate(value=imm0), imm1=Immediate(value=imm1)
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg0)} {str(self.reg1)} {str(self.imm0)} {str(self.imm1)}"


@dataclass
class RegRegRegInstruction(NetQASMInstruction):
    """
    An instruction with 3 Register operands.
    """

    reg0: Register = None  # type: ignore
    reg1: Register = None  # type: ignore
    reg2: Register = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1, self.reg2]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegRegRegCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg0 = Register.from_raw(c_struct.reg0)
        reg1 = Register.from_raw(c_struct.reg1)
        reg2 = Register.from_raw(c_struct.reg2)
        return cls(reg0=reg0, reg1=reg1, reg2=reg2)

    def serialize(self) -> bytes:
        c_struct = encoding.RegRegRegCommand(
            id=self.id,
            reg0=self.reg0.cstruct,
            reg1=self.reg1.cstruct,
            reg2=self.reg2.cstruct,
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 3
        reg0, reg1, reg2 = operands
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        assert isinstance(reg2, Register)
        return cls(reg0=reg0, reg1=reg1, reg2=reg2)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg0)} {str(self.reg1)} {str(self.reg2)}"


@dataclass
class RegRegRegRegInstruction(NetQASMInstruction):
    """
    An instruction with 4 Register operands.
    """

    reg0: Register = None  # type: ignore
    reg1: Register = None  # type: ignore
    reg2: Register = None  # type: ignore
    reg3: Register = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1, self.reg2, self.reg3]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegRegRegRegCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg0 = Register.from_raw(c_struct.reg0)
        reg1 = Register.from_raw(c_struct.reg1)
        reg2 = Register.from_raw(c_struct.reg2)
        reg3 = Register.from_raw(c_struct.reg3)
        return cls(reg0=reg0, reg1=reg1, reg2=reg2, reg3=reg3)

    def serialize(self) -> bytes:
        c_struct = encoding.RegRegRegRegCommand(
            id=self.id,
            reg0=self.reg0.cstruct,
            reg1=self.reg1.cstruct,
            reg2=self.reg2.cstruct,
            reg3=self.reg3.cstruct,
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 4
        reg0, reg1, reg2, reg3 = operands
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        assert isinstance(reg2, Register)
        assert isinstance(reg3, Register)
        return cls(
            reg0=reg0,
            reg1=reg1,
            reg2=reg2,
            reg3=reg3,
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg0)} {str(self.reg1)} {str(self.reg2)} {str(self.reg3)}"


@dataclass
class ImmInstruction(NetQASMInstruction):
    """
    An instruction with 1 Immediate operand.
    """

    imm: Immediate = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.imm]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.ImmCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        imm = Immediate(value=c_struct.imm)
        return cls(imm=imm)

    def serialize(self) -> bytes:
        c_struct = encoding.ImmCommand(id=self.id, imm=self.imm.value)
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 1
        imm = operands[0]
        assert isinstance(imm, int)
        return cls(imm=Immediate(value=imm))

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.imm)}"


@dataclass
class ImmImmInstruction(NetQASMInstruction):
    """
    An instruction with 2 Immediate operands.
    """

    imm0: Immediate = None  # type: ignore
    imm1: Immediate = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.imm0, self.imm1]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.ImmImmCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        imm0 = Immediate(value=c_struct.imm0)
        imm1 = Immediate(value=c_struct.imm1)
        return cls(imm0=imm0, imm1=imm1)

    def serialize(self) -> bytes:
        c_struct = encoding.ImmImmCommand(
            id=self.id, imm0=self.imm0.value, imm1=self.imm1.value
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 2
        imm0 = operands[0]
        imm1 = operands[1]
        assert isinstance(imm0, int)
        assert isinstance(imm1, int)
        return cls(imm0=Immediate(value=imm0), imm1=Immediate(value=imm1))

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.imm0)} {str(self.imm1)}"


@dataclass
class RegRegImmInstruction(NetQASMInstruction):
    """
    An instruction with 2 Register operands and one Immediate operand.
    """

    reg0: Register = None  # type: ignore
    reg1: Register = None  # type: ignore
    imm: Immediate = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1, self.imm]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegRegImmCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg0 = Register.from_raw(c_struct.reg0)
        reg1 = Register.from_raw(c_struct.reg1)
        imm = Immediate(value=c_struct.imm)
        return cls(reg0=reg0, reg1=reg1, imm=imm)

    def serialize(self) -> bytes:
        c_struct = encoding.RegRegImmCommand(
            id=self.id,
            reg0=self.reg0.cstruct,
            reg1=self.reg1.cstruct,
            imm=self.imm.value,
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 3
        reg0, reg1, imm = operands
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        assert isinstance(imm, int)
        return cls(reg0=reg0, reg1=reg1, imm=Immediate(value=imm))

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg0)} {str(self.reg1)} {str(self.imm)}"


@dataclass
class RegImmInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand and one Immediate operand.
    """

    reg: Register = None  # type: ignore
    imm: Immediate = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.imm]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegImmCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.reg)
        imm = Immediate(value=c_struct.imm)
        return cls(reg=reg, imm=imm)

    def serialize(self) -> bytes:
        c_struct = encoding.RegImmCommand(
            id=self.id, reg=self.reg.cstruct, imm=self.imm.value
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 2
        reg, imm = operands
        assert isinstance(reg, Register)
        assert isinstance(imm, int)
        return cls(reg=reg, imm=Immediate(value=imm))

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.imm)}"


@dataclass
class RegEntryInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand and one ArrayEntry operand.
    """

    reg: Register = None  # type: ignore
    entry: ArrayEntry = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.entry]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegEntryCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.reg)
        entry = ArrayEntry.from_raw(c_struct.entry)
        return cls(reg=reg, entry=entry)

    def serialize(self) -> bytes:
        c_struct = encoding.RegEntryCommand(
            id=self.id, reg=self.reg.cstruct, entry=self.entry.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 2
        reg, entry = operands
        assert isinstance(reg, Register)
        assert isinstance(entry, ArrayEntry)
        return cls(reg=reg, entry=entry)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.entry)}"


@dataclass
class RegAddrInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand and one Address operand.
    """

    reg: Register = None  # type: ignore
    address: Address = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.address]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RegAddrCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.reg)
        address = Address.from_raw(c_struct.addr)
        return cls(reg=reg, address=address)

    def serialize(self) -> bytes:
        c_struct = encoding.RegAddrCommand(
            id=self.id, reg=self.reg.cstruct, addr=self.address.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 2
        reg, addr = operands
        assert isinstance(reg, Register)
        assert isinstance(addr, Address)
        return cls(reg=reg, address=addr)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.address)}"


@dataclass
class ArrayEntryInstruction(NetQASMInstruction):
    """
    An instruction with 1 ArrayEntry operand and one Address operand.
    """

    entry: ArrayEntry = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.entry]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.ArrayEntryCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        entry = ArrayEntry.from_raw(c_struct.entry)
        return cls(entry=entry)

    def serialize(self) -> bytes:
        c_struct = encoding.ArrayEntryCommand(id=self.id, entry=self.entry.cstruct)
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 1
        entry = operands[0]
        assert isinstance(entry, ArrayEntry)
        return cls(entry=entry)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.entry)}"


@dataclass
class ArraySliceInstruction(NetQASMInstruction):
    """
    An instruction with 1 ArraySlice operand.
    """

    slice: ArraySlice = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.slice]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.ArraySliceCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        slice = ArraySlice.from_raw(c_struct.slice)
        return cls(slice=slice)

    def serialize(self) -> bytes:
        c_struct = encoding.ArraySliceCommand(id=self.id, slice=self.slice.cstruct)
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 1
        slice = operands[0]
        assert isinstance(slice, ArraySlice)
        return cls(slice=slice)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.slice)}"


@dataclass
class AddrInstruction(NetQASMInstruction):
    """
    An instruction with 1 Address operand.
    """

    address: Address = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.address]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.AddrCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        addr = Address.from_raw(c_struct.addr)
        return cls(address=addr)

    def serialize(self) -> bytes:
        c_struct = encoding.AddrCommand(id=self.id, addr=self.address.cstruct)
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 1
        addr = operands[0]
        assert isinstance(addr, Address)
        return cls(address=addr)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.address)}"


@dataclass
class Reg5Instruction(NetQASMInstruction):
    """
    An instruction with 5 Register operands.
    """

    reg0: Register = None  # type: ignore
    reg1: Register = None  # type: ignore
    reg2: Register = None  # type: ignore
    reg3: Register = None  # type: ignore
    reg4: Register = None  # type: ignore

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1, self.reg2, self.reg3, self.reg4]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.Reg5Command.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        return cls(
            reg0=Register.from_raw(c_struct.reg0),
            reg1=Register.from_raw(c_struct.reg1),
            reg2=Register.from_raw(c_struct.reg2),
            reg3=Register.from_raw(c_struct.reg3),
            reg4=Register.from_raw(c_struct.reg4),
        )

    def serialize(self) -> bytes:
        c_struct = encoding.Reg5Command(
            id=self.id,
            reg0=self.reg0.cstruct,
            reg1=self.reg1.cstruct,
            reg2=self.reg2.cstruct,
            reg3=self.reg3.cstruct,
            reg4=self.reg4.cstruct,
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 5
        reg0, reg1, reg2, reg3, reg4 = operands
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        assert isinstance(reg2, Register)
        assert isinstance(reg3, Register)
        assert isinstance(reg4, Register)
        return cls(
            reg0=reg0,
            reg1=reg1,
            reg2=reg2,
            reg3=reg3,
            reg4=reg4,
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg0)} {str(self.reg1)} {str(self.reg2)} \
{str(self.reg3)} {str(self.reg4)}"


@dataclass
class DebugInstruction(NetQASMInstruction):
    text: str = ""

    @property
    def operands(self) -> List[Operand]:
        pass

    @classmethod
    def deserialize_from(cls, raw: bytes):
        pass

    def serialize(self) -> bytes:
        return b""

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        pass

    def _pretty_print(self):
        return f"# {self.text}"
