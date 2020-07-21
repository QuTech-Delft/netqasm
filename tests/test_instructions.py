from netqasm.encoding import Command
from netqasm.instructions.instr_enum import Instruction, COMMAND_STRUCTS


def test_all_commmands():
    for instr in Instruction:
        command = COMMAND_STRUCTS[instr]
        assert isinstance(command(), Command)
