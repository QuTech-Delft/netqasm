import os
import sys
import importlib
from typing import List
from concurrent.futures import ProcessPoolExecutor as Pool
from time import sleep

from netqasm.logging import (
    set_log_level,
    get_netqasm_logger,
)
from netqasm.yaml_util import dump_yaml
from netqasm.sdk.config import LogConfig
from netqasm.run.process_logs import make_last_log
from netqasm.output import save_all_struct_loggers

from .app_config import AppConfig
from netqasm.run import env

logger = get_netqasm_logger()


def run_apps(
    app_dir=None,
    lib_dirs=None,
    track_lines=True,
    app_config_dir=None,
    roles_config_file=None,
    log_dir=None,
    log_level="WARNING",
    results_file=None,
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

    if roles_config_file is None:
        roles_config_file = env.get_roles_config_path(app_dir)
    else:
        roles_config_file = os.path.expanduser(roles_config_file)

    if log_dir is None:
        log_dir = env.get_log_dir(app_dir=app_dir)
    else:
        log_dir = os.path.expanduser(log_dir)

    timed_log_dir = env.get_timed_log_dir(log_dir=log_dir)

    if results_file is None:
        results_file = env.get_results_path(timed_log_dir)

    log_config = LogConfig()
    log_config.track_lines = track_lines
    log_config.log_subroutines_dir = timed_log_dir
    log_config.comm_log_dir = timed_log_dir
    log_config.app_dir = app_dir
    log_config.lib_dirs = lib_dirs

    roles_cfg = env.load_roles_config(roles_config_file)

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

    run_applications(
        app_cfgs=app_cfgs,
        instr_log_dir=timed_log_dir,
        results_file=results_file,
    )

    make_last_log(log_dir=timed_log_dir)


def as_completed(futures, names=None, sleep_time=0):
    futures = list(futures)
    if names is not None:
        names = list(names)
    while len(futures) > 0:
        for i, future in enumerate(futures):
            if future.done():
                futures.pop(i)
                if names is None:
                    yield future
                else:
                    name = names.pop(i)
                    yield future, name
        if sleep_time > 0:
            sleep(sleep_time)


def run_applications(
    app_cfgs: List[AppConfig],
    instr_log_dir=None,
    results_file=None,
    use_app_config=True,  # whether to give app_config as argument to app's main()
):
    """Executes functions containing application scripts"""
    app_names = [app_cfg.app_name for app_cfg in app_cfgs]

    with Pool(len(app_names)) as executor:
        # Start the application processes
        app_futures = []
        for app_cfg in app_cfgs:
            inputs = app_cfg.inputs
            if use_app_config:
                inputs['app_config'] = app_cfg
            future = executor.submit(app_cfg.main_func, **inputs)
            app_futures.append(future)

        # Join the application processes and the backend
        names = [f'app_{app_name}' for app_name in app_names]
        results = {}
        for future, name in as_completed(app_futures, names=names):
            results[name] = future.result()
        if results_file is not None:
            save_results(results=results, results_file=results_file)
    save_all_struct_loggers()


def save_results(results, results_file):
    dump_yaml(data=results, file_path=results_file)
