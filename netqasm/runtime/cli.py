import json
import logging
import os
import click
import importlib
import requests
import netqasm
from netqasm.runtime.settings import Simulator, Formalism, Flavour, set_simulator, set_is_using_hardware
from netqasm.runtime.env import new_folder, init_folder, get_example_apps
from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk.config import LogConfig

EXAMPLE_APPS = get_example_apps()
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
QNE_FOLDER_PATH = os.path.expanduser('~') + '/.qne'

logger = get_netqasm_logger(sub_logger='cli')
logger.setLevel(logging.INFO)
logger.propagate = False
logger.handlers = []  # Clear all handlers
formatter = logging.Formatter('{message}', style='{')
sh = logging.StreamHandler()
sh.setFormatter(formatter)
logger.addHandler(sh)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('--verbose', '-v', is_flag=True, help='Print info and debug warnings to the console.')
def cli(verbose):
    """Command line interface for managing virtual python environments."""
    if verbose:
        logger.setLevel(logging.DEBUG)


@cli.group(context_settings=CONTEXT_SETTINGS)
def qne():
    """Command line interface for managing calls to the QNE apirouter."""


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

option_specify_host = click.option(
    "--host", type=str, default='qne-staging.quantum-inspire.com',
    help="Specify the IP and port of the api router."
)


#########
# login #
#########

@qne.command()
@option_specify_host
def login(host):
    """Generate an API token by logging in."""
    username = click.prompt('Username')
    password = click.prompt('Password', hide_input=True)
    try:
        return _login(username, password, host)
    except (ValueError, TypeError, AssertionError) as e:
        logger.error(e)


def _login(username: str, password: str, host: str = 'qne-staging.quantum-inspire.com'):
    # All the login logic except the user input.
    if not isinstance(username, str):
        raise TypeError("The username must be a string.")
    elif len(username) == 0:
        raise ValueError("The username cannot be empty.")
    if not isinstance(password, str):
        raise TypeError("The password must be a string.")
    elif len(password) == 0:
        raise ValueError("The password cannot be empty.")
    if not isinstance(host, str):
        raise TypeError("The host address must be a string.")
    logger.debug("Logging in.")
    jwt_req = requests.post(f'http://{host}/jwt/',
                            {'username': [username],
                             'password': [password]}
                            )
    if jwt_req.status_code == 401:
        raise ValueError("Invalid credentials supplied.")
    if jwt_req.status_code != 200:
        raise AssertionError(f'Received invalid response code ({jwt_req.status_code}) from the host.')
    try:
        jwt_token = jwt_req.json().get('access')
    except json.JSONDecodeError:
        raise AssertionError('Received invalid response from the host.')
    jwt_header = {'Authorization': f"JWT {jwt_token}"}
    # NOTE: Since we get a JWT token, do we need to be cautious the token will fail also?
    logger.debug("Generating new API token.")
    rm_req = requests.post(f'http://{host}/auth/token/destroy/',
                           data={'user': username},
                           headers=jwt_header)
    if rm_req.status_code != 204:
        raise AssertionError(f'Received invalid response code ({rm_req.status_code}) from the host.')
    api_req = requests.post(f'http://{host}/auth/token/create/',
                            data={'user': username},
                            headers=jwt_header)
    if api_req.status_code != 200:
        raise AssertionError(f'Received invalid response code ({api_req.status_code}) from the host.')
    api_token = api_req.json()['access']
    if not os.path.exists(QNE_FOLDER_PATH):
        os.mkdir(QNE_FOLDER_PATH)
    with open(f'{QNE_FOLDER_PATH}/api_token', 'w') as f:
        json.dump({host: (username, api_token)}, f)
    logger.info("Generated API token successfully.")


@qne.command()
def logout():
    try:
        host, username, token_header = _get_token_header()
    except FileNotFoundError:
        logger.info('User is not logged in.')
        return
    rm_req = requests.post(f'http://{host}/auth/token/destroy/',
                           data={'user': username},
                           headers=token_header)
    if rm_req.status_code == 401:
        logger.debug('API token was already invalid.')
    elif rm_req.status_code != 204:
        raise AssertionError(f'Received invalid response code ({rm_req.status_code}) from the host.')
    logger.debug('API token successfully removed from host.')
    os.remove(f'{QNE_FOLDER_PATH}/api_token')
    logger.info('User logged out successfully.')


def _get_token_header():
    # Extract username and token header from API token file.
    with open(f'{QNE_FOLDER_PATH}/api_token', 'r') as f:
        api_token = json.load(f)
    assert len(api_token) == 1
    host, (username, token_value) = list(api_token.items())[0]
    token_header = {'Authorization': f'TOKEN {token_value}'}
    return host, username, token_header


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
def simulate2(
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
    # setup_apps = importlib.import_module("netqasm.runtime.run").setup_apps
    # setup_apps(
    #     app_dir=app_dir,
    #     lib_dirs=lib_dirs,
    #     track_lines=track_lines,
    #     network_config_file=network_config_file,
    #     app_config_dir=app_config_dir,
    #     log_dir=log_dir,
    #     log_level=log_level.upper(),
    #     log_to_files=log_to_files,
    #     post_function_file=post_function_file,
    #     results_file=results_file,
    #     formalism=formalism,
    #     flavour=flavour
    # )

    # simulator = importlib.import_module("squidasm.run.simulate")
    simulate_application = importlib.import_module("netqasm.sdk.external").simulate_application
    app_instance = netqasm.runtime.application.app_instance_from_path(app_dir)
    network_cfg = netqasm.runtime.application.network_cfg_from_path(app_dir, network_config_file)
    log_cfg = LogConfig(log_dir=os.path.join(app_dir, "log"))
    simulate_application(app_instance, network_cfg=network_cfg, log_cfg=log_cfg)


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
