import click
import netqasm
from netqasm.io_util import execute_subroutine

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
@click.option("-b", "--backend", type=click.Choice(["debug", "netsquid"]), default="debug",
              help="Which backend to be used.\n"
                   "debug (default): simple debug executioner which does not perform any quantum operations.\n"
                   "netsquid: use netsquid to simulate qubit operations "
                   "(for this the package 'squidasm' needs to be installed.\n"
              )
@click.option("-n", "--num_qubits", type=int, default=5,
              help="Number of qubits to be used in the executioner.")
@click.option("-o", "--output-file", type=str, default=None,
              help="File to write output to, if not specified the name of "
                   "the netqasm file will be used with '.out' as extension.")
@click.option("--flavour", type=click.Choice(["vanilla", "nv"]), default="vanilla",
              help="Choose the NetQASM flavour that is used. Default is vanilla."
              )
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]), default="WARNING",
              help="What log-level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL)."
                   "Note, this affects logging to stderr, not logging instructions to file."
              )
def execute(netqasm_file, backend, num_qubits, output_file, flavour, log_level):
    """
    Executes a given NetQASM file using a specified executioner.
    """
    execute_subroutine(
        backend,
        num_qubits,
        netqasm_file=netqasm_file,
        output_file=output_file,
        flavour=flavour,
        log_level=log_level
    )
