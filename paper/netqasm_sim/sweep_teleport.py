from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Tuple

import numpy as np
from squidasm.run.stack.config import StackNetworkConfig

from teleport import teleport

PI = math.pi
PI_OVER_2 = math.pi / 2
PI_OVER_4 = math.pi / 2
THREE_PI_OVER_4 = math.pi / 2

# COMPILE_VERSIONS = ["None"]
COMPILE_VERSIONS = ["meas_epr_first", "meas_epr_last"]


def dump_data(data: Any, filename: str) -> None:
    output_dir = os.path.join(os.path.dirname(__file__), "sweep_data_teleport")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        json.dump(data, f)
    print(f"data written to {path}")


def get_avg_fidelity(
    cfg: StackNetworkConfig, num_times: int = 1, return_time: bool = False
):
    fidelities = {}
    for version in COMPILE_VERSIONS:
        fidelities[version] = []

    times = {}
    for version in COMPILE_VERSIONS:
        times[version] = []

    thetas = [0, PI_OVER_2, PI]
    phis = [0, PI_OVER_2, PI]
    theta_phis = [
        (0, 0),  # |0>
        (PI, 0),  # |1>
        (PI_OVER_2, 0),  # |+>
        (PI_OVER_2, PI),  # |->
        (PI_OVER_2, PI_OVER_2),  # |i>
        (PI_OVER_2, -PI_OVER_2),  # |-i>
    ]
    # nr_of_theta_phi_combis = len(thetas) * len(phis)

    for version in COMPILE_VERSIONS:
        inner_times = []
        for (theta, phi) in theta_phis:
            fid, durations = teleport.do_teleportation(
                cfg=cfg,
                num_times=num_times,
                theta=theta,
                phi=phi,
                compile_version=version,
            )
            fidelities[version] += fid
            inner_times += durations
        for i in range(num_times):
            times_for_run_i = []
            for j in range(len(theta_phis)):
                times_for_run_i.append(inner_times[j * num_times + i])
            avg_for_run_i = sum(times_for_run_i) / len(times_for_run_i)
            times[version].append(avg_for_run_i)

    print(fidelities)
    print(f"time: {times}")

    result_dict = {}
    for version in COMPILE_VERSIONS:
        fid = fidelities[version]
        mean = round(sum(fid) / len(fid), 3)
        variance = sum((r - mean) * (r - mean) for r in fid) / len(fid)
        std_deviation = math.sqrt(variance)
        std_error = round(std_deviation / math.sqrt(len(fid)), 3)

        result_dict[version] = (mean, std_error)

    if not return_time:
        return result_dict

    times_result_dict = {}
    for version in COMPILE_VERSIONS:
        tim = times[version]
        mean = round(sum(tim) / len(tim), 3)
        variance = sum((r - mean) * (r - mean) for r in tim) / len(tim)
        std_deviation = math.sqrt(variance)
        std_error = round(std_deviation / math.sqrt(len(tim)), 3)

        times_result_dict[version] = (mean, std_error)

    return result_dict, times_result_dict


def sweep_fidelity(cfg_file: str, num_times: int) -> None:
    cfg = StackNetworkConfig.from_file(cfg_file)

    data = {"t_cycle = 1e3": [], "t_cycle = 1e6": []}

    cfg.links[0].cfg["t_cycle"] = 1e3
    for link_fidelity in [0.7, 0.75, 0.80, 0.85, 0.90]:
        cfg.links[0].cfg["fidelity"] = link_fidelity
        error_rate, std_err = get_avg_fidelity(cfg, num_times=num_times)["compile_1"]
        print(
            f"fidelity = {link_fidelity}: error rate = {error_rate}, std_err = {std_err}"
        )
        data["t_cycle = 1e3"].append(
            {
                "sweep_value": link_fidelity,
                "error_rate": error_rate,
                "std_err": std_err,
            }
        )

    cfg.links[0].cfg["t_cycle"] = 1e6
    for link_fidelity in [0.7, 0.75, 0.80, 0.85, 0.90]:
        cfg.links[0].cfg["fidelity"] = link_fidelity
        error_rate, std_err = get_avg_fidelity(cfg, num_times=num_times)["compile_1"]
        print(
            f"fidelity = {link_fidelity}: error rate = {error_rate}, std_err = {std_err}"
        )
        data["t_cycle = 1e6"].append(
            {
                "sweep_value": link_fidelity,
                "error_rate": error_rate,
                "std_err": std_err,
            }
        )

    dump_data(data, "sweep_fidelity.json")


def sweep_rate(cfg_file: str, num_times: int) -> None:
    cfg = StackNetworkConfig.from_file(cfg_file)

    data = []

    for link_rate in [0.01, 0.1, 0.2, 0.5, 1]:
        cfg.links[0].cfg["prob_success"] = link_rate
        error_rate, std_err = get_avg_fidelity(cfg, num_times=num_times)["compile_1"]
        print(
            f"prob_success = {link_rate}: error rate = {error_rate}, std_err = {std_err}"
        )
        data.append(
            {
                "sweep_value": link_rate,
                "error_rate": error_rate,
                "std_err": std_err,
            }
        )

    dump_data(data, "sweep_rate.json")


def sweep_t2(cfg_file: str, num_times: int) -> None:
    cfg = StackNetworkConfig.from_file(cfg_file)

    data = []
    for T2 in [1e8, 3e8, 1e9, 3e9, 1e10]:
        cfg.stacks[0].qdevice_cfg["T2"] = T2
        cfg.stacks[1].qdevice_cfg["T2"] = T2
        error_rate, std_err = get_avg_fidelity(cfg, num_times=num_times)["compile_1"]
        print(f"T2 = {T2}: error rate = {error_rate}, std_err = {std_err}")

        data.append(
            {
                "sweep_value": T2,
                "error_rate": error_rate,
                "std_err": std_err,
            }
        )

    dump_data(data, "sweep_t2.json")


def sweep_gate_noise(cfg_file: str, num_times: int) -> None:
    cfg = StackNetworkConfig.from_file(cfg_file)
    # cfg.links[0].cfg["fidelity"] = 0.85

    data = {}
    for version in COMPILE_VERSIONS:
        data[version] = []

    # for depolar_prob in [0.0, 0.1, 0.3, 0.4]:
    probs = list(np.linspace(0, 0.15, 10))
    for depolar_prob in probs:
        cfg.stacks[0].qdevice_cfg["ec_gate_depolar_prob"] = depolar_prob
        cfg.stacks[1].qdevice_cfg["ec_gate_depolar_prob"] = depolar_prob
        result = get_avg_fidelity(cfg, num_times=num_times)

        for version in COMPILE_VERSIONS:
            fidelity, std_err = result[version]
            print(
                f"depolar_prob = {depolar_prob}: fidelity = {fidelity}, std_err = {std_err}"
            )

            data[version].append(
                {
                    "sweep_value": depolar_prob,
                    "fidelity": fidelity,
                    "std_err": std_err,
                }
            )

    dump_data(data, "sweep_gate_noise.json")


def sweep_gate_time(cfg_file: str, num_times: int) -> None:
    cfg = StackNetworkConfig.from_file(cfg_file)
    # cfg.links[0].cfg["fidelity"] = 0.85

    data = {}
    for version in COMPILE_VERSIONS:
        data[version] = []

    times = list(np.linspace(0, 1_000_000, 10))
    for gate_time in times:
        cfg.stacks[0].qdevice_cfg["ec_controlled_dir_x"] = gate_time
        cfg.stacks[0].qdevice_cfg["ec_controlled_dir_y"] = gate_time
        cfg.stacks[1].qdevice_cfg["ec_controlled_dir_x"] = gate_time
        cfg.stacks[1].qdevice_cfg["ec_controlled_dir_y"] = gate_time
        result, time = get_avg_fidelity(cfg, num_times=num_times, return_time=True)

        for version in COMPILE_VERSIONS:
            fidelity, fid_std_err = result[version]
            duration, dur_std_err = time[version]
            print(
                f"gate_time = {gate_time}: fidelity = {fidelity}, std_err = {fid_std_err}"
            )
            print(
                f"gate_time = {gate_time}: duration = {duration}, std_err = {dur_std_err}"
            )

            data[version].append(
                {
                    "sweep_value": gate_time,
                    "fidelity": fidelity,
                    "duration": duration,
                    "fid_std_err": fid_std_err,
                    "dur_std_err": dur_std_err,
                }
            )

    dump_data(data, "sweep_gate_time.json")


def teleport_sweep_t2(cfg_file: str, num_times: int) -> None:
    cfg = StackNetworkConfig.from_file(cfg_file)

    data = []
    for T2 in [1e8, 3e8, 1e9, 3e9, 1e10]:
        cfg.stacks[0].qdevice_cfg["T2"] = T2
        cfg.stacks[1].qdevice_cfg["T2"] = T2
        error_rate, std_err = get_avg_fidelity(cfg, num_times=num_times)["compile_1"]
        print(f"T2 = {T2}: error rate = {error_rate}, std_err = {std_err}")

        data.append(
            {
                "sweep_value": T2,
                "error_rate": error_rate,
                "std_err": std_err,
            }
        )

    dump_data(data, "sweep_t2.json")


def sweep_latency(cfg_file: str, num_times: int) -> None:
    cfg = StackNetworkConfig.from_file(cfg_file)

    data = {}
    for version in COMPILE_VERSIONS:
        data[version] = []

    for latency in [5e5, 1e6, 10e6, 20e6, 50e6]:
        cfg.stacks[0].classical_cfg.host_qnos_latency = latency
        cfg.stacks[1].classical_cfg.host_qnos_latency = latency
        result = get_avg_fidelity(cfg, num_times=num_times)

        for version in COMPILE_VERSIONS:
            fidelity, std_err = result[version]
            print(
                f"version: {version}, latency = {latency}: fidelity = "
                f"{fidelity}, std_err = {std_err}"
            )

            data[version].append(
                {
                    "sweep_value": latency,
                    "fidelity": fidelity,
                    "std_err": std_err,
                }
            )

    dump_data(data, "sweep_latency.json")
