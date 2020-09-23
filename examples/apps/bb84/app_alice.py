import json
import random

from qlink_interface import EPRType, RandomBasis

from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket

logger = get_netqasm_logger()


def sendClassicalAssured(socket, data):
    data = json.dumps(data)
    socket.send(data)
    while socket.recv() != 'ACK':
        pass


def recvClassicalAssured(socket):
    data = socket.recv()
    data = json.loads(data)
    socket.send('ACK')
    return data


def distribute_bb84_states(epr_socket, socket, target, n):
    bit_flips = []
    basis_flips = []

    ent_infos = epr_socket.create(
        number=n,
        tp=EPRType.M,
        random_basis_local=RandomBasis.XZ,
        random_basis_remote=RandomBasis.XZ,
    )
    for ent_info in ent_infos:
        bit_flips.append(ent_info.measurement_outcome)
        basis_flips.append(ent_info.measurement_basis)
    return bit_flips, basis_flips


def filter_theta(socket, x, theta):
    x_remain = []
    sendClassicalAssured(socket, theta)
    theta_hat = recvClassicalAssured(socket)
    for bit, basis, basis_hat in zip(x, theta, theta_hat):
        if basis == basis_hat:
            x_remain.append(bit)

    return x_remain


def estimate_error_rate(socket, x, num_test_bits):
    test_bits = []
    test_indices = []

    while len(test_indices) < num_test_bits and len(x) > 0:
        index = random.randint(0, len(x) - 1)
        test_bits.append(x.pop(index))
        test_indices.append(index)

    logger.info(f"alice finding {num_test_bits} test bits")
    logger.info(f"alice test indices: {test_indices}")
    logger.info(f"alice test bits: {test_bits}")

    sendClassicalAssured(socket, test_indices)
    target_test_bits = recvClassicalAssured(socket)
    sendClassicalAssured(socket, test_bits)
    logger.info(f"alice target_test_bits: {target_test_bits}")

    num_error = 0
    for t1, t2 in zip(test_bits, target_test_bits):
        if t1 != t2:
            num_error += 1

    return (num_error / num_test_bits)


def extract_key(x, r):
    return (sum([xj*rj for xj, rj in zip(x, r)]) % 2)


def main(app_config=None, num_bits=100):
    num_test_bits = num_bits // 4

    # Socket for classical communication
    socket = Socket("alice", "bob", log_config=app_config.log_config)
    # Socket for EPR generation
    epr_socket = EPRSocket("bob")

    node_name = app_config.node_name
    if node_name is None:
        node_name = app_config.app_name

    alice = NetQASMConnection(
        node_name=node_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket],
    )
    with alice:
        bit_flips, basis_flips = distribute_bb84_states(epr_socket, socket, "bob", num_bits)
    x = [int(b) for b in bit_flips]
    theta = [int(b) for b in basis_flips]

    logger.info(f"alice x: {x}")
    logger.info(f"alice theta: {theta}")

    m = recvClassicalAssured(socket)
    if m != 'BB84DISTACK':
        logger.info(m)
        raise RuntimeError("Failure to distributed BB84 states")

    x_remain = filter_theta(socket, x, theta)

    error_rate = estimate_error_rate(socket, x_remain, num_test_bits)
    logger.info(f"alice error rate: {error_rate}")

    if error_rate > 1:
        raise RuntimeError(f"Error rate of {error_rate}, aborting protocol")

    r = [random.randint(0, 1) for _ in x_remain]
    sendClassicalAssured(socket, r)
    k = extract_key(x_remain, r)

    logger.info(f"alice R: {r}")
    logger.info(f"alice raw key: {x_remain}")
    logger.info(f"alice key: {k}")

    return {
        'raw_key': x_remain,
        'key': k,
    }


if __name__ == '__main__':
    main()
