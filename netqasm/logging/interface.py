from dataclasses import dataclass
from typing import List, Optional, Tuple, TypedDict, Union, Dict
from enum import Enum


QubitState = Tuple[Tuple[complex, complex], Tuple[complex, complex]]  # 2x2 matrix
AbsoluteQubitID = List[Union[str, int]]  # [node_name, qubit_id]


class QubitGroup(TypedDict):
    is_entangled: Optional[bool]
    qubit_ids: List[AbsoluteQubitID]


QubitGroups = Dict[int, QubitGroup]  # group_id -> qubit_group


class EntanglementType(Enum):
    CK = "CK"   # Create and Keep
    MD = "MD"   # Measure Directly


class EntanglementStage(Enum):
    START = "start"
    FINISH = "finish"


@dataclass
class InstrLogEntry:
    # Wall clock time. Format is Python's `datetime.now()`.
    WCT: str

    # Time in NetSquid simulation, in nanoseconds.
    SIT: int

    # App ID, used internally by the backend.
    AID: int

    # Subroutine ID. Used internally by the Executor.
    SID: int

    # Program counter. Used internally by the Executor.
    PRC: int

    # Host line number.
    # Line number in source file (.py) related to what is currently executed.
    # The line is in the file given by HFL (see below).
    HLN: int

    # Host file.
    # Source file (.py) of current executed instruction.
    HFL: str

    # Mnemonic of the NetQASM instruction being executed.
    INS: str

    # Operands (register, array-entries..).
    # List of "op=val" strings
    OPR: List[str]

    # Physical qubit IDs of qubits part of the current operation.
    QID: List[int]

    # Virtual qubit IDs of qubits part of the current operation.
    VID: List[int]

    # Qubit states of the qubits part of the operations after execution.
    QST: Optional[List[QubitState]]

    # Measurement outcome. Only set in case of a measurement instruction.
    OUT: Optional[int]

    # Dictionary specifying groups of qubits across the network.
    QGR: Optional[QubitGroups]

    # Human-readable message.
    LOG: str


@dataclass
class NetworkLogEntry:
    # Wall clock time. Format is Python's `datetime.now()`.
    WCT: str

    # Time in NetSquid simulation, in nanoseconds.
    SIT: int

    # Entanglement generation type (Measure Directly or Create and Keep).
    # For the 'start' entanglement stage (see INS below), this value is None
    # since at this stage the value cannot be determined yet.
    # For the 'finish' stage, the correct value is filled in, however.
    TYP: Optional[EntanglementType]

    # Entanglement generation stage (start or finish).
    INS: EntanglementStage

    # Bases in which the two qubits (one on each end) were measured in.
    # Only applies to the Measure Directly case. It is `None` otherwise.
    BAS: Optional[List[int]]

    # Measurement outcomes of the two qubits (one on each end).
    # Only applies to the Measure Directly case. It is `None` otherwise.
    MSR: List[int]

    # Node names involved in this entanglement operation.
    NOD: List[str]

    # Path of links used for entanglement generation.
    # Links are identified using their names.
    PTH: List[str]

    # Physical qubit IDs of qubits part of the current operation.
    QID: List[int]

    # Qubit states of the qubits part of the operations after execution.
    QST: Optional[List[QubitState]]

    # Dictionary specifying groups of qubits across the network,
    # as they are after the current operation.
    QGR: Optional[QubitGroups]

    # Human-readable message.
    LOG: str


@dataclass
class ClassCommLogEntry:
    # Wall clock time. Format is Python's `datetime.now()`.
    WCT: str

    # Host line number.
    # Line number in source file (.py) related to what is currently executed.
    # The line is in the file given by HFL (see below).
    HLN: int

    # Host file.
    # Source file (.py) of current executed instruction.
    HFL: str

    # Classical operation being performed.
    INS: str

    # Message that is sent or received.
    MSG: str

    # Name (role) of the sender.
    SEN: str

    # Name (role) of the receiver.
    REC: str

    # Socket ID (used internally).
    SOD: str

    # Human-readable message.
    LOG: str


@dataclass
class AppLogEntry:
    # Wall clock time. Format is Python's `datetime.now()`.
    WCT: str

    # Host line number.
    # Line number in source file (.py) related to what is currently executed.
    # The line is in the file given by HFL (see below).
    HLN: int

    # Host file.
    # Source file (.py) of current executed instruction.
    HFL: str

    # Human-readable message.
    LOG: str
