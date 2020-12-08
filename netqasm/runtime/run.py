import os
import sys
import importlib
from typing import List

from netqasm.logging.glob import (
    set_log_level,
    get_netqasm_logger,
)
from netqasm.util.yaml import load_yaml
from netqasm.sdk.config import LogConfig
from netqasm.lang.instr.flavour import NVFlavour, VanillaFlavour
from netqasm.runtime.settings import Formalism, Flavour
from netqasm.sdk.external import run_applications

from .app_config import AppConfig
from .process_logs import process_log, make_last_log
from netqasm.runtime import env

logger = get_netqasm_logger()


def get_network_config_path(app_dir):
    ext = '.yaml'
    file_path = os.path.join(app_dir, f'network{ext}')
    return file_path


def get_nv_config_path(app_dir):
    ext = '.yaml'
    file_path = os.path.join(app_dir, f'nv{ext}')
    return file_path


def load_network_config(network_config_file):
    if os.path.exists(network_config_file):
        return load_yaml(network_config_file)
    else:
        return None


def load_nv_config(nv_config_file):
    if os.path.exists(nv_config_file):
        return load_yaml(nv_config_file)
    else:
        return None


def setup_apps(
    app_dir=None,
    start_backend=True,
    lib_dirs=None,
    track_lines=True,
    app_config_dir=None,
    network_config_file=None,
    nv_config_file=None,
    roles_config_file=None,
    log_dir=None,
    log_level="WARNING",
    log_to_files=True,
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

    app_files = env.load_app_files(app_dir)
    if app_config_dir is None:
        app_config_dir = app_dir
    else:
        app_config_dir = os.path.expanduser(app_config_dir)

    if nv_config_file is None:
        nv_config_file = get_nv_config_path(app_dir)
    else:
        nv_config_file = os.path.expanduser(nv_config_file)

    if roles_config_file is None:
        roles_config_file = env.get_roles_config_path(app_dir)
    else:
        roles_config_file = os.path.expanduser(roles_config_file)

    log_config = LogConfig()

    if log_to_files:
        if log_dir is None:
            log_dir = env.get_log_dir(app_dir=app_dir)
        else:
            log_dir = os.path.expanduser(log_dir)

        timed_log_dir = env.get_timed_log_dir(log_dir=log_dir)

        if results_file is None:
            results_file = env.get_results_path(timed_log_dir)

        log_config.track_lines = track_lines
        log_config.log_subroutines_dir = timed_log_dir
        log_config.comm_log_dir = timed_log_dir
        log_config.app_dir = app_dir
        log_config.lib_dirs = lib_dirs
    else:
        log_dir = None
        timed_log_dir = None
        track_lines = False

    roles_cfg = env.load_roles_config(roles_config_file)

    if post_function_file is None:
        post_function_file = env.get_post_function_path(app_dir)

    # Load app functions and configs to run
    sys.path.append(app_dir)
    app_cfgs: List[AppConfig] = []
    for app_name, app_file in app_files.items():
        app_module = importlib.import_module(app_file[:-len('.py')])
        main_func = getattr(app_module, "main")

        inputs = env.load_app_config_file(app_config_dir, app_name)

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

    # Load post function if exists
    post_function = env.load_post_function(post_function_file)

    if start_backend:
        # simulation-specific configuration:
        if network_config_file is None:
            network_config_file = get_network_config_path(app_dir)
        else:
            network_config_file = os.path.expanduser(network_config_file)

        network_config = load_network_config(network_config_file)
        nv_config = load_nv_config(nv_config_file)

        if flavour is None:
            flavour = Flavour.VANILLA

        if flavour == Flavour.NV:
            flavour = NVFlavour()
        elif flavour == Flavour.VANILLA:
            flavour = VanillaFlavour()
        else:
            raise TypeError(f"Unsupported flavour: {flavour}")
    else:
        network_config = None
        formalism = None
        flavour = None

    run_applications(
        app_cfgs=app_cfgs,
        network_config=network_config,
        nv_config=nv_config,
        instr_log_dir=timed_log_dir,
        post_function=post_function,
        results_file=results_file,
        formalism=formalism,
        flavour=flavour
    )

    if log_to_files:
        if start_backend:  # full processing including instr logs from simulator
            process_log(log_dir=timed_log_dir)
        else:
            make_last_log(log_dir=timed_log_dir)
