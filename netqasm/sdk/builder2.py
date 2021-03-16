# type: ignore
# flake8: noqa
"""TODO write about connections"""

from __future__ import annotations

import abc
import logging
import math
import os
import pickle
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, auto
from itertools import count
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

from qlink_interface import (
    EPRType,
    LinkLayerCreate,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
    RandomBasis,
)

from netqasm import NETQASM_VERSION
from netqasm.backend.network_stack import OK_FIELDS_K, OK_FIELDS_M
from netqasm.lang import operand
from netqasm.lang.ir import (
    Address,
    ArrayEntry,
    ArraySlice,
    BranchLabel,
    GenericInstr,
    ICmd,
    Label,
    PreSubroutine,
    Symbols,
    T_OperandUnion,
    flip_branch_instr,
)
from netqasm.lang.ir2 import *
from netqasm.lang.subroutine import Subroutine
from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk.compiling import NVSubroutineCompiler, SubroutineCompiler
from netqasm.sdk.config import LogConfig
from netqasm.sdk.futures import Array, Future, RegFuture
from netqasm.sdk.network import NetworkInfo
from netqasm.sdk.progress_bar import ProgressBar
from netqasm.sdk.qubit import Qubit, _FutureQubit
from netqasm.sdk.shared_memory import SharedMemory, SharedMemoryManager
from netqasm.sdk.toolbox import get_angle_spec_from_float
from netqasm.util.log import LineTracker

T_Cmd = Union[ICmd, BranchLabel]
T_LinkLayerOkList = Union[
    List[LinkLayerOKTypeK], List[LinkLayerOKTypeM], List[LinkLayerOKTypeR]
]
T_CValue = Union[int, Future, RegFuture]
T_PostRoutine = Callable[
    ["BaseNetQASMConnection", Union[_FutureQubit, List[Future]], operand.Register], None
]
T_BranchRoutine = Callable[["BaseNetQASMConnection"], None]
T_LoopRoutine = Callable[["BaseNetQASMConnection"], None]

T_IntegerHandle = Union["BitHandle", "IntHandle"]

if TYPE_CHECKING:
    from netqasm.sdk.epr_socket import EPRSocket


ENT_INFO = {
    EPRType.K: LinkLayerOKTypeK,
    EPRType.M: LinkLayerOKTypeM,
    EPRType.R: LinkLayerOKTypeR,
}


# 1. allocate registers without bound
# 2. compile
# 3. allocate concrete registers


class _ICmdType(Enum):
    NEW_VAL = auto()
    Q_SINGLE = auto()
    Q_SINGLE_PARM = auto()
    Q_MULTI = auto()
    Q_MULTI_PARM = auto()
    Q_ALLOC = auto()
    Q_FREE = auto()
    Q_MEAS = auto()
    Q_ENTANGLE = auto()
    C_NEW = auto()
    C_NEW_ARRAY = auto()
    B_LABEL = auto()
    B_BRANCH = auto()


class ArrayHandle:
    def __init__(self, iarr: IrArr):
        self._iarr: IrArr = iarr

    def get_value(self, index: int) -> Optional[int]:
        raise NotImplementedError

    def get_values(self, range: slice) -> List[Optional[int]]:
        raise NotImplementedError

    def get_value_as_future(self, index: int) -> Future:
        raise NotImplementedError

    def get_values_as_futures(self, range: slice) -> List[Future]:
        raise NotImplementedError


class RegisterHandle:
    def __init__(self, ireg: IrReg):
        self._ireg: IrReg = ireg

    def get_value(self, index: int) -> Optional[int]:
        raise NotImplementedError

    def get_value_as_future(self, index: int) -> Future:
        raise NotImplementedError


class BitHandle:
    def __init__(self, ibit: IrBit):
        self._ibit: IrBit = ibit

    def get_value(self) -> Optional[int]:
        raise NotImplementedError


class IntHandle:
    def __init__(self, iint: IrInt):
        self._iint: IrInt = iint

    def get_value(self) -> Optional[int]:
        raise NotImplementedError


class EprResultHandle:
    def __init__(self, ierslt: IrEprResult):
        self._ierslt: IrEprResult = ierslt

    def get_value(self) -> Optional[Any]:
        raise NotImplementedError


class QubitHandle:
    def __init__(self, iqbt: IrQbt):
        self._iqbt: IrQbt = iqbt

    def get_qubit(self) -> Qubit:
        raise NotImplementedError


# Fixed IR Functions
IR_new_array = IrFun(
    args={
        "array": IrArr,
        "length": int,
    }
)

IR_epr_create_keep = IrFun(
    args={
        "socket": IrEprSocket,
        "number": int,
    }
)


class Builder:
    def __init__(
        self,
        app_name: str,
        node_name: Optional[str] = None,
        app_id: Optional[int] = None,
        max_qubits: int = 5,
        epr_sockets: Optional[List[EPRSocket]] = None,
    ):
        # IR
        self._iregs: Set[IrReg] = set()
        self._iarrays: Set[IrArr] = set()
        self._ibits: Set[IrBit] = set()
        self._iints: Set[IrInt] = set()
        self._iqubits: Set[IrQbt] = set()
        self._ierslts: Set[IrEprResult] = set()

        self._iinstrs: List[IrInstr] = []
        self._iblks: List[IrBlk] = []
        self._outer_blk: IrBlk = IrBlk()

        # All qubits active for this connection
        self.active_qubits: List[Qubit] = []

        self._used_array_addresses: List[int] = []

        self._used_meas_registers: List[int] = []

        self._pending_commands: List[T_Cmd] = []

        self._max_qubits: int = max_qubits

    def print_instrs(self) -> str:
        return "\n".join([str(ins) for ins in self._iinstrs])

    def _new_array(self) -> IrArr:
        arr = IrArr()
        self._iarrays.add(arr)
        return arr

    def new_array(
        self, length: int = 1, init_values: Optional[List[Optional[int]]] = None
    ) -> ArrayHandle:
        # Register new variable
        arr: IrArr = self._new_array()

        # Generate IR code
        self._iinstrs.append(
            IrInstr(
                typ=IrInstrType.NEW_ARRAY,
                operands=[arr, length],
            )
        )

        if init_values:
            self._iinstrs.append(IrInstr(typ=IrInstrType.PARAM, operands=[length]))
            self._iinstrs.append(
                IrInstr(typ=IrInstrType.CALL, operands=[None, "IR_init_array", 1])
            )

        # Return handle to variable for use in SDK
        return ArrayHandle(arr)

    def _new_register(self) -> IrReg:
        reg = IrReg()
        self._iregs.add(reg)
        return reg

    def new_register(self, init_value: int = 0) -> RegisterHandle:
        # Register new variable
        reg: IrReg = self._new_register()

        # Generate IR code
        if init_value:
            self._iinstrs.append(
                IrInstr(typ=IrInstrType.ASSIGN, operands=[reg, init_value])
            )

        # Return handle to variable for use in SDK
        return RegisterHandle(reg)

    def _new_bit(self) -> IrBit:
        bit = IrBit()
        self._ibits.add(bit)
        return bit

    def new_bit(self) -> BitHandle:
        # Register new variable
        bit: IrBit = self._new_bit()

        # Return handle to variable for use in SDK
        return BitHandle(bit)

    def _new_int(self) -> IrInt:
        int_ = IrInt()
        self._iints.add(int_)
        return int_

    def new_int(self) -> IntHandle:
        # Register new variable
        int_: IrInt = self._new_int()

        # Return handle to variable for use in SDK
        return IntHandle(int_)

    def _new_epr_result(self) -> IrEprResult:
        erslt = IrEprResult()
        self._ierslts.add(erslt)
        return erslt

    def _new_qubit(self) -> IrQbt:
        qbt = IrQbt()
        self._iqubits.add(qbt)
        return qbt

    def new_qubit(self) -> QubitHandle:
        # Register new variable
        qbt = self._new_qubit()

        # Generate IR code
        self._iinstrs.append(IrInstr(typ=IrInstrType.NEW_QUBIT, operands=[qbt]))

        # Return handle to variable for use in SDK
        return QubitHandle(qbt)

    def q_rotate(self, axis: IrRotAxis, qubit: QubitHandle, angle: float) -> None:
        # Find qubit
        qbt = qubit._iqbt

        # Generate IR code
        rot_map = {
            "X": IrInstrType.Q_ROT_X,
            "Y": IrInstrType.Q_ROT_Y,
            "Z": IrInstrType.Q_ROT_Z,
        }
        instr_type = rot_map[axis.name]
        self._iinstrs.append(IrInstr(typ=instr_type, operands=[qbt, angle]))

    def q_gate(self, gate: IrSingleGate, qubit: QubitHandle) -> None:
        # Find qubit
        qbt = qubit._iqbt

        # Generate IR code
        gate_map = {
            "X": IrInstrType.Q_X,
            "Y": IrInstrType.Q_Y,
            "Z": IrInstrType.Q_Z,
            "H": IrInstrType.Q_H,
            "S": IrInstrType.Q_S,
        }
        instr_type = gate_map[gate.name]
        self._iinstrs.append(IrInstr(typ=instr_type, operands=[qbt]))

    def q_two_gate(
        self,
        gate: IrTwoGate,
        qubit1: QubitHandle,
        qubit2: QubitHandle,
    ) -> None:
        # Find qubit
        qbt1 = qubit1._iqbt
        qbt2 = qubit2._iqbt

        # Generate IR code
        gate_map = {
            "CNOT": IrInstrType.Q_CNOT,
            "CPHASE": IrInstrType.Q_CPHASE,
            "MS": IrInstrType.Q_MS,
        }
        instr_type = gate_map[gate.name]
        self._iinstrs.append(IrInstr(typ=instr_type, operands=[qbt1, qbt2]))

    def measure(self, qubit: QubitHandle, inplace: bool = False) -> RegisterHandle:
        qbt: IrQbt = qubit._iqbt
        bit: IrBit = self._new_bit()

        self._iinstrs.append(IrInstr(typ=IrInstrType.Q_MEAS, operands=[qbt, bit]))

        if not inplace:
            self._iinstrs.append(IrInstr(typ=IrInstrType.Q_FREE, operands=[qbt]))

    def epr_create_keep(
        self,
        socket: IrEprSocket,
        number: int = 1,
        post_routine: Optional[T_PostRoutine] = None,
        sequential: bool = False,
    ) -> List[QubitHandle]:
        qubits: List[IrQbt] = [self._new_qubit() for _ in range(number)]

        # Generate IR code
        self._iinstrs.append(IrInstr(typ=IrInstrType.PARAM, operands=[number]))
        self._iinstrs.append(IrInstr(typ=IrInstrType.PARAM, operands=[socket]))
        self._iinstrs.append(
            IrInstr(typ=IrInstrType.CALL, operands=[qubits, "IR_epr_create_keep", 2])
        )

        # Return handle to variable for use in SDK
        return [QubitHandle(qbt) for qbt in qubits]

    def epr_recv_keep(
        self,
        socket: IrEprSocket,
        number: int = 1,
        post_routine: Optional[T_PostRoutine] = None,
        sequential: bool = False,
    ) -> List[QubitHandle]:
        qubits: List[IrQbt] = [self._new_qubit() for _ in range(number)]

        # Generate IR code
        self._iinstrs.append(IrInstr(typ=IrInstrType.PARAM, operands=[number]))
        self._iinstrs.append(IrInstr(typ=IrInstrType.PARAM, operands=[socket]))
        self._iinstrs.append(
            IrInstr(typ=IrInstrType.CALL, operands=[qubits, "IR_epr_recv_keep", 2])
        )

        # Return handle to variable for use in SDK
        return [QubitHandle(qbt) for qbt in qubits]

    def epr_create_meas(
        self,
        socket: IrEprSocket,
        number: int = 1,
        post_routine: Optional[T_PostRoutine] = None,
        sequential: bool = False,
    ) -> List[EprResultHandle]:
        # Register temporary qubits.
        # They are not made available to the user and are never really stored,
        # but they do require an empty qubit memory spot.
        _: List[IrQbt] = [self._new_qubit() for _ in range(number)]

        results: List[IrEprResult] = [self._new_epr_result() for _ in range(number)]

        # Generate IR code
        self._iinstrs.append(IrInstr(typ=IrInstrType.PARAM, operands=[number]))
        self._iinstrs.append(IrInstr(typ=IrInstrType.PARAM, operands=[socket]))
        self._iinstrs.append(
            IrInstr(typ=IrInstrType.CALL, operands=[results, "IR_epr_create_meas", 2])
        )

        # Return handle to variable for use in SDK
        return [EprResultHandle(rslt) for rslt in results]

    def epr_recv_meas(
        self,
        socket: IrEprSocket,
        number: int = 1,
        post_routine: Optional[T_PostRoutine] = None,
        sequential: bool = False,
    ) -> List[EprResultHandle]:
        # Register temporary qubits.
        # They are not made available to the user and are never really stored,
        # but they do require an empty qubit memory spot.
        _: List[IrQbt] = [self._new_qubit() for _ in range(number)]

        results: List[IrEprResult] = [self._new_epr_result() for _ in range(number)]

        # Generate IR code
        self._iinstrs.append(IrInstr(typ=IrInstrType.PARAM, operands=[number]))
        self._iinstrs.append(IrInstr(typ=IrInstrType.PARAM, operands=[socket]))
        self._iinstrs.append(
            IrInstr(typ=IrInstrType.CALL, operands=[results, "IR_epr_recv_meas", 2])
        )

        # Return handle to variable for use in SDK
        return [EprResultHandle(rslt) for rslt in results]

    def _new_block(self) -> IrBlk:
        blk = IrBlk()
        self._iblks.append(blk)
        return blk

    def _cond_binary(
        self, a: T_IntegerHandle, b: T_IntegerHandle, typ: IrInstrType
    ) -> None:
        assert typ in [
            IrInstrType.BEQ,
            IrInstrType.BNE,
            IrInstrType.BGE,
            IrInstrType.BLT,
        ]
        # Block for body
        body: IrBlk = self._new_block()
        self._iinstrs.append(IrInstr(typ=typ, operands=[a, b, body]))
        self._iinstrs.append(IrInstr(typ=IrInstrType.BLK_START, operands=[body, 0]))
        self._iinstrs.append(IrInstr(typ=IrInstrType.BLK_END, operands=[body]))

        # Block for after body
        after: IrBlk = self._new_block()
        self._iinstrs.append(IrInstr(typ=IrInstrType.BLK_START, operands=[after, 0]))

    def if_eq(self, a: T_IntegerHandle, b: T_IntegerHandle) -> None:
        """Execute `body` if a == b"""
        self._cond_binary(a, b, IrInstrType.BEQ)

    def if_ne(self, a: T_IntegerHandle, b: T_IntegerHandle) -> None:
        """Execute `body` if a != b"""
        self._cond_binary(a, b, IrInstrType.BNE)

    def if_lt(self, a: T_IntegerHandle, b: T_IntegerHandle) -> None:
        """Execute `body` if a < b"""
        self._cond_binary(a, b, IrInstrType.BLT)

    def if_ge(self, a: T_IntegerHandle, b: T_IntegerHandle) -> None:
        """Execute `body` if a > b"""
        self._cond_binary(a, b, IrInstrType.BGE)

    def _cond_unary(self, a: T_IntegerHandle, typ: IrInstrType) -> None:
        assert typ in [IrInstrType.BEZ, IrInstrType.BNZ]
        # Block for body
        body: IrBlk = self._new_block()
        self._iinstrs.append(IrInstr(typ=typ, operands=[a, body]))
        self._iinstrs.append(IrInstr(typ=IrInstrType.BLK_START, operands=[body, 0]))
        self._iinstrs.append(IrInstr(typ=IrInstrType.BLK_END, operands=[body]))

        # Block for after body
        after: IrBlk = self._new_block()
        self._iinstrs.append(IrInstr(typ=IrInstrType.BLK_START, operands=[after, 0]))

    def if_ez(self, a: T_IntegerHandle) -> None:
        """Execute `body` if a == 0"""
        self._cond_unary(a, IrInstrType.BEZ)

    def if_nz(self, a: T_IntegerHandle) -> None:
        """Execute `body` if a != 0"""
        self._cond_unary(a, IrInstrType.BNZ)

    # @contextmanager
    # def loop(
    #     self,
    #     stop: int,
    #     start: int = 0,
    #     step: int = 1,
    #     loop_register: Optional[operand.Register] = None,
    # ) -> Iterator[operand.Register]:
    #     try:
    #         pre_commands = self._pop_pending_commands()
    #         loop_register_result = self._handle_loop_register(
    #             loop_register, activate=True
    #         )
    #         yield loop_register_result
    #     finally:
    #         body_commands = self._pop_pending_commands()
    #         self._add_loop_commands(
    #             pre_commands=pre_commands,
    #             body_commands=body_commands,
    #             stop=stop,
    #             start=start,
    #             step=step,
    #             loop_register=loop_register_result,
    #         )
    #         self._remove_active_register(register=loop_register_result)

    # def loop_body(
    #     self,
    #     body: T_LoopRoutine,
    #     stop: int,
    #     start: int = 0,
    #     step: int = 1,
    #     loop_register: Optional[operand.Register] = None,
    # ) -> None:
    #     """An effective loop-statement where body is a function executed, a number of times specified
    #     by `start`, `stop` and `step`.
    #     """
    #     loop_register = self._handle_loop_register(loop_register)

    #     pre_commands = self._pop_pending_commands()
    #     with self._activate_register(loop_register):
    #         body(self)
    #     body_commands = self._pop_pending_commands()
    #     self._add_loop_commands(
    #         pre_commands=pre_commands,
    #         body_commands=body_commands,
    #         stop=stop,
    #         start=start,
    #         step=step,
    #         loop_register=loop_register,
    #     )
