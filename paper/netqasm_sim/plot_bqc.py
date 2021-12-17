import json
import os
from argparse import ArgumentParser
from pathlib import Path

import matplotlib.pyplot as plt

COMPILE_VERSIONS = ["vanilla", "nv"]
FORMATS = {
    "vanilla": "-ro",
    "nv": "-bs",
}
FORMATS_2 = {
    "vanilla": "--ro",
    "nv": "--bo",
}
VERSION_LABELS = {
    "vanilla": "Vanilla NetQASM",
    "nv": "NV NetQASM",
}

X_LABELS = {
    "fidelity": "Fidelity",
    "rate": "Success probability per entanglement attempt",
    "t2": "T2 (ns)",
    "gate_noise": "2-qubit gate depolarising probability",
    "gate_noise_trap": "2-qubit gate depolarising probability",
    "gate_time": "2-qubit gate duration (ms)",
    "gate_time_trap": "2-qubit gate duration (ms)",
    "latency": "Host <-> QNodeOS latency (ms)",
}


def create_png(param_name):
    output_dir = os.path.join(os.path.dirname(__file__), "plots_bqc")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = os.path.join(output_dir, f"bqc_sweep_{param_name}.png")
    plt.savefig(output_path)
    print(f"plot written to {output_path}")


def plot_gate_noise():
    param_name = "gate_noise"

    data_path = os.path.join(
        os.path.dirname(__file__), f"sweep_data_bqc/sweep_{param_name}.json"
    )

    with open(data_path, "r") as f:
        all_data = json.load(f)

    fig, ax = plt.subplots()

    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Error rate")

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
            label=version,
        )

    ax.set_title(
        "BQC trap round error rate vs two-qubit gate noise probability",
        wrap=True,
    )

    # ax.set_ylim(0.10, 0.35)
    # ax.axhline(y=0.25, color="red", label="BQC threshold")
    ax.legend()
    # plt.tight_layout()

    create_png(param_name)


def plot_gate_noise_trap():
    param_name = "gate_noise_trap"

    data_path = os.path.join(
        os.path.dirname(__file__), f"sweep_data_bqc/sweep_{param_name}.json"
    )

    with open(data_path, "r") as f:
        all_data = json.load(f)

    fig, ax = plt.subplots()

    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Error rate")

    for version in COMPILE_VERSIONS:
        data = all_data[version]
        sweep_values = [v["sweep_value"] for v in data]
        error_rates = [v["error_rate"] for v in data]
        std_errs = [v["std_err"] for v in data]
        ax.errorbar(
            x=sweep_values,
            y=error_rates,
            yerr=std_errs,
            fmt=FORMATS[version],
            label=VERSION_LABELS[version],
        )

    ax.set_title(
        "BQC trap round error rate vs two-qubit gate noise probability",
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
        os.path.dirname(__file__), f"sweep_data_bqc/sweep_{param_name}.json"
    )

    with open(data_path, "r") as f:
        all_data = json.load(f)

    fig, ax = plt.subplots()

    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Fidelity")

    ax2 = ax.twinx()
    ax2.set_ylabel("Execution time")

    lines = []

    for version in COMPILE_VERSIONS:
        data = all_data[version]
        sweep_values = [v["sweep_value"] / 1e6 for v in data]  # ns -> ms
        fidelities = [v["fidelity"] for v in data]
        fid_std_errs = [v["fid_std_err"] for v in data]
        durations = [v["duration"] / 1e6 for v in data]  # ns -> ms
        dur_std_errs = [v["dur_std_err"] / 1e6 for v in data]
        # lines.append(
        #     ax.errorbar(
        #         x=sweep_values,
        #         y=fidelities,
        #         yerr=fid_std_errs,
        #         fmt=FORMATS[version],
        #         label=version,
        #     )
        # )

        lines.append(
            ax2.errorbar(
                x=sweep_values,
                y=durations,
                yerr=dur_std_errs,
                fmt=FORMATS_2[version],
                label=version,
            )
        )

    ax.set_title(
        "Error rate vs two-qubit gate noise\n(fidelity: 0.85, T2: 1e9 ns, "
        "ent attempt time: 1e6 ns, ent success prob: 0.01)",
        wrap=True,
    )

    # ax.set_ylim(0.75, 0.9)
    # ax.axhline(y=0.25, color="red", label="BQC threshold")
    labels = [l.get_label() for l in lines]
    ax.legend(lines, labels, loc=0, bbox_to_anchor=(0.25, 0.8))
    # ax2.legend()
    # plt.tight_layout()

    create_png(param_name)


def plot_gate_time_trap():
    param_name = "gate_time_trap"

    data_path = os.path.join(
        os.path.dirname(__file__), f"sweep_data_bqc/sweep_{param_name}.json"
    )

    with open(data_path, "r") as f:
        all_data = json.load(f)

    fig, ax = plt.subplots()

    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Error rate")

    ax2 = ax.twinx()

    lines = []

    for version in COMPILE_VERSIONS:
        data = all_data[version]
        sweep_values = [v["sweep_value"] / 1e6 for v in data]  # ns -> ms
        error_rates = [v["error_rate"] for v in data]
        error_rate_std_errs = [v["err_rate_std_err"] for v in data]
        durations = [v["duration"] / 1e6 for v in data]  # ns -> ms
        dur_std_errs = [v["dur_std_err"] / 1e6 for v in data]
        lines.append(
            ax.errorbar(
                x=sweep_values,
                y=error_rates,
                yerr=error_rate_std_errs,
                fmt=FORMATS[version],
                label=version,
            )
        )

        lines.append(
            ax2.errorbar(
                x=sweep_values,
                y=durations,
                yerr=dur_std_errs,
                fmt=FORMATS_2[version],
                label=version,
            )
        )

    ax.set_title(
        "Error rate vs two-qubit gate noise\n(fidelity: 0.85, T2: 1e9 ns, "
        "ent attempt time: 1e6 ns, ent success prob: 0.01)",
        wrap=True,
    )

    # ax.set_ylim(0.75, 0.9)
    # ax.axhline(y=0.25, color="red", label="BQC threshold")
    labels = [l.get_label() for l in lines]
    ax.legend(lines, labels, loc=0, bbox_to_anchor=(0.25, 0.8))
    # ax2.legend()
    # plt.tight_layout()

    create_png(param_name)


def plot_fidelity():
    param_name = "fidelity"

    with open(
        os.path.join(
            os.path.dirname(__file__), f"sweep_data_bqc/sweep_{param_name}.json"
        ),
        "r",
    ) as f:
        all_data = json.load(f)

    fig, ax = plt.subplots()

    data1 = all_data["t_cycle = 1e3"]
    data2 = all_data["t_cycle = 1e6"]
    sweep_values1 = [v["sweep_value"] for v in data1]
    error_rates1 = [v["error_rate"] for v in data1]
    std_errs1 = [v["std_err"] for v in data1]
    sweep_values2 = [v["sweep_value"] for v in data2]
    error_rates2 = [v["error_rate"] for v in data2]
    std_errs2 = [v["std_err"] for v in data2]
    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Error rate")
    ax.axhline(y=0.25, color="red", label="BQC threshold")
    ax.errorbar(
        x=sweep_values1,
        y=error_rates1,
        yerr=std_errs1,
        fmt="-bo",
        label="entanglement attempt duration = 1e3 ns",
    )
    ax.errorbar(
        x=sweep_values2,
        y=error_rates2,
        yerr=std_errs2,
        fmt="-go",
        label="entanglement attempt duration = 1e6 ns",
    )
    ax.legend()
    ax.set_title(
        "Error rate vs fidelity\n(T2: 1e9 ns, default gate noise, ent success prob: 0.01)"
    )

    create_png(param_name)


def plot(args):
    if args.param == "fidelity":
        plot_fidelity()
    elif args.param == "rate":
        plot_rate()
    elif args.param == "gate_noise":
        plot_gate_noise()
    elif args.param == "gate_noise_trap":
        plot_gate_noise_trap()
    elif args.param == "gate_time":
        plot_gate_time()
    elif args.param == "gate_time_trap":
        plot_gate_time_trap()
    elif args.param == "T2":
        plot_t2()
    elif args.param == "latency":
        plot_latency()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.set_defaults(func=plot)
    parser.add_argument(
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

    args = parser.parse_args()
    args.func(args)
