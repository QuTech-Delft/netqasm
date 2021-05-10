from typing import Union

from netqasm.lang.ir import BranchLabel, ICmd

T_Cmd = Union[ICmd, BranchLabel]
