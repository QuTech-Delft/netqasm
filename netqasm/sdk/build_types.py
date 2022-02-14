from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Union

from netqasm.qlink_compat import LinkLayerOKTypeK, LinkLayerOKTypeM, LinkLayerOKTypeR
from netqasm.sdk.futures import Future, RegFuture
from netqasm.sdk.qubit import FutureQubit

if TYPE_CHECKING:
    from netqasm.sdk import connection
    from netqasm.sdk.builder import Builder

T_LinkLayerOkList = Union[
    List[LinkLayerOKTypeK], List[LinkLayerOKTypeM], List[LinkLayerOKTypeR]
]
T_PostRoutine = Callable[["Builder", Union[FutureQubit, List[Future]], RegFuture], None]

# Callback function type for conditional statements.
T_BranchRoutine = Callable[["connection.BaseNetQASMConnection"], None]

# Callback function type for loop statements.
T_LoopRoutine = Callable[["connection.BaseNetQASMConnection", RegFuture], None]

# Function that is called when the exit condition of a while-loop is False.
T_CleanupRoutine = Callable[["connection.BaseNetQASMConnection"], None]


class HardwareConfig:
    """Base class for hardware information used by the Builder."""

    @property
    def comm_qubit_count(self) -> int:
        """Number of communication qubits available."""
        raise NotImplementedError

    @property
    def mem_qubit_count(self) -> int:
        """Number of memory qubits available."""
        raise NotImplementedError

    @property
    def qubit_count(self) -> int:
        """Total number of qubits available."""
        return self.comm_qubit_count + self.mem_qubit_count


class NVHardwareConfig(HardwareConfig):
    """Hardware information for NV, where there is only one communication qubit."""

    def __init__(self, num_qubits: int) -> None:
        assert num_qubits > 0
        self._comm_qubit_count = 1
        self._mem_qubit_count = num_qubits - 1

    @property
    def comm_qubit_count(self) -> int:
        return self._comm_qubit_count

    @property
    def mem_qubit_count(self) -> int:
        return self._mem_qubit_count


class GenericHardwareConfig(HardwareConfig):
    """Hardware information for a generic platform where all qubits are
    communication qubits."""

    def __init__(self, num_qubits: int) -> None:
        assert num_qubits > 0
        self._comm_qubit_count = num_qubits
        self._mem_qubit_count = 0

    @property
    def comm_qubit_count(self) -> int:
        return self._comm_qubit_count

    @property
    def mem_qubit_count(self) -> int:
        return self._mem_qubit_count
