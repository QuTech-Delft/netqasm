import pytest

from netqasm.parser import Parser
from netqasm.util import NetQASMInstrError, NetQASMSyntaxError


def test_split_preamble():
    subroutine = """
# NETQASM 1.0
# APPID 0
# DEFINE op h
# DEFINE q @0
creg(1) m
qreg(1) q!
init q!
op! q! // this is a comment
meas q! m
beq m[0] 0 EXIT
x q!
EXIT:
// this is also a comment
"""

    nqparser = Parser(subroutine)
    print(nqparser)


@pytest.mark.parametrize("subroutine, error", [
    ("# WRONG", NetQASMInstrError),  # Wrong keyword
    ("# APPID 0\nH 0\n#APPID 0", NetQASMSyntaxError),  # Preamble after body
    ("# DEFINE args {0, 0", NetQASMSyntaxError),  # No end-bracket
    ("# NETQASM", NetQASMSyntaxError),  # No argument
    ("# NETQASM 1 2", NetQASMSyntaxError),  # Two arguments
    ("# APPID", NetQASMSyntaxError),  # No argument
    ("# APPID 1 2", NetQASMSyntaxError),  # Two arguments
    ("# DEFINE args", NetQASMSyntaxError),  # One arguments
    ("# DEFINE args 0 0", NetQASMSyntaxError),  # Three arguments
    ("# DEFINE 1args 0", NetQASMInstrError),  # Not a valid macro key
    ("# DEFINE args 0\n# DEFINE args 1", NetQASMInstrError),  # Not unique macro keys
])
def test_faulty_preamble(subroutine, error):
    with pytest.raises(error):
        Parser(subroutine)
