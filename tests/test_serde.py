from netqasm.oop.vanilla import get_vanilla_map
from netqasm.oop.vanilla import CphaseInstruction

from netqasm.parsing import parse_binary_subroutine

def test_deserialize_subroutine():
    metadata = b"\x00\x00\x00\x00"
    cphase_gate = b"\x1F\x00\x00\x00\x00\x00\x00"
    raw = bytes(metadata + cphase_gate)
    print(raw)
    # vanilla = get_vanilla_map()
    # print(f"vanilla: {vanilla}")
    # deser = Deserializer(instr_map=vanilla)
    # subroutine = deser.deserialize_subroutine(raw)
    subroutine = parse_binary_subroutine(raw)
    print(subroutine)
    for instr in subroutine.commands:
        if isinstance(instr, CphaseInstruction):
            print(f"qreg0: {instr.qreg0}, qreg1: {instr.qreg1}")

    subroutine2 = parse_binary_subroutine(raw)
    print(subroutine2)

if __name__ == '__main__':
    test_deserialize_subroutine()