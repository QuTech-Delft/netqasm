import ctypes

from netqasm.subroutine import Subroutine, Command
from netqasm import encoding
from netqasm.instr2.core import InstrMap

INSTR_ID = ctypes.c_uint8


def serialize_subroutine(subroutine: Subroutine) -> bytes:
    pass

def serialize_command(command: Command) -> bytes:
    pass
