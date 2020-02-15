import os

from netqasm.processor import FromStringProcessor


NETQASM_EXT = ".nqasm"


def execute_subroutine(processor, netqasm_file, output_file=None):
    if not isinstance(processor, FromStringProcessor):
        raise TypeError("processor needs to be of class FromStringProcessor")
    if not netqasm_file.endswith(NETQASM_EXT):
        raise ValueError("{netqasm_file} is not a NetQASM file, should have '{NETQASM_EXT}' extension")
    if output_file is None:
        output_file = os.path.splitext(netqasm_file)[0] + ".out"
    with open(netqasm_file, 'r') as f:
        subroutine = f.read()

    processor.put_subroutine(subroutine)
    processor.execute_next_subroutine()
    output_data = processor.output_data

    with open(output_file, 'w') as f:
        for data in output_data:
            f.write(f"{data.address}, {data.data}\n")
