from typing import List
from concurrent.futures import ProcessPoolExecutor as Pool

from netqasm.logging.glob import get_netqasm_logger
from netqasm.util.yaml import dump_yaml
from netqasm.logging.output import save_all_struct_loggers
from netqasm.util.thread import as_completed

from .app_config import AppConfig

logger = get_netqasm_logger()


def run_applications(
    app_cfgs: List[AppConfig],
    post_function=None,
    instr_log_dir=None,
    network_config=None,  # not used
    results_file=None,
    formalism=None,  # not used
    flavour=None,  # not used
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
