# Exports not-implemented function such that the DebugConnection can be used
from typing import List

from netqasm.runtime.app_config import AppConfig
from netqasm.runtime.settings import Formalism


def get_qubit_state(qubit, reduced_dm=True):
    return None


def run_applications(
    app_cfgs: List[AppConfig],
    post_function=None,
    instr_log_dir=None,
    network_config=None,
    results_file=None,
    formalism=Formalism.KET,
    flavour=None,
    use_app_config=True,  # whether to give app_config as argument to app's main()
):
    raise NotImplementedError("Running applications in debug mode not yet supported")
