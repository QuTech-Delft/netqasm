import os

from netqasm.executioner import Executioner


NETQASM_EXT = ".nqasm"


# TODO
def execute_subroutine(executioner, netqasm_file, output_file=None):
    if not isinstance(executioner, Executioner):
        raise TypeError("executioner needs to be of class Executioner")
    if not netqasm_file.endswith(NETQASM_EXT):
        raise ValueError("{netqasm_file} is not a NetQASM file, should have '{NETQASM_EXT}' extension")
    if output_file is None:
        output_file = os.path.splitext(netqasm_file)[0] + ".out"
    with open(netqasm_file, 'r') as f:
        subroutine = f.read()

    executioner.put_subroutine(subroutine)
    executioner.execute_next_subroutine()
    output_data = executioner.output_data

    with open(output_file, 'w') as f:
        for data in output_data:
            f.write(f"{data.address}, {data.data}\n")
