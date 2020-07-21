from dataclasses import dataclass
from typing import List, Union

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
    Label
)


# Abstract instruction types. Should not be instantiated directly.
# Some of these are named 'Generic_XXX' to distinguish them from the explicit instruction classes below.

@dataclass
class NetQASMInstruction:
    """
    Base NetQASM instruction class.
    """
    id: int = -1
    mnemonic: str = None
    lineno: HostLine = None

    @property
    def operands(self) -> List[Operand]:
        return []

    @classmethod
    def deserialize_from(cls, raw: bytes):
        pass

    def serialize(self) -> bytes:
        pass

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        pass

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

    def update_labels(self, labels):
        pass


@dataclass
class SingleQubitInstruction(NetQASMInstruction):
    qreg: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.qreg]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.SingleQubitCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        register = Register.from_raw(c_struct.qubit)
        return cls(id=cls.id, qreg=register)

    def serialize(self) -> bytes:
        c_struct = encoding.SingleQubitCommand(
            id=self.id,
            qubit=self.qreg.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 1
        qreg = operands[0]
        assert isinstance(qreg, Register)
        return cls(id=cls.id, qreg=qreg)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.qreg)}"


@dataclass
class TwoQubitInstruction(NetQASMInstruction):
    qreg0: Register = None
    qreg1: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.qreg0, self.qreg1]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.TwoQubitCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        qreg0 = Register.from_raw(c_struct.qubit1)
        qreg1 = Register.from_raw(c_struct.qubit2)
        return cls(qreg0=qreg0, qreg1=qreg1)

    def serialize(self) -> bytes:
        c_struct = encoding.TwoQubitCommand(
            id=self.id,
            qubit1=self.qreg0.cstruct,
            qubit2=self.qreg1.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 2
        qreg0, qreg1 = operands
        assert isinstance(qreg0, Register)
        assert isinstance(qreg1, Register)
        return cls(qreg0=qreg0, qreg1=qreg1)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.qreg0)} {str(self.qreg1)}"


@dataclass
class GenericMeasInstruction(NetQASMInstruction):
    qreg: Register = None
    creg: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.qreg, self.creg]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.MeasCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        qreg = Register.from_raw(c_struct.qubit)
        creg = Register.from_raw(c_struct.outcome)
        return cls(qreg=qreg, creg=creg)

    def serialize(self) -> bytes:
        c_struct = encoding.MeasCommand(
            id=self.id,
            qubit=self.qreg.cstruct,
            outcome=self.creg.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 2
        qreg, creg = operands
        assert isinstance(qreg, Register)
        assert isinstance(creg, Register)
        return cls(qreg=qreg, creg=creg)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.qreg)} {str(self.creg)}"


@dataclass
class RotationInstruction(NetQASMInstruction):
    qreg: Register = None
    angle_num: Immediate = None
    angle_denom: Immediate = None

    @property
    def operands(self) -> List[Operand]:
        return [self.qreg, self.angle_num, self.angle_denom]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.RotationCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        qreg = Register.from_raw(c_struct.qubit)
        angle_num = Immediate(value=c_struct.angle_numerator)
        angle_denom = Immediate(value=c_struct.angle_denominator)
        return cls(qreg=qreg, angle_num=angle_num, angle_denom=angle_denom)

    def serialize(self) -> bytes:
        c_struct = encoding.RotationCommand(
            id=self.id,
            qubit=self.qreg.cstruct,
            angle_numerator=self.angle_num.value,
            angle_denominator=self.angle_denom.value
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 3
        qreg, num, denom = operands
        assert isinstance(qreg, Register)
        assert isinstance(num, int)
        assert isinstance(denom, int)
        return cls(
            qreg=qreg,
            angle_num=Immediate(value=num),
            angle_denom=Immediate(value=denom)
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.qreg)} {str(self.angle_num)} {str(self.angle_denom)}"


@dataclass
class ClassicalOpInstruction(NetQASMInstruction):
    regout: Register = None
    reg0: Register = None
    reg1: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.regout, self.reg0, self.reg1]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.ClassicalOpCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        regout = Register.from_raw(c_struct.out)
        reg0 = Register.from_raw(c_struct.a)
        reg1 = Register.from_raw(c_struct.b)
        return cls(regout=regout, reg0=reg0, reg1=reg1)

    def serialize(self) -> bytes:
        c_struct = encoding.ClassicalOpCommand(
            id=self.id,
            out=self.regout.cstruct,
            a=self.reg0.cstruct,
            b=self.reg1.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 3
        regout, reg0, reg1 = operands
        assert isinstance(regout, Register)
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        return cls(
            regout=regout,
            reg0=reg0,
            reg1=reg1
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.regout)} {str(self.reg0)} {str(self.reg1)}"


@dataclass
class ClassicalOpModInstruction(NetQASMInstruction):
    regout: Register = None
    reg0: Register = None
    reg1: Register = None
    regmod: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.regout, self.reg0, self.reg1, self.regmod]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.ClassicalOpModCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        regout = Register.from_raw(c_struct.out)
        reg0 = Register.from_raw(c_struct.a)
        reg1 = Register.from_raw(c_struct.b)
        regmod = Register.from_raw(c_struct.mod)
        return cls(regout=regout, reg0=reg0, reg1=reg1, regmod=regmod)

    def serialize(self) -> bytes:
        c_struct = encoding.ClassicalOpModCommand(
            id=self.id,
            out=self.regout.cstruct,
            a=self.reg0.cstruct,
            b=self.reg1.cstruct,
            mod=self.regmod.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 4
        regout, reg0, reg1, regmod = operands
        assert isinstance(regout, Register)
        assert isinstance(reg0, Register)
        assert isinstance(reg1, Register)
        assert isinstance(regmod, Register)
        return cls(
            regout=regout,
            reg0=reg0,
            reg1=reg1,
            regmod=regmod
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.regout)} {str(self.reg0)} {str(self.reg1)} {str(self.regmod)}"


@dataclass
class GenericJumpInstruction(NetQASMInstruction):
    line: Immediate = None
    line_label: Label = None

    @property
    def operands(self) -> List[Operand]:
        return [self.line]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.JumpCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        line = Immediate(value=c_struct.line)
        return cls(line=line)

    def serialize(self) -> bytes:
        c_struct = encoding.JumpCommand(
            id=self.id,
            line=self.line.value
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 1
        line = operands[0]
        assert (isinstance(line, int) or isinstance(line, Label))
        if isinstance(line, int):
            return cls(line=Immediate(value=line))
        elif isinstance(line, Label):
            return cls(line_label=line)

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.line)}"


@dataclass
class BranchUnaryInstruction(NetQASMInstruction):
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
    def parse_from(cls, operands: List[Operand]):
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
    def parse_from(cls, operands: List[Operand]):
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
class GenericSetInstruction(NetQASMInstruction):
    reg: Register = None
    value: Immediate = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg, self.value]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.SetCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.register)
        value = Immediate(value=c_struct.value)
        return cls(reg=reg, value=value)

    def serialize(self) -> bytes:
        c_struct = encoding.SetCommand(
            id=self.id,
            register=self.reg.cstruct,
            value=self.value.value
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 2
        reg, value = operands
        assert isinstance(reg, Register)
        assert isinstance(value, int)
        return cls(
            reg=reg,
            value=Immediate(value=value)
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)} {str(self.value)}"


@dataclass
class LoadStoreInstruction(NetQASMInstruction):
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
    def parse_from(cls, operands: List[Operand]):
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
class GenericLeaInstruction(NetQASMInstruction):
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
    def parse_from(cls, operands: List[Operand]):
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
class SingleArrayEntryInstruction(NetQASMInstruction):
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
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 1
        entry = operands[0]
        assert isinstance(entry, ArrayEntry)
        return cls(
            entry=entry
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.entry)}"


@dataclass
class SingleArraySliceInstruction(NetQASMInstruction):
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
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 1
        slice = operands[0]
        assert isinstance(slice, ArraySlice)
        return cls(
            slice=slice
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.slice)}"


@dataclass
class GenericSingleRegisterInstruction(NetQASMInstruction):
    reg: Register = None

    @property
    def operands(self) -> List[Operand]:
        return [self.reg]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.SingleRegisterCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        reg = Register.from_raw(c_struct.register)
        return cls(reg=reg)

    def serialize(self) -> bytes:
        c_struct = encoding.SingleRegisterCommand(
            id=self.id,
            register=self.reg.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 1
        reg = operands[0]
        assert isinstance(reg, Register)
        return cls(
            reg=reg
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.reg)}"


@dataclass
class GenericArrayInstruction(NetQASMInstruction):
    size: Register = None
    address: Address = None

    @property
    def operands(self) -> List[Operand]:
        return [self.size, self.address]

    @classmethod
    def deserialize_from(cls, raw: bytes):
        c_struct = encoding.ArrayCommand.from_buffer_copy(raw)
        assert c_struct.id == cls.id
        size = Register.from_raw(c_struct.size)
        address = Address.from_raw(c_struct.address)
        return cls(size=size, address=address)

    def serialize(self) -> bytes:
        c_struct = encoding.ArrayCommand(
            id=self.id,
            size=self.size.cstruct,
            address=self.address.cstruct
        )
        return bytes(c_struct)

    @classmethod
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 2
        size, addr = operands
        assert isinstance(size, Register)
        assert isinstance(addr, Address)
        return cls(
            size=size,
            address=addr
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.size)} {str(self.address)}"


@dataclass
class GenericRetArrInstruction(NetQASMInstruction):
    address: Union[Address, ArraySlice] = None
    # address: ArraySlice = None
    # TODO: should it be an Address or ArraySlice?

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
    def parse_from(cls, operands: List[Operand]):
        assert len(operands) == 1
        addr = operands[0]
        assert isinstance(addr, Address) or isinstance(addr, ArraySlice)
        # assert isinstance(addr, ArraySlice)
        return cls(
            address=addr
        )

    def _pretty_print(self):
        return f"{self.mnemonic} {str(self.address)}"


@dataclass
class GenericCreateEPRInstruction(NetQASMInstruction):
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
    def parse_from(cls, operands: List[Operand]):
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
    def parse_from(cls, operands: List[Operand]):
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


# Explicit core NetQASM instructions.

@dataclass
class QAllocInstruction(SingleQubitInstruction):
    id: int = 1
    mnemonic: str = "qalloc"


@dataclass
class InitInstruction(SingleQubitInstruction):
    id: int = 2
    mnemonic: str = "init"


@dataclass
class ArrayInstruction(GenericArrayInstruction):
    id: int = 3
    mnemonic: str = "array"


@dataclass
class SetInstruction(GenericSetInstruction):
    id: int = 4
    mnemonic: str = "set"


@dataclass
class StoreInstruction(LoadStoreInstruction):
    id: int = 5
    mnemonic: str = "store"


@dataclass
class LoadInstruction(LoadStoreInstruction):
    id: int = 6
    mnemonic: str = "load"


@dataclass
class UndefInstruction(SingleArrayEntryInstruction):
    id: int = 7
    mnemonic: str = "undef"


@dataclass
class LeaInstruction(GenericLeaInstruction):
    id: int = 8
    mnemonic: str = "lea"


@dataclass
class JmpInstruction(GenericJumpInstruction):
    id: int = 9
    mnemonic: str = "jmp"


@dataclass
class BezInstruction(BranchUnaryInstruction):
    id: int = 10
    mnemonic: str = "bez"

    def check_condition(self, a) -> bool:
        return a == 0


@dataclass
class BnzInstruction(BranchUnaryInstruction):
    id: int = 11
    mnemonic: str = "bnz"

    def check_condition(self, a) -> bool:
        return a != 0


@dataclass
class BeqInstruction(BranchBinaryInstruction):
    id: int = 12
    mnemonic: str = "beq"

    def check_condition(self, a, b) -> bool:
        return a == b


@dataclass
class BneInstruction(BranchBinaryInstruction):
    id: int = 13
    mnemonic: str = "bne"

    def check_condition(self, a, b) -> bool:
        return a != b


@dataclass
class BltInstruction(BranchBinaryInstruction):
    id: int = 14
    mnemonic: str = "blt"

    def check_condition(self, a, b) -> bool:
        return a < b


@dataclass
class BgeInstruction(BranchBinaryInstruction):
    id: int = 15
    mnemonic: str = "bge"

    def check_condition(self, a, b) -> bool:
        return a >= b


@dataclass
class AddInstruction(ClassicalOpInstruction):
    id: int = 16
    mnemonic: str = "add"


@dataclass
class SubInstruction(ClassicalOpInstruction):
    id: int = 17
    mnemonic: str = "sub"


@dataclass
class AddmInstruction(ClassicalOpModInstruction):
    id: int = 18
    mnemonic: str = "addm"


@dataclass
class SubmInstruction(ClassicalOpModInstruction):
    id: int = 19
    mnemonic: str = "subm"


@dataclass
class MeasInstruction(GenericMeasInstruction):
    id: int = 32
    mnemonic: str = "meas"


@dataclass
class CreateEPRInstruction(GenericCreateEPRInstruction):
    id: int = 33
    mnemonic: str = "create_epr"


@dataclass
class RecvEPRInstruction(GenericRecvEPRInstruction):
    id: int = 34
    mnemonic: str = "recv_epr"


@dataclass
class WaitAllInstruction(SingleArraySliceInstruction):
    id: int = 35
    mnemonic: str = "wait_all"


@dataclass
class WaitAnyInstruction(SingleArraySliceInstruction):
    id: int = 36
    mnemonic: str = "wait_any"


@dataclass
class WaitSingleInstruction(SingleArrayEntryInstruction):
    id: int = 37
    mnemonic: str = "wait_single"


@dataclass
class QFreeInstruction(SingleQubitInstruction):
    id: int = 38
    mnemonic: str = "qfree"


@dataclass
class RetRegInstruction(GenericSingleRegisterInstruction):
    id: int = 39
    mnemonic: str = "ret_reg"


@dataclass
class RetArrInstruction(GenericRetArrInstruction):
    id: int = 40
    mnemonic: str = "ret_arr"
