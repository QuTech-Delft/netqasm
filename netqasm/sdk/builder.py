"""Conversion from Python code into an NetQASM subroutines.

This module contains the `Builder` class, which is used by a Connection to transform
Python application script code into NetQASM subroutines.
"""

from __future__ import annotations

from contextlib import contextmanager
from itertools import count
from typing import (
    TYPE_CHECKING,
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
from netqasm.qlink_compat import EPRRole, EPRType, LinkLayerOKTypeK
from netqasm.sdk.build_epr import (
    EntRequestParams,
    EprKeepResult,
    EprMeasureResult,
    deserialize_epr_keep_results,
    deserialize_epr_measure_results,
    serialize_request,
)
from netqasm.sdk.build_nv import NVEprCompiler
from netqasm.sdk.build_types import (
    GenericHardwareConfig,
    HardwareConfig,
    NVHardwareConfig,
    T_BranchRoutine,
    T_CleanupRoutine,
    T_LoopRoutine,
    T_PostRoutine,
)
from netqasm.sdk.compiling import NVSubroutineCompiler, SubroutineCompiler
from netqasm.sdk.config import LogConfig
from netqasm.sdk.constraint import SdkConstraint, ValueAtMostConstraint
from netqasm.sdk.futures import Array, Future, RegFuture, T_CValue
from netqasm.sdk.memmgr import MemoryManager
from netqasm.sdk.qubit import FutureQubit, Qubit
from netqasm.sdk.toolbox import get_angle_spec_from_float
from netqasm.typedefs import T_Cmd
from netqasm.util.log import LineTracker

if TYPE_CHECKING:
    from netqasm.sdk.connection import BaseNetQASMConnection


class LabelManager:
    """Simple manager class for providing unique branch labels."""

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
                    break
            return name


class SdkIfContext:
    """Context object for if statements in SDK code such as `with conn.if_eq()`."""

    def __init__(
        self,
        id: int,
        builder: Builder,
        condition: GenericInstr,
        op0: Optional[T_CValue],
        op1: Optional[T_CValue],
    ):
        self._id = id
        self._builder = builder
        self._condition = condition
        self._op0 = op0
        self._op1 = op1

    def __enter__(self):
        return self._builder.if_context_enter(context_id=self._id)

    def __exit__(self, *args, **kwargs):
        return self._builder.if_context_exit(
            context_id=self._id, condition=self._condition, op0=self._op0, op1=self._op1
        )


class SdkForEachContext:
    """Context object for foreach statements in SDK code such as `with conn.foreach()`."""

    def __init__(
        self,
        id: int,
        builder: Builder,
        array: Array,
        return_index: bool,
    ):
        self._id = id
        self._builder = builder
        self._array = array
        self._return_index = return_index

    def __enter__(self):
        return self._builder._foreach_context_enter(
            context_id=self._id, array=self._array, return_index=self._return_index
        )

    def __exit__(self, *args, **kwargs):
        return self._builder._foreach_context_exit(
            context_id=self._id, array=self._array
        )


class SdkLoopUntilContext:
    """Context object for loop_until() statements in SDK code."""

    def __init__(self, id: int, builder: Builder, max_iterations: int):
        self._id = id
        self._builder = builder
        self._exit_condition: Optional[SdkConstraint] = None
        self._cleanup_code: Optional[T_CleanupRoutine] = None
        self._loop_register: Optional[RegFuture] = None
        self._max_iterations = max_iterations

    def set_exit_condition(self, constraint: SdkConstraint) -> None:
        """Set the exit condition for this while loop."""
        self._exit_condition = constraint

    @property
    def exit_condition(self) -> Optional[SdkConstraint]:
        """Get the exit condition for this while loop."""
        return self._exit_condition

    def set_cleanup_code(self, cleanup_code: T_CleanupRoutine) -> None:
        """Set the cleanup code for this while loop."""
        self._cleanup_code = cleanup_code

    @property
    def cleanup_code(self) -> Optional[T_CleanupRoutine]:
        """Get the cleanup code for this while loop."""
        return self._cleanup_code

    def set_loop_register(self, register: RegFuture) -> None:
        """Set the register used that holds the iteration index for this while loop."""
        self._loop_register = register

    @property
    def loop_register(self) -> Optional[RegFuture]:
        """Get the register used that holds the iteration index for this while loop."""
        return self._loop_register

    @property
    def max_iterations(self) -> int:
        """Get the maximum number of iterations for this while loop."""
        return self._max_iterations


class Builder:
    """Object that transforms Python script code into `PreSubroutine`s.

    A Connection uses a Builder to handle statements in application script code.
    The Builder converts the statements into pseudo-NetQASM instructions that are
    assembled into a PreSubroutine. When the connectin flushes, the PreSubroutine is
    is compiled into a NetQASM subroutine.
    """

    def __init__(
        self,
        connection: BaseNetQASMConnection,
        app_id: int,
        hardware_config: Optional[HardwareConfig] = None,
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

        self._mem_mgr: MemoryManager = MemoryManager()

        # If False, don't return arrays even if they are used in a subroutine
        self._return_arrays: bool = return_arrays

        self._next_context_id: int = 0
        # Storing commands before an conditional statement
        self._pre_context_commands: Dict[int, List[T_Cmd]] = {}
        self._pre_context_registers: Dict[int, List[operand.Register]] = {}

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

        self._hardware_config = hardware_config
        if self._hardware_config is None:
            self._hardware_config = GenericHardwareConfig(5)

        self._max_qubits: int = self._hardware_config.qubit_count

        # What compiler (if any) to be used
        self._compiler: Optional[Type[SubroutineCompiler]] = compiler

        # If an NV compiler is specified but not an NV hardware config,
        # make sure an NV config is used after all.
        if compiler == NVSubroutineCompiler:
            num_qubits = self._hardware_config.qubit_count
            self._hardware_config = NVHardwareConfig(num_qubits)

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
        self._mem_mgr.add_register_to_return(reg)
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

    def subrt_pop_all_pending_commands(self) -> List[T_Cmd]:
        commands = self._pending_commands
        self._pending_commands = []
        return commands

    def subrt_pop_pending_subroutine(self) -> Optional[PreSubroutine]:
        # Add commands for initialising and returning arrays
        self._build_cmds_allocated_arrays()
        self._build_cmds_return_registers()
        if len(self._pending_commands) > 0:
            commands = self.subrt_pop_all_pending_commands()
            metadata = self.subrt_get_metadata()
            return PreSubroutine(**metadata, commands=commands)
        else:
            return None

    def subrt_get_metadata(self) -> Dict:
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
        serialized_args = serialize_request(tp, params)
        return self.alloc_array(
            length=len(serialized_args), init_values=serialized_args
        )

    def _build_cmds_wait_move_epr_to_mem(
        self, number: int, ent_results_array: Array
    ) -> None:

        loop_register = self._mem_mgr.get_inactive_register()

        def post_loop(conn: BaseNetQASMConnection, loop_reg: RegFuture):
            # Wait for each pair individually
            pair = loop_register
            conn.builder._add_wait_for_ent_info_cmd(
                ent_results_array=ent_results_array,
                pair=pair,
            )

            # If it's the last pair, don't move it to a mem qubit
            with loop_reg.if_ne(number - 1):
                reg0 = self._mem_mgr.get_inactive_register(activate=True)
                reg1 = self._mem_mgr.get_inactive_register(activate=True)
                assert loop_reg.reg is not None

                # Calculate the virtual ID of the memory qubit this state should move to.
                # It is "number of pairs" - 1 - "current index".
                sub_cmd = ICmd(
                    instruction=GenericInstr.SUB,
                    operands=[reg0, number - 1, loop_reg.reg],
                )
                set_0_cmds = ICmd(instruction=GenericInstr.SET, operands=[reg1, 0])

                # Move the state from the communication qubit (ID = 0) to the
                # memory qubit for which we calculated the ID above.
                mov_cmd = ICmd(
                    instruction=GenericInstr.MOV,
                    operands=[reg1, reg0],
                )

                # Mark the communication qubit as free.
                free_cmd = ICmd(instruction=GenericInstr.QFREE, operands=[reg1])

                # Add the commands to the subroutine.
                commands = [sub_cmd] + [set_0_cmds] + [mov_cmd] + [free_cmd]  # type: ignore
                self.subrt_add_pending_commands(commands)  # type: ignore

                self._mem_mgr.remove_active_register(reg0)
                self._mem_mgr.remove_active_register(reg1)

        self._build_cmds_loop_body(post_loop, stop=number, loop_register=loop_register)

    def _build_cmds_post_epr(
        self,
        qubit_ids: Array,
        number: int,
        ent_results_array: Array,
        tp: EPRType,
        post_routine: T_PostRoutine,
    ) -> None:

        loop_register = self._mem_mgr.get_inactive_register()

        def post_loop(conn: BaseNetQASMConnection, _: RegFuture):
            # Wait for each pair individually
            pair = loop_register
            conn.builder._add_wait_for_ent_info_cmd(
                ent_results_array=ent_results_array,
                pair=pair,
            )
            assert tp == EPRType.K or tp == EPRType.R
            q_id = qubit_ids.get_future_index(pair)
            q = FutureQubit(conn=conn, future_id=q_id)
            pair_future = RegFuture(self._connection, pair)
            post_routine(self, q, pair_future)

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
        def add_arr_start(conn, _):
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
        def add_arr_stop(conn, _):
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
            self._mem_mgr.remove_active_register(reg)

    def _pre_epr_context(
        self,
        role: EPRRole,
        params: EntRequestParams,
    ) -> Tuple[List[T_Cmd], operand.Register, Array, FutureQubit, operand.Register]:
        self._assert_epr_args(
            number=params.number,
            post_routine=lambda: None,  # type: ignore
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

        pre_commands = self.subrt_pop_all_pending_commands()
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
        body_commands = self.subrt_pop_all_pending_commands()
        self._add_wait_for_ent_info_cmd(
            ent_results_array=ent_results_array,
            pair=pair,
        )
        wait_cmds = self.subrt_pop_all_pending_commands()
        body_commands = wait_cmds + body_commands
        self._build_cmds_loop(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=number,
            start=0,
            step=1,
            loop_register=loop_register,
        )
        self._mem_mgr.remove_active_register(loop_register)

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

    def _create_ent_qubits(
        self, ent_info_slices: List[LinkLayerOKTypeK], sequential: bool
    ) -> List[Qubit]:
        qubits: List[Qubit] = []
        num_pairs = len(ent_info_slices)

        if isinstance(self._hardware_config, NVHardwareConfig):
            # NV: only ID 0 can be used for entanglement
            self._build_cmds_free_up_qubit_location(0)
            if sequential:
                # all qubits get ID 0
                for _, ent_info_slice in enumerate(ent_info_slices):
                    q = Qubit(
                        self._connection,
                        add_new_command=False,
                        ent_info=ent_info_slice,
                        virtual_address=0,
                    )
                    qubits.append(q)
            else:  # not sequential
                # EXPLICIT MOVE (i.e. application moves states from comm to mem qubits)

                # Create the Qubit object that is returned to the SDK.
                for i, ent_info_slice in enumerate(ent_info_slices):
                    # Allocate and initialize the memory qubit which the entangled
                    # state should finally end up in.

                    final_id = num_pairs - 1 - i

                    # If the final qubit is the comm qubit (ID 0), don't allocate it,
                    # since it will automatically be allocated as part of
                    # entanglement generation.
                    add_new_command = True
                    if final_id == 0:
                        add_new_command = False
                    else:
                        # Make sure the memory qubit is free so we can allocate it.
                        assert not self._mem_mgr.is_qubit_id_used(final_id)

                    q = Qubit(
                        self._connection,
                        add_new_command=add_new_command,
                        ent_info=ent_info_slice,
                        virtual_address=final_id,
                    )
                    qubits.append(q)
        else:  # generic hardware
            virt_id: Optional[int]
            if sequential:
                # use one and the same virtual ID for all qubits
                virt_id = self._mem_mgr.get_new_qubit_address()
            else:
                virt_id = None  # let Qubit constructor choose unused ID
            for i, ent_info_slice in enumerate(ent_info_slices):
                q = Qubit(
                    self._connection,
                    add_new_command=False,
                    ent_info=ent_info_slice,
                    virtual_address=virt_id,
                )
                qubits.append(q)
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
        op: T_CValue,
    ) -> Tuple[List[ICmd], List[BranchLabel]]:
        # Exit label
        exit_label = self._label_mgr.new_label(start_with="IF_EXIT")
        if_start: List[ICmd] = []

        using_new_temp_reg = False

        cmds, cond_operand = self._get_condition_operand(op)
        if_start.extend(cmds)

        branch = ICmd(
            instruction=branch_instruction,
            operands=[cond_operand, Label(exit_label)],
        )
        if_start.append(branch)

        if using_new_temp_reg:
            assert isinstance(cond_operand, operand.Register)
            self._mem_mgr.remove_active_register(cond_operand)

        exit = BranchLabel(exit_label)
        if_end = [exit]

        return if_start, if_end

    def _get_branch_commands(
        self,
        branch_instruction: GenericInstr,
        op0: T_CValue,
        op1: T_CValue,
    ) -> Tuple[List[ICmd], List[BranchLabel]]:
        # Exit label
        exit_label = self._label_mgr.new_label(start_with="IF_EXIT")
        cond_operands: List[T_OperandUnion] = []
        if_start: List[ICmd] = []

        temp_regs_to_remove: List[operand.Register] = []

        for x in [op0, op1]:
            cmds, cond_operand = self._get_condition_operand(x)
            if_start.extend(cmds)
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
            self._mem_mgr.remove_active_register(reg)

        exit = BranchLabel(exit_label)
        if_end = [exit]

        return if_start, if_end

    @contextmanager
    def _activate_register(self, register: operand.Register) -> Iterator[None]:
        try:
            self._mem_mgr.add_active_register(register)
            yield
        except Exception as err:
            raise err
        finally:
            self._mem_mgr.remove_active_register(register)

    def _loop_get_register(
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

        if self._mem_mgr.is_register_active(loop_register):
            raise ValueError("Register used for looping should not already be active")
        return loop_register

    def _loop_get_entry_commands(
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

    def _loop_get_exit_commands(
        self,
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

    def _loop_until_get_entry_commands(
        self,
        entry_label: str,
        exit_label: str,
        stop: int,
        loop_register: operand.Register,
    ) -> List[T_Cmd]:
        return [
            ICmd(instruction=GenericInstr.SET, operands=[loop_register, 0]),
            BranchLabel(entry_label),
            ICmd(
                instruction=GenericInstr.BEQ,
                operands=[loop_register, stop, Label(exit_label)],
            ),
        ]

    def _loop_until_get_break_commands(
        self,
        context: SdkLoopUntilContext,
        exit_label: str,
    ) -> List[T_Cmd]:
        commands: List[ICmd] = []
        condition = context.exit_condition

        if isinstance(condition, ValueAtMostConstraint):
            if_start: List[ICmd] = []

            temp_regs_to_remove: List[operand.Register] = []

            cmds, cond_operand = self._get_condition_operand(condition.future)
            if_start.extend(cmds)

            if isinstance(condition.future, Future):
                assert isinstance(cond_operand, operand.Register)
                temp_regs_to_remove.append(cond_operand)

            branch = ICmd(
                instruction=GenericInstr.BLT,
                operands=[cond_operand, condition.value, Label(exit_label)],
            )
            if_start.append(branch)
            commands = if_start
        else:
            assert False, "not supported"
        return commands  # type: ignore

    def _loop_until_get_exit_commands(
        self, entry_label: str, exit_label: str, loop_register: operand.Register
    ) -> List[T_Cmd]:
        return [
            ICmd(
                instruction=GenericInstr.ADD,
                operands=[loop_register, loop_register, 1],
            ),
            ICmd(instruction=GenericInstr.JMP, operands=[Label(entry_label)]),
            BranchLabel(exit_label),
        ]

    def if_context_enter(self, context_id: int) -> None:
        pre_commands = self.subrt_pop_all_pending_commands()
        self._pre_context_commands[context_id] = pre_commands

    def if_context_exit(
        self,
        context_id: int,
        condition: GenericInstr,
        op0: T_CValue,
        op1: Optional[T_CValue],
    ) -> None:
        # pop commands that were added while evaluting the context body
        body_commands = self.subrt_pop_all_pending_commands()

        # get all commands that were pending before entering this context
        pre_context_commands = self._pre_context_commands.pop(context_id, None)
        if pre_context_commands is None:
            raise RuntimeError("Something went wrong, no pre_context_commands")

        self._build_cmds_condition(
            pre_commands=pre_context_commands,
            body_commands=body_commands,
            condition=condition,
            op0=op0,
            op1=op1,
        )

    def _foreach_context_enter(
        self, context_id: int, array: Array, return_index: bool
    ) -> Union[Tuple[operand.Register, Future], Future]:
        pre_commands = self.subrt_pop_all_pending_commands()
        loop_register = self._mem_mgr.get_inactive_register(activate=True)

        # NOTE (BUG): the below assignment is NOT consistent with the type of _pre_context_commands
        # It works (maybe?) because the values are pushed only temporarily
        self._pre_context_commands[context_id] = pre_commands, loop_register  # type: ignore
        if return_index:
            return loop_register, array.get_future_index(loop_register)
        else:
            return array.get_future_index(loop_register)

    def _foreach_context_exit(self, context_id: int, array: Array) -> None:
        body_commands = self.subrt_pop_all_pending_commands()
        pre_context_commands: Tuple[List[T_Cmd], operand.Register] = self._pre_context_commands.pop(  # type: ignore
            context_id, None  # type: ignore
        )
        if pre_context_commands is None:
            raise RuntimeError("Something went wrong, no pre_context_commands")

        # NOTE (BUG): see NOTE (BUG) in _foreach_context_enter
        pre_commands, loop_register = pre_context_commands  # type: ignore
        self._build_cmds_loop(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=len(array),
            start=0,
            step=1,
            loop_register=loop_register,
        )
        self._mem_mgr.remove_active_register(loop_register)

    def _loop_until_context_enter(self, context_id: int) -> operand.Register:
        pre_commands = self.subrt_pop_all_pending_commands()
        loop_register = self._mem_mgr.get_inactive_register(activate=True)

        self._pre_context_commands[context_id] = pre_commands
        self._pre_context_registers[context_id] = [loop_register]

        return loop_register

    def _loop_until_context_exit(
        self, context_id: int, context: SdkLoopUntilContext
    ) -> None:
        body_commands = self.subrt_pop_all_pending_commands()
        pre_commands = self._pre_context_commands.pop(context_id, None)
        if pre_commands is None:
            raise RuntimeError("Something went wrong, no pre_commands")
        loop_registers = self._pre_context_registers.pop(context_id, None)
        if loop_registers is None:
            raise RuntimeError("Something went wrong, no loop_registers for context")
        loop_register = loop_registers[0]

        self._build_cmds_loop_until(
            pre_commands=pre_commands,
            body_commands=body_commands,
            context=context,
            loop_register=loop_register,
        )

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
        if isinstance(self._hardware_config, NVHardwareConfig):
            # If compiling for NV, only virtual ID 0 can be used to measure a qubit.
            # So, if this qubit is already in use, we need to move it away first.
            if not isinstance(qubit_id, Future):
                if qubit_id != 0:
                    self._build_cmds_free_up_qubit_location(virtual_address=0)
        outcome_reg = self._mem_mgr.get_new_meas_outcome_register()
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
                self._mem_mgr.meas_register_set_unused(outcome_reg)
            elif isinstance(future, RegFuture):
                future.reg = outcome_reg
                self._mem_mgr.add_register_to_return(outcome_reg)
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
        current_commands = self.subrt_pop_all_pending_commands()

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

                def init_array_elt(conn, _):
                    conn._builder.subrt_add_pending_command(store_cmd)

                self._build_cmds_loop_body(
                    init_array_elt, stop=length, loop_register=loop_register
                )
                commands.extend(self.subrt_pop_all_pending_commands())
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
            set_reg_cmds = value.get_load_commands(register)
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
        if isinstance(self._hardware_config, NVHardwareConfig):
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

    def _build_cmds_undefine_array(self, array: Array) -> None:
        index_reg = self._mem_mgr.get_inactive_register()
        undef_cmd = ICmd(
            instruction=GenericInstr.UNDEF,
            operands=[ArrayEntry(Address(array.address), index_reg)],
        )

        def undef_result_element(conn: BaseNetQASMConnection, _: RegFuture):
            conn.builder.subrt_add_pending_command(undef_cmd)

        self._build_cmds_loop_body(
            undef_result_element,
            stop=len(array),
            loop_register=index_reg,
        )

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
        loop_register = self._loop_get_register(loop_register)
        pre_commands = self.subrt_pop_all_pending_commands()

        self._mem_mgr.add_active_register(loop_register)
        # evaluate body (will add pending commands)
        body(
            self._connection,
            RegFuture(connection=self._connection, reg=loop_register),
        )
        body_commands = self.subrt_pop_all_pending_commands()

        self._build_cmds_loop(
            pre_commands=pre_commands,
            body_commands=body_commands,
            stop=stop,
            start=start,
            step=step,
            loop_register=loop_register,
        )
        self._mem_mgr.remove_active_register(loop_register)

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

        loop_start = self._loop_get_entry_commands(
            start=start,
            stop=stop,
            entry_label=entry_label,
            exit_label=exit_label,
            loop_register=loop_register,
        )
        loop_end = self._loop_get_exit_commands(
            step=step,
            entry_label=entry_label,
            exit_label=exit_label,
            loop_register=loop_register,
        )

        commands = pre_commands + loop_start + body_commands + loop_end

        self.subrt_add_pending_commands(commands=commands)

    def _build_cmds_loop_until(
        self,
        pre_commands: List[T_Cmd],
        body_commands: List[T_Cmd],
        context: SdkLoopUntilContext,
        loop_register: operand.Register,
    ) -> None:
        if len(body_commands) == 0:
            self.subrt_add_pending_commands(commands=pre_commands)
            return

        entry_label = self._label_mgr.new_label(start_with="WHILE")
        exit_label = self._label_mgr.new_label(start_with="WHILE_EXIT")

        loop_until_start = self._loop_until_get_entry_commands(
            entry_label=entry_label,
            exit_label=exit_label,
            stop=context.max_iterations,
            loop_register=loop_register,
        )
        loop_until_break = self._loop_until_get_break_commands(
            context=context, exit_label=exit_label
        )

        cleanup_body = context.cleanup_code
        if cleanup_body is not None:
            cleanup_body(self._connection)
            cleanup_commands = self.subrt_pop_all_pending_commands()
        else:
            cleanup_commands = []

        loop_until_end = self._loop_until_get_exit_commands(
            entry_label=entry_label, exit_label=exit_label, loop_register=loop_register
        )

        commands = (
            pre_commands
            + loop_until_start
            + body_commands
            + loop_until_break
            + cleanup_commands
            + loop_until_end
        )

        self.subrt_add_pending_commands(commands=commands)

    def _build_cmds_if_stmt(
        self,
        condition: GenericInstr,
        op0: T_CValue,
        op1: Optional[T_CValue],
        body: T_BranchRoutine,
    ) -> None:
        """Used to build effective if-statements"""
        current_commands = self.subrt_pop_all_pending_commands()

        # evaluate body (will add pending commands)
        body(self._connection)

        # get those commands
        body_commands = self.subrt_pop_all_pending_commands()

        # combine existing commands with body commands and branch instructions
        self._build_cmds_condition(
            pre_commands=current_commands,
            body_commands=body_commands,
            condition=condition,
            op0=op0,
            op1=op1,
        )

    def _build_cmds_condition(
        self,
        pre_commands: List[T_Cmd],
        body_commands: List[T_Cmd],
        condition: GenericInstr,
        op0: T_CValue,
        op1: Optional[T_CValue],
    ) -> None:
        if len(body_commands) == 0:
            self.subrt_add_pending_commands(commands=pre_commands)
            return
        negated_predicate = flip_branch_instr(condition)
        # Construct a list of all commands to see what branch labels are already used
        all_commands = pre_commands + body_commands
        # We also need to check any existing other pre context commands if they are nested
        for pre_context_cmds in self._pre_context_commands.values():
            all_commands.extend(pre_context_cmds)

        if negated_predicate in [GenericInstr.BEZ, GenericInstr.BNZ]:
            if_start, if_end = self._get_branch_commands_single_operand(
                branch_instruction=negated_predicate, op=op0
            )
        else:
            assert op1 is not None
            if_start, if_end = self._get_branch_commands(
                branch_instruction=negated_predicate,
                op0=op0,
                op1=op1,
            )
        commands: List[T_Cmd] = pre_commands + if_start + body_commands + if_end  # type: ignore

        self.subrt_add_pending_commands(commands=commands)

    def sdk_epr_keep(
        self,
        role: EPRRole,
        params: EntRequestParams,
        reset_results_array: bool = False,
    ) -> Tuple[List[Qubit], Array]:
        """Build commands for an EPR keep operation and return the result futures."""
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
        if (
            self._hardware_config is not None
            and self._hardware_config.comm_qubit_count == 1
        ):
            # If there is only one comm qubit, only ID 0 can be used to receive the
            # EPR qubit. The Builder will however insert instructions to move this
            # qubit to one of the memory qubits. The corresponding QubitFuture object
            # still has the ID of this memory qubit (and not ID 0)!
            virtual_qubit_ids = [0 for _ in qubit_futures]
        else:
            virtual_qubit_ids = [q.qubit_id for q in qubit_futures]
        qubit_ids_array: Array = self.alloc_array(init_values=virtual_qubit_ids)  # type: ignore

        wait_all = True
        # If there is a post routine, handle pairs one by one.
        # If there is only one comm qubit, handle pairs one by one.
        if (
            params.post_routine is not None
            or self._hardware_config is not None
            and self._hardware_config.comm_qubit_count == 1
        ):
            wait_all = False

        if reset_results_array:
            self._build_cmds_undefine_array(ent_results_array)

        # Construct and add the NetQASM instructions
        if role == EPRRole.CREATE:
            # NetQASM array for entanglement request parameters.
            create_args_array: Array = self._alloc_epr_create_args(EPRType.K, params)

            self._build_cmds_epr_create_keep(
                create_args_array,
                qubit_ids_array,
                ent_results_array,
                wait_all,
                params,
            )
        else:
            self._build_cmds_epr_recv_keep(
                qubit_ids_array, ent_results_array, wait_all, params
            )

        if (
            not params.sequential
            and self._hardware_config is not None
            and self._hardware_config.comm_qubit_count == 1
        ):
            self._build_cmds_wait_move_epr_to_mem(
                number=params.number, ent_results_array=ent_results_array
            )

        # Construct and add NetQASM instructions for post routine
        if params.post_routine:
            self._build_cmds_post_epr(
                qubit_ids_array,
                params.number,
                ent_results_array,
                EPRType.K,
                params.post_routine,
            )

        return qubit_futures, ent_results_array

    def sdk_epr_measure(
        self,
        role: EPRRole,
        params: EntRequestParams,
    ) -> List[EprMeasureResult]:
        """Build commands for an EPR measure operation and return the result futures."""
        self._check_epr_args(tp=EPRType.M, params=params)

        # Setup NetQASM arrays and SDK handles.

        # Entanglement results array.
        # This will be filled in by the quantum node controller.
        ent_results_array = self._alloc_ent_results_array(
            number=params.number, tp=EPRType.M
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

        results = deserialize_epr_measure_results(params.number, ent_results_array)
        return results

    def sdk_epr_rsp_create(
        self,
        params: EntRequestParams,
    ) -> List[EprMeasureResult]:
        """Build commands for a 'create remote state preparation' EPR operation
        and return the result futures."""
        self._check_epr_args(tp=EPRType.R, params=params)

        # Setup NetQASM arrays and SDK handles.

        # Entanglement results array.
        # This will be filled in by the quantum node controller.
        ent_results_array = self._alloc_ent_results_array(
            number=params.number, tp=EPRType.R
        )

        # NetQASM array for entanglement request parameters.
        create_args_array: Array = self._alloc_epr_create_args(EPRType.R, params)

        wait_all = params.post_routine is None

        # Construct and add the NetQASM instructions
        self._build_cmds_epr_create_rsp(
            create_args_array, ent_results_array, wait_all, params
        )

        return deserialize_epr_measure_results(params.number, ent_results_array)

    def sdk_epr_rsp_recv(
        self,
        params: EntRequestParams,
    ) -> Tuple[List[Qubit], List[EprKeepResult]]:
        """Build commands for a 'receive remote state preparation' EPR operation
        and return the created qubits and result futures."""
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

        epr_results = deserialize_epr_keep_results(params.number, ent_results_array)
        return qubit_futures, epr_results

    def sdk_create_epr_keep(
        self, params: EntRequestParams
    ) -> Tuple[List[Qubit], List[EprKeepResult]]:
        """Build commands for a 'create and keep' EPR operation and return the
        created qubits and result futures."""
        if params.min_fidelity_all_at_end is not None:
            # If a min-fidelity constraint is specified, wrap the operation in a loop
            assert params.max_tries is not None
            with self.sdk_new_loop_until_context(params.max_tries) as loop:
                qubits, result_array = self.sdk_epr_keep(
                    role=EPRRole.CREATE, params=params
                )

                results = deserialize_epr_keep_results(params.number, result_array)

                duration = results[-1].generation_duration
                max_time = NVEprCompiler.get_max_time_for_fidelity(
                    params.min_fidelity_all_at_end
                )
                self._connection._logger.info(
                    f"converting min fidelity constraint of "
                    f"{params.min_fidelity_all_at_end} to a max time of {max_time}"
                )

                loop.set_exit_condition(ValueAtMostConstraint(duration, max_time))

                def cleanup(_: BaseNetQASMConnection):
                    result_array.undefine()
                    # If the request was sequential, each pair has already been
                    # measured and does not need to be freed.
                    # Otherwise: free the qubits.
                    if not params.sequential:
                        for q in qubits:
                            q.free()

                loop.set_cleanup_code(cleanup)

            return qubits, results
        else:
            # otherwise, just do the operation once
            qubits, result_array = self.sdk_epr_keep(role=EPRRole.CREATE, params=params)
            results = deserialize_epr_keep_results(params.number, result_array)
            return qubits, results

    def sdk_recv_epr_keep(
        self, params: EntRequestParams
    ) -> Tuple[List[Qubit], List[EprKeepResult]]:
        """Build commands for a 'receive and keep' EPR operation and return the
        created qubits and result futures."""

        if params.min_fidelity_all_at_end is not None:
            # If a min-fidelity constraint is specified, wrap the operation in a loop
            assert params.max_tries is not None
            with self.sdk_new_loop_until_context(params.max_tries) as loop:
                qubits, result_array = self.sdk_epr_keep(
                    role=EPRRole.RECV, params=params, reset_results_array=True
                )

                results = deserialize_epr_keep_results(params.number, result_array)

                duration = results[-1].generation_duration
                max_time = NVEprCompiler.get_max_time_for_fidelity(
                    params.min_fidelity_all_at_end
                )
                loop.set_exit_condition(ValueAtMostConstraint(duration, max_time))

                def cleanup(_: BaseNetQASMConnection):
                    result_array.undefine()
                    # If the request was sequential, each pair has already been
                    # measured and does not need to be freed.
                    # Otherwise: free the qubits.
                    if not params.sequential:
                        for q in qubits:
                            q.free()

                loop.set_cleanup_code(cleanup)

            return qubits, results
        else:
            # otherwise, just do the operation once
            qubits, result_array = self.sdk_epr_keep(role=EPRRole.RECV, params=params)
            results = deserialize_epr_keep_results(params.number, result_array)
            return qubits, results

    def sdk_create_epr_measure(
        self, params: EntRequestParams
    ) -> List[EprMeasureResult]:
        """Build commands for a 'create and measure' EPR operation and return the
        result futures."""
        return self.sdk_epr_measure(role=EPRRole.CREATE, params=params)

    def sdk_recv_epr_measure(self, params: EntRequestParams) -> List[EprMeasureResult]:
        """Build commands for a 'receive and measure' EPR operation and return the
        result futures."""
        return self.sdk_epr_measure(role=EPRRole.RECV, params=params)

    def sdk_create_epr_rsp(self, params: EntRequestParams) -> List[EprMeasureResult]:
        """Build commands for a 'create remote state preperation' EPR operation
        and return the result futures."""
        if params.min_fidelity_all_at_end is not None:
            # If a min-fidelity constraint is specified, wrap the operation in a loop
            assert params.max_tries is not None
            with self.sdk_new_loop_until_context(params.max_tries) as loop:
                results = self.sdk_epr_rsp_create(params=params)
                duration = results[-1].generation_duration
                max_time = NVEprCompiler.get_max_time_for_fidelity(
                    params.min_fidelity_all_at_end
                )
                loop.set_exit_condition(ValueAtMostConstraint(duration, max_time))

            return results
        else:
            # otherwise, just do the operation once
            return self.sdk_epr_rsp_create(params=params)

    def sdk_recv_epr_rsp(
        self, params: EntRequestParams
    ) -> Tuple[List[Qubit], List[EprKeepResult]]:
        """Build commands for a 'receive remote state preparation' EPR operation
        and return the created qubits and result futures."""

        if params.min_fidelity_all_at_end is not None:
            # If a min-fidelity constraint is specified, wrap the operation in a loop
            assert params.max_tries is not None
            with self.sdk_new_loop_until_context(params.max_tries) as loop:
                qubits, results = self.sdk_epr_rsp_recv(params=params)
                duration = results[-1].generation_duration
                max_time = NVEprCompiler.get_max_time_for_fidelity(
                    params.min_fidelity_all_at_end
                )
                loop.set_exit_condition(ValueAtMostConstraint(duration, max_time))
            return qubits, results
        else:
            # otherwise, just do the operation once
            return self.sdk_epr_rsp_recv(params=params)

    @contextmanager
    def sdk_loop_context(
        self,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[Union[operand.Register, str]] = None,
    ) -> Iterator[operand.Register]:
        """Build commands for a 'loop' context and return the context object."""
        try:
            pre_commands = self.subrt_pop_all_pending_commands()
            loop_register_result = self._loop_get_register(loop_register, activate=True)
            yield loop_register_result
        finally:
            body_commands = self.subrt_pop_all_pending_commands()
            self._build_cmds_loop(
                pre_commands=pre_commands,
                body_commands=body_commands,
                stop=stop,
                start=start,
                step=step,
                loop_register=loop_register_result,
            )
            self._mem_mgr.remove_active_register(loop_register_result)

    def sdk_loop_body(
        self,
        body: T_LoopRoutine,
        stop: int,
        start: int = 0,
        step: int = 1,
        loop_register: Optional[Union[operand.Register, str]] = None,
    ) -> None:
        """Build commands for looping the code in the specified body."""
        self._build_cmds_loop_body(body, stop, start, step, loop_register)

    def sdk_if_eq(self, op0: T_CValue, op1: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a == b"""
        self._build_cmds_if_stmt(GenericInstr.BEQ, op0, op1, body)

    def sdk_if_ne(self, op0: T_CValue, op1: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a != b"""
        self._build_cmds_if_stmt(GenericInstr.BNE, op0, op1, body)

    def sdk_if_lt(self, op0: T_CValue, op1: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a < b"""
        self._build_cmds_if_stmt(GenericInstr.BLT, op0, op1, body)

    def sdk_if_ge(self, op0: T_CValue, op1: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a >= b"""
        self._build_cmds_if_stmt(GenericInstr.BGE, op0, op1, body)

    def sdk_if_ez(self, op0: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a == 0"""
        self._build_cmds_if_stmt(GenericInstr.BEZ, op0, op1=None, body=body)

    def sdk_if_nz(self, op0: T_CValue, body: T_BranchRoutine) -> None:
        """An effective if-statement where body is a function executing the clause for a != 0"""
        self._build_cmds_if_stmt(GenericInstr.BNZ, op0, op1=None, body=body)

    def sdk_new_if_context(
        self, condition: GenericInstr, op0: T_CValue, op1: Optional[T_CValue]
    ) -> SdkIfContext:
        """Build commands for an 'if' context and return the context object."""
        id = self._next_context_id
        context = SdkIfContext(
            id=id, builder=self, condition=condition, op0=op0, op1=op1
        )
        self._next_context_id += 1
        return context

    def sdk_new_foreach_context(
        self, array: Array, return_index: bool
    ) -> SdkForEachContext:
        """Build commands for an 'foreach' context and return the context object."""
        id = self._next_context_id
        context = SdkForEachContext(
            id=id, builder=self, array=array, return_index=return_index
        )
        self._next_context_id += 1
        return context

    @contextmanager
    def sdk_new_loop_until_context(
        self, max_iterations: int
    ) -> Iterator[SdkLoopUntilContext]:
        """Build commands for a 'loop_until' context and return the context object."""
        try:
            id = self._next_context_id
            context = SdkLoopUntilContext(
                id=id, builder=self, max_iterations=max_iterations
            )
            self._next_context_id += 1
            loop_register = self._loop_until_context_enter(id)
            reg_future = RegFuture(self._connection, loop_register)
            context.set_loop_register(reg_future)
            yield context
        finally:
            assert context.exit_condition is not None
            self._loop_until_context_exit(
                context_id=id,
                context=context,
            )

    @contextmanager
    def sdk_try_context(
        self,
        max_tries: int = 1,
    ) -> Iterator[None]:
        """Build commands for a 'try' context."""
        try:
            pre_commands = self.subrt_pop_all_pending_commands()
            yield
        finally:
            body_commands = self.subrt_pop_all_pending_commands()
            commands = pre_commands + body_commands
            self.subrt_add_pending_commands(commands)

    @contextmanager
    def sdk_create_epr_context(
        self, params: EntRequestParams
    ) -> Iterator[Tuple[FutureQubit, RegFuture]]:
        """Build commands for an EPR context and return an iterator over
        the EPR qubits and indices created in this context."""
        try:
            (
                pre_commands,
                loop_register,
                ent_results_array,
                output,
                pair,
            ) = self._pre_epr_context(role=EPRRole.CREATE, params=params)
            pair_future = RegFuture(self._connection, pair)
            yield output, pair_future
        finally:
            self._post_epr_context(
                pre_commands=pre_commands,
                number=params.number,
                loop_register=loop_register,
                ent_results_array=ent_results_array,
                pair=pair,
            )
