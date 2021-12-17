import json
import os
from argparse import ArgumentParser
from pathlib import Path

import matplotlib.pyplot as plt

COMPILE_VERSIONS = ["meas_epr_first", "meas_epr_last"]
FORMATS = {
    "meas_epr_first": "-rs",
    "meas_epr_last": "-bo",
}
FORMATS_2 = {
    "meas_epr_first": "--gs",
    "meas_epr_last": "--yo",
}

VERSION_LABELS = {
    "meas_epr_first": "Unit modules",
    "meas_epr_last": "No unit modules",
}
VERSION_LABELS_1 = {
    "meas_epr_first": "Unit modules (fidelity)",
    "meas_epr_last": "No unit modules (fidelity)",
}
VERSION_LABELS_2 = {
    "meas_epr_first": "Unit modules (execution time)",
    "meas_epr_last": "No unit modules (execution time)",
}

X_LABELS = {
    "fidelity": "Fidelity",
    "rate": "Success probability per entanglement attempt",
    "t2": "T2 (ns)",
    "gate_noise": "2-qubit gate depolarising probability",
    "gate_time": "2-qubit gate duration (ms)",
    "latency": "Host <-> QNodeOS latency (ms)",
}


def create_png(param_name):
    output_dir = os.path.join(os.path.dirname(__file__), "plots_teleport")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = os.path.join(output_dir, f"teleport_sweep_{param_name}.png")
    plt.savefig(output_path)
    print(f"plot written to {output_path}")


def plot_gate_noise():
    param_name = "gate_noise"

    data_path = os.path.join(
        os.path.dirname(__file__), f"sweep_data_teleport/sweep_{param_name}.json"
    )

    with open(data_path, "r") as f:
        all_data = json.load(f)

    fig, ax = plt.subplots()

    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Fidelity")

    for version in COMPILE_VERSIONS:
        data = all_data[version]
        sweep_values = [v["sweep_value"] for v in data]
        error_rates = [v["fidelity"] for v in data]
        std_errs = [v["std_err"] for v in data]
        ax.errorbar(
            x=sweep_values,
            y=error_rates,
            yerr=std_errs,
            fmt=FORMATS[version],
            label=VERSION_LABELS[version],
        )

    ax.set_title(
        "Fidelity of teleported state vs 2-qubit gate noise probability",
        wrap=True,
    )

    # ax.set_ylim(0.10, 0.35)
    # ax.axhline(y=0.25, color="red", label="BQC threshold")
    ax.legend()
    # plt.tight_layout()

    create_png(param_name)


def plot_gate_time():
    param_name = "gate_time"

    data_path = os.path.join(
        os.path.dirname(__file__), f"sweep_data_teleport/sweep_{param_name}.json"
    )

    with open(data_path, "r") as f:
        all_data = json.load(f)

    fig, ax = plt.subplots()

    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Fidelity")

    ax2 = ax.twinx()
    ax2.set_ylabel("Execution time (ms)")

    for version in COMPILE_VERSIONS:
        data = all_data[version]
        sweep_values = [v["sweep_value"] / 1e6 for v in data]  # ns -> ms
        fidelities = [v["fidelity"] for v in data]
        fid_std_errs = [v["fid_std_err"] for v in data]
        durations = [v["duration"] / 1e6 for v in data]  # ns -> ms
        dur_std_errs = [v["dur_std_err"] / 1e6 for v in data]
        ax.errorbar(
            x=sweep_values,
            y=fidelities,
            yerr=fid_std_errs,
            fmt=FORMATS[version],
            label=VERSION_LABELS_1[version],
        )

        ax2.errorbar(
            x=sweep_values,
            y=durations,
            yerr=dur_std_errs,
            fmt=FORMATS_2[version],
            label=VERSION_LABELS_2[version],
        )

    ax.set_title(
        "Fidelity of teleported state and total executation time "
        "vs 2-qubit gate duration",
        wrap=True,
    )

    ax.set_ylim(0.75, 0.9)
    # ax.axhline(y=0.25, color="red", label="BQC threshold")
    ax.legend(loc="upper left")
    ax2.legend(loc="upper left", bbox_to_anchor=(0.0, 0.85))
    # plt.tight_layout()

    create_png(param_name)


def plot(args):
    if args.param == "gate_noise":
        plot_gate_noise()
    elif args.param == "gate_time":
        plot_gate_time()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.set_defaults(func=plot)
    parser.add_argument(
        "--param",
        type=str,
        choices={"fidelity", "rate", "T2", "gate_noise", "gate_time", "latency"},
        required=True,
    )

    args = parser.parse_args()
    args.func(args)
