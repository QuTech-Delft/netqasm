import click
import netqasm
from netqasm.processor import FromStringProcessor
from netqasm.io_util import execute_subroutine
try:
    from squidasm.processor import FromStringNetSquidProcessor
except ModuleNotFoundError:
    FromStringNetSquidProcessor = None

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """Command line interface for managing virtual python environments."""
    pass


###########
# version #
###########

@cli.command()
def version():
    """
    Prints the version of manven.
    """
    print(netqasm.__version__)


###########
# execute #
###########

@cli.command()
@click.argument("netqasm-file", type=str)
@click.option("-p", "--processor", type=click.Choice(["debug", "netsquid"]), default="debug",
              help="Which processor to be used.\n"
                   "debug (default): simple debug processor which does not perform any quantum operations.\n"
                   "netsquid: use netsquid to simulate qubit operations "
                   "(for this the package 'squidasm' needs to be installed.\n"
              )
@click.option("-n", "--num_qubits", type=int, default=5,
              help="Number of qubits to be used in the processor.")
@click.option("-o", "--output-file", type=str, default=None,
              help="File to write output to, if not specified the name of "
                   "the netqasm file will be used with '.out' as extension.")
def execute(netqasm_file, processor, num_qubits, output_file):
    """
    Executes a given NetQASM file using a specified processor.
    """
    if processor == "debug":
        processor = FromStringProcessor(num_qubits=num_qubits)
    elif processor == "netsquid":
        if FromStringNetSquidProcessor is None:
            raise ModuleNotFoundError("To execute a subroutine using NetSquid the package "
                                      "'squidasm' needs to be installed")
        processor = FromStringNetSquidProcessor(num_qubits=num_qubits)
    else:
        raise ValueError("Unkown processor {processor}")
    execute_subroutine(processor, netqasm_file=netqasm_file, output_file=output_file)
