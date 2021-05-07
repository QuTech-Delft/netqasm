"""NetQASM application definitions.

NetQASM applications are modeled as pieces of Python code together with metadata.
Generally, applications are multi-node, i.e. they consist of separate chunks of code
that are run by separate nodes.

To distinguish the notion of a multiple-node-spanning collection of code and single-node
piece of code, the following terminology is used:

- A *Program* is code that runs on a single node. It is a Python script whose code is
  executed on (1) the Host component of that node and (2) the quantum node controller
  of that node.
- An *Application* is a collection of Programs (specifically, one Program per node).

"""

import importlib
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from netqasm.runtime import env
from netqasm.runtime.interface.config import NetworkConfig, parse_network_config
from netqasm.sdk.config import LogConfig
from netqasm.util.yaml import load_yaml


@dataclass
class Program:
    """Program running on one specific node. Part of a multi-node application.

    :param party: name of the party or role in the multi-node application (protocol).
        E.g. a blind computation application may have two parties: "client" and
        "server". Note that the party name is not necessarily the name of the node this
        Program runs on (which may be, e.g. "Delft").
    :param entry: entry point of the Program. This must be Python function.
    :param args: list of argument names that the entry point expects
    :param results: list of result names that are keys in the dictionary that this
        Program returns on completion
    """

    party: str
    entry: Callable
    args: List[str]
    results: List[str]


@dataclass
class AppMetadata:
    """Metadata about a NetQASM application.

    :param name: name of the application
    :param description: description of the application
    :param authors: list of authors of the application
    :param version: application version
    """

    name: str
    description: str
    authors: List[str]
    version: str


@dataclass
class Application:
    """Static NetQASM application (or protocol) information.

    :param programs: list of programs for each of the parties that are involved
        in this application (or protocol).
    :param metadata: application metadata
    """

    programs: List[Program]
    metadata: Optional[AppMetadata]


@dataclass
class ApplicationInstance:
    """Instantiation of a NetQASM application with concrete input values and
        configuration of the underlying network.

    :param app: static application info
    :param program_inputs: program input values for each of the application's programs
    :param network: configuration for a simulated network
    :param party_alloc: mapping of application parties to nodes in the network
    :param logging_cfg: logging configuration
    """

    app: Application
    program_inputs: Dict[str, Dict[str, Any]]
    network: Optional[NetworkConfig]
    party_alloc: Dict[str, str]
    logging_cfg: Optional[LogConfig]


@dataclass
class ApplicationOutput:
    """Results of a finished run of an ApplicationInstance. Should be subclassed."""

    pass


def load_yaml_file(path: str) -> Any:
    if not os.path.exists(path):
        raise ValueError(f"Could not read file {path} since it does not exist.")
    return load_yaml(path)


def app_instance_from_path(app_dir: str = None) -> ApplicationInstance:
    """
    Create an Application Instance based on files in a directory.
    Uses the current working directory if `app_dir` is None.
    """
    app_dir = os.path.abspath(".") if app_dir is None else os.path.expanduser(app_dir)
    sys.path.append(app_dir)
    program_files = env.load_app_files(app_dir)

    programs = []
    program_inputs = {}
    for party, prog_file in program_files.items():
        prog_module = importlib.import_module(prog_file[: -len(".py")])
        main_func = getattr(prog_module, "main")
        prog = Program(party=party, entry=main_func, args=[], results=[])
        programs += [prog]
        prog_inputs = env.load_app_config_file(app_dir, party)
        program_inputs[party] = prog_inputs

    roles_cfg_path = (
        os.path.abspath(".") if app_dir is None else os.path.join(app_dir, "roles.yaml")
    )
    party_alloc = env.load_roles_config(roles_cfg_path)
    party_alloc = (
        {prog.party: prog.party for prog in programs}
        if party_alloc is None
        else party_alloc
    )

    app = Application(programs=programs, metadata=None)
    app_instance = ApplicationInstance(
        app=app,
        program_inputs=program_inputs,
        network=None,
        party_alloc=party_alloc,
        logging_cfg=None,
    )

    return app_instance


def default_app_instance(programs: List[Tuple[str, Callable]]) -> ApplicationInstance:
    """
    Create an Application Instance with programs that take no arguments.
    """
    program_objects = [
        Program(party=party, entry=entry, args=[], results=[])
        for (party, entry) in programs
    ]
    app = Application(programs=program_objects, metadata=None)
    app_instance = ApplicationInstance(
        app=app,
        program_inputs={party: {} for (party, _) in programs},
        network=None,
        party_alloc={party: party for (party, _) in programs},
        logging_cfg=None,
    )
    return app_instance


def network_cfg_from_path(
    app_dir: str = None, network_config_file: str = None
) -> Optional[NetworkConfig]:
    if network_config_file is None:
        network_config_file = "network.yaml"
    if app_dir is not None:
        network_config_file = os.path.join(app_dir, network_config_file)

    if not os.path.exists(network_config_file):
        return None
    else:
        yaml_dict = load_yaml_file(network_config_file)
        network_cfg = parse_network_config(yaml_dict)
        return network_cfg


def post_function_from_path(
    app_dir: str = None, post_function_file: str = None
) -> Optional[Callable]:
    if post_function_file is None:
        post_function_file = "post_function.yaml"
    if app_dir is not None:
        post_function_file = os.path.join(app_dir, post_function_file)

    if not os.path.exists(post_function_file):
        return None
    else:
        module = importlib.import_module(post_function_file)
        main_func = getattr(module, "main")
        return main_func  # type: ignore
