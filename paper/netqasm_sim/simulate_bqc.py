import math
import os
import time
from argparse import ArgumentParser

import netsquid as ns
from squidasm.run.stack.config import LinkConfig, StackConfig, StackNetworkConfig

import sweep_bqc as sweep
from bqc import bqc


def get_config_file(name: str) -> str:
    if not name.endswith(".yaml"):
        name += ".yaml"
    return os.path.join(os.path.dirname(__file__), f"configs/{name}")


def command_trap(args):
    cfg_file = get_config_file(args.config)
    n = args.num
    theta1 = args.theta1 * math.pi / 4
    theta2 = args.theta2 * math.pi / 4
    dummy = args.dummy
    log_level = args.log_level

    bqc.n_trap_rounds(
        cfg_file=cfg_file,
        n=n,
        theta1=theta1,
        theta2=theta2,
        dummy=dummy,
        log_level=log_level,
    )


def command_sweep(args):
    cfg_file = get_config_file(args.config)
    num_times = args.num
    log_level = args.log_level

    if args.param == "fidelity":
        sweep.sweep_fidelity(
            cfg_file=cfg_file, num_times=num_times, log_level=log_level
        )
    elif args.param == "rate":
        sweep.sweep_rate(cfg_file=cfg_file, num_times=num_times, log_level=log_level)
    elif args.param == "gate_noise":
        sweep.sweep_gate_noise(
            cfg_file=cfg_file, num_times=num_times, log_level=log_level
        )
    elif args.param == "gate_noise_trap":
        sweep.sweep_gate_noise_error_rate(
            cfg_file=cfg_file, num_times=num_times, log_level=log_level
        )
    elif args.param == "gate_time":
        sweep.sweep_gate_time(
            cfg_file=cfg_file, num_times=num_times, log_level=log_level
        )
    elif args.param == "gate_time_trap":
        sweep.sweep_gate_time_error_rate(
            cfg_file=cfg_file, num_times=num_times, log_level=log_level
        )
    elif args.param == "T2":
        sweep.sweep_t2(cfg_file=cfg_file, num_times=num_times, log_level=log_level)
    elif args.param == "latency":
        sweep.sweep_latency(cfg_file=cfg_file, num_times=num_times, log_level=log_level)


def command_test(args):
    bqc.test_perfect_config()


def command_computation(args):
    cfg_file = get_config_file(args.config)
    alpha = args.alpha * math.pi / 4
    beta = args.beta * math.pi / 4
    theta1 = args.theta1 * math.pi / 4
    theta2 = args.theta2 * math.pi / 4
    r1 = args.r1
    r2 = args.r2
    log_level = args.log_level
    compile_version = args.compile_version
    num = args.num

    cfg = StackNetworkConfig.from_file(cfg_file)

    bqc.computation_round(
        cfg=cfg,
        num_times=num,
        alpha=alpha,
        beta=beta,
        theta1=theta1,
        theta2=theta2,
        r1=r1,
        r2=r2,
        log_level=log_level,
    )


def add_input_args(parser) -> None:
    parser.add_argument("--alpha", type=int, default=0)
    parser.add_argument("--beta", type=int, default=0)
    parser.add_argument("--theta1", type=int, default=0)
    parser.add_argument("--theta2", type=int, default=0)
    parser.add_argument("--r1", type=int, default=0)
    parser.add_argument("--r2", type=int, default=0)
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
    parser = ArgumentParser(prog="BQC simulation")
    subparsers = parser.add_subparsers(dest="cmd")
    subparsers.required = True

    comp_parser = subparsers.add_parser("computation")
    comp_parser.set_defaults(func=command_computation)
    add_input_args(comp_parser)
    add_global_args(comp_parser)
    comp_parser.add_argument("--num", type=int, default=1)

    trap_parser = subparsers.add_parser("trap")
    trap_parser.set_defaults(func=command_trap)
    add_input_args(trap_parser)
    add_global_args(trap_parser)
    trap_parser.add_argument("--dummy", type=int, default=1)
    trap_parser.add_argument("--num", type=int, default=1)

    sweep_parser = subparsers.add_parser("sweep")
    sweep_parser.set_defaults(func=command_sweep)
    add_input_args(sweep_parser)
    add_global_args(sweep_parser)
    sweep_parser.add_argument(
        "--param",
        type=str,
        choices={
            "fidelity",
            "rate",
            "T2",
            "gate_noise",
            "gate_noise_trap",
            "gate_time",
            "gate_time_trap",
            "latency",
        },
        required=True,
    )
    sweep_parser.add_argument("--num", type=int, default=1)

    comp_parser = subparsers.add_parser("test")
    comp_parser.set_defaults(func=command_test)

    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    start = time.perf_counter()

    args = parser.parse_args()
    args.func(args)

    print(f"finished in {round(time.perf_counter() - start, 2)} seconds")
