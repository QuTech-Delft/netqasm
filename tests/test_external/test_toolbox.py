import numpy as np
import pytest

from netqasm.runtime.application import Program, default_app_instance
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket, simulate_application
from netqasm.sdk.toolbox import create_ghz, get_angle_spec_from_float


@pytest.mark.parametrize(
    "angle, tol, expected_nds",
    [
        (np.pi, 1e-6, [(1, 0)]),
        (np.pi / 2, 1e-6, [(1, 1)]),
        (np.pi / 1024, 1e-6, [(1, 10)]),
        (np.pi * (1 + 1 / 2 + 1 / 4 + 1 / 16), 1e-6, [(16 + 8 + 4 + 1, 4)]),
        (np.pi * (1 + 1 / 2 + 1 / 4 + 1 / 16 + 1 / 1024), 1e-6, [(29, 4), (1, 10)]),
        (np.pi / 3, 1e-6, None),
        (1.5, 1e-6, None),
    ],
)
def test(angle, tol, expected_nds):
    print(angle)
    nds = get_angle_spec_from_float(angle=angle, tol=tol)
    if expected_nds is not None:
        assert nds == expected_nds
    print(nds)
    approx = sum(n * np.pi / 2 ** d for n, d, in nds)
    print(approx)
    assert np.abs(approx - angle) < tol


def run_node(node, down_node=None, up_node=None, do_corrections=False):
    # Setup EPR sockets, depending on the role of the node
    epr_sockets = []
    down_epr_socket = None
    down_socket = None
    up_epr_socket = None
    up_socket = None
    if down_node is not None:
        down_epr_socket = EPRSocket(down_node)
        epr_sockets.append(down_epr_socket)
        if do_corrections:
            down_socket = Socket(node, down_node)
    if up_node is not None:
        up_epr_socket = EPRSocket(up_node)
        epr_sockets.append(up_epr_socket)
        if do_corrections:
            up_socket = Socket(node, up_node)

    with NetQASMConnection(node, epr_sockets=epr_sockets):
        # Create a GHZ state with the other nodes
        q, corr = create_ghz(
            down_epr_socket=down_epr_socket,
            up_epr_socket=up_epr_socket,
            down_socket=down_socket,
            up_socket=up_socket,
            do_corrections=do_corrections,
        )
        m = q.measure()

    return (int(m), int(corr))


def _gen_create_ghz(num_nodes, do_corrections=False):

    # Setup the applications
    app_instance = default_app_instance(programs=[])
    for i in range(num_nodes):
        node = f"node{i}"
        if i == 0:
            down_node = None
        else:
            down_node = f"node{i - 1}"
        if i == num_nodes - 1:
            up_node = None
        else:
            up_node = f"node{i + 1}"
        app_instance.app.programs += [
            Program(
                party=node,
                entry=run_node,
                args=["node", "down_node", "up_node", "do_corrections"],
                results=[],
            )
        ]
        app_instance.program_inputs[node] = {
            "node": node,
            "down_node": down_node,
            "up_node": up_node,
            "do_corrections": do_corrections,
        }
        app_instance.party_alloc[node] = node

    # Run the applications
    outcomes = simulate_application(
        app_instance, use_app_config=False, enable_logging=False
    )[0]
    outcomes = {
        node: outcome for node, outcome in outcomes.items() if node != "backend"
    }
    print(outcomes)

    if do_corrections:
        corrected_outcomes = [m for (m, _) in outcomes.values()]
    else:
        corrected_outcomes = []
        # Check the outcomes
        correction = 0
        for i in range(num_nodes):
            node = f"app_node{i}"
            m, corr = outcomes[node]
            corrected_outcome = (m + correction) % 2
            corrected_outcomes.append(corrected_outcome)

            if 0 < i < num_nodes - 1:
                correction = (correction + corr) % 2

    print(corrected_outcomes)

    assert len(set(corrected_outcomes)) == 1


@pytest.mark.parametrize("do_corrections", [True, False])
@pytest.mark.parametrize("num_nodes", range(2, 6))
@pytest.mark.parametrize("i", range(5))  # Run 10 times
def test_create_ghz(do_corrections, num_nodes, i):
    _gen_create_ghz(num_nodes, do_corrections)
