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
T_BranchRoutine = Callable[["connection.BaseNetQASMConnection"], None]
T_LoopRoutine = Callable[["connection.BaseNetQASMConnection"], None]
