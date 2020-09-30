import os
import abc
from enum import Enum
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Union

from netqasm.typing import TypedDict
from netqasm.subroutine import Register, ArrayEntry, Address
from netqasm.yaml_util import dump_yaml
from netqasm.log_util import LineTracker

from netqasm import instructions
from netqasm.encoding import RegisterName


def should_log_instr(instr):
    return (
        isinstance(instr, instructions.core.SingleQubitInstruction)
        or isinstance(instr, instructions.core.RotationInstruction)
        or isinstance(instr, instructions.core.TwoQubitInstruction)
        or isinstance(instr, instructions.core.CreateEPRInstruction)
        or isinstance(instr, instructions.core.RecvEPRInstruction)
        or isinstance(instr, instructions.core.MeasInstruction)
        or isinstance(instr, instructions.core.InitInstruction)
    ) and not (
        isinstance(instr, instructions.core.QAllocInstruction)
        or isinstance(instr, instructions.core.QFreeInstruction)
    )


def should_check_qubit_state(instr):
    return (
        isinstance(instr, instructions.core.SingleQubitInstruction)
        or isinstance(instr, instructions.core.TwoQubitInstruction)
        or isinstance(instr, instructions.core.MeasInstruction)
        or isinstance(instr, instructions.core.InitInstruction)
    ) and not (
        isinstance(instr, instructions.core.QAllocInstruction)
        or isinstance(instr, instructions.core.QFreeInstruction)
    )


QubitState = Tuple[Tuple[complex, complex], Tuple[complex, complex]]  # 2x2 matrix
AbsoluteQubitID = List[Union[str, int]]  # [node_name, qubit_id]


class QubitGroup(TypedDict):
    is_entangled: Optional[bool]
    qubit_ids: List[AbsoluteQubitID]


QubitGroups = Dict[int, QubitGroup]  # group_id -> qubit_group


class InstrField(Enum):
    WCT = "WCT"  # Wall clock time
    SIT = "SIT"  # Simulated time
    AID = "AID"  # App ID
    SID = "SID"  # Subroutine ID
    PRC = "PRC"  # Program counter
    HLN = "HLN"  # Host line number
    HFL = "HFL"  # Host file
    INS = "INS"  # Instruction
    OPR = "OPR"  # Operands (register, array-entries..)
    QID = "QID"  # Qubit IDs of qubits part of operation
    QST = "QST"  # Qubit states if the qubits part of the operations after execution
    OUT = "OUT"  # Measurement outcome
    QGR = "QGR"  # Dictionary specifying groups of qubit across the network
    # NOTE Qubits are in a group if they have interacted at some point.
    # This does not necessarily imply entanglement.
    # There is an additional flag specifying weather the group is entangled or not.
    LOG = "LOG"  # Human-readable message


# Keep track of all structured loggers
# to be able to save them while finished applications
_STRUCT_LOGGERS: List['StructuredLogger'] = []


def reset_struct_loggers():
    while len(_STRUCT_LOGGERS) > 0:
        _STRUCT_LOGGERS.pop()


def save_all_struct_loggers():
    while len(_STRUCT_LOGGERS) > 0:
        struct_logger = _STRUCT_LOGGERS.pop()
        struct_logger.save()


class StructuredLogger(abc.ABC):
    def __init__(self, filepath):
        self._filepath = filepath

        self._storage = []

        _STRUCT_LOGGERS.append(self)

    def log(self, *args, **kwargs):
        entry = self._construct_entry(*args, **kwargs)
        if entry is not None:
            self._storage.append(entry)

    @abc.abstractmethod
    def _construct_entry(self, *args, **kwargs):
        pass

    def _get_op_values(self, subroutine_id, operands):
        values = []
        for operand in operands:
            value = self._get_op_value(
                subroutine_id=subroutine_id,
                operand=operand,
            )
            values.append(value)
        return values

    def _get_op_value(self, subroutine_id, operand):
        app_id = self._executioner._get_app_id(subroutine_id=subroutine_id)
        value = None
        if isinstance(operand, int):
            value = operand
        elif isinstance(operand, Register):
            value = self._executioner._get_register(app_id=app_id, register=operand)
        elif isinstance(operand, ArrayEntry):
            value = self._executioner._get_array_entry(app_id=app_id, array_entry=operand)
        return value

    def save(self):
        dump_yaml(self._storage, self._filepath)


class InstrLogger(StructuredLogger):
    def __init__(self, filepath: str, executioner):
        super().__init__(filepath)
        self._executioner = executioner

    def _construct_entry(self, *args, **kwargs):
        command = kwargs['command']
        app_id = kwargs['app_id']
        subroutine_id = kwargs['subroutine_id']
        output = kwargs['output']
        wall_time = str(datetime.now())
        sim_time = self._executioner._get_simulated_time()
        program_counter = kwargs['program_counter']
        instr_name = command.mnemonic
        operands = command.operands
        op_values = self._get_op_values(subroutine_id=subroutine_id, operands=operands)
        ops_str = [f"{op}={opv}" for op, opv in zip(operands, op_values)]
        log = f"Doing instruction {instr_name} with operands {ops_str}"
        qubit_ids = self._get_qubit_ids(
            subroutine_id=subroutine_id,
            command=command,
        )
        self._update_qubits(
            subroutine_id=subroutine_id,
            instr=command,
            qubit_ids=qubit_ids,
        )
        if not should_log_instr(command):
            return None
        if should_check_qubit_state(command):
            qubit_states = self._get_qubit_states(
                subroutine_id=subroutine_id,
                qubit_ids=qubit_ids,
            )
            qubit_groups = self._get_qubit_groups()
        else:
            qubit_states = None
            qubit_groups = None
        if isinstance(command, instructions.core.MeasInstruction):
            outcome = output
        else:
            outcome = None
        return {
            InstrField.WCT.value: wall_time,
            InstrField.SIT.value: sim_time,
            InstrField.AID.value: app_id,
            InstrField.SID.value: subroutine_id,
            InstrField.PRC.value: program_counter,
            InstrField.HLN.value: None,
            InstrField.INS.value: instr_name,
            InstrField.OPR.value: ops_str,
            InstrField.QID.value: qubit_ids,
            InstrField.QST.value: qubit_states,
            InstrField.OUT.value: outcome,
            InstrField.QGR.value: qubit_groups,
            InstrField.LOG.value: log,
        }

    def _get_qubit_ids(
        self,
        subroutine_id: int,
        command: instructions.base.NetQASMInstruction,
    ) -> List[int]:
        """Gets the qubit IDs involved in a command"""
        qreg_instructions = [
            instructions.core.SingleQubitInstruction,
            instructions.core.InitInstruction,
            instructions.core.QAllocInstruction,
            instructions.core.QFreeInstruction,
            instructions.core.MeasInstruction,
        ]
        epr_instructions = [
            instructions.core.CreateEPRInstruction,
            instructions.core.RecvEPRInstruction,
        ]
        if any(isinstance(command, cmd_cls) for cmd_cls in qreg_instructions):
            qubit_id = self._get_op_value(
                subroutine_id=subroutine_id,
                operand=command.qreg,  # type: ignore
            )
            return [qubit_id]
        elif isinstance(command, instructions.core.TwoQubitInstruction):
            qubit_ids = []
            for qreg in [command.qreg0, command.qreg1]:
                qubit_id = self._get_op_value(
                    subroutine_id=subroutine_id,
                    operand=qreg,
                )
                qubit_ids.append(qubit_id)
            return qubit_ids
        elif any(isinstance(command, cmd_cls) for cmd_cls in epr_instructions):
            # Ignore a constant register since this indicates it's a measure directly request
            if command.qubit_addr_array.name == RegisterName.C:  # type: ignore
                return []
            qubit_id_array_address = Address(self._get_op_value(
                subroutine_id=subroutine_id,
                operand=command.qubit_addr_array,  # type: ignore
            ))
            app_id = self._executioner._get_app_id(subroutine_id=subroutine_id)
            return self._executioner._get_array(app_id=app_id, address=qubit_id_array_address)  # type: ignore
        else:
            return []

    @classmethod
    def _get_qubit_states(
        cls,
        subroutine_id: int,
        qubit_ids: List[int],
    ) -> Optional[List[QubitState]]:
        """Returns the reduced qubit states of the qubits involved in a command"""
        # NOTE should be subclassed
        return None

    @classmethod
    def _get_qubit_groups(cls) -> Optional[QubitGroups]:
        """Returns the current qubit groups in the simulation (qubits which have interacted
        and therefore may or may not be entangled)"""
        # NOTE should be subclassed
        return None


class NetworkField(Enum):
    WCT = InstrField.WCT.value  # Wall clock time
    SIT = InstrField.SIT.value  # Simulated time
    INS = InstrField.INS.value  # Entanglement generation stage
    NOD = "NOD"  # End nodes
    QID = InstrField.QID.value  # Qubit ids (node1, node2)
    QST = InstrField.QST.value  # Reduced qubit states
    QGR = InstrField.QGR.value  # Dictionary specifying groups of qubit across the network
    LOG = InstrField.LOG.value  # Human-readable message


class EntanglementStage(Enum):
    START = "start"
    FINISH = "finish"


class NetworkLogger(StructuredLogger):
    def __init__(self, filepath):
        super().__init__(filepath)

    def _construct_entry(self, *args, **kwargs):
        wall_time = str(datetime.now())
        sim_time = kwargs['sim_time']
        ent_stage = kwargs['ent_stage']
        nodes = kwargs['nodes']
        qubit_ids = kwargs['qubit_ids']
        qubit_states = kwargs['qubit_states']
        qubit_groups = kwargs['qubit_groups']
        msg = kwargs['msg']
        return {
            NetworkField.WCT.value: wall_time,
            NetworkField.SIT.value: sim_time,
            NetworkField.INS.value: f"epr_{ent_stage}",
            NetworkField.NOD.value: nodes,
            NetworkField.QID.value: qubit_ids,
            NetworkField.QST.value: qubit_states,
            NetworkField.QGR.value: qubit_groups,
            NetworkField.LOG.value: msg,
        }


class SocketOperation(Enum):
    SEND = "SEND"
    RECV = "RECV"
    WAIT_RECV = "WAIT_RECV"


class ClassCommField(Enum):
    WCT = InstrField.WCT.value  # Wall clock time
    HLN = InstrField.HLN.value  # Host line number
    HFL = InstrField.HFL.value  # Host file
    INS = InstrField.INS.value  # Instruction (SEND, WAIT_RECV or RECV)
    MSG = "MSG"  # Message sent or received
    SEN = "SEN"  # Sender
    REC = "REC"  # Receiver
    SOD = "SOD"  # Socket ID
    LOG = InstrField.LOG.value  # Human-readable message


class ClassCommLogger(StructuredLogger):
    def _construct_entry(self, *args, **kwargs):
        socket_op = kwargs['socket_op']
        msg = kwargs['msg']
        sender = kwargs['sender']
        receiver = kwargs['receiver']
        socket_id = kwargs['socket_id']
        hln = kwargs['hln']
        hfl = kwargs['hfl']
        log = kwargs['log']
        wall_time = str(datetime.now())
        return {
            ClassCommField.WCT.value: wall_time,
            ClassCommField.HLN.value: hln,
            ClassCommField.HFL.value: hfl,
            ClassCommField.INS.value: socket_op.value,
            ClassCommField.MSG.value: msg,
            ClassCommField.SEN.value: sender,
            ClassCommField.REC.value: receiver,
            ClassCommField.SOD.value: socket_id,
            ClassCommField.LOG.value: log,
        }


class AppLogField(Enum):
    WCT = InstrField.WCT.value  # Wall clock time
    HLN = InstrField.HLN.value  # Host line number
    HFL = InstrField.HFL.value  # Host file
    LOG = InstrField.LOG.value  # Human-readable message


class AppLogger(StructuredLogger):
    def __init__(self, filepath, log_config):
        super().__init__(filepath=filepath)

        self._line_tracker = LineTracker(log_config)

    def _construct_entry(self, *args, **kwargs):
        log = kwargs.get("log", None)
        if log is None:
            assert len(args) == 1, "AppLogger only takes on argument"
            log = args[0]
        host_line = self._line_tracker.get_line()
        hln = host_line.lineno
        hfl = host_line.filename
        wall_time = str(datetime.now())
        return {
            AppLogField.WCT.value: wall_time,
            AppLogField.HLN.value: hln,
            AppLogField.HFL.value: hfl,
            AppLogField.LOG.value: log,
        }


def get_new_app_logger(app_name, log_config):
    filename = f"{str(app_name).lower()}_app_log.yaml"
    log_dir = log_config.log_subroutines_dir
    filepath = os.path.join(log_dir, filename)
    app_logger = AppLogger(filepath=filepath, log_config=log_config)
    return app_logger
