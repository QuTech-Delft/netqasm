import os
import sys
import shutil
import pickle
import importlib
from runpy import run_path
from datetime import datetime
from typing import List

from netqasm.logging import (
    set_log_level,
    get_netqasm_logger,
)
from netqasm.yaml_util import load_yaml, dump_yaml
from netqasm.output import InstrField
from netqasm.sdk.config import LogConfig
from netqasm.instructions.flavour import NVFlavour, VanillaFlavour
from netqasm.settings import Formalism, Flavour
from netqasm.sdk.external import run_applications

from .app_config import AppConfig

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


def get_network_config_path(app_dir):
    ext = '.yaml'
    file_path = os.path.join(app_dir, f'network{ext}')
    return file_path


def load_network_config(network_config_file):
    if os.path.exists(network_config_file):
        return load_yaml(network_config_file)
    else:
        return None


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


_LAST_LOG = 'LAST'


def process_log(log_dir):
    # Add host line numbers to logs
    _add_hln_to_logs(log_dir)

    # Make this the last log
    base_log_dir, log_dir_name = os.path.split(log_dir)
    last_log_dir = os.path.join(base_log_dir, _LAST_LOG)
    if os.path.exists(last_log_dir):
        shutil.rmtree(last_log_dir)
    shutil.copytree(log_dir, last_log_dir)


def _add_hln_to_logs(log_dir):
    file_end = '_instrs.yaml'
    for entry in os.listdir(log_dir):
        if entry.endswith(file_end):
            node_name = entry[:-len(file_end)]
            output_file_path = os.path.join(log_dir, entry)
            subroutines_file_path = os.path.join(log_dir, f"subroutines_{node_name}.pkl")
            _add_hln_to_log(
                output_file_path=output_file_path,
                subroutines_file_path=subroutines_file_path,
            )


def _add_hln_to_log(output_file_path, subroutines_file_path):
    if not os.path.exists(subroutines_file_path):
        return

    # Read subroutines and log file
    with open(subroutines_file_path, 'rb') as f:
        subroutines = pickle.load(f)
    data = load_yaml(output_file_path)

    # Update entries
    for entry in data:
        _add_hln_to_log_entry(subroutines, entry)

    # Write updated log file
    dump_yaml(data, output_file_path)


def _add_hln_to_log_entry(subroutines, entry):
    prc = entry[InstrField.PRC.value]
    sid = entry[InstrField.SID.value]
    subroutine = subroutines[sid]
    hostline = subroutine.commands[prc].lineno
    entry[InstrField.HLN.value] = hostline.lineno
    entry[InstrField.HFL.value] = hostline.filename


def get_post_function_path(app_dir):
    return os.path.join(app_dir, 'post_function.py')


def load_post_function(post_function_file):
    if not os.path.exists(post_function_file):
        return None
    return run_path(post_function_file)['main']


def get_results_path(timed_log_dir):
    return os.path.join(timed_log_dir, 'results.yaml')


def simulate_apps(
    app_dir=None,
    lib_dirs=None,
    track_lines=True,
    app_config_dir=None,
    network_config_file=None,
    roles_config_file=None,
    log_dir=None,
    log_level="WARNING",
    post_function_file=None,
    results_file=None,
    formalism=Formalism.KET,
    flavour=None
):

    set_log_level(log_level)

    # Setup paths to directories
    if app_dir is None:
        app_dir = os.path.abspath('.')
    else:
        app_dir = os.path.expanduser(app_dir)

    if lib_dirs is None:
        lib_dirs = []
    # Add lib_dirs and app_dir to path so scripts can be loaded
    for lib_dir in lib_dirs:
        sys.path.append(lib_dir)

    sys.path.append(app_dir)

    app_files = load_app_files(app_dir)
    if app_config_dir is None:
        app_config_dir = app_dir
    else:
        app_config_dir = os.path.expanduser(app_config_dir)

    if network_config_file is None:
        network_config_file = get_network_config_path(app_dir)
    else:
        network_config_file = os.path.expanduser(network_config_file)

    if roles_config_file is None:
        roles_config_file = get_roles_config_path(app_dir)
    else:
        roles_config_file = os.path.expanduser(roles_config_file)

    if log_dir is None:
        log_dir = get_log_dir(app_dir=app_dir)
    else:
        log_dir = os.path.expanduser(log_dir)

    timed_log_dir = get_timed_log_dir(log_dir=log_dir)

    if post_function_file is None:
        post_function_file = get_post_function_path(app_dir)
    if results_file is None:
        results_file = get_results_path(timed_log_dir)

    log_config = LogConfig()
    log_config.track_lines = track_lines
    log_config.log_subroutines_dir = timed_log_dir
    log_config.comm_log_dir = timed_log_dir
    log_config.app_dir = app_dir
    log_config.lib_dirs = lib_dirs

    roles_cfg = load_roles_config(roles_config_file)

    # Load app functions and configs to run
    sys.path.append(app_dir)
    app_cfgs: List[AppConfig] = []
    for app_name, app_file in app_files.items():
        app_module = importlib.import_module(app_file[:-len('.py')])
        main_func = getattr(app_module, "main")

        inputs = load_app_config_file(app_config_dir, app_name)

        if roles_cfg is not None:
            node_name = roles_cfg.get(app_name)
        else:
            node_name = app_name

        app_config = AppConfig(
            app_name=app_name,
            node_name=node_name,
            main_func=main_func,
            log_config=log_config,
            inputs=inputs
        )

        app_cfgs += [app_config]

    network_config = load_network_config(network_config_file)

    # Load post function if exists
    post_function = load_post_function(post_function_file)

    if flavour is None:
        flavour = Flavour.VANILLA

    if flavour == Flavour.NV:
        flavour = NVFlavour()
    elif flavour == Flavour.VANILLA:
        flavour = VanillaFlavour()
    else:
        raise TypeError(f"Unsupported flavour: {flavour}")

    run_applications(
        app_cfgs=app_cfgs,
        network_config=network_config,
        instr_log_dir=timed_log_dir,
        post_function=post_function,
        results_file=results_file,
        formalism=formalism,
        flavour=flavour
    )

    process_log(log_dir=timed_log_dir)
