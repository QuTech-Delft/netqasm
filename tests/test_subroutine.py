from netqasm.lang.encoding import RegisterName
from netqasm.lang.instr.vanilla import RotXInstruction, RotZInstruction
from netqasm.lang.ir import GenericInstr, ICmd, ProtoSubroutine
from netqasm.lang.operand import Register, Template
from netqasm.lang.parsing import parse_text_subroutine
from netqasm.lang.parsing.text import parse_text_protosubroutine
from netqasm.lang.subroutine import Subroutine
from netqasm.lang.version import NETQASM_VERSION


def test_protosubroutine_instantiation():
    commands = [
        ICmd(
            instruction=GenericInstr.ROT_X,
            operands=[
                Register(RegisterName.R, 0),
                Template("rot_num"),
                Template("rot_denom"),
            ],
        )
    ]
    arguments = ["rot_num", "rot_denom"]
    protosubrt = ProtoSubroutine(commands, arguments)
    print(protosubrt)

    protosubrt.instantiate(app_id=1, arguments={"rot_num": 3, "rot_denom": 1})
    print(protosubrt)


def test_subroutine_instantiation():
    instructions = [
        RotXInstruction(
            reg=Register(name=RegisterName.R, index=0),
            imm0=Template("rot_num"),
            imm1=Template("rot_denom"),
        ),
        RotXInstruction(
            reg=Register(name=RegisterName.R, index=0),
            imm0=Template("rot_num"),
            imm1=Template("rot_denom"),
        ),
    ]
    arguments = ["rot_num", "rot_denom"]
    subrt = Subroutine(instructions, arguments)
    print(subrt)

    subrt.instantiate(app_id=1, arguments={"rot_num": 3, "rot_denom": 1})
    print(subrt)


def test_protosubroutine_parsing():
    subroutine = """
rot_z R0 {num} {denom}
"""

    commands = [
        ICmd(
            instruction=GenericInstr.ROT_Z,
            operands=[
                Register(RegisterName.R, 0),
                Template("num"),
                Template("denom"),
            ],
        )
    ]
    arguments = ["num", "denom"]
    expected = ProtoSubroutine(commands, arguments)
    print(expected)

    protosubrt = parse_text_protosubroutine(subroutine)
    print(protosubrt)

    for cmd1, cmd2 in zip(protosubrt.commands, expected.commands):
        assert cmd1 == cmd2
    for arg1, arg2 in zip(protosubrt.arguments, expected.arguments):
        assert arg1 == arg2


def test_subroutine_parsing():
    subroutine = """
rot_z R0 {num} {denom}
"""

    instructions = [
        RotZInstruction(
            reg=Register(name=RegisterName.R, index=0),
            imm0=Template("num"),
            imm1=Template("denom"),
        ),
    ]
    arguments = ["num", "denom"]
    expected = Subroutine(instructions, arguments)

    subrt = parse_text_subroutine(subroutine)
    print(subrt)

    for instr1, instr2 in zip(subrt.instructions, expected.instructions):
        assert instr1 == instr2
    for arg1, arg2 in zip(subrt.arguments, expected.arguments):
        assert arg1 == arg2


def test_parse_and_instantiate():
    template = """
rot_z R0 {num} {denom}
"""

    expected_text = f"""
# NETQASM {NETQASM_VERSION[0]}.{NETQASM_VERSION[1]}
# APPID 0
rot_z R0 3 1
"""

    template: Subroutine = parse_text_subroutine(template)
    print(f"template: {template}")

    expected: Subroutine = parse_text_subroutine(expected_text)
    print(f"expected: {expected}")

    template.instantiate(app_id=0, arguments={"num": 3, "denom": 1})
    print(f"subroutine: {template}")

    assert template.instructions == expected.instructions


if __name__ == "__main__":
    test_protosubroutine_instantiation()
    test_subroutine_instantiation()
    test_subroutine_parsing()
    test_protosubroutine_parsing()
    test_parse_and_instantiate()
