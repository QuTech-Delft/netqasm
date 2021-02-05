import os
import shutil
import inspect
from runpy import run_path
from datetime import datetime
from itertools import combinations
from functools import wraps

from netqasm.logging.glob import get_netqasm_logger
from netqasm.util.yaml import load_yaml, dump_yaml
from netqasm.examples import apps
from netqasm.runtime.settings import set_simulator, Simulator

EXAMPLE_APPS_DIR = os.path.dirname(os.path.abspath(apps.__file__))

IGNORED_FILES = [
    "__init__.py",
    "__pycache__",
    "log",
    "cysignals_crash_logs",
]

logger = get_netqasm_logger()


def load_app_config_file(app_dir, app_name):
    ext = '.yaml'
    file_path = os.path.join(app_dir, f"{app_name}{ext}")
    if os.path.exists(file_path):
        config = load_yaml(file_path=file_path)
    else:
        config = None
    if config is None:
        return {}
    else:
        return config


def get_roles_config_path(app_dir):
    ext = '.yaml'
    file_path = os.path.join(app_dir, f'roles{ext}')
    return file_path


def load_roles_config(roles_config_file):
    if os.path.exists(roles_config_file):
        return load_yaml(roles_config_file)
    else:
        return None


def load_app_files(app_dir):
    app_tag = 'app_'
    ext = '.py'
    app_files = {}
    for entry in os.listdir(app_dir):
        if entry.startswith(app_tag) and entry.endswith('.py'):
            app_name = entry[len(app_tag):-len(ext)]
            app_files[app_name] = entry
    if len(app_files) == 0:
        raise ValueError(f"directory {app_dir} does not seem to be a application directory (no app_xxx.py files)")
    return app_files


def get_log_dir(app_dir):
    log_dir = os.path.join(app_dir, "log")
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    return log_dir


def get_timed_log_dir(log_dir):
    now = datetime.now().strftime('%Y%m%d-%H%M%S')
    timed_log_dir = os.path.join(log_dir, now)
    if not os.path.exists(timed_log_dir):
        os.mkdir(timed_log_dir)
    return timed_log_dir


def get_post_function_path(app_dir):
    return os.path.join(app_dir, 'post_function.py')


def load_post_function(post_function_file):
    if not os.path.exists(post_function_file):
        return None
    return run_path(post_function_file)['main']


def get_results_path(timed_log_dir):
    return os.path.join(timed_log_dir, 'results.yaml')


def new_folder(path, template="teleport", quiet=False):
    """Used by the CLI to create an app folder template

    Parameters
    ----------
    path : str
        Path to the directory
    template : str
        Which pre-defined app to use as template
    quiet : bool
        Whether to print info to stdout or not (default `False`)
    """
    assert not os.path.exists(path), "Destination already exists"
    os.mkdir(path)
    template_example_dir = os.path.join(EXAMPLE_APPS_DIR, template)
    for entry in os.listdir(template_example_dir):
        entry_path = os.path.join(template_example_dir, entry)
        if entry not in IGNORED_FILES:
            target_path = os.path.join(path, entry)
            if os.path.isfile(entry_path):
                shutil.copyfile(entry_path, target_path)
            elif os.path.isdir(entry_path):
                shutil.copytree(entry_path, target_path)
    if not quiet:
        print(f"Creating application template ({template} example) in `{path}`")


def init_folder(path, quiet=False):
    """Used by the CLI to initialize a directory by adding missing config files.

    Parameters
    ----------
    path : str
        Path to the directory
    quiet : bool
        Whether to print info to stdout or not (default `False`)
    """
    app_files = load_app_files(path)
    file_added = False

    # Create network file if non-existant
    network_file_path = os.path.join(path, "network.yaml")
    if not os.path.exists(network_file_path):
        _create_new_network_file(
            app_files=app_files,
            file_path=network_file_path,
            quiet=quiet,
        )
        file_added = True

    # Create roles file if non-existant
    roles_file_path = os.path.join(path, "roles.yaml")
    if not os.path.exists(roles_file_path):
        _create_new_roles_file(
            app_files=app_files,
            file_path=roles_file_path,
            quiet=quiet,
        )
        file_added = True

    # Create input files if non-existant
    for app_name, app_file in app_files.items():
        input_file_path = os.path.join(path, f"{app_name}.yaml")
        if not os.path.exists(input_file_path):
            app_file_path = os.path.join(path, app_file)
            _create_new_input_file(
                app_name=app_name,
                app_file_path=app_file_path,
                file_path=input_file_path,
                quiet=quiet,
            )
            file_added = True

    # Create README.md if non-existant
    readme_file_path = os.path.join(path, "README.md")
    if not os.path.exists(readme_file_path):
        _create_new_readme_file(
            file_path=readme_file_path,
        )
        file_added = True

    # Create results_config.json if non-existant
    results_config_file_path = os.path.join(path, "results_config.json")
    if not os.path.exists(results_config_file_path):
        _create_new_results_config_file(
            file_path=results_config_file_path,
        )
        file_added = True

    if file_added:
        if not quiet:
            if path == '.':
                path_str = 'current path'
            else:
                path_str = '`{path}`'
            print(f"Initialized {path_str} with missing config files")
    else:
        if not quiet:
            print("No files needed to be added")


def file_creation_notify(func):
    """Decorator for notification about file creation"""
    @wraps(func)
    def new_func(file_path, *args, quiet=False, **kwargs):
        func(file_path, *args, quiet=quiet, **kwargs)

        if not quiet:
            print(f"Created file `{file_path}`")
    return new_func


@file_creation_notify
def _create_new_network_file(file_path, app_files, quiet=False):
    # Create nodes
    nodes = []
    for app_name in app_files.keys():
        qubit = {
            "id": 0,
            "t1": 0,
            "t2": 0,
        }
        node = {
            "name": app_name,
            "gate_fidelity": 1.0,
            "qubits": [qubit],
        }
        nodes.append(node)

    # Create links
    links = []
    for i, (app_name1, app_name2) in enumerate(combinations(app_files.keys(), 2)):
        if app_name1 == app_name2:
            continue
        link = {
            "name": f"ch{i}",
            "node_name1": app_name1,
            "node_name2": app_name2,
            "noise_type": "Depolarise",
            "fidelity": 1.0,
        }
        links.append(link)

    # Create network
    network = {
        "nodes": nodes,
        "links": links,
    }

    dump_yaml(data=network, file_path=file_path)


@file_creation_notify
def _create_new_roles_file(file_path, app_files, quiet=False):
    # Create roles
    roles = {}
    for app_name in app_files.keys():
        roles[app_name] = app_name

    dump_yaml(data=roles, file_path=file_path)


@file_creation_notify
def _create_new_input_file(file_path, app_name, app_file_path, quiet=False):
    arguments = _find_argument_for_app_file(app_file_path)

    dump_yaml(data=arguments, file_path=file_path)


def _find_argument_for_app_file(app_file_path):
    set_simulator(Simulator.DEBUG)
    members = run_path(app_file_path)
    main = members.get("main")
    if main is None:
        raise RuntimeError(f"File `{app_file_path}` does not have a `main`-function")

    signature = inspect.signature(main)
    return {
        param.name: param.default
        for param in signature.parameters.values()
        if param.name != 'app_config'
    }


@file_creation_notify
def _create_new_readme_file(file_path, quiet=False):
    with open(file_path, 'w') as f:
        f.write(
            "# Application name\n"
            "Some description of the application.\n"
            "\n"
            "## Inputs\n"
            "Description of inputs.\n"
            "\n"
            "## Outputs\n"
            "Description of outputs.\n"
        )


@file_creation_notify
def _create_new_results_config_file(file_path, quiet=False):
    with open(file_path, 'w') as f:
        f.write(
            r"""[
    [
        {
            "output_type": "text",
            "title": "Results",
            "parameters": {
                "content": "Information about the results."
            }
        }
    ]
]"""
        )


def get_example_apps():
    return [app_name for app_name in os.listdir(EXAMPLE_APPS_DIR) if app_name not in IGNORED_FILES]
