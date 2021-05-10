"""Execution of application scripts without setting up a backend.

The `run_applications` function simply spawns a thread for each of the applications
given to it, and runs the Python script of each application.
The relevant quantum node controllers are expected to be setup elsewhere, e.g. as real
hardware that is connected to the machine that runs `run_applications`.
"""

from multiprocessing.pool import ThreadPool

from netqasm.logging.glob import get_netqasm_logger
from netqasm.logging.output import save_all_struct_loggers
from netqasm.util.thread import as_completed
from netqasm.util.yaml import dump_yaml

from .app_config import AppConfig
from .application import ApplicationInstance

logger = get_netqasm_logger()


def run_application(
    app_instance: ApplicationInstance,
    post_function=None,
    results_file=None,
    use_app_config=True,  # whether to give app_config as argument to app's main()
):
    programs = app_instance.app.programs

    with ThreadPool(len(programs) + 1) as executor:
        # Start the program threads
        program_futures = []
        for program in programs:
            inputs = app_instance.program_inputs[program.party]
            if use_app_config:
                app_cfg = AppConfig(
                    app_name=program.party,
                    node_name=app_instance.party_alloc[program.party],
                    main_func=program.entry,
                    log_config=app_instance.logging_cfg,
                    inputs=inputs,
                )
                inputs["app_config"] = app_cfg
            future = executor.apply_async(program.entry, kwds=inputs)
            program_futures.append(future)

        # Join the application threads and the backend
        program_names = [program.party for program in app_instance.app.programs]
        # NOTE: use app_<name> instead of prog_<name> for now for backward compatibility
        names = [f"app_{prog_name}" for prog_name in program_names]
        results = {}
        for future, name in as_completed(program_futures, names=names):
            results[name] = future.get()
        if results_file is not None:
            save_results(results=results, results_file=results_file)

    save_all_struct_loggers()


def save_results(results, results_file):
    dump_yaml(data=results, file_path=results_file)
