"""Conversion from Python code into an NetQASM subroutines.

This module contains the `Builder` class, which is used by a Connection to transform
Python application script code into NetQASM subroutines.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
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

from netqasm import NETQASM_VERSION
from netqasm.backend.network_stack import OK_FIELDS_K, OK_FIELDS_M
from netqasm.lang import operand
from netqasm.lang.encoding import REG_INDEX_BITS, RegisterName
from netqasm.lang.ir import (
    Address,
    ArrayEntry,
    ArraySlice,
    BranchLabel,
    BreakpointAction,
    BreakpointRole,
    GenericInstr,
    ICmd,
    Label,
    PreSubroutine,
    Symbols,
    T_OperandUnion,
    flip_branch_instr,
)
from netqasm.lang.parsing.text import (
    assemble_subroutine,
    get_current_registers,
    parse_address,
    parse_register,
)
from netqasm.lang.subroutine import Subroutine
from netqasm.qlink_compat import (
    EPRType,
    LinkLayerCreate,
    LinkLayerOKTypeK,
    LinkLayerOKTypeM,
    LinkLayerOKTypeR,
    RandomBasis,
    TimeUnit,
)
from netqasm.sdk.compiling import NVSubroutineCompiler, SubroutineCompiler
from netqasm.sdk.config import LogConfig
from netqasm.sdk.futures import Array, Future, RegFuture, T_CValue
from netqasm.sdk.qubit import FutureQubit, Qubit
from netqasm.sdk.toolbox import get_angle_spec_from_float
from netqasm.typedefs import T_Cmd
from netqasm.util.log import LineTracker

T_LinkLayerOkList = Union[
    List[LinkLayerOKTypeK], List[LinkLayerOKTypeM], List[LinkLayerOKTypeR]
]
T_PostRoutine = Callable[
    ["Builder", Union[FutureQubit, List[Future]], operand.Register], None
]
T_BranchRoutine = Callable[["BaseNetQASMConnection"], None]
T_LoopRoutine = Callable[["BaseNetQASMConnection"], None]

if TYPE_CHECKING:
    from .connection import BaseNetQASMConnection


@dataclass
class EntRequestParams:
    remote_node_id: int
    epr_socket_id: int
    number: int
    post_routine: Optional[T_PostRoutine]
    sequential: bool
    time_unit: TimeUnit = TimeUnit.MICRO_SECONDS
    max_time: int = 0
    random_basis_local: Optional[RandomBasis] = None
    random_basis_remote: Optional[RandomBasis] = None
    rotations_local: Tuple[int, int, int] = (0, 0, 0)
    rotations_remote: Tuple[int, int, int] = (0, 0, 0)


class Builder:
    """Object that transforms Python script code into `PreSubroutine`s.

    A Connection uses a Builder to handle statements in application script code.
    The Builder converts the statements into pseudo-NetQASM instructions that are
    assembled into a PreSubroutine. When the connectin flushes, the PreSubroutine is
    is compiled into a NetQASM subroutine.
    """

    ENT_INFO = {
        EPRType.K: LinkLayerOKTypeK,
        EPRType.M: LinkLayerOKTypeM,
        EPRType.R: LinkLayerOKTypeR,
    }

    def __init__(
        self,
        connection,
        app_id: int,
        max_qubits: int = 5,
        log_config: LogConfig = None,
        compiler: Optional[Type[SubroutineCompiler]] = None,
        return_arrays: bool = True,
    ):
        """Builder constructor. Typically not used directly by the Host script.

        :param connection: Connection that this builder builds for
        :param app_id: ID of the application as given by the quantum node controller
        :param max_qubits: maximum number of qubits allowed (as registered with the
            quantum node controller)
        :param log_config: logging configuration, typically just passed as-is by the
            connection object
        :param compiler: which compiler class to use for the translation from
            PreSubroutine to Subroutine
        :param return_arrays: whether to add ret_arr NetQASM instructions at the end of
            each subroutine (for all arrays that are used in the subroutine). May be
            set to False if the quantum node controller does not support returning
            arrays.
        """
        self._connection = connection
        self._app_id = app_id

        # All qubits active for this connection
        self.active_qubits: List[Qubit] = []

        self._used_array_addresses: List[int] = []

        self._used_meas_registers: Dict[operand.Register, bool] = {
            operand.Register(RegisterName.M, i): False for i in range(16)
        }

        self._pending_commands: List[T_Cmd] = []

        self._max_qubits: int = max_qubits

        # Registers for looping etc.
        # These are registers that are for example currently hold data and should
        # not be used for something else.
        # For example a register used for looping.
        self._active_registers: Set[operand.Register] = set()

        # Arrays to return
        self._arrays_to_return: List[Array] = []

        # If False, don't return arrays even if they are used in a subroutine
        self._return_arrays: bool = return_arrays

        # Registers to return
        self._registers_to_return: List[operand.Register] = []

        # Storing commands before an conditional statement
        self._pre_context_commands: Dict[int, List[T_Cmd]] = {}

        self._used_branch_variables: List[str] = []

        # Can be set to false for e.g. debugging, not exposed to user atm
        self._clear_app_on_exit: bool = True
        self._stop_backend_on_exit: bool = True

        if log_config is None:
            log_config = LogConfig()

        self._line_tracker: LineTracker = LineTracker(log_config=log_config)
        self._track_lines: bool = log_config.track_lines

        # Commited subroutines saved for logging/debugging
        self._committed_subroutines: List[Subroutine] = []

        # What compiler (if any) to be used
        self._compiler: Optional[Type[SubroutineCompiler]] = compiler

    @property
    def app_id(self) -> int:
        return self._app_id

    @app_id.setter
    def app_id(self, id: int) -> None:
        self._app_id = id

    def inactivate_qubits(self) -> None:
        while len(self.active_qubits) > 0:
            q = self.active_qubits.pop()
            q.active = False

    def new_qubit_id(self) -> int:
        return self._get_new_qubit_address()

    def new_array(
        self, length: int = 1, init_values: Optional[List[Optional[int]]] = None
    ) -> Array:
        address = self._get_new_array_address()
        lineno = self._line_tracker.get_line()
        array = Array(
            connection=self._connection,
            length=length,
            address=address,
            init_values=init_values,
            lineno=lineno,
        )
        self._arrays_to_return.append(array)
        return array

    def new_register(self, init_value: int = 0) -> RegFuture:
        reg = self._get_inactive_register(activate=True)
        self.add_pending_command(
            ICmd(instruction=GenericInstr.SET, operands=[reg, init_value])
        )
        self._registers_to_return.append(reg)
        return RegFuture(connection=self._connection, reg=reg)

    def add_pending_commands(self, commands: List[T_Cmd]) -> None:
        calling_lineno = self._line_tracker.get_line()
        for command in commands:
            if command.lineno is None:
                command.lineno = calling_lineno
            self.add_pending_command(command)

    def add_pending_command(self, command: T_Cmd) -> None:
        assert isinstance(command, ICmd) or isinstance(command, BranchLabel)
        if command.lineno is None:
            command.lineno = self._line_tracker.get_line()
        self._pending_commands.append(command)

    def _pop_pending_subroutine(self) -> Optional[PreSubroutine]:
        # Add commands for initialising and returning arrays
        self._add_array_commands()
        self._add_ret_reg_commands()
        subroutine = None
        if len(self._pending_commands) > 0:
            commands = self._pop_pending_commands()
            subroutine = self._subroutine_from_commands(commands)
        return subroutine

    def _add_ret_reg_commands(self) -> None:
        ret_reg_instrs: List[T_Cmd] = []
        for reg in self._registers_to_return:
            ret_reg_instrs.append(
                ICmd(instruction=GenericInstr.RET_REG, operands=[reg])
            )
        self.add_pending_commands(commands=ret_reg_instrs)

    def _add_array_commands(self) -> None:
        current_commands = self._pop_pending_commands()
        array_commands = self._get_array_commands()
        init_arrays, return_arrays = array_commands
        commands: List[T_Cmd] = init_arrays + current_commands + return_arrays  # type: ignore
        self.add_pending_commands(commands=commands)

    def _get_array_commands(self) -> Tuple[List[T_Cmd], List[T_Cmd]]:
        init_arrays: List[T_Cmd] = []
        return_arrays: List[T_Cmd] = []
        for array in self._arrays_to_return:
            # ICmd for initialising the array
            init_arrays.append(
                ICmd(
                    instruction=GenericInstr.ARRAY,
                    operands=[
                        len(array),
                        Address(array.address),
                    ],
                    lineno=array.lineno,
                )
            )
            # Populate the array if needed
            init_vals = array._init_values
            if init_vals is not None:
                length = len(init_vals)
                if length > 1 and init_vals.count(init_vals[0]) == length:
                    # Ad-hoc optimization: if all values are the same, put the initialization commands in a loop
                    loop_register = self._get_inactive_register()

                    def init_array_elt(conn):
                        conn._builder.add_pending_command(
                            ICmd(
                                instruction=GenericInstr.STORE,
                                operands=[
                                    init_vals[0],
                                    ArrayEntry(Address(array.address), loop_register),
                                ],
                                lineno=array.lineno,
                            )
                        )

                    self.loop_body(
                        init_array_elt, stop=length, loop_register=loop_register
                    )
                    init_arrays += self._pop_pending_commands()
                else:
                    for i, value in enumerate(init_vals):
                        if value is None:
                            continue
                        else:
                            init_arrays.append(
                                ICmd(
                                    instruction=GenericInstr.STORE,
                                    operands=[
                                        value,
                                        ArrayEntry(Address(array.address), i),
                                    ],
                                    lineno=array.lineno,
                                )
                            )
            # ICmd for returning the array by the end of the subroutine
            if self._return_arrays:
                return_arrays.append(
                    ICmd(
                        instruction=GenericInstr.RET_ARR,
                        operands=[
                            Address(array.address),
                        ],
                        lineno=array.lineno,
                    )
                )
        return init_arrays, return_arrays

    def _subroutine_from_commands(self, commands: List[T_Cmd]) -> PreSubroutine:
        # Build sub-routine
        metadata = self._get_metadata()
        return PreSubroutine(**metadata, commands=commands)  # type: ignore

    def _get_metadata(self) -> Dict:
        return {
            "netqasm_version": NETQASM_VERSION,
            "app_id": self.app_id,
        }

    def _pop_pending_commands(self) -> List[T_Cmd]:
        commands = self._pending_commands
        self._pending_commands = []
        return commands

    def _pre_process_subroutine(self, pre_subroutine: PreSubroutine) -> Subroutine:
        """Convert a PreSubroutine into a Subroutine."""
        subroutine: Subroutine = assemble_subroutine(pre_subroutine)
        if self._compiler is not None:
            subroutine = self._compiler(subroutine=subroutine).compile()
        if self._track_lines:
            self._log_subroutine(subroutine=subroutine)
        return subroutine

    def _log_subroutine(self, subroutine: Subroutine) -> None:
        self._committed_subroutines.append(subroutine)

    @property
    def committed_subroutines(self) -> List[Subroutine]:
        return self._committed_subroutines

    def add_single_qubit_rotation_commands(
        self,
        instruction: GenericInstr,
        virtual_qubit_id: int,
        n: int = 0,
        d: int = 0,
        angle: Optional[float] = None,
    ) -> None:
        if angle is not None:
            nds = get_angle_spec_from_float(angle=angle)
            for n, d in nds:
                self.add_single_qubit_rotation_commands(
                    instruction=instruction,
                    virtual_qubit_id=virtual_qubit_id,
                    n=n,
                    d=d,
                )
            return
        if not (isinstance(n, int) and isinstance(d, int) and n >= 0 and d >= 0):
            raise ValueError(f"{n} * pi / 2 ^ {d} is not a valid angle specification")
        register, set_commands = self._get_set_qubit_reg_commands(virtual_qubit_id)
        rot_command = ICmd(
            instruction=instruction,
            operands=[register, n, d],
        )
        commands: List[T_Cmd] = set_commands + [rot_command]
        self.add_pending_commands(commands)

    def add_single_qubit_commands(self, instr: GenericInstr, qubit_id: int) -> None:
        register, set_commands = self._get_set_qubit_reg_commands(qubit_id)
        # Construct the qubit command
        qubit_command = ICmd(
            instruction=instr,
            operands=[register],
        )
        commands: List[T_Cmd] = set_commands + [qubit_command]
        self.add_pending_commands(commands)

    def _get_set_qubit_reg_commands(
        self, q_address: Union[Future, int], reg_index: int = 0
    ) -> Tuple[operand.Register, List[T_Cmd]]:
        # Set the register with the qubit address
        register = operand.Register(RegisterName.Q, reg_index)
        if isinstance(q_address, Future):
            set_reg_cmds = q_address._get_load_commands(register)
        elif isinstance(q_address, int):
            set_reg_cmds = [
                ICmd(
                    instruction=GenericInstr.SET,
                    operands=[
                        register,
                        q_address,
                    ],
                )
            ]
        else:
            raise NotImplementedError(
                "Setting qubit reg for other types not yet implemented"
            )
        return register, set_reg_cmds

    def add_two_qubit_commands(
        self, instr: GenericInstr, control_qubit_id: int, target_qubit_id: int
    ) -> None:
        register1, set_commands1 = self._get_set_qubit_reg_commands(
            control_qubit_id, reg_index=0
        )
        register2, set_commands2 = self._get_set_qubit_reg_commands(
            target_qubit_id, reg_index=1
        )
        qubit_command = ICmd(
            instruction=instr,
            operands=[register1, register2],
        )
        commands = set_commands1 + set_commands2 + [qubit_command]
        self.add_pending_commands(commands=commands)

    def _add_move_qubit_commands(self, source: int, target: int) -> None:
        # Moves a qubit from one position to another (assumes that target is free)
        assert target not in [q.qubit_id for q in self.active_qubits]
        self.add_new_qubit_commands(target)
        self.add_two_qubit_commands(GenericInstr.MOV, source, target)
        self.add_qfree_commands(source)

    def _free_up_qubit(self, virtual_address: int) -> None:
        if self._compiler == NVSubroutineCompiler:
            for q in self.active_qubits:
                # Find a free qubit
                new_virtual_address = self._get_new_qubit_address()
                if q.qubit_id == virtual_address:
                    # Virtual address is already used. Move it to the new virtual address.
                    # NOTE: this assumes that the new virtual address is *not* currently used.
                    self._add_move_qubit_commands(
                        source=virtual_address, target=new_virtual_address
                    )
                    # From now on, the original qubit should be referred to with the new virtual address.
                    q.qubit_id = new_virtual_address

    def add_measure_commands(
        self, qubit_id: int, future: Union[Future, RegFuture], inplace: bool
    ) -> None:
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
            free_commands = [
                ICmd(
                    instruction=GenericInstr.QFREE,
                    operands=[qubit_reg],
                )
            ]
        else:
            free_commands = []
        if future is not None:
            if isinstance(future, Future):
                outcome_commands = future._get_store_commands(outcome_reg)
                self._used_meas_registers[outcome_reg] = False
            elif isinstance(future, RegFuture):
                future.reg = outcome_reg
                self._registers_to_return.append(outcome_reg)
                outcome_commands = []
            else:
                outcome_commands = []
        commands = set_commands + [meas_command] + free_commands + outcome_commands  # type: ignore
        self.add_pending_commands(commands)

    def _get_new_meas_outcome_reg(self) -> operand.Register:
        # Find the next unused M-register.
        for reg, used in self._used_meas_registers.items():
            if not used:
                self._used_meas_registers[reg] = True
                return reg
        raise RuntimeError("Ran out of M-registers")

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

    def _build_epr_create_args(self, tp: EPRType, params: EntRequestParams) -> Array:
        create_kwargs: Dict[str, Any] = {}
        create_kwargs["type"] = tp
        create_kwargs["number"] = params.number
        if params.max_time != 0:  # if 0, don't need to set value explicitly
            create_kwargs["time_unit"] = params.time_unit.value
            create_kwargs["max_time"] = params.max_time
        # TODO currently this give 50 / 50 since with the current link layer
        # This should change and not be hardcoded here
        if params.random_basis_local is not None:
            # NOTE Currently there is not value one can set to specify
            # a uniform distribution for three bases. This needs to be changed
            # in the underlying link layer/network stack
            assert params.random_basis_local in [
                RandomBasis.XZ,
                RandomBasis.CHSH,
            ], "Can only random measure in one of two bases for now"
            create_kwargs["random_basis_local"] = params.random_basis_local
            create_kwargs["probability_dist_local1"] = 128
        if params.random_basis_remote is not None:
            assert params.random_basis_remote in [
                RandomBasis.XZ,
                RandomBasis.CHSH,
            ], "Can only random measure in one of two bases for now"
            create_kwargs["random_basis_remote"] = params.random_basis_remote
            create_kwargs["probability_dist_remote1"] = 128

        if tp == EPRType.M or tp == EPRType.R:
            rotx1_local, roty_local, rotx2_local = params.rotations_local
            rotx1_remote, roty_remote, rotx2_remote = params.rotations_remote

            if params.rotations_local != (
                0,
                0,
                0,
            ):  # instructions for explicitly setting to zero are redundant
                create_kwargs["rotation_X_local1"] = rotx1_local
                create_kwargs["rotation_Y_local"] = roty_local
                create_kwargs["rotation_X_local2"] = rotx2_local

            if params.rotations_remote != (
                0,
                0,
                0,
            ):  # instructions for explicitly setting to zero are redundant
                create_kwargs["rotation_X_remote1"] = rotx1_remote
                create_kwargs["rotation_Y_remote"] = roty_remote
                create_kwargs["rotation_X_remote2"] = rotx2_remote

        create_args = []
        # NOTE we don't include the two first args since these are remote_node_id
        # and epr_socket_id which come as registers
        for field in LinkLayerCreate._fields[2:]:
            arg = create_kwargs.get(field)
            # If Enum, use its value
            if isinstance(arg, Enum):
                arg = arg.value
            create_args.append(arg)
        # TODO don't create a new array if already created from previous command
        return self.new_array(init_values=create_args)

    def _add_epr_commands(
        self,
        instruction: GenericInstr,
        qubit_ids_array: Optional[Array],
        ent_results_array: Array,
        wait_all: bool,
        tp: EPRType,
        params: EntRequestParams,
        **kwargs,
    ) -> None:
        qubit_ids_array_address: Union[int, operand.Register]
        epr_cmd_operands: List[T_OperandUnion]

        if tp == EPRType.K or (
            tp == EPRType.R and instruction == GenericInstr.RECV_EPR
        ):
            assert qubit_ids_array is not None
            qubit_ids_array_address = qubit_ids_array.address
        else:
            # NOTE since this argument won't be used just set it to some
            # constant register for now
            qubit_ids_array_address = operand.Register(RegisterName.C, 0)

        if instruction == GenericInstr.CREATE_EPR:
            create_args_array = self._build_epr_create_args(tp, params)
            epr_cmd_operands = [
                qubit_ids_array_address,
                create_args_array.address,
                ent_results_array.address,
            ]
        elif instruction == GenericInstr.RECV_EPR:
            epr_cmd_operands = [
                qubit_ids_array_address,
                ent_results_array.address,
            ]
        else:
            raise ValueError(f"Not an epr instruction {instruction}")

        # epr command
        epr_cmd = ICmd(
            instruction=instruction,
            args=[params.remote_node_id, params.epr_socket_id],
            operands=epr_cmd_operands,
        )

        # wait
        arr_slice = ArraySlice(
            ent_results_array.address, start=0, stop=len(ent_results_array)  # type: ignore
        )
        if wait_all:
            wait_cmds = [ICmd(instruction=GenericInstr.WAIT_ALL, operands=[arr_slice])]
        else:
            wait_cmds = []

        commands: List[T_Cmd] = [epr_cmd] + wait_cmds  # type: ignore
        self.add_pending_commands(commands)

    def _add_post_commands(
        self,
        qubit_ids: Optional[Array],
        number: int,
        ent_results_array: Array,
        tp: EPRType,
        post_routine: T_PostRoutine,
    ) -> None:

        loop_register = self._get_inactive_register()

        def post_loop(conn):
            # Wait for each pair individually
            pair = loop_register
            conn._builder._add_wait_for_ent_info_cmd(
                ent_results_array=ent_results_array,
                pair=pair,
            )
            if tp == EPRType.K or tp == EPRType.R:
                q_id = qubit_ids.get_future_index(pair)
                q = FutureQubit(conn=conn, future_id=q_id)
                post_routine(self, q, pair)
            elif tp == EPRType.M:
                slc = slice(pair * OK_FIELDS_M, (pair + 1) * OK_FIELDS_M)
                ent_info_slice = ent_results_array.get_future_slice(slc)
                post_routine(self, ent_info_slice, pair)
            else:
                raise NotImplementedError

        # TODO use loop context
        self.loop_body(post_loop, stop=number, loop_register=loop_register)

    def _add_wait_for_ent_info_cmd(
        self, ent_results_array: Array, pair: operand.Register
    ) -> None:
        """Wait for the correct slice of the entanglement info array for the given pair"""
        # NOTE arr_start should be pair * OK_FIELDS and
        # arr_stop should be (pair + 1) * OK_FIELDS
        arr_start = self._get_inactive_register(activate=True)
        tmp = self._get_inactive_register(activate=True)
        arr_stop = self._get_inactive_register(activate=True)
        created_regs = [arr_start, tmp, arr_stop]

        for reg in created_regs:
            self.add_pending_command(
                ICmd(
                    instruction=GenericInstr.SET,
                    operands=[reg, 0],
                )
            )

        # Multiply pair * OK_FIELDS
        # TODO use loop context
        def add_arr_start(conn):
            self.add_pending_command(
                ICmd(
                    instruction=GenericInstr.ADD,
                    operands=[arr_start, arr_start, pair],
                )
            )

        self.loop_body(add_arr_start, stop=OK_FIELDS_K)

        # Let tmp be pair + 1
        self.add_pending_command(
            ICmd(
                instruction=GenericInstr.ADD,
                operands=[tmp, pair, 1],
            )
        )

        # Multiply (tmp = pair + 1) * OK_FIELDS
        # TODO use loop context
        def add_arr_stop(conn):
            self.add_pending_command(
                ICmd(
                    instruction=GenericInstr.ADD,
                    operands=[arr_stop, arr_stop, tmp],
                )
            )

        self.loop_body(add_arr_stop, stop=OK_FIELDS_K)

        wait_cmd = ICmd(
            instruction=GenericInstr.WAIT_ALL,
            operands=[
                ArraySlice(
                    Address(ent_results_array.address), start=arr_start, stop=arr_stop
                )
            ],
        )
        self.add_pending_command(wait_cmd)

        for reg in created_regs:
            self._remove_active_register(register=reg)

    def _handle_request(
        self,
        instruction: GenericInstr,
        tp: EPRType,
        params: EntRequestParams,
    ) -> Union[List[Qubit], T_LinkLayerOkList]:
        self._assert_epr_args(
            number=params.number,
            post_routine=params.post_routine,
            sequential=params.sequential,
            tp=tp,
        )
        # NOTE the `output` is either a list of qubits or a list of entanglement information
        # depending on the type of the request.

        # Setup NetQASM arrays and SDK handles.

        # Entanglement results array.
        # This will be filled in by the quantum node controller.
        ent_results_array = self._create_ent_results_array(number=params.number, tp=tp)

        # K-type requests and receivers of R-type requests need to specify an array
        # with qubit IDs for the generated qubits.
        qubit_ids_array: Optional[Array]

        # SDK handles to result values. For K-type requests and receivers of R-type
        # requests, these are Qubit objects.
        # For M-type requests and senders of R-type requests, these are
        # T_LinkLayerOkType objects.
        result_futures: Union[List[Qubit], T_LinkLayerOkList]

        if tp == EPRType.K or (
            tp == EPRType.R and instruction == GenericInstr.RECV_EPR
        ):
            result_futures = self._get_qubit_futures_array(
                params.number, params.sequential, ent_results_array
            )
            assert all(isinstance(q, Qubit) for q in result_futures)
            virtual_qubit_ids = [q.qubit_id for q in result_futures]
            qubit_ids_array = self.new_array(init_values=virtual_qubit_ids)  # type: ignore
        elif tp == EPRType.M or (
            tp == EPRType.R and instruction == GenericInstr.CREATE_EPR
        ):
            result_futures = self._get_meas_dir_futures_array(
                params.number, ent_results_array
            )
            qubit_ids_array = None

        wait_all = params.post_routine is None

        # Construct and add the NetQASM instructions
        self._add_epr_commands(
            instruction=instruction,
            qubit_ids_array=qubit_ids_array,
            ent_results_array=ent_results_array,
            wait_all=wait_all,
            tp=tp,
            params=params,
        )

        # Construct and add NetQASM instructions for post routine
        if params.post_routine:
            self._add_post_commands(
                qubit_ids_array,
                params.number,
                ent_results_array,
                tp,
                params.post_routine,
            )

        return result_futures

    def _pre_epr_context(
        self,
        instruction: GenericInstr,
        tp: EPRType,
        params: EntRequestParams,
    ) -> Tuple[
        List[T_Cmd],
        operand.Register,
        Array,
        Union[List[Qubit], T_LinkLayerOkList, FutureQubit],
        operand.Register,
    ]:
        # NOTE since this is in a context there will be a post_routine
        # TODO Fix weird handling of post_routine parameter here
        def dummy():
            pass

        self._assert_epr_args(
            number=params.number,
            post_routine=dummy,  # type: ignore
            sequential=params.sequential,
            tp=tp,
        )

        # Entanglement results array.
        # This will be filled in by the quantum node controller.
        ent_results_array = self._create_ent_results_array(number=params.number, tp=tp)

        # K-type requests need to specify an array with qubit IDs for the generated
        # qubits.
        qubit_ids_array: Optional[Array]

        # SDK handles to result values. For K-type requests, these are Qubit objects.
        # For M-type requests, these are T_LinkLayerOkTypeM objects.
        result_futures: Union[List[Qubit], T_LinkLayerOkList]

        if tp == EPRType.K or (
            tp == EPRType.R and instruction == GenericInstr.RECV_EPR
        ):
            result_futures = self._get_qubit_futures_array(
                params.number, params.sequential, ent_results_array
            )
            assert all(isinstance(q, Qubit) for q in result_futures)
            virtual_qubit_ids = [q.qubit_id for q in result_futures]
            qubit_ids_array = self.new_array(init_values=virtual_qubit_ids)  # type: ignore
        elif tp == EPRType.M or (
            tp == EPRType.R and instruction == GenericInstr.CREATE_EPR
        ):
            result_futures = self._get_meas_dir_futures_array(
                params.number, ent_results_array
            )
            qubit_ids_array = None

        output: Union[List[Qubit], T_LinkLayerOkList, FutureQubit] = result_futures

        if tp == EPRType.K:
            virtual_qubit_ids = [q.qubit_id for q in result_futures]  # type: ignore
        else:
            raise ValueError(
                "EPR generation as a context is only allowed for K type requests"
            )

        self._add_epr_commands(
            instruction=instruction,
            qubit_ids_array=qubit_ids_array,
            ent_results_array=ent_results_array,
            wait_all=False,
            tp=tp,
            params=params,
        )
        if qubit_ids_array is None:
            raise RuntimeError("qubit_ids_array is None")
        pre_commands = self._pop_pending_commands()
        loop_register = self._get_inactive_register(activate=True)
        pair = loop_register
        if tp == EPRType.K:
            q_id = qubit_ids_array.get_future_index(pair)
            q = FutureQubit(conn=self._connection, future_id=q_id)
            output = q
        # elif tp == EPRType.M:
        #     slc = slice(pair * OK_FIELDS, (pair + 1) * OK_FIELDS)
        #     ent_info_slice = ent_results_array.get_future_slice(slc)
        #     output = ent_info_slice
        else:
            raise NotImplementedError
        return pre_commands, loop_register, ent_results_array, output, pair

    def _post_epr_context(
        self,
        pre_commands: List[T_Cmd],
        number: int,
        loop_register: operand.Register,
        ent_results_array: Array,
        pair: operand.Register,
    ) -> None:
        body_commands = self._pop_pending_commands()
        self._add_wait_for_ent_info_cmd(
            ent_results_array=ent_results_array,
            pair=pair,
        )
        wait_cmds = self._pop_pending_commands()
        body_commands = wait_cmds + body_commands
        self._add_loop_commands(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=number,
            start=0,
            step=1,
            loop_register=loop_register,
        )
        self._remove_active_register(register=loop_register)

    def _assert_epr_args(
        self,
        number: int,
        post_routine: Optional[T_PostRoutine],
        sequential: bool,
        tp: EPRType,
    ) -> None:
        assert isinstance(tp, EPRType), "tp is not an EPRType"
        if sequential and number > 1:
            if post_routine is None:
                raise ValueError(
                    "When using sequential mode with more than one pair "
                    "a post_routine needs to be specified which consumes the "
                    "generated pair as they come in."
                )
        if tp == EPRType.K and not sequential and number > self._max_qubits:
            raise ValueError(
                f"When not using sequential mode for K type, the number of pairs {number} cannot be "
                f"greater than the maximum number of qubits specified ({self._max_qubits})."
            )

    def _create_ent_results_array(self, number: int, tp: EPRType) -> Array:
        if tp == EPRType.K:
            ent_results_array = self.new_array(length=OK_FIELDS_K * number)
        elif tp == EPRType.M:
            ent_results_array = self.new_array(length=OK_FIELDS_M * number)
        elif tp == EPRType.R:
            # NOTE: also for R-type request we use the LinkLayerOkTypeM type
            ent_results_array = self.new_array(length=OK_FIELDS_M * number)
        else:
            raise ValueError(f"Unsupported Create type: {tp}")
        return ent_results_array

    def _get_meas_dir_futures_array(
        self, number: int, ent_results_array: Array
    ) -> T_LinkLayerOkList:
        return self._create_ent_info_m_slices(
            num_pairs=number, ent_results_array=ent_results_array
        )

    def _get_qubit_futures_array(
        self, number: int, sequential: bool, ent_results_array: Array
    ) -> List[Qubit]:
        ent_info_slices = self._create_ent_info_k_slices(
            num_pairs=number, ent_results_array=ent_results_array
        )
        qubits = self._create_ent_qubits(
            ent_info_slices=ent_info_slices,
            sequential=sequential,
        )
        return qubits

    def _create_ent_info_k_slices(
        self, num_pairs: int, ent_results_array: Array
    ) -> List[LinkLayerOKTypeK]:
        ent_info_slices = []
        for i in range(num_pairs):
            ent_info_slice_futures: List[Future] = ent_results_array.get_future_slice(
                slice(i * OK_FIELDS_K, (i + 1) * OK_FIELDS_K)
            )
            ent_info_slice = LinkLayerOKTypeK(*ent_info_slice_futures)
            ent_info_slices.append(ent_info_slice)
        return ent_info_slices

    def _create_ent_info_m_slices(
        self, num_pairs: int, ent_results_array: Array
    ) -> List[LinkLayerOKTypeM]:
        ent_info_slices = []
        for i in range(num_pairs):
            ent_info_slice_futures: List[Future] = ent_results_array.get_future_slice(
                slice(i * OK_FIELDS_M, (i + 1) * OK_FIELDS_M)
            )
            ent_info_slice = LinkLayerOKTypeM(*ent_info_slice_futures)
            ent_info_slices.append(ent_info_slice)
        return ent_info_slices

    def _create_ent_qubits(
        self,
        ent_info_slices: T_LinkLayerOkList,
        sequential: bool,
    ) -> List[Qubit]:
        qubits = []
        virtual_address = None
        for i, ent_info_slice in enumerate(ent_info_slices):
            # If sequential we want all qubits to have the same ID
            if sequential:
                if i == 0:
                    if self._compiler == NVSubroutineCompiler:
                        # If compiling for NV, only virtual ID 0 can be used to store the entangled
                        # qubit. So, if this qubit is already in use, we need to move it away first.
                        virtual_address = 0
                        # FIXME: Unlike in the non-sequential case we do not free. This is because
                        # currently if multiple CREATE commands are issued this will incorrectly think
                        # that the virtual_address 0 is in use. This will in turn trigger a move which
                        # will break the code on nodes with no storage qubits.
                    qubit = Qubit(
                        self._connection,
                        add_new_command=False,
                        ent_info=ent_info_slice,  # type: ignore
                        virtual_address=virtual_address,
                    )
                    virtual_address = qubit.qubit_id
                else:
                    qubit = Qubit(
                        self._connection,
                        add_new_command=False,
                        ent_info=ent_info_slice,  # type: ignore
                        virtual_address=virtual_address,
                    )
            else:
                virtual_address = None
                if self._compiler == NVSubroutineCompiler:
                    # If compiling for NV, only virtual ID 0 can be used to store the entangled qubit.
                    # So, if this qubit is already in use, we need to move it away first.
                    virtual_address = 0
                    self._free_up_qubit(virtual_address=virtual_address)
                qubit = Qubit(
                    self._connection,
                    add_new_command=False,
                    ent_info=ent_info_slice,  # type: ignore
                    virtual_address=virtual_address,
                )
            qubits.append(qubit)

        return qubits

    def create_epr(
        self,
        tp: EPRType,
        params: EntRequestParams,
    ) -> Union[List[Qubit], T_LinkLayerOkList]:
        """Receives EPR pair with a remote node"""
        if not isinstance(params.remote_node_id, int):
            raise TypeError(
                f"remote_node_id should be an int, not of type {type(params.remote_node_id)}"
            )

        return self._handle_request(
            instruction=GenericInstr.CREATE_EPR, tp=tp, params=params
        )

    def recv_epr(
        self,
        tp: EPRType,
        params: EntRequestParams,
    ) -> Union[List[Qubit], T_LinkLayerOkList]:
        """Receives EPR pair with a remote node"""
        return self._handle_request(
            instruction=GenericInstr.RECV_EPR, tp=tp, params=params
        )

    def _get_new_qubit_address(self) -> int:
        qubit_addresses_in_use = [q.qubit_id for q in self.active_qubits]
        for address in count(0):
            if address not in qubit_addresses_in_use:
                return address
        raise RuntimeError("Could not get new qubit address")

    def _get_new_array_address(self) -> int:
        if len(self._used_array_addresses) > 0:
            # last element is always the highest address
            address = self._used_array_addresses[-1] + 1
        else:
            address = 0
        self._used_array_addresses.append(address)
        return address

    def _reset(self) -> None:
        # if len(self._active_registers) > 0:
        #     raise RuntimeError("Should not have active registers left when flushing")
        self._arrays_to_return = []
        self._registers_to_return = []
        self._used_meas_registers = {
            operand.Register(RegisterName.M, i): False for i in range(16)
        }
        self._pre_context_commands = {}

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

    def _handle_if(
        self,
        condition: GenericInstr,
        a: Optional[T_CValue],
        b: Optional[T_CValue],
        body: T_BranchRoutine,
    ) -> None:
        """Used to build effective if-statements"""
        current_commands = self._pop_pending_commands()
        body(self._connection)
        body_commands = self._pop_pending_commands()
        self._add_if_statement_commands(
            pre_commands=current_commands,
            body_commands=body_commands,
            condition=condition,
            a=a,
            b=b,
        )

    def _add_if_statement_commands(
        self,
        pre_commands: List[T_Cmd],
        body_commands: List[T_Cmd],
        condition: GenericInstr,
        a: Optional[T_CValue],
        b: Optional[T_CValue],
    ) -> None:
        if len(body_commands) == 0:
            self.add_pending_commands(commands=pre_commands)
            return
        branch_instruction = flip_branch_instr(condition)
        # Construct a list of all commands to see what branch labels are already used
        all_commands = pre_commands + body_commands
        # We also need to check any existing other pre context commands if they are nested
        for pre_context_cmds in self._pre_context_commands.values():
            all_commands += pre_context_cmds
        if_start, if_end = self._get_branch_commands(
            branch_instruction=branch_instruction,
            a=a,
            b=b,
            current_branch_variables=self._used_branch_variables,
        )
        commands: List[T_Cmd] = pre_commands + if_start + body_commands + if_end  # type: ignore

        self.add_pending_commands(commands=commands)

    def _get_branch_commands(
        self,
        branch_instruction: GenericInstr,
        a: Optional[T_CValue],
        b: Optional[T_CValue],
        current_branch_variables: List[str],
    ) -> Tuple[List[ICmd], List[BranchLabel]]:
        # Exit label
        exit_label = self._find_unused_variable(
            start_with="IF_EXIT", current_variables=current_branch_variables
        )
        self._used_branch_variables.append(exit_label)
        cond_values: List[T_OperandUnion] = []
        if_start = []
        for x in [a, b]:
            if isinstance(x, Future):
                # Register for checking branching based on condition
                reg = self._get_inactive_register(activate=True)
                # Load values
                address_entry = parse_address(
                    f"{Symbols.ADDRESS_START}{x._address}[{x._index}]"
                )
                load = ICmd(
                    instruction=GenericInstr.LOAD,
                    operands=[
                        reg,
                        address_entry,
                    ],
                )
                cond_values.append(reg)
                if_start.append(load)
            elif isinstance(x, RegFuture):
                assert x.reg is not None
                cond_values.append(x.reg)
            elif isinstance(x, int):
                cond_values.append(x)
            else:
                raise TypeError(f"Cannot do conditional statement with type {type(x)}")
        branch = ICmd(
            instruction=branch_instruction,
            operands=[
                cond_values[0],
                cond_values[1],
                Label(exit_label),
            ],
        )
        if_start.append(branch)

        # Inactivate the temporary registers
        for val in cond_values:
            if isinstance(val, operand.Register):
                if not val.name == RegisterName.M:  # M-registers are never temporary
                    self._remove_active_register(register=val)

        exit = BranchLabel(exit_label)
        if_end = [exit]

        return if_start, if_end

    @contextmanager
    def loop(
        self,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[operand.Register] = None,
    ) -> Iterator[operand.Register]:
        try:
            pre_commands = self._pop_pending_commands()
            loop_register_result = self._handle_loop_register(
                loop_register, activate=True
            )
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
        loop_register: Optional[operand.Register] = None,
    ) -> None:
        """An effective loop-statement where body is a function executed, a number of times specified
        by `start`, `stop` and `step`.
        """
        loop_register = self._handle_loop_register(loop_register)

        pre_commands = self._pop_pending_commands()
        with self._activate_register(loop_register):
            body(self._connection)
        body_commands = self._pop_pending_commands()
        self._add_loop_commands(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=stop,
            start=start,
            step=step,
            loop_register=loop_register,
        )

    def _add_loop_commands(
        self,
        pre_commands: List[T_Cmd],
        body_commands: List[T_Cmd],
        stop: int,
        start: int,
        step: int,
        loop_register: operand.Register,
    ) -> None:
        if len(body_commands) == 0:
            self.add_pending_commands(commands=pre_commands)
            return
        current_registers = get_current_registers(body_commands)
        loop_start, loop_end = self._get_loop_commands(
            start=start,
            stop=stop,
            step=step,
            current_registers=current_registers,
            loop_register=loop_register,
        )
        commands = pre_commands + loop_start + body_commands + loop_end

        self.add_pending_commands(commands=commands)

    def _handle_loop_register(
        self, loop_register: Optional[operand.Register], activate: bool = False
    ) -> operand.Register:
        if loop_register is None:
            loop_register = self._get_inactive_register(activate=activate)
        else:
            if isinstance(loop_register, operand.Register):
                pass
            elif isinstance(loop_register, str):
                loop_register = parse_register(loop_register)
            else:
                raise ValueError(
                    f"not a valid loop_register with type {type(loop_register)}"
                )
            if loop_register in self._active_registers:
                raise ValueError(
                    "Register used for looping should not already be active"
                )
        # self._add_active_register(loop_register)
        return loop_register

    def _get_inactive_register(self, activate: bool = False) -> operand.Register:
        for i in range(2 ** REG_INDEX_BITS):
            register = parse_register(f"R{i}")
            if register not in self._active_registers:
                if activate:
                    self._add_active_register(register=register)
                return register
        raise RuntimeError("could not find an available loop register")

    @contextmanager
    def _activate_register(self, register: operand.Register) -> Iterator[None]:
        try:
            self._add_active_register(register=register)
            yield
        except Exception as err:
            raise err
        finally:
            self._remove_active_register(register=register)

    def _add_active_register(self, register: operand.Register) -> None:
        if register in self._active_registers:
            raise ValueError(f"Register {register} is already active")
        self._active_registers.add(register)

    def _remove_active_register(self, register: operand.Register) -> None:
        self._active_registers.remove(register)

    def _get_loop_commands(
        self,
        start: int,
        stop: int,
        step: int,
        current_registers: Set[str],
        loop_register: operand.Register,
    ) -> Tuple[List[T_Cmd], List[T_Cmd]]:
        entry_label = self._find_unused_variable(
            start_with="LOOP", current_variables=self._used_branch_variables
        )
        exit_label = self._find_unused_variable(
            start_with="LOOP_EXIT", current_variables=self._used_branch_variables
        )
        self._used_branch_variables.append(entry_label)
        self._used_branch_variables.append(exit_label)

        entry_loop, exit_loop = self._get_entry_exit_loop_cmds(
            start=start,
            stop=stop,
            step=step,
            entry_label=entry_label,
            exit_label=exit_label,
            loop_register=loop_register,
        )

        return entry_loop, exit_loop

    @staticmethod
    def _get_entry_exit_loop_cmds(
        start: int,
        stop: int,
        step: int,
        entry_label: str,
        exit_label: str,
        loop_register: operand.Register,
    ) -> Tuple[List[T_Cmd], List[T_Cmd]]:
        entry_loop: List[T_Cmd] = [
            ICmd(
                instruction=GenericInstr.SET,
                operands=[loop_register, start],
            ),
            BranchLabel(entry_label),
            ICmd(
                instruction=GenericInstr.BEQ,
                operands=[
                    loop_register,
                    stop,
                    Label(exit_label),
                ],
            ),
        ]
        exit_loop: List[T_Cmd] = [
            ICmd(
                instruction=GenericInstr.ADD,
                operands=[
                    loop_register,
                    loop_register,
                    step,
                ],
            ),
            ICmd(
                instruction=GenericInstr.JMP,
                operands=[Label(entry_label)],
            ),
            BranchLabel(exit_label),
        ]
        return entry_loop, exit_loop

    @staticmethod
    def _find_unused_variable(
        start_with: str = "", current_variables: Optional[List[str]] = None
    ) -> str:
        current_variables_set: Set[str] = set([])
        if current_variables is not None:
            current_variables_set = set(current_variables)
        if start_with not in current_variables_set:
            return start_with
        else:
            for i in count(1):
                var_name = f"{start_with}{i}"
                if var_name not in current_variables_set:
                    return var_name
            raise RuntimeError("Could not find unused variable")

    def _enter_if_context(
        self,
        context_id: int,
        condition: GenericInstr,
        a: Optional[T_CValue],
        b: Optional[T_CValue],
    ) -> None:
        pre_commands = self._pop_pending_commands()
        self._pre_context_commands[context_id] = pre_commands

    def _exit_if_context(
        self,
        context_id: int,
        condition: GenericInstr,
        a: Optional[T_CValue],
        b: Optional[T_CValue],
    ) -> None:
        body_commands = self._pop_pending_commands()
        pre_context_commands = self._pre_context_commands.pop(context_id, None)
        if pre_context_commands is None:
            raise RuntimeError("Something went wrong, no pre_context_commands")
        self._add_if_statement_commands(
            pre_commands=pre_context_commands,
            body_commands=body_commands,
            condition=condition,
            a=a,
            b=b,
        )

    def _enter_foreach_context(
        self, context_id: int, array: Array, return_index: bool
    ) -> Union[Tuple[operand.Register, Future], Future]:
        pre_commands = self._pop_pending_commands()
        loop_register = self._get_inactive_register(activate=True)

        # NOTE (BUG): the below assignment is NOT consistent with the type of _pre_context_commands
        # It works (maybe?) because the values are pushed only temporarily
        self._pre_context_commands[context_id] = pre_commands, loop_register  # type: ignore
        if return_index:
            return loop_register, array.get_future_index(loop_register)
        else:
            return array.get_future_index(loop_register)

    def _exit_foreach_context(
        self, context_id: int, array: Array, return_index: bool
    ) -> None:
        body_commands = self._pop_pending_commands()
        pre_context_commands: Tuple[List[T_Cmd], operand.Register] = self._pre_context_commands.pop(  # type: ignore
            context_id, None  # type: ignore
        )
        if pre_context_commands is None:
            raise RuntimeError("Something went wrong, no pre_context_commands")

        # NOTE (BUG): see NOTE (BUG) in _enter_foreach_context
        pre_commands, loop_register = pre_context_commands  # type: ignore
        self._add_loop_commands(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=len(array),
            start=0,
            step=1,
            loop_register=loop_register,
        )
        self._remove_active_register(register=loop_register)

    def insert_breakpoint(
        self, action: BreakpointAction, role: BreakpointRole = BreakpointRole.CREATE
    ) -> None:
        self.add_pending_command(
            ICmd(
                instruction=GenericInstr.BREAKPOINT, operands=[action.value, role.value]
            )
        )
