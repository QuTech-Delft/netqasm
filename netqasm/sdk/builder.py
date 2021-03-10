# type: ignore
# flake8: noqa
"""TODO write about connections"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
import abc

from netqasm.sdk.network import NetworkInfo
from netqasm.sdk.config import LogConfig
from netqasm.backend.messages import (
    Signal,
    InitNewAppMessage,
    StopAppMessage,
    OpenEPRSocketMessage,
    SubroutineMessage,
    SignalMessage,
    Message,
)
from netqasm.lang.instr import operand
from netqasm.lang.subroutine import Subroutine
from netqasm.lang.ir import (
    PreSubroutine,
    ICmd,
    Address,
    ArrayEntry,
    ArraySlice,
    Label,
    BranchLabel,
    Symbols,
    T_OperandUnion
)
from netqasm.lang.encoding import RegisterName, REG_INDEX_BITS
from netqasm.backend.network_stack import OK_FIELDS_K, OK_FIELDS_M
from netqasm.util.log import LineTracker
from netqasm.sdk.compiling import NVSubroutineCompiler, SubroutineCompiler
from netqasm.sdk.progress_bar import ProgressBar
from netqasm.sdk.toolbox import get_angle_spec_from_float
from netqasm.sdk.futures import Future, RegFuture, Array
from netqasm.sdk.qubit import Qubit, _FutureQubit
from netqasm.sdk.shared_memory import SharedMemory, SharedMemoryManager
from netqasm.lang.instr.instr_enum import GenericInstr, flip_branch_instr
from netqasm.lang.parsing.text import assemble_subroutine, parse_register, get_current_registers, parse_address
from netqasm.logging.glob import get_netqasm_logger
from netqasm import NETQASM_VERSION
from qlink_interface import (
    EPRType,
    RandomBasis,
    LinkLayerCreate,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
)
from typing import TYPE_CHECKING
import os
import abc
import math
import pickle
import logging
from enum import Enum
from itertools import count
from contextlib import contextmanager
from typing import List, Optional, Dict, Type, Union, Set, Tuple, Callable, Iterator

T_Cmd = Union[ICmd, BranchLabel]
T_LinkLayerOkList = Union[List[LinkLayerOKTypeK], List[LinkLayerOKTypeM], List[LinkLayerOKTypeR]]
T_Message = Union[Message, SubroutineMessage]
T_CValue = Union[int, Future, RegFuture]
T_PostRoutine = Callable[['BaseNetQASMConnection', Union[_FutureQubit, List[Future]], operand.Register], None]
T_BranchRoutine = Callable[['BaseNetQASMConnection'], None]
T_LoopRoutine = Callable[['BaseNetQASMConnection'], None]

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


class _IReg:
    _COUNT: int = 0

    def __init__(self):
        self.id: int = self.__class__._COUNT
        self.__class__._COUNT += 1


class _IArr:
    _COUNT: int = 0

    def __init__(self):
        self.id: int = self.__class__._COUNT
        self.__class__._COUNT += 1


class _IQbt:
    _COUNT: int = 0

    def __init__(self):
        self.id: int = self.__class__._COUNT
        self.__class__._COUNT += 1


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


class _ICmd:
    def __init__(self, typ: _ICmdType):
        self.typ: _ICmdType = typ


class ArrayHandle:
    def __init__(self, iarr: _IArr):
        self._iarr: _IArr = iarr

    def get_value(self, index: int) -> Optional[int]:
        raise NotImplementedError

    def get_values(self, range: slice) -> List[Optional[int]]:
        raise NotImplementedError

    def get_value_as_future(self, index: int) -> Future:
        raise NotImplementedError

    def get_values_as_futures(self, range: slice) -> List[Future]:
        raise NotImplementedError


class RegisterHandle:
    def __init__(self, ireg: _IReg):
        self._ireg: _IReg = ireg

    def get_value(self, index: int) -> Optional[int]:
        raise NotImplementedError

    def get_value_as_future(self, index: int) -> Future:
        raise NotImplementedError


class QubitHandle:
    def __init__(self, iqbt: _IQbt):
        self._iqbt: _IQbt = iqbt

    def get_qubit(self) -> Qubit:
        raise NotImplementedError


class Builder:
    def __init__(
        self,
        app_name: str,
        node_name: Optional[str] = None,
        app_id: Optional[int] = None,
        max_qubits: int = 5,
        log_config: LogConfig = None,
        epr_sockets: Optional[List[EPRSocket]] = None,
        compiler: Optional[Type[SubroutineCompiler]] = None,
        return_arrays: bool = True,
    ):
        # IR
        self._iregs: Set[_IReg] = set()
        self._iarrays: Set[_IArr] = set()
        self._iqubits: Set[_IQbt] = set()

        self._icmds: List[_ICmd] = []

        # All qubits active for this connection
        self.active_qubits: List[Qubit] = []

        self._used_array_addresses: List[int] = []

        self._used_meas_registers: List[int] = []

        self._pending_commands: List[T_Cmd] = []

        self._max_qubits: int = max_qubits

        # What compiler (if any) to be used
        self._compiler: Optional[Type[SubroutineCompiler]] = compiler

    def new_array(self, length: int = 1, init_values: Optional[List[Optional[int]]] = None) -> ArrayHandle:
        arr = _IArr()
        self._iarrays.add(arr)
        return ArrayHandle(arr)

    def new_register(self, init_value: int = 0) -> RegisterHandle:
        reg = _IReg()
        self._iregs.add(reg)
        return RegisterHandle(reg)

    def new_qubit(self) -> QubitHandle:
        qbt = _IQbt()
        self._iqubits.add(qbt)
        return QubitHandle(qbt)

    def _push_cmd(self, cmd: _ICmd) -> None:
        self._icmds.append(cmd)

    def add_single_qubit_rotation_commands(
        self, instruction: GenericInstr, virtual_qubit_id: int, angle: float
    ) -> None:
        cmd = _ICmd(typ=_ICmdType.Q_SINGLE_PARM)
        self._push_cmd(cmd)

    def add_single_qubit_commands(self, instr: GenericInstr, qubit_id: int) -> None:
        register, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        # Construct the qubit command
        qubit_command = ICmd(
            instruction=instr,
            operands=[register],
        )
        commands: List[T_Cmd] = set_commands + [qubit_command]
        self.add_pending_commands(commands)

    def add_two_qubit_commands(self, instr: GenericInstr, control_qubit_id: int, target_qubit_id: int) -> None:
        register1, set_commands1 = self._get_set_qubit_reg_commands(control_qubit_id, reg_index=0)
        register2, set_commands2 = self._get_set_qubit_reg_commands(target_qubit_id, reg_index=1)
        qubit_command = ICmd(
            instruction=instr,
            operands=[register1, register2],
        )
        commands = set_commands1 + set_commands2 + [qubit_command]
        self.add_pending_commands(commands=commands)

    def add_measure_commands(self, qubit_id: int, future: Union[Future, RegFuture], inplace: bool) -> None:
        if self._compiler == NVSubroutineCompiler:
            # If compiling for NV, only virtual ID 0 can be used to measure a qubit.
            # So, if this qubit is already in use, we need to move it away first.
            if not isinstance(qubit_id, Future):
                if qubit_id != 0:
                    self._free_up_qubit(virtual_address=0)
        outcome_reg = self._get_new_meas_outcome_reg()
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        meas_command = ICmd(
            instruction=GenericInstr.MEAS,
            operands=[qubit_reg, outcome_reg],
        )
        if not inplace:
            free_commands = [ICmd(
                instruction=GenericInstr.QFREE,
                operands=[qubit_reg],
            )]
        else:
            free_commands = []
        if future is not None:
            if isinstance(future, Future):
                outcome_commands = future._get_store_commands(outcome_reg)
            elif isinstance(future, RegFuture):
                future.reg = outcome_reg
                self._registers_to_return.append(outcome_reg)
                outcome_commands = []
            else:
                outcome_commands = []
        commands = set_commands + [meas_command] + free_commands + outcome_commands  # type: ignore
        self.add_pending_commands(commands)

    def add_new_qubit_commands(self, qubit_id: int) -> None:
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        qalloc_command = ICmd(
            instruction=GenericInstr.QALLOC,
            operands=[qubit_reg],
        )
        init_command = ICmd(
            instruction=GenericInstr.INIT,
            operands=[qubit_reg],
        )
        commands = set_commands + [qalloc_command, init_command]
        self.add_pending_commands(commands)

    def add_init_qubit_commands(self, qubit_id: int) -> None:
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        init_command = ICmd(
            instruction=GenericInstr.INIT,
            operands=[qubit_reg],
        )
        commands = set_commands + [init_command]
        self.add_pending_commands(commands)

    def add_qfree_commands(self, qubit_id: int) -> None:
        qubit_reg, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        qfree_command = ICmd(
            instruction=GenericInstr.QFREE,
            operands=[qubit_reg],
        )
        commands = set_commands + [qfree_command]
        self.add_pending_commands(commands)

    def create_epr(
        self,
        remote_node_id: int,
        epr_socket_id: int,
        number: int = 1,
        post_routine: Optional[T_PostRoutine] = None,
        sequential: bool = False,
        tp: EPRType = EPRType.K,
        random_basis_local: Optional[RandomBasis] = None,
        random_basis_remote: Optional[RandomBasis] = None,
        rotations_local: Tuple[int, int, int] = (0, 0, 0),
        rotations_remote: Tuple[int, int, int] = (0, 0, 0),
    ) -> Union[List[Qubit], T_LinkLayerOkList]:
        """Receives EPR pair with a remote node"""
        if not isinstance(remote_node_id, int):
            raise TypeError(f"remote_node_id should be an int, not of type {type(remote_node_id)}")

        return self._handle_request(
            instruction=GenericInstr.CREATE_EPR,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            number=number,
            post_routine=post_routine,
            sequential=sequential,
            tp=tp,
            random_basis_local=random_basis_local,
            random_basis_remote=random_basis_remote,
            rotations_local=rotations_local,
            rotations_remote=rotations_remote,
        )

    def recv_epr(
        self,
        remote_node_id: int,
        epr_socket_id: int,
        number: int = 1,
        post_routine: Optional[T_PostRoutine] = None,
        sequential: bool = False,
        tp: EPRType = EPRType.K,
    ) -> Union[List[Qubit], T_LinkLayerOkList]:
        """Receives EPR pair with a remote node"""
        return self._handle_request(
            instruction=GenericInstr.RECV_EPR,
            remote_node_id=remote_node_id,
            epr_socket_id=epr_socket_id,
            number=number,
            post_routine=post_routine,
            sequential=sequential,
            tp=tp,
        )

    def if_eq(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a == b"""
        self._handle_if(GenericInstr.BEQ, a, b, body)

    def if_ne(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a != b"""
        self._handle_if(GenericInstr.BNE, a, b, body)

    def if_lt(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a < b"""
        self._handle_if(GenericInstr.BLT, a, b, body)

    def if_ge(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a >= b"""
        self._handle_if(GenericInstr.BGE, a, b, body)

    def if_ez(self, a: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a == 0"""
        self._handle_if(GenericInstr.BEZ, a, b=None, body=body)

    def if_nz(self, a: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a != 0"""
        self._handle_if(GenericInstr.BNZ, a, b=None, body=body)

    @contextmanager
    def loop(
        self, stop: int, start: int = 0, step: int = 1, loop_register: Optional[operand.Register] = None
    ) -> Iterator[operand.Register]:
        try:
            pre_commands = self._pop_pending_commands()
            loop_register_result = self._handle_loop_register(loop_register, activate=True)
            yield loop_register_result
        finally:
            body_commands = self._pop_pending_commands()
            self._add_loop_commands(
                pre_commands=pre_commands,
                body_commands=body_commands,
                stop=stop,
                start=start,
                step=step,
                loop_register=loop_register_result,
            )
            self._remove_active_register(register=loop_register_result)

    def loop_body(
        self,
        body: T_LoopRoutine,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[operand.Register] = None
    ) -> None:
        """An effective loop-statement where body is a function executed, a number of times specified
        by `start`, `stop` and `step`.
        """
        loop_register = self._handle_loop_register(loop_register)

        pre_commands = self._pop_pending_commands()
        with self._activate_register(loop_register):
            body(self)
        body_commands = self._pop_pending_commands()
        self._add_loop_commands(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=stop,
            start=start,
            step=step,
            loop_register=loop_register,
        )
