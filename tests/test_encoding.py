from netqasm.parsing import parse_subroutine


def test_encode():
    subroutine = """
# NETQASM 0.0
# APPID 0
# DEFINE ms @0

// Setup classical registers
set Q0 0
lea R1 ms!
array(10) R1
set R0 0

// Loop entry
LOOP:
beq R0 10 EXIT

// Loop body
qalloc Q0
init Q0
h Q0
meas Q0 M0

// Store to array
store M0 ms![R0]

qfree Q0
addm R0 R0 1

// Loop exit
beq 0 0 LOOP
EXIT:
"""

    subroutine = parse_subroutine(subroutine)

    print("\nInstructions:")
    for cstruct in subroutine.cstructs:
        print(f"{cstruct.__class__.__name__}: {bytes(cstruct)}")
   
    print("\nFull subroutine:")
    print(bytes(subroutine))


if __name__ == '__main__':
    test_encode()
