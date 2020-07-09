import os
import abc
from enum import Enum
from datetime import datetime

from netqasm.instructions import (
    Instruction,
    instruction_to_string,
    QUBIT_GATES,
    SINGLE_QUBIT_GATES,
    TWO_QUBIT_GATES,
    EPR_INSTR,
)
from netqasm.subroutine import Register, ArrayEntry
from netqasm.yaml_util import dump_yaml
from netqasm.log_util import LineTracker


INSTR_TO_LOG = QUBIT_GATES + EPR_INSTR + [Instruction.MEAS]


class InstrField(Enum):
    WCT = "WCT"  # Wall clock time
    SIT = "SIT"  # Simulated time
    SID = "SID"  # Subroutine ID
    PRC = "PRC"  # Program counter
    HLN = "HLN"  # Host line number
    HFL = "HFL"  # Host file
    INS = "INS"  # Instruction
    OPR = "OPR"  # Operands (register, array-entries..)
    OPV = "OPV"  # Values of operands as stored in memory
    OUT = "OUT"  # Measurement outcome
    QST = "QST"  # Single-qubit state after operation
    ENT = "ENT"  # Is qubit entangled (bool)
    LOG = "LOG"  # Human-readable message


# Keep track of all structured loggers
# to be able to save them while finished applications
_STRUCT_LOGGERS = []


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

    def _get_current_qubit_state(self, subroutine_id, qubit_address_reg):
        app_id = self._executioner._get_app_id(subroutine_id=subroutine_id)
        virtual_address = self._executioner._get_register(app_id=app_id, register=qubit_address_reg)
        q_state = self._executioner._get_qubit_state(app_id=app_id, virtual_address=virtual_address)
        return q_state.state.tolist(), q_state.is_entangled

    def _get_op_values(self, subroutine_id, operands):
        values = []
        app_id = self._executioner._get_app_id(subroutine_id=subroutine_id)
        for operand in operands:
            value = None
            if isinstance(operand, int):
                value = operand
            elif isinstance(operand, Register):
                value = self._executioner._get_register(app_id=app_id, register=operand)
            elif isinstance(operand, ArrayEntry):
                value = self._executioner._get_array_entry(app_id=app_id, array_entry=operand)
            values.append(value)
        return values

    def save(self):
        dump_yaml(self._storage, self._filepath)


class InstrLogger(StructuredLogger):
    def __init__(self, filepath, executioner):
        super().__init__(filepath)
        self._executioner = executioner

    def _construct_entry(self, *args, **kwargs):
        command = kwargs['command']
        if command.instruction not in INSTR_TO_LOG:
            return None
        subroutine_id = kwargs['subroutine_id']
        output = kwargs['output']
        wall_time = str(datetime.now())
        sim_time = self._executioner._get_simulated_time()
        program_counter = kwargs['program_counter']
        instr_name = instruction_to_string(command.instruction)
        operands = command.operands
        ops_str = [str(op) for op in operands]
        op_values = self._get_op_values(subroutine_id=subroutine_id, operands=operands)
        log = f"Doing instruction {instr_name} with operands {ops_str}"
        if command.instruction in SINGLE_QUBIT_GATES + TWO_QUBIT_GATES + [Instruction.MEAS]:
            qubit_address_reg = operands[0]
            qubit_state, is_entangled = self._get_current_qubit_state(
                subroutine_id=subroutine_id,
                qubit_address_reg=qubit_address_reg,
            )
        else:
            qubit_state = None
            is_entangled = None
        if command.instruction == Instruction.MEAS:
            outcome = output
        else:
            outcome = None
        return {
            InstrField.WCT.value: wall_time,
            InstrField.SIT.value: sim_time,
            InstrField.SID.value: subroutine_id,
            InstrField.PRC.value: program_counter,
            InstrField.HLN.value: None,
            InstrField.INS.value: instr_name,
            InstrField.OPR.value: ops_str,
            InstrField.OPV.value: op_values,
            InstrField.OUT.value: outcome,
            InstrField.QST.value: qubit_state,
            InstrField.ENT.value: is_entangled,
            InstrField.LOG.value: log,
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


def get_new_app_logger(node_name, log_config):
    filename = f"{str(node_name).lower()}_app_log.yaml"
    log_dir = log_config.log_subroutines_dir
    filepath = os.path.join(log_dir, filename)
    app_logger = AppLogger(filepath=filepath, log_config=log_config)
    return app_logger
