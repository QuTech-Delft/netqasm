import math
import os
import time
from argparse import ArgumentParser

import netsquid as ns
from squidasm.run.stack.config import LinkConfig, StackConfig, StackNetworkConfig

import sweep_teleport as sweep
from teleport import teleport


def get_config_file(name: str) -> str:
    if not name.endswith(".yaml"):
        name += ".yaml"
    return os.path.join(os.path.dirname(__file__), f"configs/{name}")


def command_sweep(args):
    cfg_file = get_config_file(args.config)
    num_times = args.num

    if args.param == "fidelity":
        sweep.sweep_fidelity(cfg_file=cfg_file, num_times=num_times)
    elif args.param == "rate":
        sweep.sweep_rate(cfg_file=cfg_file, num_times=num_times)
    elif args.param == "gate_noise":
        sweep.sweep_gate_noise(cfg_file=cfg_file, num_times=num_times)
    elif args.param == "gate_time":
        sweep.sweep_gate_time(cfg_file=cfg_file, num_times=num_times)
    elif args.param == "T2":
        sweep.sweep_t2(cfg_file=cfg_file, num_times=num_times)
    elif args.param == "latency":
        sweep.sweep_latency(cfg_file=cfg_file, num_times=num_times)


def command_computation(args):
    cfg_file = get_config_file(args.config)
    theta = args.theta * math.pi / 4
    phi = args.phi * math.pi / 4
    compile_version = args.compile_version
    log_level = args.log_level
    num = args.num

    cfg = StackNetworkConfig.from_file(cfg_file)

    teleport.do_teleportation(
        cfg=cfg,
        num_times=num,
        theta=theta,
        phi=phi,
        compile_version=compile_version,
        log_level=log_level,
    )


def add_input_args(parser) -> None:
    parser.add_argument("--theta", type=int, default=0)
    parser.add_argument("--phi", type=int, default=0)
    parser.add_argument("--compile-version", type=str, default="None")


def add_global_args(parser) -> None:
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help=(
            "Name of the config file. "
            "The config file should be in the netqasm_sim/configs directory."
        ),
    )
    parser.add_argument("--log-level", type=str, default="WARNING")


if __name__ == "__main__":
    parser = ArgumentParser(prog="Teleportation simulation")
    subparsers = parser.add_subparsers(dest="cmd")
    subparsers.required = True

    comp_parser = subparsers.add_parser("computation")
    comp_parser.set_defaults(func=command_computation)
    add_input_args(comp_parser)
    add_global_args(comp_parser)
    comp_parser.add_argument("--num", type=int, default=1)

    sweep_parser = subparsers.add_parser("sweep")
    sweep_parser.set_defaults(func=command_sweep)
    add_input_args(sweep_parser)
    add_global_args(sweep_parser)
    sweep_parser.add_argument(
        "--param",
        type=str,
        choices={"fidelity", "rate", "T2", "gate_noise", "gate_time", "latency"},
        required=True,
    )
    sweep_parser.add_argument("--num", type=int, default=1)

    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    start = time.perf_counter()

    args = parser.parse_args()
    args.func(args)

    print(f"finished in {round(time.perf_counter() - start, 2)} seconds")
