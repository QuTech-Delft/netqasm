from dataclasses import dataclass
from typing import List
from abc import ABC, abstractmethod

from netqasm.string_util import rspaces
from netqasm import encoding
from netqasm.log_util import HostLine

from netqasm.instructions.operand import (
    Operand,
    Register,
    Immediate,
    Address,
    ArrayEntry,
    ArraySlice,
)

# Abstract base instruction types. Should not be instantiated directly.


@dataclass
class NetQASMInstruction(ABC):
    """
    Base NetQASM instruction class.
    """
    id: int = -1
    mnemonic: str = None
    lineno: HostLine = None

    @property
    @abstractmethod
    def operands(self) -> List[Operand]:
        pass

    @classmethod
    @abstractmethod
    def deserialize_from(cls, raw: bytes):
        pass

    @abstractmethod
    def serialize(self) -> bytes:
        pass

    @classmethod
    @abstractmethod
    def from_operands(cls, operands: List[Operand]):
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
class RegInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand.
    """
    reg: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.SingleQubitCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        register = Register.from_raw(c_struct.qubit)
        return cls(id=cls.id, reg=register)

    def serialize(self) -> bytes:
        c_struct = encoding.SingleQubitCommand(
            id=self.id,
            qubit=self.reg.cstruct
        )
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
    reg0: Register = None
    reg1: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.TwoQubitCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg0 = Register.from_raw(c_struct.qubit1)
        reg1 = Register.from_raw(c_struct.qubit2)
        return cls(reg0=reg0, reg1=reg1)

    def serialize(self) -> bytes:
        c_struct = encoding.TwoQubitCommand(
            id=self.id,
            qubit1=self.reg0.cstruct,
            qubit2=self.reg1.cstruct
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
    reg: Register = None
    imm0: Immediate = None
    imm1: Immediate = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.imm0, self.imm1]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RotationCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.qubit)
        imm0 = Immediate(value=c_struct.angle_numerator)
        imm1 = Immediate(value=c_struct.angle_denominator)
        return cls(reg=reg, imm0=imm0, imm1=imm1)

    def serialize(self) -> bytes:
        c_struct = encoding.RotationCommand(
            id=self.id,
            qubit=self.reg.cstruct,
            angle_numerator=self.imm0.value,
            angle_denominator=self.imm1.value
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 3
        reg, imm0, imm1 = operands
        assert isinstance(reg, Register)
        assert isinstance(imm0, int)
        assert isinstance(imm1, int)
        return cls(
            reg=reg,
            imm0=Immediate(value=imm0),
            imm1=Immediate(value=imm1)
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.imm0)} {str(self.imm1)}"


@dataclass
class RegRegRegInstruction(NetQASMInstruction):
    """
    An instruction with 3 Register operands.
    """
    reg0: Register = None
    reg1: Register = None
    reg2: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1, self.reg2]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.ClassicalOpCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg0 = Register.from_raw(c_struct.out)
        reg1 = Register.from_raw(c_struct.a)
        reg2 = Register.from_raw(c_struct.b)
        return cls(reg0=reg0, reg1=reg1, reg2=reg2)

    def serialize(self) -> bytes:
        c_struct = encoding.ClassicalOpCommand(
            id=self.id,
            out=self.reg0.cstruct,
            a=self.reg1.cstruct,
            b=self.reg2.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 3
        reg0, reg1, reg2 = operands
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        assert isinstance(reg2, Register)
        return cls(
            reg0=reg0,
            reg1=reg1,
            reg2=reg2
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg0)} {str(self.reg1)} {str(self.reg2)}"


@dataclass
class RegRegRegRegInstruction(NetQASMInstruction):
    """
    An instruction with 4 Register operands.
    """
    reg0: Register = None
    reg1: Register = None
    reg2: Register = None
    reg3: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1, self.reg2, self.reg3]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.ClassicalOpModCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg0 = Register.from_raw(c_struct.out)
        reg1 = Register.from_raw(c_struct.a)
        reg2 = Register.from_raw(c_struct.b)
        reg3 = Register.from_raw(c_struct.mod)
        return cls(reg0=reg0, reg1=reg1, reg2=reg2, reg3=reg3)

    def serialize(self) -> bytes:
        c_struct = encoding.ClassicalOpModCommand(
            id=self.id,
            out=self.reg0.cstruct,
            a=self.reg1.cstruct,
            b=self.reg2.cstruct,
            mod=self.reg3.cstruct
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
    imm: Immediate = None

    @property
    def operands(self) -> List[Operand]:
        return [self.imm]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.JumpCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        imm = Immediate(value=c_struct.line)
        return cls(imm=imm)

    def serialize(self) -> bytes:
        c_struct = encoding.JumpCommand(
            id=self.id,
            line=self.imm.value
        )
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
class BranchUnaryInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand and one Immediate operand.
    Represents an instruction to branch to a certain line, depending on a
    unary expression.
    """
    reg: Register = None
    line: Immediate = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.line]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.BranchUnaryCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.a)
        line = Immediate(value=c_struct.line)
        return cls(reg=reg, line=line)

    def serialize(self) -> bytes:
        c_struct = encoding.BranchUnaryCommand(
            id=self.id,
            reg=self.reg.cstruct,
            line=self.line.value
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 2
        reg, line = operands
        assert isinstance(reg, Register)
        assert isinstance(line, int)
        return cls(reg=reg, line=Immediate(value=line))

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.line)}"

    def check_condition(self, a) -> bool:
        raise RuntimeError("check_condition called on the base BranchUnaryInstruction class")


@dataclass
class BranchBinaryInstruction(NetQASMInstruction):
    """
    An instruction with 2 Register operands and one Immediate operand.
    Represents an instruction to branch to a certain line, depending on a
    binary expression.
    """
    reg0: Register = None
    reg1: Register = None
    line: Immediate = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg0, self.reg1, self.line]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.BranchBinaryCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg0 = Register.from_raw(c_struct.a)
        reg1 = Register.from_raw(c_struct.b)
        line = Immediate(value=c_struct.line)
        return cls(reg0=reg0, reg1=reg1, line=line)

    def serialize(self) -> bytes:
        c_struct = encoding.BranchBinaryCommand(
            id=self.id,
            a=self.reg0.cstruct,
            b=self.reg1.cstruct,
            line=self.line.value
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 3
        reg0, reg1, line = operands
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        assert isinstance(line, int)
        return cls(reg0=reg0, reg1=reg1, line=Immediate(value=line))

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg0)} {str(self.reg1)} {str(self.line)}"

    def check_condition(self, a, b) -> bool:
        raise RuntimeError("check_condition called on the base BranchBinaryInstruction class")


@dataclass
class RegImmInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand and one Immediate operand.
    """
    reg: Register = None
    imm: Immediate = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.imm]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.SetCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.register)
        imm = Immediate(value=c_struct.value)
        return cls(reg=reg, imm=imm)

    def serialize(self) -> bytes:
        c_struct = encoding.SetCommand(
            id=self.id,
            register=self.reg.cstruct,
            value=self.imm.value
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 2
        reg, imm = operands
        assert isinstance(reg, Register)
        assert isinstance(imm, int)
        return cls(
            reg=reg,
            imm=Immediate(value=imm)
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.imm)}"


@dataclass
class RegEntryInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand and one ArrayEntry operand.
    """
    reg: Register = None
    entry: ArrayEntry = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.entry]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.LoadStoreCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.register)
        entry = ArrayEntry.from_raw(c_struct.entry)
        return cls(reg=reg, entry=entry)

    def serialize(self) -> bytes:
        c_struct = encoding.LoadStoreCommand(
            id=self.id,
            register=self.reg.cstruct,
            entry=self.entry.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 2
        reg, entry = operands
        assert isinstance(reg, Register)
        assert isinstance(entry, ArrayEntry)
        return cls(
            reg=reg,
            entry=entry
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.entry)}"


@dataclass
class RegAddrInstruction(NetQASMInstruction):
    """
    An instruction with 1 Register operand and one Address operand.
    """
    reg: Register = None
    address: Address = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.address]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.LeaCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.register)
        address = Address.from_raw(c_struct.address)
        return cls(reg=reg, address=address)

    def serialize(self) -> bytes:
        c_struct = encoding.LeaCommand(
            id=self.id,
            register=self.reg.cstruct,
            address=self.address.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 2
        reg, addr = operands
        assert isinstance(reg, Register)
        assert isinstance(addr, Address)
        return cls(
            reg=reg,
            address=addr
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.address)}"


@dataclass
class EntryAddrInstruction(NetQASMInstruction):
    """
    An instruction with 1 ArrayEntry operand and one Address operand.
    """
    entry: ArrayEntry = None
    address: Address = None

    @property
    def operands(self) -> List[Operand]:
        return [self.address]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.SingleArrayEntryCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        entry = ArrayEntry.from_raw(raw.array_entry)
        return cls(entry=entry)

    def serialize(self) -> bytes:
        c_struct = encoding.SingleArrayEntryCommand(
            id=self.id,
            array_entry=self.entry.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 1
        entry = operands[0]
        assert isinstance(entry, ArrayEntry)
        return cls(
            entry=entry
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.entry)}"


@dataclass
class ArraySliceInstruction(NetQASMInstruction):
    """
    An instruction with 1 ArraySlice operand.
    """
    slice: ArraySlice = None

    @property
    def operands(self) -> List[Operand]:
        return [self.slice]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.SingleArraySliceCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        slice = ArraySlice.from_raw(c_struct.array_slice)
        return cls(slice=slice)

    def serialize(self) -> bytes:
        c_struct = encoding.SingleArraySliceCommand(
            id=self.id,
            array_slice=self.slice.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 1
        slice = operands[0]
        assert isinstance(slice, ArraySlice)
        return cls(
            slice=slice
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.slice)}"


@dataclass
class AddressInstruction(NetQASMInstruction):
    """
    An instruction with 1 Address operand.
    """
    address: Address = None

    @property
    def operands(self) -> List[Operand]:
        return [self.address]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RetArrCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        address = Address.from_raw(c_struct.address)
        return cls(address=address)

    def serialize(self) -> bytes:
        c_struct = encoding.RetArrCommand(
            id=self.id,
            address=self.address.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 1
        addr = operands[0]
        assert isinstance(addr, Address)
        return cls(
            address=addr
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.address)}"


@dataclass
class GenericCreateEPRInstruction(NetQASMInstruction):
    """
    An instruction with 5 Register operands. Represents the CreateEPR instruction.
    """
    remote_node_id: Register = None
    epr_socket_id: Register = None
    qubit_addr_array: Register = None
    arg_array: Register = None
    ent_info_array: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.remote_node_id, self.epr_socket_id, self.qubit_addr_array, self.arg_array, self.ent_info_array]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.CreateEPRCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        return cls(
            remote_node_id=Register.from_raw(c_struct.remote_node_id),
            epr_socket_id=Register.from_raw(c_struct.epr_socket_id),
            qubit_addr_array=Register.from_raw(c_struct.qubit_address_array),
            arg_array=Register.from_raw(c_struct.arg_array),
            ent_info_array=Register.from_raw(c_struct.ent_info_array)
        )

    def serialize(self) -> bytes:
        c_struct = encoding.CreateEPRCommand(
            id=self.id,
            remote_node_id=self.remote_node_id.cstruct,
            epr_socket_id=self.epr_socket_id.cstruct,
            qubit_address_array=self.qubit_addr_array.cstruct,
            arg_array=self.arg_array.cstruct,
            ent_info_array=self.ent_info_array.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 5
        rem_nid, epr_sid, q_aid, arg_arr, ent_info_arr = operands
        assert isinstance(rem_nid, Register)
        assert isinstance(epr_sid, Register)
        assert isinstance(q_aid, Register)
        assert isinstance(arg_arr, Register)
        assert isinstance(ent_info_arr, Register)
        return cls(
            remote_node_id=rem_nid,
            epr_socket_id=epr_sid,
            qubit_addr_array=q_aid,
            arg_array=arg_arr,
            ent_info_array=ent_info_arr
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.remote_node_id)} {str(self.epr_socket_id)} {str(self.qubit_addr_array)} \
{str(self.arg_array)} {str(self.ent_info_array)}"


@dataclass
class GenericRecvEPRInstruction(NetQASMInstruction):
    """
    An instruction with 4 Register operands. Represents the RecvEPR instruction.
    """
    remote_node_id: Register = None
    epr_socket_id: Register = None
    qubit_addr_array: Register = None
    ent_info_array: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.remote_node_id, self.epr_socket_id, self.qubit_addr_array, self.ent_info_array]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RecvEPRCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        return cls(
            remote_node_id=Register.from_raw(c_struct.remote_node_id),
            epr_socket_id=Register.from_raw(c_struct.epr_socket_id),
            qubit_addr_array=Register.from_raw(c_struct.qubit_address_array),
            ent_info_array=Register.from_raw(c_struct.ent_info_array)
        )

    def serialize(self) -> bytes:
        c_struct = encoding.RecvEPRCommand(
            id=self.id,
            remote_node_id=self.remote_node_id.cstruct,
            epr_socket_id=self.epr_socket_id.cstruct,
            qubit_address_array=self.qubit_addr_array.cstruct,
            ent_info_array=self.ent_info_array.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def from_operands(cls, operands: List[Operand]):
        assert len(operands) == 4
        rem_nid, epr_sid, q_aid, ent_info_arr = operands
        assert isinstance(rem_nid, Register)
        assert isinstance(epr_sid, Register)
        assert isinstance(q_aid, Register)
        assert isinstance(ent_info_arr, Register)
        return cls(
            remote_node_id=rem_nid,
            epr_socket_id=epr_sid,
            qubit_addr_array=q_aid,
            ent_info_array=ent_info_arr
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.remote_node_id)} {str(self.epr_socket_id)} {str(self.qubit_addr_array)} \
{str(self.ent_info_array)}"
