from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

QubitState = Tuple[Tuple[complex, complex], Tuple[complex, complex]]  # 2x2 matrix
AbsoluteQubitID = List[Union[str, int]]  # [app_name, qubit_id]


@dataclass
class QubitGroup:
    is_entangled: Optional[bool]
    qubit_ids: List[AbsoluteQubitID]
    state: Optional[QubitState]  # only set when group size is 1


QubitGroups = Dict[int, QubitGroup]  # group_id -> qubit_group


class EntanglementType(Enum):
    CK = "CK"  # Create and Keep
    MD = "MD"  # Measure Directly


class EntanglementStage(Enum):
    START = "start"
    FINISH = "finish"


@dataclass
class InstrLogEntry:
    WCT: str
    """Wall clock time. Format is Python's `datetime.now()`."""

    SIT: int
    """ Time in NetSquid simulation, in nanoseconds."""

    AID: int
    """ App ID, used internally by the backend."""

    SID: int
    """ Subroutine ID. Used internally by the Executor."""

    PRC: int
    """ Program counter. Used internally by the Executor."""

    HLN: int
    """
    Host line number.
    Line number in source file (.py) related to what is currently executed.
    The line is in the file given by HFL (see below).
    """

    HFL: str
    """
    Host file.
    Source file (.py) of current executed instruction.
    """

    INS: str
    """ Mnemonic of the NetQASM instruction being executed."""

    OPR: List[str]
    """
    Operands (register, array-entries..).
    List of "op=val" strings
    """

    ANG: Optional[Dict[str, int]]
    """
    Angle represented as the fraction num/den.
    For non-rotation instructions, ANG is None.
    For rotation instructions ANG is a dictionary with 2 entries:
    'num' (an int) and 'den' (an int).
    """

    QID: List[int]
    """ Physical qubit IDs of qubits part of the current operation."""

    VID: List[int]
    """ Virtual qubit IDs of qubits part of the current operation."""

    OUT: Optional[int]
    """ Measurement outcome. Only set in case of a measurement instruction."""

    QGR: Optional[QubitGroups]
    """ Dictionary specifying groups of qubits across the network."""

    LOG: str
    """ Human-readable message."""


@dataclass
class NetworkLogEntry:
    WCT: str
    """ Wall clock time. Format is Python's `datetime.now()`."""

    SIT: int
    """ Time in NetSquid simulation, in nanoseconds."""

    TYP: Optional[EntanglementType]
    """
    Entanglement generation type(Measure Directly or Create and Keep).
    For the 'start' entanglement stage (see INS below), this value is None
    since at this stage the value cannot be determined yet.
    For the 'finish' stage, the correct value is filled in, however.
    """

    INS: EntanglementStage
    """ Entanglement generation stage(start or finish)."""

    BAS: Optional[List[int]]
    """
    Bases in which the two qubits(one on each end) were measured in .
    Only applies to the Measure Directly case. It is `None` otherwise.
    """

    MSR: List[int]
    """
    Measurement outcomes of the two qubits(one on each end).
    Only applies to the Measure Directly case. It is `None` otherwise.
    """

    NOD: List[str]
    """ Node names involved in this entanglement operation."""

    PTH: List[str]
    """
    Path of links used for entanglement generation.
    Links are identified using their names.
    """

    QID: List[int]
    """ Physical qubit IDs of qubits part of the current operation."""

    QGR: Optional[QubitGroups]
    """
    Dictionary specifying groups of qubits across the network,
    as they are after the current operation.
    """

    LOG: str
    """ Human-readable message."""


@dataclass
class ClassCommLogEntry:
    WCT: str
    """ Wall clock time. Format is Python's `datetime.now()`."""

    HLN: int
    """
    Host line number.
    Line number in source file (.py) related to what is currently executed.
    The line is in the file given by HFL(see below).
    """

    HFL: str
    """
    Host file.
    Source file (.py) of current executed instruction.
    """

    INS: str
    """ Classical operation being performed."""

    MSG: str
    """ Message that is sent or received."""

    SEN: str
    """ Name(role) of the sender."""

    REC: str
    """ Name(role) of the receiver."""

    SOD: str
    """ Socket ID(used internally)."""

    LOG: str
    """ Human-readable message."""


@dataclass
class AppLogEntry:
    WCT: str
    """ Wall clock time. Format is Python's `datetime.now()`."""

    HLN: int
    """
    Host line number.
    Line number in source file (.py) related to what is currently executed.
    The line is in the file given by HFL(see below).
    """

    # Source file (.py) of current executed instruction.
    """ Host file."""
    HFL: str

    LOG: str
    """ Human-readable message."""
