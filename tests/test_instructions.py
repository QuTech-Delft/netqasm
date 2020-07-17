from netqasm.encoding import Command
from netqasm.instructions import Instruction, COMMAND_STRUCTS


def test_all_commmands():
    for instr in Instruction:
        command = COMMAND_STRUCTS[instr]
        print(type(command))
        assert isinstance(command(), Command)

if __name__ == '__main__':
    test_all_commmands()