# Exports not-implemented function such that the DebugConnection can be used

from .application import ApplicationInstance


def get_qubit_state(qubit, reduced_dm=True):
    return None


def run_application(
    app_instance: ApplicationInstance,
    post_function=None,
    instr_log_dir=None,
    results_file=None,
    use_app_config=True,  # whether to give app_config as argument to app's main()
):
    raise NotImplementedError("Running applications in debug mode not yet supported")
