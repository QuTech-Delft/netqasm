import inspect
import logging
import os
import runpy
import subprocess
import sys
from collections import namedtuple

from netqasm.logging.glob import set_log_level
from netqasm.runtime.settings import Simulator, get_simulator

# Used to specify to skip some apps in some cases
SkipIf = namedtuple("SkipIf", ["skip", "reason"])


skip_ifs = {
    "anonymous_transmission": SkipIf(
        get_simulator() == Simulator.SIMULAQRON,
        reason="Current broadcast channel in simulaqron cannot handle socket IDs",
    ),
    "link_layer_md": SkipIf(
        get_simulator() == Simulator.NETSQUID
        or get_simulator() == Simulator.SIMULAQRON,
        reason="Current simulators do not handle MD requests well.",
    ),
}


def _has_first_argument(function, argument):
    """Checks if a function takes a named argument as the first argument"""
    argnames = inspect.getfullargspec(function).args
    return argnames[0] == "no_output"


def main(external):
    set_log_level(logging.WARNING)
    path_to_here = os.path.dirname(os.path.abspath(__file__))

    if external:
        apps_path = os.path.join(path_to_here, "apps")
        apps = os.listdir(apps_path)
        for app in apps:
            app_path = os.path.join(apps_path, app)
            if not os.path.isdir(app_path) or app == "__pycache__":
                continue
            skip_if = skip_ifs.get(app)
            if skip_if is not None and skip_if.skip:
                print(f"Skipping example app {app_path} since {skip_if.reason}")
                continue
            print(f"Running example app {app_path} using simulator {get_simulator()}")
            result = subprocess.run(
                ["netqasm", "simulate", "--app-dir", app_path],
                stdout=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Example {app} failed!")
    else:
        for root, _folders, files in os.walk(path_to_here):
            for filename in files:
                if filename.startswith("example") and filename.endswith(".py"):
                    filepath = os.path.join(root, filename)
                    members = runpy.run_path(filepath)
                    if "main" in members:
                        print(f"Running example {filepath}")
                        result = subprocess.run(
                            ["python3", filepath],
                            stdout=subprocess.DEVNULL,
                        )
                        if result.returncode != 0:
                            raise RuntimeError(f"Example {filepath} failed!")
                    else:
                        print(f"The example {filepath} does not have a main function")
    print("All examples work!")


if __name__ == "__main__":
    external = "--external" in sys.argv
    main(external=external)
