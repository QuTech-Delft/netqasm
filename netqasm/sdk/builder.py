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
from netqasm.lang.encoding import RegisterName
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
    T_OperandUnion,
    flip_branch_instr,
)
from netqasm.lang.parsing.text import assemble_subroutine, parse_register
from netqasm.lang.subroutine import Subroutine
from netqasm.qlink_compat import (
    EPRRole,
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
from netqasm.sdk.memmgr import MemoryManager
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
T_BranchRoutine = Callable[["connection.BaseNetQASMConnection"], None]
T_LoopRoutine = Callable[["connection.BaseNetQASMConnection"], None]

if TYPE_CHECKING:
    from . import connection


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


class LabelManager:
    def __init__(self) -> None:
        self._labels: Set[str] = set()

    def new_label(self, start_with: str = "") -> str:
        if start_with not in self._labels:
            self._labels.add(start_with)
            return start_with
        else:
            for i in count(1):
                name = f"{start_with}{i}"
                if name not in self._labels:
                    self._labels.add(name)
                    return name
            assert False, "should never be reached"


class Builder:
    """Object that transforms Python script code into `PreSubroutine`s.

    A Connection uses a Builder to handle statements in application script code.
    The Builder converts the statements into pseudo-NetQASM instructions that are
    assembled into a PreSubroutine. When the connectin flushes, the PreSubroutine is
    is compiled into a NetQASM subroutine.
    """

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

        self._pending_commands: List[T_Cmd] = []

        self._max_qubits: int = max_qubits

        self._mem_mgr: MemoryManager = MemoryManager()

        # If False, don't return arrays even if they are used in a subroutine
        self._return_arrays: bool = return_arrays

        # Storing commands before an conditional statement
        self._pre_context_commands: Dict[int, List[T_Cmd]] = {}

        self._label_mgr = LabelManager()

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
        self._mem_mgr.inactivate_qubits()

    def new_qubit_id(self) -> int:
        return self._mem_mgr.get_new_qubit_address()

    def alloc_array(
        self, length: int = 1, init_values: Optional[List[Optional[int]]] = None
    ) -> Array:
        address = self._mem_mgr.get_new_array_address()
        lineno = self._line_tracker.get_line()
        array = Array(
            connection=self._connection,
            length=length,
            address=address,
            init_values=init_values,
            lineno=lineno,
        )
        self._mem_mgr.add_array_to_return(array)
        return array

    def new_register(self, init_value: int = 0) -> RegFuture:
        reg = self._mem_mgr.get_inactive_register(activate=True)
        self.subrt_add_pending_command(
            ICmd(instruction=GenericInstr.SET, operands=[reg, init_value])
        )
        self._mem_mgr.add_reg_to_return(reg)
        return RegFuture(connection=self._connection, reg=reg)

    def subrt_add_pending_commands(self, commands: List[T_Cmd]) -> None:
        calling_lineno = self._line_tracker.get_line()
        for command in commands:
            if command.lineno is None:
                command.lineno = calling_lineno
            self.subrt_add_pending_command(command)

    def subrt_add_pending_command(self, command: T_Cmd) -> None:
        assert isinstance(command, ICmd) or isinstance(command, BranchLabel)
        if command.lineno is None:
            command.lineno = self._line_tracker.get_line()
        self._pending_commands.append(command)

    def subrt_pop_pending_commands(self) -> List[T_Cmd]:
        commands = self._pending_commands
        self._pending_commands = []
        return commands

    def subrt_pop_pending_subroutine(self) -> Optional[PreSubroutine]:
        # Add commands for initialising and returning arrays
        self._build_cmds_allocated_arrays()
        self._build_cmds_return_registers()
        if len(self._pending_commands) > 0:
            commands = self.subrt_pop_pending_commands()
            metadata = self._get_metadata()
            return PreSubroutine(**metadata, commands=commands)
        else:
            return None

    def _get_metadata(self) -> Dict:
        return {
            "netqasm_version": NETQASM_VERSION,
            "app_id": self.app_id,
        }

    def subrt_compile_subroutine(self, pre_subroutine: PreSubroutine) -> Subroutine:
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

    def _get_qubit_register(self, reg_index: int = 0) -> operand.Register:
        return operand.Register(RegisterName.Q, reg_index)

    def _alloc_epr_create_args(self, tp: EPRType, params: EntRequestParams) -> Array:
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
        return self.alloc_array(init_values=create_args)

    def _add_post_commands(
        self,
        qubit_ids: Optional[Array],
        number: int,
        ent_results_array: Array,
        tp: EPRType,
        post_routine: T_PostRoutine,
    ) -> None:

        loop_register = self._mem_mgr.get_inactive_register()

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
        self._build_cmds_loop_body(post_loop, stop=number, loop_register=loop_register)

    def _add_wait_for_ent_info_cmd(
        self, ent_results_array: Array, pair: operand.Register
    ) -> None:
        """Wait for the correct slice of the entanglement info array for the given pair"""
        # NOTE arr_start should be pair * OK_FIELDS and
        # arr_stop should be (pair + 1) * OK_FIELDS
        arr_start = self._mem_mgr.get_inactive_register(activate=True)
        tmp = self._mem_mgr.get_inactive_register(activate=True)
        arr_stop = self._mem_mgr.get_inactive_register(activate=True)
        created_regs = [arr_start, tmp, arr_stop]

        for reg in created_regs:
            self.subrt_add_pending_command(
                ICmd(
                    instruction=GenericInstr.SET,
                    operands=[reg, 0],
                )
            )

        # Multiply pair * OK_FIELDS
        # TODO use loop context
        def add_arr_start(conn):
            self.subrt_add_pending_command(
                ICmd(
                    instruction=GenericInstr.ADD,
                    operands=[arr_start, arr_start, pair],
                )
            )

        self._build_cmds_loop_body(add_arr_start, stop=OK_FIELDS_K)

        # Let tmp be pair + 1
        self.subrt_add_pending_command(
            ICmd(
                instruction=GenericInstr.ADD,
                operands=[tmp, pair, 1],
            )
        )

        # Multiply (tmp = pair + 1) * OK_FIELDS
        # TODO use loop context
        def add_arr_stop(conn):
            self.subrt_add_pending_command(
                ICmd(
                    instruction=GenericInstr.ADD,
                    operands=[arr_stop, arr_stop, tmp],
                )
            )

        self._build_cmds_loop_body(add_arr_stop, stop=OK_FIELDS_K)

        wait_cmd = ICmd(
            instruction=GenericInstr.WAIT_ALL,
            operands=[
                ArraySlice(
                    Address(ent_results_array.address), start=arr_start, stop=arr_stop
                )
            ],
        )
        self.subrt_add_pending_command(wait_cmd)

        for reg in created_regs:
            self._mem_mgr.remove_active_reg(reg)

    def _pre_epr_context(
        self,
        role: EPRRole,
        params: EntRequestParams,
    ) -> Tuple[List[T_Cmd], operand.Register, Array, FutureQubit, operand.Register]:
        # NOTE since this is in a context there will be a post_routine
        # TODO Fix weird handling of post_routine parameter here
        def dummy():
            pass

        self._assert_epr_args(
            number=params.number,
            post_routine=dummy,  # type: ignore
            sequential=params.sequential,
        )

        # Entanglement results array.
        # This will be filled in by the quantum node controller.
        ent_results_array = self._alloc_ent_results_array(
            number=params.number, tp=EPRType.K
        )

        qubit_futures = self._get_qubit_futures(
            params.number, params.sequential, ent_results_array
        )
        assert all(isinstance(q, Qubit) for q in qubit_futures)

        # NetQASM array with IDs for the generated qubits.
        virtual_qubit_ids = [q.qubit_id for q in qubit_futures]
        qubit_ids_array = self.alloc_array(init_values=virtual_qubit_ids)  # type: ignore

        # Construct and add the NetQASM instructions
        if role == EPRRole.CREATE:
            # NetQASM array for entanglement request parameters.
            create_args_array: Array = self._alloc_epr_create_args(EPRType.K, params)

            self._build_cmds_epr_create_keep(
                create_args_array, qubit_ids_array, ent_results_array, False, params
            )
        else:
            self._build_cmds_epr_recv_keep(
                qubit_ids_array, ent_results_array, False, params
            )

        pre_commands = self.subrt_pop_pending_commands()
        loop_register = self._mem_mgr.get_inactive_register(activate=True)
        pair = loop_register

        q_id = qubit_ids_array.get_future_index(pair)
        q = FutureQubit(conn=self._connection, future_id=q_id)

        return pre_commands, loop_register, ent_results_array, q, pair

    def _post_epr_context(
        self,
        pre_commands: List[T_Cmd],
        number: int,
        loop_register: operand.Register,
        ent_results_array: Array,
        pair: operand.Register,
    ) -> None:
        body_commands = self.subrt_pop_pending_commands()
        self._add_wait_for_ent_info_cmd(
            ent_results_array=ent_results_array,
            pair=pair,
        )
        wait_cmds = self.subrt_pop_pending_commands()
        body_commands = wait_cmds + body_commands
        self._build_cmds_loop(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=number,
            start=0,
            step=1,
            loop_register=loop_register,
        )
        self._mem_mgr.remove_active_reg(loop_register)

    def _assert_epr_args(
        self,
        number: int,
        post_routine: Optional[T_PostRoutine],
        sequential: bool,
    ) -> None:
        if sequential and number > 1:
            if post_routine is None:
                raise ValueError(
                    "When using sequential mode with more than one pair "
                    "a post_routine needs to be specified which consumes the "
                    "generated pair as they come in."
                )
        if not sequential and number > self._max_qubits:
            raise ValueError(
                f"When not using sequential mode for K type, the number of pairs {number} cannot be "
                f"greater than the maximum number of qubits specified ({self._max_qubits})."
            )

    def _check_epr_args(self, tp: EPRType, params: EntRequestParams) -> None:
        assert isinstance(tp, EPRType), "tp is not an EPRType"
        if params.sequential and params.number > 1:
            if params.post_routine is None:
                raise ValueError(
                    "When using sequential mode with more than one pair "
                    "a post_routine needs to be specified which consumes the "
                    "generated pair as they come in."
                )
        if (
            tp == EPRType.K
            and not params.sequential
            and params.number > self._max_qubits
        ):
            raise ValueError(
                f"When not using sequential mode for K type, the number of pairs "
                f"{params.number} cannot be "
                f"greater than the maximum number of qubits specified "
                f"({self._max_qubits})."
            )

    def _alloc_ent_results_array(self, number: int, tp: EPRType) -> Array:
        if tp == EPRType.K:
            ent_results_array = self.alloc_array(length=OK_FIELDS_K * number)
        elif tp == EPRType.M:
            ent_results_array = self.alloc_array(length=OK_FIELDS_M * number)
        elif tp == EPRType.R:
            # NOTE: also for R-type request we use the LinkLayerOkTypeM type
            ent_results_array = self.alloc_array(length=OK_FIELDS_M * number)
        else:
            raise ValueError(f"Unsupported Create type: {tp}")
        return ent_results_array

    def _get_meas_dir_futures_array(
        self, number: int, ent_results_array: Array
    ) -> List[LinkLayerOKTypeM]:
        return self._create_ent_info_m_slices(
            num_pairs=number, ent_results_array=ent_results_array
        )

    def _get_qubit_futures(
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
                    self._build_cmds_free_up_qubit_location(
                        virtual_address=virtual_address
                    )
                qubit = Qubit(
                    self._connection,
                    add_new_command=False,
                    ent_info=ent_info_slice,  # type: ignore
                    virtual_address=virtual_address,
                )
            qubits.append(qubit)

        return qubits

    def _reset(self) -> None:
        # if len(self._active_registers) > 0:
        #     raise RuntimeError("Should not have active registers left when flushing")
        self._mem_mgr.reset()
        self._pre_context_commands = {}

    def _get_condition_operand(
        self, value: T_CValue
    ) -> Tuple[List[ICmd], T_OperandUnion]:
        if isinstance(value, Future):
            # Register for checking branching based on condition
            reg = self._mem_mgr.get_inactive_register(activate=True)
            # Load values
            address_entry = value.get_address_entry()
            load = ICmd(instruction=GenericInstr.LOAD, operands=[reg, address_entry])
            return [load], reg
        elif isinstance(value, RegFuture):
            assert value.reg is not None
            return [], value.reg
        elif isinstance(value, int):
            return [], value
        else:
            raise TypeError(f"Cannot do conditional statement with type {type(value)}")

    def _get_branch_commands_single_operand(
        self,
        branch_instruction: GenericInstr,
        a: T_CValue,
    ) -> Tuple[List[ICmd], List[BranchLabel]]:
        # Exit label
        exit_label = self._label_mgr.new_label(start_with="IF_EXIT")
        if_start: List[ICmd] = []

        using_new_temp_reg = False

        cmds, cond_operand = self._get_condition_operand(a)
        if_start += cmds

        branch = ICmd(
            instruction=branch_instruction,
            operands=[cond_operand, Label(exit_label)],
        )
        if_start.append(branch)

        if using_new_temp_reg:
            assert isinstance(cond_operand, operand.Register)
            self._mem_mgr.remove_active_reg(cond_operand)

        exit = BranchLabel(exit_label)
        if_end = [exit]

        return if_start, if_end

    def _get_branch_commands(
        self,
        branch_instruction: GenericInstr,
        a: T_CValue,
        b: T_CValue,
    ) -> Tuple[List[ICmd], List[BranchLabel]]:
        # Exit label
        exit_label = self._label_mgr.new_label(start_with="IF_EXIT")
        cond_operands: List[T_OperandUnion] = []
        if_start: List[ICmd] = []

        temp_regs_to_remove: List[operand.Register] = []

        for x in [a, b]:
            cmds, cond_operand = self._get_condition_operand(x)
            if_start += cmds
            cond_operands.append(cond_operand)

            if isinstance(x, Future):
                assert isinstance(cond_operand, operand.Register)
                temp_regs_to_remove.append(cond_operand)

        branch = ICmd(
            instruction=branch_instruction,
            operands=[cond_operands[0], cond_operands[1], Label(exit_label)],
        )
        if_start.append(branch)

        # Inactivate the temporary registers
        for reg in temp_regs_to_remove:
            self._mem_mgr.remove_active_reg(reg)

        exit = BranchLabel(exit_label)
        if_end = [exit]

        return if_start, if_end

    def _get_loop_register(
        self,
        register: Optional[Union[operand.Register, str]],
        activate: bool = False,
    ) -> operand.Register:
        if register is None:
            return self._mem_mgr.get_inactive_register(activate=activate)

        assert isinstance(register, operand.Register) or isinstance(
            register, str
        ), f"not a valid loop_register with type {type(register)}"
        if isinstance(register, str):
            loop_register = parse_register(register)
        else:
            loop_register = register

        if self._mem_mgr.is_reg_active(loop_register):
            raise ValueError("Register used for looping should not already be active")
        return loop_register

    @contextmanager
    def _activate_register(self, register: operand.Register) -> Iterator[None]:
        try:
            self._mem_mgr.add_active_reg(register)
            yield
        except Exception as err:
            raise err
        finally:
            self._mem_mgr.remove_active_reg(register)

    def _get_loop_entry_commands(
        self,
        start: int,
        stop: int,
        entry_label: str,
        exit_label: str,
        loop_register: operand.Register,
    ) -> List[T_Cmd]:
        return [
            ICmd(instruction=GenericInstr.SET, operands=[loop_register, start]),
            BranchLabel(entry_label),
            ICmd(
                instruction=GenericInstr.BEQ,
                operands=[loop_register, stop, Label(exit_label)],
            ),
        ]

    def _get_loop_exit_commands(
        self,
        start: int,
        step: int,
        entry_label: str,
        exit_label: str,
        loop_register: operand.Register,
    ) -> List[T_Cmd]:
        return [
            ICmd(
                instruction=GenericInstr.ADD,
                operands=[loop_register, loop_register, step],
            ),
            ICmd(instruction=GenericInstr.JMP, operands=[Label(entry_label)]),
            BranchLabel(exit_label),
        ]

    def _enter_if_context(
        self,
        context_id: int,
        condition: GenericInstr,
        a: Optional[T_CValue],
        b: Optional[T_CValue],
    ) -> None:
        pre_commands = self.subrt_pop_pending_commands()
        self._pre_context_commands[context_id] = pre_commands

    def _exit_if_context(
        self,
        context_id: int,
        condition: GenericInstr,
        a: T_CValue,
        b: Optional[T_CValue],
    ) -> None:
        body_commands = self.subrt_pop_pending_commands()
        pre_context_commands = self._pre_context_commands.pop(context_id, None)
        if pre_context_commands is None:
            raise RuntimeError("Something went wrong, no pre_context_commands")
        self._build_cmds_condition(
            pre_commands=pre_context_commands,
            body_commands=body_commands,
            condition=condition,
            a=a,
            b=b,
        )

    def _enter_foreach_context(
        self, context_id: int, array: Array, return_index: bool
    ) -> Union[Tuple[operand.Register, Future], Future]:
        pre_commands = self.subrt_pop_pending_commands()
        loop_register = self._mem_mgr.get_inactive_register(activate=True)

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
        body_commands = self.subrt_pop_pending_commands()
        pre_context_commands: Tuple[List[T_Cmd], operand.Register] = self._pre_context_commands.pop(  # type: ignore
            context_id, None  # type: ignore
        )
        if pre_context_commands is None:
            raise RuntimeError("Something went wrong, no pre_context_commands")

        # NOTE (BUG): see NOTE (BUG) in _enter_foreach_context
        pre_commands, loop_register = pre_context_commands  # type: ignore
        self._build_cmds_loop(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=len(array),
            start=0,
            step=1,
            loop_register=loop_register,
        )
        self._mem_mgr.remove_active_reg(loop_register)

    def _build_cmds_breakpoint(
        self, action: BreakpointAction, role: BreakpointRole = BreakpointRole.CREATE
    ) -> None:
        self.subrt_add_pending_command(
            ICmd(
                instruction=GenericInstr.BREAKPOINT, operands=[action.value, role.value]
            )
        )

    def _build_cmds_single_qubit_rotation(
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
                self._build_cmds_single_qubit_rotation(
                    instruction=instruction,
                    virtual_qubit_id=virtual_qubit_id,
                    n=n,
                    d=d,
                )
            return
        if not (isinstance(n, int) and isinstance(d, int) and n >= 0 and d >= 0):
            raise ValueError(f"{n} * pi / 2 ^ {d} is not a valid angle specification")
        register = self._get_qubit_register()
        self._build_cmds_set_register_value(register, virtual_qubit_id)
        rot_command = ICmd(
            instruction=instruction,
            operands=[register, n, d],
        )
        self.subrt_add_pending_command(rot_command)

    def _build_cmds_single_qubit(self, instr: GenericInstr, qubit_id: int) -> None:
        register = self._get_qubit_register()
        self._build_cmds_set_register_value(register, qubit_id)
        # Construct the qubit command
        qubit_command = ICmd(
            instruction=instr,
            operands=[register],
        )
        self.subrt_add_pending_command(qubit_command)

    def _build_cmds_two_qubit(
        self, instr: GenericInstr, control_qubit_id: int, target_qubit_id: int
    ) -> None:
        register1 = self._get_qubit_register(0)
        self._build_cmds_set_register_value(register1, control_qubit_id)
        register2 = self._get_qubit_register(1)
        self._build_cmds_set_register_value(register2, target_qubit_id)
        qubit_command = ICmd(
            instruction=instr,
            operands=[register1, register2],
        )
        self.subrt_add_pending_command(qubit_command)

    def _build_cmds_move_qubit(self, source: int, target: int) -> None:
        # Moves a qubit from one position to another (assumes that target is free)
        assert target not in [q.qubit_id for q in self._mem_mgr.get_active_qubits()]
        self._build_cmds_new_qubit(target)
        self._build_cmds_two_qubit(GenericInstr.MOV, source, target)
        self._build_cmds_qfree(source)

    def _build_cmds_measure(
        self, qubit_id: int, future: Union[Future, RegFuture], inplace: bool
    ) -> None:
        if self._compiler == NVSubroutineCompiler:
            # If compiling for NV, only virtual ID 0 can be used to measure a qubit.
            # So, if this qubit is already in use, we need to move it away first.
            if not isinstance(qubit_id, Future):
                if qubit_id != 0:
                    self._build_cmds_free_up_qubit_location(virtual_address=0)
        outcome_reg = self._mem_mgr.get_new_meas_outcome_reg()
        qubit_reg = self._get_qubit_register()
        self._build_cmds_set_register_value(qubit_reg, qubit_id)
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
                self._mem_mgr.meas_reg_set_unused(outcome_reg)
            elif isinstance(future, RegFuture):
                future.reg = outcome_reg
                self._mem_mgr.add_reg_to_return(outcome_reg)
                outcome_commands = []
            else:
                outcome_commands = []
        commands = [meas_command] + free_commands + outcome_commands  # type: ignore
        self.subrt_add_pending_commands(commands)  # type: ignore

    def _build_cmds_new_qubit(self, qubit_id: int) -> None:
        qubit_reg = self._get_qubit_register()
        self._build_cmds_set_register_value(qubit_reg, qubit_id)
        qalloc_command = ICmd(
            instruction=GenericInstr.QALLOC,
            operands=[qubit_reg],
        )
        init_command = ICmd(
            instruction=GenericInstr.INIT,
            operands=[qubit_reg],
        )
        commands = [qalloc_command, init_command]
        self.subrt_add_pending_commands(commands)  # type: ignore

    def _build_cmds_init_qubit(self, qubit_id: int) -> None:
        qubit_reg = self._get_qubit_register()
        self._build_cmds_set_register_value(qubit_reg, qubit_id)
        init_command = ICmd(
            instruction=GenericInstr.INIT,
            operands=[qubit_reg],
        )
        self.subrt_add_pending_command(init_command)

    def _build_cmds_qfree(self, qubit_id: int) -> None:
        qubit_reg = self._get_qubit_register()
        self._build_cmds_set_register_value(qubit_reg, qubit_id)
        qfree_command = ICmd(
            instruction=GenericInstr.QFREE,
            operands=[qubit_reg],
        )
        self.subrt_add_pending_command(qfree_command)

    def _build_cmds_allocated_arrays(self) -> None:
        current_commands = self.subrt_pop_pending_commands()

        for array in self._mem_mgr.get_arrays_to_return():
            self._build_cmds_init_array(array)
        self.subrt_add_pending_commands(current_commands)

        if self._return_arrays:
            for array in self._mem_mgr.get_arrays_to_return():
                self._build_cmds_return_array(array)

    def _build_cmds_init_array(self, array: Array) -> None:
        commands: List[T_Cmd] = []

        array_cmd = ICmd(
            instruction=GenericInstr.ARRAY,
            operands=[len(array), Address(array.address)],
            lineno=array.lineno,
        )
        commands.append(array_cmd)

        init_vals = array._init_values
        if init_vals is not None:
            length = len(init_vals)
            if (
                length > 1
                and init_vals[0] is not None
                and init_vals.count(init_vals[0]) == length
            ):
                # Ad-hoc optimization: if all values are the same, put the initialization commands in a loop
                loop_register = self._mem_mgr.get_inactive_register()

                store_cmd = ICmd(
                    instruction=GenericInstr.STORE,
                    operands=[
                        init_vals[0],
                        ArrayEntry(Address(array.address), loop_register),
                    ],
                    lineno=array.lineno,
                )

                def init_array_elt(conn):
                    conn._builder.subrt_add_pending_command(store_cmd)

                self._build_cmds_loop_body(
                    init_array_elt, stop=length, loop_register=loop_register
                )
                commands += self.subrt_pop_pending_commands()
            else:
                for i, value in enumerate(init_vals):
                    if value is None:
                        continue
                    else:
                        store_cmd = ICmd(
                            instruction=GenericInstr.STORE,
                            operands=[value, ArrayEntry(Address(array.address), i)],
                            lineno=array.lineno,
                        )
                        commands.append(store_cmd)
        self.subrt_add_pending_commands(commands)

    def _build_cmds_set_register_value(
        self, register: operand.Register, value: Union[Future, int]
    ) -> None:
        if isinstance(value, Future):
            set_reg_cmds = value._get_load_commands(register)
        elif isinstance(value, int):
            set_reg_cmds = [
                ICmd(instruction=GenericInstr.SET, operands=[register, value])
            ]
        self.subrt_add_pending_commands(set_reg_cmds)

    def _build_cmds_return_array(self, array: Array) -> None:
        self.subrt_add_pending_command(
            ICmd(
                instruction=GenericInstr.RET_ARR,
                operands=[Address(array.address)],
                lineno=array.lineno,
            )
        )

    def _build_cmds_return_registers(self) -> None:
        ret_reg_instrs: List[T_Cmd] = []
        for reg in self._mem_mgr.get_registers_to_return():
            ret_reg_instrs.append(
                ICmd(instruction=GenericInstr.RET_REG, operands=[reg])
            )
        self.subrt_add_pending_commands(commands=ret_reg_instrs)

    def _build_cmds_free_up_qubit_location(self, virtual_address: int) -> None:
        if self._compiler == NVSubroutineCompiler:
            for q in self._mem_mgr.get_active_qubits():
                # Find a free qubit
                new_virtual_address = self._mem_mgr.get_new_qubit_address()
                if q.qubit_id == virtual_address:
                    # Virtual address is already used. Move it to the new virtual address.
                    # NOTE: this assumes that the new virtual address is *not* currently used.
                    self._build_cmds_move_qubit(
                        source=virtual_address, target=new_virtual_address
                    )
                    # From now on, the original qubit should be referred to with the new virtual address.
                    q.qubit_id = new_virtual_address

    def _build_cmds_epr(
        self,
        qubit_ids_array: Optional[Array],
        ent_results_array: Array,
        wait_all: bool,
        tp: EPRType,
        params: EntRequestParams,
        role: EPRRole = EPRRole.CREATE,
        **kwargs,
    ) -> None:
        qubit_ids_array_address: Union[int, operand.Register]
        epr_cmd_operands: List[T_OperandUnion]

        if tp == EPRType.K or (tp == EPRType.R and role == EPRRole.RECV):
            assert qubit_ids_array is not None
            qubit_ids_array_address = qubit_ids_array.address
        else:
            # NOTE since this argument won't be used just set it to some
            # constant register for now
            qubit_ids_array_address = operand.Register(RegisterName.C, 0)

        if role == EPRRole.CREATE:
            create_args_array = self._alloc_epr_create_args(tp, params)
            epr_cmd_operands = [
                qubit_ids_array_address,
                create_args_array.address,
                ent_results_array.address,
            ]
        else:
            epr_cmd_operands = [
                qubit_ids_array_address,
                ent_results_array.address,
            ]

        # epr command
        instr = {
            EPRRole.CREATE: GenericInstr.CREATE_EPR,
            EPRRole.RECV: GenericInstr.RECV_EPR,
        }[role]
        epr_cmd = ICmd(
            instruction=instr,
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
        self.subrt_add_pending_commands(commands)

    def _build_cmds_epr_create_keep(
        self,
        create_args_array: Array,
        qubit_ids_array: Array,
        ent_results_array: Array,
        wait_all: bool,
        params: EntRequestParams,
        **kwargs,
    ) -> None:
        epr_cmd_operands = [
            qubit_ids_array.address,
            create_args_array.address,
            ent_results_array.address,
        ]

        # epr command
        epr_cmd = ICmd(
            instruction=GenericInstr.CREATE_EPR,
            args=[params.remote_node_id, params.epr_socket_id],
            operands=epr_cmd_operands,  # type: ignore
        )
        self.subrt_add_pending_command(epr_cmd)

        # wait
        arr_slice = ArraySlice(
            ent_results_array.address, start=0, stop=len(ent_results_array)  # type: ignore
        )
        if wait_all:
            wait_cmds = [ICmd(instruction=GenericInstr.WAIT_ALL, operands=[arr_slice])]
        else:
            wait_cmds = []

        self.subrt_add_pending_commands(wait_cmds)  # type: ignore

    def _build_cmds_epr_recv_keep(
        self,
        qubit_ids_array: Array,
        ent_results_array: Array,
        wait_all: bool,
        params: EntRequestParams,
        **kwargs,
    ) -> None:
        epr_cmd_operands = [
            qubit_ids_array.address,
            ent_results_array.address,
        ]

        # epr command
        epr_cmd = ICmd(
            instruction=GenericInstr.RECV_EPR,
            args=[params.remote_node_id, params.epr_socket_id],
            operands=epr_cmd_operands,  # type: ignore
        )
        self.subrt_add_pending_command(epr_cmd)

        # wait
        arr_slice = ArraySlice(
            ent_results_array.address, start=0, stop=len(ent_results_array)  # type: ignore
        )
        if wait_all:
            wait_cmds = [ICmd(instruction=GenericInstr.WAIT_ALL, operands=[arr_slice])]
        else:
            wait_cmds = []

        self.subrt_add_pending_commands(wait_cmds)  # type: ignore

    def _build_cmds_epr_create_measure(
        self,
        create_args_array: Array,
        ent_results_array: Array,
        wait_all: bool,
        params: EntRequestParams,
        **kwargs,
    ) -> None:
        epr_cmd_operands = [
            # NOTE since the qubit IDs array won't be used just set it to some
            # constant register for now
            operand.Register(RegisterName.C, 0),
            create_args_array.address,
            ent_results_array.address,
        ]

        # epr command
        epr_cmd = ICmd(
            instruction=GenericInstr.CREATE_EPR,
            args=[params.remote_node_id, params.epr_socket_id],
            operands=epr_cmd_operands,  # type: ignore
        )
        self.subrt_add_pending_command(epr_cmd)

        # wait
        arr_slice = ArraySlice(
            ent_results_array.address, start=0, stop=len(ent_results_array)  # type: ignore
        )
        if wait_all:
            wait_cmds = [ICmd(instruction=GenericInstr.WAIT_ALL, operands=[arr_slice])]
        else:
            wait_cmds = []

        self.subrt_add_pending_commands(wait_cmds)  # type: ignore

    def _build_cmds_epr_recv_measure(
        self,
        ent_results_array: Array,
        wait_all: bool,
        params: EntRequestParams,
        **kwargs,
    ) -> None:
        epr_cmd_operands = [
            # NOTE since the qubit IDs array won't be used just set it to some
            # constant register for now
            operand.Register(RegisterName.C, 0),
            ent_results_array.address,
        ]

        # epr command
        epr_cmd = ICmd(
            instruction=GenericInstr.RECV_EPR,
            args=[params.remote_node_id, params.epr_socket_id],
            operands=epr_cmd_operands,  # type: ignore
        )
        self.subrt_add_pending_command(epr_cmd)

        # wait
        arr_slice = ArraySlice(
            ent_results_array.address, start=0, stop=len(ent_results_array)  # type: ignore
        )
        if wait_all:
            wait_cmds = [ICmd(instruction=GenericInstr.WAIT_ALL, operands=[arr_slice])]
        else:
            wait_cmds = []

        self.subrt_add_pending_commands(wait_cmds)  # type: ignore

    def _build_cmds_epr_create_rsp(
        self,
        create_args_array: Array,
        ent_results_array: Array,
        wait_all: bool,
        params: EntRequestParams,
        **kwargs,
    ) -> None:
        epr_cmd_operands = [
            # NOTE since the qubit IDs array won't be used just set it to some
            # constant register for now
            operand.Register(RegisterName.C, 0),
            create_args_array.address,
            ent_results_array.address,
        ]

        # epr command
        epr_cmd = ICmd(
            instruction=GenericInstr.CREATE_EPR,
            args=[params.remote_node_id, params.epr_socket_id],
            operands=epr_cmd_operands,  # type: ignore
        )
        self.subrt_add_pending_command(epr_cmd)

        # wait
        arr_slice = ArraySlice(
            ent_results_array.address, start=0, stop=len(ent_results_array)  # type: ignore
        )
        if wait_all:
            wait_cmds = [ICmd(instruction=GenericInstr.WAIT_ALL, operands=[arr_slice])]
        else:
            wait_cmds = []

        self.subrt_add_pending_commands(wait_cmds)  # type: ignore

    def _build_cmds_epr_recv_rsp(
        self,
        qubit_ids_array: Array,
        ent_results_array: Array,
        wait_all: bool,
        params: EntRequestParams,
        **kwargs,
    ) -> None:
        epr_cmd_operands = [
            qubit_ids_array.address,
            ent_results_array.address,
        ]

        # epr command
        epr_cmd = ICmd(
            instruction=GenericInstr.RECV_EPR,
            args=[params.remote_node_id, params.epr_socket_id],
            operands=epr_cmd_operands,  # type: ignore
        )
        self.subrt_add_pending_command(epr_cmd)

        # wait
        arr_slice = ArraySlice(
            ent_results_array.address, start=0, stop=len(ent_results_array)  # type: ignore
        )
        if wait_all:
            wait_cmds = [ICmd(instruction=GenericInstr.WAIT_ALL, operands=[arr_slice])]
        else:
            wait_cmds = []

        self.subrt_add_pending_commands(wait_cmds)  # type: ignore

    def _build_cmds_loop_body(
        self,
        body: T_LoopRoutine,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[Union[operand.Register, str]] = None,
    ) -> None:
        """An effective loop-statement where body is a function executed, a number of times specified
        by `start`, `stop` and `step`.
        """
        loop_register = self._get_loop_register(loop_register)
        pre_commands = self.subrt_pop_pending_commands()

        with self._activate_register(loop_register):
            # evalute body (will add pending commands)
            body(self._connection)
        body_commands = self.subrt_pop_pending_commands()

        self._build_cmds_loop(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=stop,
            start=start,
            step=step,
            loop_register=loop_register,
        )

    def _build_cmds_loop(
        self,
        pre_commands: List[T_Cmd],
        body_commands: List[T_Cmd],
        stop: int,
        start: int,
        step: int,
        loop_register: operand.Register,
    ) -> None:
        if len(body_commands) == 0:
            self.subrt_add_pending_commands(commands=pre_commands)
            return

        entry_label = self._label_mgr.new_label(start_with="LOOP")
        exit_label = self._label_mgr.new_label(start_with="LOOP_EXIT")

        loop_start = self._get_loop_entry_commands(
            start=start,
            stop=stop,
            entry_label=entry_label,
            exit_label=exit_label,
            loop_register=loop_register,
        )
        loop_end = self._get_loop_exit_commands(
            start=start,
            step=step,
            entry_label=entry_label,
            exit_label=exit_label,
            loop_register=loop_register,
        )

        commands = pre_commands + loop_start + body_commands + loop_end

        self.subrt_add_pending_commands(commands=commands)

    def _build_cmds_if_stmt(
        self,
        condition: GenericInstr,
        a: T_CValue,
        b: Optional[T_CValue],
        body: T_BranchRoutine,
    ) -> None:
        """Used to build effective if-statements"""
        current_commands = self.subrt_pop_pending_commands()

        # evaluate body (will add pending commands)
        body(self._connection)

        # get those commands
        body_commands = self.subrt_pop_pending_commands()

        # combine existing commands with body commands and branch instructions
        self._build_cmds_condition(
            pre_commands=current_commands,
            body_commands=body_commands,
            condition=condition,
            a=a,
            b=b,
        )

    def _build_cmds_condition(
        self,
        pre_commands: List[T_Cmd],
        body_commands: List[T_Cmd],
        condition: GenericInstr,
        a: T_CValue,
        b: Optional[T_CValue],
    ) -> None:
        if len(body_commands) == 0:
            self.subrt_add_pending_commands(commands=pre_commands)
            return
        negated_predicate = flip_branch_instr(condition)
        # Construct a list of all commands to see what branch labels are already used
        all_commands = pre_commands + body_commands
        # We also need to check any existing other pre context commands if they are nested
        for pre_context_cmds in self._pre_context_commands.values():
            all_commands += pre_context_cmds

        if negated_predicate in [GenericInstr.BEZ, GenericInstr.BNZ]:
            if_start, if_end = self._get_branch_commands_single_operand(
                branch_instruction=negated_predicate, a=a
            )
        else:
            assert b is not None
            if_start, if_end = self._get_branch_commands(
                branch_instruction=negated_predicate,
                a=a,
                b=b,
            )
        commands: List[T_Cmd] = pre_commands + if_start + body_commands + if_end  # type: ignore

        self.subrt_add_pending_commands(commands=commands)

    def sdk_epr_keep(
        self,
        role: EPRRole,
        params: EntRequestParams,
    ) -> List[Qubit]:
        self._check_epr_args(tp=EPRType.K, params=params)

        # Setup NetQASM arrays and SDK handles.

        # NetQASM array for entanglement results.
        # This will be filled in by the quantum node controller.
        ent_results_array: Array = self._alloc_ent_results_array(
            number=params.number, tp=EPRType.K
        )

        # SDK handles to result values (Qubit objects).
        qubit_futures: List[Qubit] = self._get_qubit_futures(
            params.number, params.sequential, ent_results_array
        )
        assert all(isinstance(q, Qubit) for q in qubit_futures)

        # NetQASM array with IDs for the generated qubits.
        virtual_qubit_ids = [q.qubit_id for q in qubit_futures]
        qubit_ids_array: Array = self.alloc_array(init_values=virtual_qubit_ids)  # type: ignore

        wait_all = params.post_routine is None

        # Construct and add the NetQASM instructions
        if role == EPRRole.CREATE:
            # NetQASM array for entanglement request parameters.
            create_args_array: Array = self._alloc_epr_create_args(EPRType.K, params)

            self._build_cmds_epr_create_keep(
                create_args_array, qubit_ids_array, ent_results_array, wait_all, params
            )
        else:
            self._build_cmds_epr_recv_keep(
                qubit_ids_array, ent_results_array, wait_all, params
            )

        # Construct and add NetQASM instructions for post routine
        if params.post_routine:
            self._add_post_commands(
                qubit_ids_array,
                params.number,
                ent_results_array,
                EPRType.K,
                params.post_routine,
            )

        return qubit_futures

    def sdk_epr_measure(
        self,
        role: EPRRole,
        params: EntRequestParams,
    ) -> List[LinkLayerOKTypeM]:
        self._check_epr_args(tp=EPRType.M, params=params)

        # Setup NetQASM arrays and SDK handles.

        # Entanglement results array.
        # This will be filled in by the quantum node controller.
        ent_results_array = self._alloc_ent_results_array(
            number=params.number, tp=EPRType.M
        )

        # SDK handles to result values (LinkLayerOkTypeM objects).
        result_futures: List[LinkLayerOKTypeM] = self._get_meas_dir_futures_array(
            params.number, ent_results_array
        )

        wait_all = params.post_routine is None

        # Construct and add the NetQASM instructions
        if role == EPRRole.CREATE:
            # NetQASM array for entanglement request parameters.
            create_args_array: Array = self._alloc_epr_create_args(EPRType.M, params)

            self._build_cmds_epr_create_measure(
                create_args_array, ent_results_array, wait_all, params
            )
        else:
            self._build_cmds_epr_recv_measure(ent_results_array, wait_all, params)

        return result_futures

    def sdk_epr_rsp_create(
        self,
        params: EntRequestParams,
    ) -> List[LinkLayerOKTypeM]:
        self._check_epr_args(tp=EPRType.R, params=params)

        # Setup NetQASM arrays and SDK handles.

        # Entanglement results array.
        # This will be filled in by the quantum node controller.
        ent_results_array = self._alloc_ent_results_array(
            number=params.number, tp=EPRType.R
        )

        # NetQASM array for entanglement request parameters.
        create_args_array: Array = self._alloc_epr_create_args(EPRType.R, params)

        # SDK handles to result values (LinkLayerOkTypeM objects).
        result_futures = self._get_meas_dir_futures_array(
            params.number, ent_results_array
        )

        wait_all = params.post_routine is None

        # Construct and add the NetQASM instructions
        self._build_cmds_epr_create_rsp(
            create_args_array, ent_results_array, wait_all, params
        )

        return result_futures

    def sdk_epr_rsp_recv(
        self,
        params: EntRequestParams,
    ) -> List[Qubit]:
        self._check_epr_args(tp=EPRType.R, params=params)

        # Setup NetQASM arrays and SDK handles.

        # Entanglement results array.
        # This will be filled in by the quantum node controller.
        ent_results_array = self._alloc_ent_results_array(
            number=params.number, tp=EPRType.K  # Keep since we are receiving RSP
        )

        qubit_ids_array: Optional[Array] = None

        # SDK handles to result values (Qubit objects).
        qubit_futures = self._get_qubit_futures(
            params.number, params.sequential, ent_results_array
        )
        assert all(isinstance(q, Qubit) for q in qubit_futures)

        # Receivers of R-type requests need an array for IDs for the generated qubits.
        virtual_qubit_ids = [q.qubit_id for q in qubit_futures]
        qubit_ids_array = self.alloc_array(init_values=virtual_qubit_ids)  # type: ignore

        wait_all = params.post_routine is None

        # Construct and add the NetQASM instructions
        self._build_cmds_epr_recv_rsp(
            qubit_ids_array, ent_results_array, wait_all, params
        )

        return qubit_futures

    def sdk_create_epr_keep(self, params: EntRequestParams) -> List[Qubit]:
        return self.sdk_epr_keep(role=EPRRole.CREATE, params=params)

    def sdk_recv_epr_keep(self, params: EntRequestParams) -> List[Qubit]:
        return self.sdk_epr_keep(role=EPRRole.RECV, params=params)

    def sdk_create_epr_measure(
        self, params: EntRequestParams
    ) -> List[LinkLayerOKTypeM]:
        return self.sdk_epr_measure(role=EPRRole.CREATE, params=params)

    def sdk_recv_epr_measure(self, params: EntRequestParams) -> List[LinkLayerOKTypeM]:
        return self.sdk_epr_measure(role=EPRRole.RECV, params=params)

    @contextmanager
    def sdk_loop_context(
        self,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[Union[operand.Register, str]] = None,
    ) -> Iterator[operand.Register]:
        try:
            pre_commands = self.subrt_pop_pending_commands()
            loop_register_result = self._get_loop_register(loop_register, activate=True)
            yield loop_register_result
        finally:
            body_commands = self.subrt_pop_pending_commands()
            self._build_cmds_loop(
                pre_commands=pre_commands,
                body_commands=body_commands,
                stop=stop,
                start=start,
                step=step,
                loop_register=loop_register_result,
            )
            self._mem_mgr.remove_active_reg(loop_register_result)

    def sdk_loop_body(
        self,
        body: T_LoopRoutine,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[Union[operand.Register, str]] = None,
    ):
        self._build_cmds_loop_body(body, stop, start, step, loop_register)

    def sdk_if_eq(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a == b"""
        self._build_cmds_if_stmt(GenericInstr.BEQ, a, b, body)

    def sdk_if_ne(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a != b"""
        self._build_cmds_if_stmt(GenericInstr.BNE, a, b, body)

    def sdk_if_lt(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a < b"""
        self._build_cmds_if_stmt(GenericInstr.BLT, a, b, body)

    def sdk_if_ge(self, a: T_CValue, b: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a >= b"""
        self._build_cmds_if_stmt(GenericInstr.BGE, a, b, body)

    def sdk_if_ez(self, a: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a == 0"""
        self._build_cmds_if_stmt(GenericInstr.BEZ, a, b=None, body=body)

    def sdk_if_nz(self, a: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a != 0"""
        self._build_cmds_if_stmt(GenericInstr.BNZ, a, b=None, body=body)
