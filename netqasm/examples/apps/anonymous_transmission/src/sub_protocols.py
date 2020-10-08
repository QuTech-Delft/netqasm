from random import randint
from collections import namedtuple

from netqasm.sdk import EPRSocket
from netqasm.sdk.external import Socket, BroadcastChannel
from netqasm.sdk.toolbox import create_ghz


def classical_anonymous_transmission(
    conn,
    sockets,
    num_nodes,
    sender=False,
    value=None,
):
    if sender:
        assert isinstance(value, bool), f"Value should be boolen, not {type(value)}"

    # Create a GHZ state
    q, _ = create_ghz(
        down_epr_socket=sockets.down_epr_socket,
        up_epr_socket=sockets.up_epr_socket,
        down_socket=sockets.down_socket,
        up_socket=sockets.up_socket,
        do_corrections=True,
    )

    # If sender and value is 1/True do Z flip
    if sender and value:
        q.Z()

    # Hadamard and measure
    q.H()
    m = q.measure()

    # Flush the commands to get the outcome
    conn.flush()

    # Send outcome to all other nodes
    broadcast_channel = sockets.broadcast_channel
    broadcast_channel.send(str(m))

    # Get measurements from all other nodes
    k = m
    for _ in range(num_nodes - 1):
        remote_node, m = broadcast_channel.recv()
        k += int(m)

    message = k % 2 == 1

    return message


def anonymous_epr(
    conn,
    sockets,
    num_nodes,
    sender=False,
    receiver=False,
):
    if sender and receiver:
        raise ValueError("Cannot be both sender and receiver")
    # Create a GHZ state
    q, _ = create_ghz(
        down_epr_socket=sockets.down_epr_socket,
        up_epr_socket=sockets.up_epr_socket,
        down_socket=sockets.down_socket,
        up_socket=sockets.up_socket,
        do_corrections=True,
    )

    # Get the broadcast_channel
    broadcast_channel = sockets.broadcast_channel

    if sender or receiver:
        b = randint(0, 1)
        broadcast_channel.send(str(b))
        if sender:
            if b == 1:
                q.Z()
    else:
        # Apply Hadamard
        q.H()
        # Measure qubit
        m = q.measure()

        conn.flush()

        # Broadcast outcome
        broadcast_channel.send(str(m))

        q = None

    # Receive all messages
    k = 0
    for _ in range(num_nodes - 1):
        _, m = broadcast_channel.recv()
        k += int(m)
    # Receiver does correction
    if receiver and k % 2 == 1:
        q.Z()

    return q


def quantum_anonymous_tranmission(
    conn,
    sockets,
    num_nodes,
    sender=False,
    receiver=False,
    qubit=None,
):
    if sender:
        if qubit is None:
            raise TypeError("The sender needs to provide the qubit to send")

    epr = anonymous_epr(
        conn=conn,
        sockets=sockets,
        num_nodes=num_nodes,
        sender=sender,
        receiver=receiver,
    )
    if sender:
        # Perform teleportation
        qubit.cnot(epr)
        qubit.H()
        m1 = qubit.measure()
        m2 = epr.measure()

        conn.flush()
        to_send = [bool(m1), bool(m2)]
    else:
        # Nothing to send
        to_send = [None, None]

    outcomes = []
    for m in to_send:
        outcome = classical_anonymous_transmission(
            conn=conn,
            sockets=sockets,
            num_nodes=num_nodes,
            sender=sender,
            value=m,
        )
        # outcomes.append(int(outcome))
        outcomes.append(outcome)

    if receiver:
        # Apply corrections and return qubit
        m1, m2 = outcomes
        if m2 == 1:
            epr.X()
        if m1 == 1:
            epr.Z()
        return epr
    else:
        return None


###################
# Setup functions #
###################
Sockets = namedtuple("Sockets", [
    "broadcast_channel",
    "down_epr_socket",
    "down_socket",
    "up_epr_socket",
    "up_socket",
    "epr_sockets",
])


def setup_sockets(app_name, apps, log_config):
    broadcast_channel = _setup_broadcast_channel(app_name, apps, log_config)
    down_epr_socket, down_socket = _setup_down_sockets(app_name, apps, log_config)
    up_epr_socket, up_socket = _setup_up_sockets(app_name, apps, log_config)
    epr_sockets = [epr_socket for epr_socket in [down_epr_socket, up_epr_socket] if epr_socket is not None]

    return Sockets(
        broadcast_channel=broadcast_channel,
        down_epr_socket=down_epr_socket,
        down_socket=down_socket,
        up_epr_socket=up_epr_socket,
        up_socket=up_socket,
        epr_sockets=epr_sockets,
    )


def _setup_broadcast_channel(app_name, app_names, log_config):
    # Create a broadcast_channel to send classical information
    remote_app_names = [an for an in app_names if an != app_name]
    broadcast_channel = BroadcastChannel(
        app_name,
        remote_app_names=remote_app_names,
        log_config=log_config,
        # Use socket ID to not mixup with the other sockets
        socket_id=1,
    )

    return broadcast_channel


def _setup_down_sockets(app_name, app_names, log_config):
    index = app_names.index(app_name)
    if index > 0:
        down_node = app_names[index - 1]
    else:
        down_node = None
    return _setup_sockets(app_name, down_node, log_config)


def _setup_up_sockets(app_name, app_names, log_config):
    index = app_names.index(app_name)
    if index < len(app_names) - 1:
        up_node = app_names[index + 1]
    else:
        up_node = None
    return _setup_sockets(app_name, up_node, log_config)


def _setup_sockets(app_name, other_node, log_config):
    if other_node is None:
        return None, None
    epr_socket = EPRSocket(other_node)
    socket = Socket(app_name, other_node, log_config=log_config)
    return epr_socket, socket
