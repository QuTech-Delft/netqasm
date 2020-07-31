from dataclasses import dataclass


from netqasm.instructions.operand import Register
from netqasm.instructions import base


# Explicit core NetQASM instructions.

@dataclass
class SingleQubitInstruction(base.RegInstruction):
    @property
    def qreg(self):
        return self.reg

    @qreg.setter
    def qreg(self, new_val: Register):
        self.reg = new_val


@dataclass
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


@dataclass
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
    def angle_num(self, new_val: Register):
        self.imm0 = new_val

    @property
    def angle_denom(self):
        return self.imm1

    @angle_denom.setter
    def angle_denom(self, new_val: Register):
        self.imm1 = new_val


@dataclass
class ClassicalOpInstruction(base.RegRegRegInstruction):
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
class QAllocInstruction(SingleQubitInstruction):
    id: int = 1
    mnemonic: str = "qalloc"


@dataclass
class InitInstruction(SingleQubitInstruction):
    id: int = 2
    mnemonic: str = "init"


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


@dataclass
class StoreInstruction(base.RegEntryInstruction):
    id: int = 5
    mnemonic: str = "store"


@dataclass
class LoadInstruction(base.RegEntryInstruction):
    id: int = 6
    mnemonic: str = "load"


@dataclass
class UndefInstruction(base.EntryAddrInstruction):
    id: int = 7
    mnemonic: str = "undef"


@dataclass
class LeaInstruction(base.RegAddrInstruction):
    id: int = 8
    mnemonic: str = "lea"


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


@dataclass
class BezInstruction(base.BranchUnaryInstruction):
    id: int = 10
    mnemonic: str = "bez"

    def check_condition(self, a) -> bool:
        return a == 0


@dataclass
class BnzInstruction(base.BranchUnaryInstruction):
    id: int = 11
    mnemonic: str = "bnz"

    def check_condition(self, a) -> bool:
        return a != 0


@dataclass
class BeqInstruction(base.BranchBinaryInstruction):
    id: int = 12
    mnemonic: str = "beq"

    def check_condition(self, a, b) -> bool:
        return a == b


@dataclass
class BneInstruction(base.BranchBinaryInstruction):
    id: int = 13
    mnemonic: str = "bne"

    def check_condition(self, a, b) -> bool:
        return a != b


@dataclass
class BltInstruction(base.BranchBinaryInstruction):
    id: int = 14
    mnemonic: str = "blt"

    def check_condition(self, a, b) -> bool:
        return a < b


@dataclass
class BgeInstruction(base.BranchBinaryInstruction):
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
class MeasInstruction(base.RegRegInstruction):
    id: int = 32
    mnemonic: str = "meas"

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
class CreateEPRInstruction(base.GenericCreateEPRInstruction):
    id: int = 33
    mnemonic: str = "create_epr"


@dataclass
class RecvEPRInstruction(base.GenericRecvEPRInstruction):
    id: int = 34
    mnemonic: str = "recv_epr"


@dataclass
class WaitAllInstruction(base.ArraySliceInstruction):
    id: int = 35
    mnemonic: str = "wait_all"


@dataclass
class WaitAnyInstruction(base.ArraySliceInstruction):
    id: int = 36
    mnemonic: str = "wait_any"


@dataclass
class WaitSingleInstruction(base.EntryAddrInstruction):
    id: int = 37
    mnemonic: str = "wait_single"


@dataclass
class QFreeInstruction(SingleQubitInstruction):
    id: int = 38
    mnemonic: str = "qfree"


@dataclass
class RetRegInstruction(base.RegInstruction):
    id: int = 39
    mnemonic: str = "ret_reg"


@dataclass
class RetArrInstruction(base.AddressInstruction):
    id: int = 40
    mnemonic: str = "ret_arr"
