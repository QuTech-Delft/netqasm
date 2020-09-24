import click
import importlib

import netqasm
from netqasm.settings import Simulator, Formalism, Flavour, set_simulator

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
    Prints the version of netqasm.
    """
    print(netqasm.__version__)


###########
# simulate #
###########

@cli.command()
@click.option("--app-dir", type=str, default=None,
              help="Path to app directory. "
                   "Defaults to CWD."
              )
@click.option("--lib-dirs", type=str, default=None, multiple=True,
              help="Path to additional library directory."
              )
@click.option("--track-lines/--no-track-lines", default=True)
@click.option("--network-config-file", type=str, default=None,
              help="Explicitly choose the network config file, "
                   "default is `app-folder/network.yaml`."
              )
@click.option("--app-config-dir", type=str, default=None,
              help="Explicitly choose the app config directory, "
                   "default is `app-folder`."
              )
@click.option("--log-dir", type=str, default=None,
              help="Explicitly choose the log directory, "
                   "default is `app-folder/log`."
              )
@click.option("--post-function-file", type=str, default=None,
              help="Explicitly choose the file defining the post function."
              )
@click.option("--results-file", type=str, default=None,
              help="Explicitly choose the file where the results of a post function should be stored."
              )
@click.option("--simulator", type=click.Choice([sim.value for sim in Simulator]), default=Simulator.NETSQUID.value,
              help="Choose with simulator to use, "
                   "default 'netsquid'"
              )
@click.option("--formalism", type=click.Choice([f.value for f in Formalism]), default=Formalism.KET.value,
              help="Choose which quantum state formalism is used by the simulator. Default is 'ket'."
              )
@click.option("--flavour", type=click.Choice(["vanilla", "nv"]), default="vanilla",
              help="Choose the NetQASM flavour that is used. Default is vanilla."
              )
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]), default="WARNING",
              help="What log-level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL)."
                   "Note, this affects logging to stderr, not logging instructions to file."
              )
def simulate(
    app_dir,
    lib_dirs,
    track_lines,
    network_config_file,
    app_config_dir,
    log_dir,
    log_level,
    post_function_file,
    results_file,
    simulator,
    formalism,
    flavour
):
    """
    Executes a given NetQASM file using a specified executioner.
    """
    simulator = Simulator(simulator)
    formalism = Formalism(formalism)
    flavour = Flavour(flavour)
    set_simulator(simulator=simulator)
    # Import correct function after setting the simulator
    simulate_apps = importlib.import_module("netqasm.sdk.external").simulate_apps
    # simulate_apps = _get_simulate_apps_func(simulator=simulator)
    simulate_apps(
        app_dir=app_dir,
        lib_dirs=lib_dirs,
        track_lines=track_lines,
        network_config_file=network_config_file,
        app_config_dir=app_config_dir,
        log_dir=log_dir,
        log_level=log_level,
        post_function_file=post_function_file,
        results_file=results_file,
        formalism=formalism,
        flavour=flavour
    )


# def _get_simulate_apps_func(simulator):
#     if simulator is Simulator.NETSQUID:
#         try:
#             return importlib.import_module("squidasm.run.simulate").simulate_apps
#         except ModuleNotFoundError:
#             raise ModuleNotFoundError("To use the netsquid simulator you need squidasm installed")
#     elif simulator is Simulator.SIMULAQRON:
#         try:
#             return importlib.import_module("simulaqron.run.simulate").simulate_apps
#         except ModuleNotFoundError:
#             raise ModuleNotFoundError("To use the simulaqron simulator you need simulaqron installed")
#     else:
#         raise ValueError(f"Unknown simulator {simulator}")


if __name__ == '__main__':
    cli()
