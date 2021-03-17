import os
import pickle
import shutil

from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.util.yaml import dump_yaml, load_yaml

_LAST_LOG = "LAST"


def process_log(log_dir):
    # Add host line numbers to logs
    _add_hln_to_logs(log_dir)
    _create_app_instr_logs(log_dir)
    make_last_log(log_dir)


def make_last_log(log_dir):
    # Make this the last log
    base_log_dir, _log_dir_name = os.path.split(log_dir)
    last_log_dir = os.path.join(base_log_dir, _LAST_LOG)
    if os.path.exists(last_log_dir):
        shutil.rmtree(last_log_dir)
    shutil.copytree(log_dir, last_log_dir)


def _add_hln_to_logs(log_dir):
    file_end = "_instrs.yaml"
    for entry in os.listdir(log_dir):
        if entry.endswith(file_end):
            node_name = entry[: -len(file_end)]
            output_file_path = os.path.join(log_dir, entry)
            subroutines_file_path = os.path.join(
                log_dir, f"subroutines_{node_name}.pkl"
            )
            _add_hln_to_log(
                output_file_path=output_file_path,
                subroutines_file_path=subroutines_file_path,
            )


def _add_hln_to_log(output_file_path, subroutines_file_path):
    if not os.path.exists(subroutines_file_path):
        return

    # Read subroutines and log file
    with open(subroutines_file_path, "rb") as f:
        subroutines = pickle.load(f)
    data = load_yaml(output_file_path)

    # Update entries
    for entry in data:
        _add_hln_to_log_entry(subroutines, entry)

    # Write updated log file
    dump_yaml(data, output_file_path)


def _add_hln_to_log_entry(subroutines, entry):
    prc = entry["PRC"]
    sid = entry["SID"]
    subroutine = subroutines[sid]
    hostline = subroutine.commands[prc].lineno
    entry["HLN"] = hostline.lineno
    entry["HFL"] = hostline.filename


def _create_app_instr_logs(log_dir):
    file_end = "_instrs.yaml"

    app_names = BaseNetQASMConnection.get_app_names()

    for entry in os.listdir(log_dir):
        if entry.endswith(file_end):
            node_name = entry[: -len(file_end)]

            if node_name not in app_names.keys():
                raise ValueError(
                    f"Node {node_name} has logged instructions, but no app ID is known to have run on this node."
                )

            if len(app_names[node_name]) > 1:
                raise ValueError(
                    "Logging does not currently support multiple apps per node."
                )

            app_name = list(app_names[node_name].values())[0]

            node_instr_log_file = os.path.join(log_dir, entry)
            app_instr_log_file = os.path.join(log_dir, f"{app_name}_instrs.yaml")

            # TODO
            # Create an {app_name}_instrs.yaml file for each app_id found in {node_name}_instrs.yaml
            # Currently, it expects all app IDs to be the same, so we can just rename the file

            os.rename(node_instr_log_file, app_instr_log_file)
