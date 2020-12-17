import os
import click
import importlib

import netqasm
from netqasm.runtime.settings import Simulator, Formalism, Flavour, set_simulator, set_is_using_hardware
from netqasm.runtime.env import new_folder, init_folder, get_example_apps

EXAMPLE_APPS = get_example_apps()
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


option_quiet = click.option(
    "-q", "--quiet",
    is_flag=True,
    help="No output printed to stdout",
)

option_app_dir = click.option(
    "--app-dir", type=str, default=None,
    help="Path to app directory. "
         "Defaults to CWD."
)

option_lib_dirs = click.option(
    "--lib-dirs", type=str, default=None, multiple=True,
    help="Path to additional library directory."
)

option_track_lines = click.option("--track-lines/--no-track-lines", default=True)

option_app_config_dir = click.option(
    "--app-config-dir", type=str, default=None,
    help="Explicitly choose the app config directory, "
         "default is `app-folder`."
)

option_log_dir = click.option(
    "--log-dir", type=str, default=None,
    help="Explicitly choose the log directory, "
         "default is `app-folder/log`."
)

option_post_func_file = click.option(
    "--post-function-file", type=str, default=None,
    help="Explicitly choose the file defining the post function."
)

option_results_file = click.option(
    "--results-file", type=str, default=None,
    help="Explicitly choose the file where the results of a post function should be stored."
)

option_log_level = click.option(
    "--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]), default="WARNING",
    help="What log-level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL)."
         "Note, this affects logging to stderr, not logging instructions to file."
)

option_log_to_files = click.option(
    "--log-to-files", type=bool, default=True,
    help="Set to false to completely disable logging to files."
)


############
# simulate #
############

@cli.command()
@option_app_dir
@option_lib_dirs
@option_track_lines
@option_app_config_dir
@option_log_dir
@option_post_func_file
@option_results_file
@option_log_level
@option_log_to_files
@click.option("--network-config-file", type=str, default=None,
              help="Explicitly choose the network config file, "
                   "default is `app-folder/network.yaml`."
              )
@click.option("--simulator", type=click.Choice([sim.value for sim in Simulator]), default=None,
              help="Choose with simulator to use, "
                   "default uses what environment variable 'NETQASM_SIMULATOR' is set to, otherwise 'netsquid'"
              )
@click.option("--formalism", type=click.Choice([f.value for f in Formalism]), default=Formalism.KET.value,
              help="Choose which quantum state formalism is used by the simulator. Default is 'ket'."
              )
@click.option("--flavour", type=click.Choice(["vanilla", "nv"]), default="vanilla",
              help="Choose the NetQASM flavour that is used. Default is vanilla."
              )
def simulate(
    app_dir,
    lib_dirs,
    track_lines,
    network_config_file,
    app_config_dir,
    log_dir,
    log_level,
    log_to_files,
    post_function_file,
    results_file,
    simulator,
    formalism,
    flavour
):
    """
    Simulate an application on a simulated QNodeOS.
    """
    if simulator is None:
        simulator = os.environ.get("NETQASM_SIMULATOR", Simulator.NETSQUID.value)
    else:
        simulator = Simulator(simulator)
    formalism = Formalism(formalism)
    flavour = Flavour(flavour)
    set_simulator(simulator=simulator)
    # Import correct function after setting the simulator
    setup_apps = importlib.import_module("netqasm.runtime.run").setup_apps
    setup_apps(
        app_dir=app_dir,
        lib_dirs=lib_dirs,
        track_lines=track_lines,
        network_config_file=network_config_file,
        app_config_dir=app_config_dir,
        log_dir=log_dir,
        log_level=log_level.upper(),
        log_to_files=log_to_files,
        post_function_file=post_function_file,
        results_file=results_file,
        formalism=formalism,
        flavour=flavour
    )


##################
# Run on QNodeOS #
##################

@cli.command()
@option_app_dir
@option_lib_dirs
@option_track_lines
@option_app_config_dir
@option_log_dir
@option_results_file
@option_log_level
@option_log_to_files
def run(
    app_dir,
    lib_dirs,
    track_lines,
    app_config_dir,
    log_dir,
    log_level,
    log_to_files,
    results_file,
):
    """
    Execute an application on QNodeOS.
    """
    set_is_using_hardware(True)

    setup_apps = importlib.import_module("netqasm.runtime.run").setup_apps
    setup_apps(
        app_dir=app_dir,
        start_backend=False,
        lib_dirs=lib_dirs,
        track_lines=track_lines,
        app_config_dir=app_config_dir,
        log_dir=log_dir,
        log_to_files=log_to_files,
        log_level=log_level.upper(),
        results_file=results_file,
    )


#######
# new #
#######
@cli.command()
@click.argument(
    'path',
    type=click.Path(exists=False),
)
@click.option(
    "--template",
    type=click.Choice(EXAMPLE_APPS),
    default="teleport",
    help="Which pre-defined app to use when creating the template (default teleport)",
)
@option_quiet
def new(path, template, quiet):
    """
    Creates a new application at PATH
    """
    if os.path.exists(path):
        raise click.BadArgumentUsage(
            f"destination `{path}` already exists\n\n"
            "Use `netqasm init` to initialize the directory"
        )
    new_folder(path, template=template, quiet=quiet)


########
# init #
########
@cli.command()
@click.option(
    '-p', '--path',
    type=click.Path(exists=True),
    default='.',
    help='Destination to initialize, defaults to current working directory'
)
@option_quiet
def init(path, quiet):
    """
    Initializes an existing directory with missing config files.
    Does not overwrite any existing files.
    Looks for any files `app_*.py` and creates a simple network config file
    (network.yaml) containing nodes corresponding to the application files.

    By default the current directory is used.
    Another directory can be specified with the -p/--path flag.
    """
    init_folder(path, quiet=quiet)


if __name__ == '__main__':
    cli()
