from netqasm.lang.encoding import COMMAND_BYTES, COMMANDS
from netqasm.lang.parsing import parse_text_subroutine


def test_command_length():
    for command_class in COMMANDS:
        length = len(bytes(command_class()))
        print(f"{command_class.__name__}: {len(bytes(command_class()))}")
        assert length == COMMAND_BYTES


def test_encode():
    subroutine = """
# NETQASM 0.0
# APPID 0

// Setup classical registers
set C1 1     // constant 1
set Q0 0     // qubit virtual address
set R0 0     // loop index
set R1 0     // counts 0s
set R2 0     // counts 1s
set R3 30000 // iterations

// Loop entry
LOOP:
beq R0 R3 EXIT

// Loop body
qalloc Q0
init Q0
x Q0
meas Q0 M0

// Count outcomes
bez M0 ZERO
// bnz M0 ZERO
add R2 R2 C1
jmp END
ZERO:
add R1 R1 C1
END:

qfree Q0
add R0 R0 C1

// Loop exit
jmp LOOP
EXIT:

ret_reg R1
ret_reg R2
"""

    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)

    print("\nInstructions:")
    for cstruct in subroutine.cstructs:
        print(f"{cstruct.__class__.__name__}: {bytes(cstruct)}")

    print("\nFull subroutine:")
    print(bytes(subroutine))


def test_encode_substitution():
    subroutine = """
# NETQASM 0.0
# APPID 0
# DEFINE ms @0

// Setup classical registers
set Q0 0
set R0 0  // loop variable
array(10) $ms

// Loop entry
LOOP:
beq R0 10 EXIT

// Loop body
qalloc Q0
init Q0
h Q0
meas Q0 M0

// Store to array
store M0 $ms[R0]

qfree Q0
add R0 R0 1

// Loop exit
jmp LOOP
EXIT:
"""

    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)

    print("\nInstructions:")
    for cstruct in subroutine.cstructs:
        print(f"{cstruct.__class__.__name__}: {bytes(cstruct)}")

    print("\nFull subroutine:")
    print(bytes(subroutine))


def test_encode_rotations():
    subroutine = """
# NETQASM 0.0
# APPID 0

set Q0 0
qalloc Q0
init Q0

// Perform rotations
rot_x Q0 1 1  // rotate by 1 * pi / 1 = pi
rot_x Q0 1 4  // rotate by 1 * pi / 4 = pi / 4
rot_y Q0 7 22  // rotate by 7 pi / 22

qfree Q0
"""

    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)

    print("\nInstructions:")
    for cstruct in subroutine.cstructs:
        print(f"{cstruct.__class__.__name__}: {bytes(cstruct)}")

    print("\nFull subroutine:")
    print(bytes(subroutine))


if __name__ == "__main__":
    test_encode()
    test_encode_substitution()
    test_encode_rotations()
