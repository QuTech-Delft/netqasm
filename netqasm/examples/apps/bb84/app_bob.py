import json
import math
import random
from dataclasses import dataclass
from typing import Optional

from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.external import NetQASMConnection, Socket

logger = get_netqasm_logger()

buf_msgs = []  # type: ignore
EOF = "EOF"
ALL_MEASURED = "All qubits measured"


def recv_single_msg(socket):
    """Used to not get multiple messages at a time"""
    if len(buf_msgs) > 0:
        msg = buf_msgs.pop(0)
    else:
        msgs = socket.recv().split(EOF)[:-1]
        buf_msgs.extend(msgs[1:])
        msg = msgs[0]
    logger.debug(f"Bob received msg {msg}")
    return msg


def send_single_msg(socket, msg):
    """Used to not get multiple messages at a time"""
    socket.send(msg + EOF)


def sendClassicalAssured(socket, data):
    data = json.dumps(data)
    send_single_msg(socket, data)
    while recv_single_msg(socket) != "ACK":
        pass


def recvClassicalAssured(socket):
    data = recv_single_msg(socket)
    data = json.loads(data)
    send_single_msg(socket, "ACK")
    return data


def receive_bb84_states(conn, epr_socket, socket, target, n):
    bit_flips = [None for _ in range(n)]
    basis_flips = [random.randint(0, 1) for _ in range(n)]

    for i in range(n):
        q = epr_socket.recv_keep(1)[0]
        if basis_flips[i]:
            q.H()
        m = q.measure()
        conn.flush()
        bit_flips[i] = int(m)

    return bit_flips, basis_flips


def filter_bases(socket, pairs_info):
    bases = [(i, pairs_info[i].basis) for (i, pair) in enumerate(pairs_info)]

    remote_bases = socket.recv_structured().payload
    socket.send_structured(StructuredMessage("Bases", bases))

    for (i, basis), (remote_i, remote_basis) in zip(bases, remote_bases):
        assert i == remote_i
        pairs_info[i].same_basis = basis == remote_basis

    return pairs_info


def estimate_error_rate(socket, pairs_info, num_test_bits):
    test_indices = socket.recv_structured().payload
    for pair in pairs_info:
        pair.test_outcome = pair.index in test_indices

    test_outcomes = [(i, pairs_info[i].outcome) for i in test_indices]

    logger.info(f"bob test indices: {test_indices}")
    logger.info(f"bob test outcomes: {test_outcomes}")

    socket.send_structured(StructuredMessage("Test outcomes", test_outcomes))
    target_test_outcomes = socket.recv_structured().payload
    logger.info(f"bob target_test_outcomes: {target_test_outcomes}")

    num_error = 0
    for (i1, t1), (i2, t2) in zip(test_outcomes, target_test_outcomes):
        assert i1 == i2
        if t1 != t2:
            num_error += 1
            pairs_info[i1].same_outcome = False
        else:
            pairs_info[i1].same_outcome = True

    return pairs_info, (num_error / num_test_bits)


def extract_key(x, r):
    return sum([xj * rj for xj, rj in zip(x, r)]) % 2


@dataclass
class PairInfo:
    """Information that Bob has about one generated pair.
    The information is filled progressively during the protocol."""

    # Index in list of all generated pairs.
    index: int

    # Basis Alice measured in. 0 = Z, 1 = X.
    basis: int

    # Measurement outcome (0 or 1).
    outcome: int

    # Whether Bob measured his qubit in the same basis or not.
    same_basis: Optional[bool] = None

    # Whether to use this pair to estimate errors by comparing the outcomes.
    test_outcome: Optional[bool] = None

    # Whether measurement outcome is the same as Bob's. (Only for pairs used for error estimation.)
    same_outcome: Optional[bool] = None


def h(p):
    if p == 0 or p == 1:
        return 0
    else:
        return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def main(app_config=None, num_bits=100):
    num_test_bits = max(num_bits // 4, 1)

    # Socket for classical communication
    socket = Socket("bob", "alice", log_config=app_config.log_config)
    # Socket for EPR generation
    epr_socket = EPRSocket("alice")

    bob = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )
    with bob:
        bit_flips, basis_flips = receive_bb84_states(
            bob, epr_socket, socket, "alice", num_bits
        )

    outcomes = [int(b) for b in bit_flips]
    bases = [int(b) for b in basis_flips]

    logger.info(f"bob outcomes: {outcomes}")
    logger.info(f"bob bases: {bases}")

    pairs_info = []
    for i in range(num_bits):
        pairs_info.append(
            PairInfo(
                index=i,
                basis=int(basis_flips[i]),
                outcome=int(bit_flips[i]),
            )
        )

    socket.send(ALL_MEASURED)
    pairs_info = filter_bases(socket, pairs_info)

    pairs_info, error_rate = estimate_error_rate(socket, pairs_info, num_test_bits)
    logger.info(f"bob error_rate: {error_rate}")

    raw_key = [pair.outcome for pair in pairs_info if not pair.test_outcome]
    logger.info(f"alice raw key: {raw_key}")

    # Return data.

    table = []
    for pair in pairs_info:
        basis = "X" if pair.basis == 1 else "Z"
        check = pair.same_outcome if pair.test_outcome else "-"
        table.append([pair.index, basis, pair.same_basis, pair.outcome, check])

    x_basis_count = sum(pair.basis for pair in pairs_info)
    z_basis_count = num_bits - x_basis_count
    same_basis_count = sum(pair.same_basis for pair in pairs_info)
    outcome_comparison_count = sum(
        pair.test_outcome for pair in pairs_info if pair.same_basis
    )
    diff_outcome_count = outcome_comparison_count - sum(
        pair.same_outcome for pair in pairs_info if pair.test_outcome
    )
    if outcome_comparison_count == 0:
        qber = 1
    else:
        qber = (diff_outcome_count) / outcome_comparison_count
    key_rate_potential = 1 - 2 * h(qber)

    return {
        # Table with one row per generated pair.
        # Columns:
        #   - Pair number
        #   - Measurement basis ("X" or "Z")
        #   - Same basis as Alice ("True" or "False")
        #   - Measurement outcome ("0" or "1")
        #   - Outcome same as Alice ("True", "False" or "-")
        #       ("-" is when outcomes are not compared)
        "table": table,
        # Number of times measured in the X basis.
        "x_basis_count": x_basis_count,
        # Number of times measured in the Z basis.
        "z_basis_count": z_basis_count,
        # Number of times measured in the same basis as Alice.
        "same_basis_count": same_basis_count,
        # Number of pairs chosen to compare measurement outcomes for.
        "outcome_comparison_count": outcome_comparison_count,
        # Number of compared outcomes with equal values.
        "diff_outcome_count": diff_outcome_count,
        # Estimated Quantum Bit Error Rate (QBER).
        "qber": qber,
        # Rate of secure key that can in theory be extracted from the raw key.
        "key_rate_potential": key_rate_potential,
        # Raw key.
        # ('Result' of this application. In practice, there'll be post-processing to produce secure shared key.)
        "raw_key": raw_key,
    }


if __name__ == "__main__":
    main()
