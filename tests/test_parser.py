import pytest

from netqasm.parser import Parser, Subroutine, Command, Address, AddressMode, QubitAddress, Array
from netqasm.util import NetQASMInstrError, NetQASMSyntaxError


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


def test_simple():
    subroutine = """# NETQASM 0.0
# APPID 0
store @0 1
store *@0 1
store m 0
init q0
init q
array(4) ms
add m m 1
add ms[0] m 1
beq 0 0 EXIT
EXIT:
"""

    expected = Subroutine(
        netqasm_version="0.0",
        app_id=0,
        commands=[
            Command(instruction="store", args=[], operands=[
                Address(0, AddressMode.DIRECT),
                Address(1, AddressMode.IMMEDIATE),
            ]),
            Command(instruction="store", args=[], operands=[
                Address(0, AddressMode.INDIRECT),
                Address(1, AddressMode.IMMEDIATE),
            ]),
            Command(instruction="store", args=[], operands=[
                Address(1, AddressMode.DIRECT),
                Address(0, AddressMode.IMMEDIATE),
            ]),
            Command(instruction="init", args=[], operands=[
                QubitAddress(0),
            ]),
            Command(instruction="init", args=[], operands=[
                QubitAddress(1),
            ]),
            Command(instruction="array", args=[4], operands=[
                Address(2, AddressMode.DIRECT),
            ]),
            Command(instruction="add", args=[], operands=[
                Address(1, AddressMode.DIRECT),
                Address(1, AddressMode.DIRECT),
                Address(1, AddressMode.IMMEDIATE),
            ]),
            Command(instruction="add", args=[], operands=[
                Array(address=Address(2, AddressMode.DIRECT), index=Address(0, AddressMode.IMMEDIATE)),
                Address(1, AddressMode.DIRECT),
                Address(1, AddressMode.IMMEDIATE),
            ]),
            Command(instruction="beq", args=[], operands=[
                Address(0, AddressMode.IMMEDIATE),
                Address(0, AddressMode.IMMEDIATE),
                Address(9, AddressMode.IMMEDIATE),
            ]),
        ])

    parser = Parser(subroutine)
    assert parser.subroutine == expected


def test_teleport():
    subroutine = """
# NETQASM 0.0
# APPID 0
array(1) epr_address
store epr_address[0] 1
array(1) entinfo
qalloc q
h q
create_epr epr_address entinfo
wait entinfo
cnot q *epr_address[0]
h q
meas q m1
meas *epr_address[0] m2
"""

    parser = Parser(subroutine)
    print(parser)


if __name__ == "__main__":
    test_teleport()
