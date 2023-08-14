from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Union

import numpy as np

from netqasm.lang.operand import Immediate, Operand, Register, Template

from . import base

# Explicit core NetQASM instructions.


@dataclass  # type: ignore
class SingleQubitInstruction(base.RegInstruction):
    @property
    def qreg(self):
        return self.reg

    @qreg.setter
    def qreg(self, new_val: Register):
        self.reg = new_val

    @abstractmethod
    def to_matrix(self) -> np.ndarray:
        pass


@dataclass  # type: ignore
class TwoQubitInstruction(base.RegRegInstruction):
    @property
    def qreg0(self):
        return self.reg0

    @qreg0.setter
    def qreg0(self, new_val: Register):
        self.reg0 = new_val

    @property
    def qreg1(self):
        return self.reg1

    @qreg1.setter
    def qreg1(self, new_val: Register):
        self.reg1 = new_val

    @abstractmethod
    def to_matrix(self):
        pass

    @abstractmethod
    def to_matrix_target_only(self):
        pass


@dataclass  # type: ignore
class RotationInstruction(base.RegImmImmInstruction):
    @property
    def qreg(self):
        return self.reg

    @qreg.setter
    def qreg(self, new_val: Register):
        self.reg = new_val

    @property
    def angle_num(self):
        return self.imm0

    @angle_num.setter
    def angle_num(self, new_val: Immediate):
        self.imm0 = new_val

    @property
    def angle_denom(self):
        return self.imm1

    @angle_denom.setter
    def angle_denom(self, new_val: Immediate):
        self.imm1 = new_val

    @abstractmethod
    def to_matrix(self):
        pass

    @classmethod
    def from_operands(cls, operands: List[Union[Operand, int]]):
        assert len(operands) == 3
        reg, imm0, imm1 = operands
        assert isinstance(reg, Register)

        if isinstance(imm0, int):
            imm0 = Immediate(value=imm0)
        elif isinstance(imm0, Immediate):
            pass
        else:
            assert isinstance(imm0, Template) or isinstance(imm0, Register)
        if isinstance(imm1, int):
            imm1 = Immediate(value=imm1)
        elif isinstance(imm1, Immediate):
            pass
        else:
            assert isinstance(imm1, Template) or isinstance(imm1, Register)
        # We allow imm0, imm1 to be Templates OR registers
        return cls(reg=reg, imm0=imm0, imm1=imm1)  # type: ignore


@dataclass  # type: ignore
class ControlledRotationInstruction(base.RegRegImmImmInstruction):
    @property
    def qreg0(self):
        return self.reg0

    @qreg0.setter
    def qreg0(self, new_val: Register):
        self.reg0 = new_val

    @property
    def qreg1(self):
        return self.reg1

    @qreg1.setter
    def qreg1(self, new_val: Register):
        self.reg1 = new_val

    @property
    def angle_num(self):
        return self.imm0

    @angle_num.setter
    def angle_num(self, new_val: Immediate):
        self.imm0 = new_val

    @property
    def angle_denom(self):
        return self.imm1

    @angle_denom.setter
    def angle_denom(self, new_val: Immediate):
        self.imm1 = new_val

    @abstractmethod
    def to_matrix(self):
        pass


@dataclass
class ClassicalOpInstruction(base.RegRegRegInstruction):
    def writes_to(self) -> List[Register]:
        return [self.regout]

    @property
    def regout(self):
        return self.reg0

    @regout.setter
    def regout(self, new_val: Register):
        self.reg0 = new_val

    @property
    def regin0(self):
        return self.reg1

    @regin0.setter
    def regin0(self, new_val: Register):
        self.reg1 = new_val

    @property
    def regin1(self):
        return self.reg2

    @regin1.setter
    def regin1(self, new_val: Register):
        self.reg2 = new_val


@dataclass
class ClassicalOpModInstruction(base.RegRegRegRegInstruction):
    def writes_to(self) -> List[Register]:
        return [self.regout]

    @property
    def regout(self):
        return self.reg0

    @regout.setter
    def regout(self, new_val: Register):
        self.reg0 = new_val

    @property
    def regin0(self):
        return self.reg1

    @regin0.setter
    def regin0(self, new_val: Register):
        self.reg1 = new_val

    @property
    def regin1(self):
        return self.reg2

    @regin1.setter
    def regin1(self, new_val: Register):
        self.reg2 = new_val

    @property
    def regmod(self):
        return self.reg3

    @regmod.setter
    def regmod(self, new_val: Register):
        self.reg3 = new_val


@dataclass
class QAllocInstruction(base.RegInstruction):
    id: int = 1
    mnemonic: str = "qalloc"

    @property
    def qreg(self):
        return self.reg

    @qreg.setter
    def qreg(self, new_val: Register):
        self.reg = new_val


@dataclass
class InitInstruction(base.RegInstruction):
    id: int = 2
    mnemonic: str = "init"

    @property
    def qreg(self):
        return self.reg

    @qreg.setter
    def qreg(self, new_val: Register):
        self.reg = new_val


@dataclass
class ArrayInstruction(base.RegAddrInstruction):
    id: int = 3
    mnemonic: str = "array"

    @property
    def size(self):
        return self.reg

    @size.setter
    def size(self, new_val):
        self.reg = new_val


@dataclass
class SetInstruction(base.RegImmInstruction):
    id: int = 4
    mnemonic: str = "set"

    def writes_to(self) -> List[Register]:
        return [self.reg]

    @classmethod
    def from_operands(cls, operands: List[Union[Operand, int]]):
        assert len(operands) == 2
        reg, imm = operands
        assert isinstance(reg, Register)

        if isinstance(imm, int):
            imm = Immediate(value=imm)
        elif isinstance(imm, Immediate):
            pass
        else:
            assert isinstance(imm, Template)

        return cls(reg=reg, imm=imm)  # type: ignore


@dataclass
class StoreInstruction(base.RegEntryInstruction):
    id: int = 5
    mnemonic: str = "store"


@dataclass
class LoadInstruction(base.RegEntryInstruction):
    id: int = 6
    mnemonic: str = "load"

    def writes_to(self) -> List[Register]:
        return [self.reg]


@dataclass
class UndefInstruction(base.ArrayEntryInstruction):
    id: int = 7
    mnemonic: str = "undef"


@dataclass
class LeaInstruction(base.RegAddrInstruction):
    id: int = 8
    mnemonic: str = "lea"

    def writes_to(self) -> List[Register]:
        return [self.reg]


@dataclass
class JmpInstruction(base.ImmInstruction):
    id: int = 9
    mnemonic: str = "jmp"

    @property
    def line(self):
        return self.imm

    @line.setter
    def line(self, new_val):
        self.imm = new_val


@dataclass  # type: ignore
class BranchUnaryInstruction(base.RegImmInstruction):
    """
    Represents an instruction to branch to a certain line, depending on a
    unary expression.
    """

    @property
    def line(self):
        return self.imm

    @line.setter
    def line(self, new_val):
        self.imm = new_val

    @abstractmethod
    def check_condition(self, a) -> bool:
        raise RuntimeError(
            "check_condition called on the base BranchUnaryInstruction class"
        )


@dataclass
class BezInstruction(BranchUnaryInstruction):
    id: int = 10
    mnemonic: str = "bez"

    def check_condition(self, a: int) -> bool:
        return a == 0


@dataclass
class BnzInstruction(BranchUnaryInstruction):
    id: int = 11
    mnemonic: str = "bnz"

    def check_condition(self, a: int) -> bool:
        return a != 0


@dataclass  # type: ignore
class BranchBinaryInstruction(base.RegRegImmInstruction):
    """
    Represents an instruction to branch to a certain line, depending on a
    binary expression.
    """

    @property
    def line(self):
        return self.imm

    @line.setter
    def line(self, new_val):
        self.imm = new_val

    @abstractmethod
    def check_condition(self, a, b) -> bool:
        raise RuntimeError(
            "check_condition called on the base BranchBinaryInstruction class"
        )


@dataclass
class BeqInstruction(BranchBinaryInstruction):
    id: int = 12
    mnemonic: str = "beq"

    def check_condition(self, a: int, b: int) -> bool:
        return a == b


@dataclass
class BneInstruction(BranchBinaryInstruction):
    id: int = 13
    mnemonic: str = "bne"

    def check_condition(self, a: int, b: int) -> bool:
        return a != b


@dataclass
class BltInstruction(BranchBinaryInstruction):
    id: int = 14
    mnemonic: str = "blt"

    def check_condition(self, a: int, b: int) -> bool:
        return a < b


@dataclass
class BgeInstruction(BranchBinaryInstruction):
    id: int = 15
    mnemonic: str = "bge"

    def check_condition(self, a: int, b: int) -> bool:
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
class MulInstruction(ClassicalOpInstruction):
    id: int = 200
    mnemonic: str = "mul"


@dataclass
class DivInstruction(ClassicalOpInstruction):
    id: int = 201
    mnemonic: str = "div"


@dataclass
class RemInstruction(ClassicalOpInstruction):
    id: int = 202
    mnemonic: str = "rem"


@dataclass
class MeasInstruction(base.RegRegInstruction):
    id: int = 32
    mnemonic: str = "meas"

    def writes_to(self) -> List[Register]:
        return [self.creg]

    @property
    def qreg(self):
        return self.reg0

    @qreg.setter
    def qreg(self, new_val: Register):
        self.reg0 = new_val

    @property
    def creg(self):
        return self.reg1

    @creg.setter
    def creg(self, new_val: Register):
        self.reg1 = new_val


@dataclass
class MeasBasisInstruction(base.RegRegImm4Instruction):
    id: int = 41
    mnemonic: str = "meas_basis"

    def writes_to(self) -> List[Register]:
        return [self.creg]

    @property
    def qreg(self):
        return self.reg0

    @qreg.setter
    def qreg(self, new_val: Register):
        self.reg0 = new_val

    @property
    def creg(self):
        return self.reg1

    @creg.setter
    def creg(self, new_val: Register):
        self.reg1 = new_val

    @property
    def angle_num_x1(self):
        return self.imm0

    @angle_num_x1.setter
    def angle_num_x1(self, new_val: Immediate):
        self.imm0 = new_val

    @property
    def angle_num_y(self):
        return self.imm1

    @angle_num_y.setter
    def angle_num_y(self, new_val: Immediate):
        self.imm1 = new_val

    @property
    def angle_num_x2(self):
        return self.imm2

    @angle_num_x2.setter
    def angle_num_x2(self, new_val: Immediate):
        self.imm2 = new_val

    @property
    def angle_denom(self):
        return self.imm3

    @angle_denom.setter
    def angle_denom(self, new_val: Immediate):
        self.imm3 = new_val


@dataclass
class CreateEPRInstruction(base.Reg5Instruction):
    id: int = 33
    mnemonic: str = "create_epr"

    @property
    def remote_node_id(self):
        return self.reg0

    @remote_node_id.setter
    def remote_node_id(self, new_val: Register):
        self.reg0 = new_val

    @property
    def epr_socket_id(self):
        return self.reg1

    @epr_socket_id.setter
    def epr_socket_id(self, new_val: Register):
        self.reg1 = new_val

    @property
    def qubit_addr_array(self):
        return self.reg2

    @qubit_addr_array.setter
    def qubit_addr_array(self, new_val: Register):
        self.reg2 = new_val

    @property
    def arg_array(self):
        return self.reg3

    @arg_array.setter
    def arg_array(self, new_val: Register):
        self.reg3 = new_val

    @property
    def ent_results_array(self):
        return self.reg4

    @ent_results_array.setter
    def ent_results_array(self, new_val: Register):
        self.reg4 = new_val


@dataclass
class RecvEPRInstruction(base.RegRegRegRegInstruction):
    id: int = 34
    mnemonic: str = "recv_epr"

    @property
    def remote_node_id(self):
        return self.reg0

    @remote_node_id.setter
    def remote_node_id(self, new_val: Register):
        self.reg0 = new_val

    @property
    def epr_socket_id(self):
        return self.reg1

    @epr_socket_id.setter
    def epr_socket_id(self, new_val: Register):
        self.reg1 = new_val

    @property
    def qubit_addr_array(self):
        return self.reg2

    @qubit_addr_array.setter
    def qubit_addr_array(self, new_val: Register):
        self.reg2 = new_val

    @property
    def ent_results_array(self):
        return self.reg3

    @ent_results_array.setter
    def ent_results_array(self, new_val: Register):
        self.reg3 = new_val


@dataclass
class WaitAllInstruction(base.ArraySliceInstruction):
    id: int = 35
    mnemonic: str = "wait_all"


@dataclass
class WaitAnyInstruction(base.ArraySliceInstruction):
    id: int = 36
    mnemonic: str = "wait_any"


@dataclass
class WaitSingleInstruction(base.ArrayEntryInstruction):
    id: int = 37
    mnemonic: str = "wait_single"


@dataclass
class QFreeInstruction(base.RegInstruction):
    id: int = 38
    mnemonic: str = "qfree"

    @property
    def qreg(self):
        return self.reg

    @qreg.setter
    def qreg(self, new_val: Register):
        self.reg = new_val


@dataclass
class RetRegInstruction(base.RegInstruction):
    id: int = 39
    mnemonic: str = "ret_reg"


@dataclass
class RetArrInstruction(base.AddrInstruction):
    id: int = 40
    mnemonic: str = "ret_arr"


@dataclass
class BreakpointInstruction(base.ImmImmInstruction):
    id: int = 100
    mnemonic: str = "breakpoint"

    @property
    def action(self):
        return self.imm0

    @action.setter
    def action(self, new_val):
        self.imm0 = new_val

    @property
    def role(self):
        return self.imm1

    @role.setter
    def role(self, new_val):
        self.imm1 = new_val
