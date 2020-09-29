"""Utility functions for Blind Quantum Computations"""


def measXY(q, angle):
    """Measure qubit `q` in the basis spanned by `|0> ± e^{i*angle} |1>`.
    This is equivalent to doing a Z-rotation of `angle`, then a Hadamard,
    and measuring in the Z-basis.
    Note: we use the convention that we rotate by +`angle` (not -`angle`).
    """
    q.rot_Z(angle=angle)
    q.H()
    return q.measure()


def teleport_state(epr_socket, theta):
    """Teleport a state Rz(theta)|+> to the server.
    The resulting state on the server's side is actually
    Rz(theta + m*pi) |+>, for the client's measurement outcome `m`.
    """
    epr = epr_socket.create()[0]
    m = measXY(epr, theta)
    return m


def recv_teleported_state(epr_socket):
    """Let the client teleport a state to the server.
    The client will do a suitable measurement on her side.
    """
    return epr_socket.recv()[0]


def send_meas_cmd(socket, phi):
    """Tell the server to measure the next qubit in angle `phi`.
    This effectively applies the operation H Rz(phi) on the logical input.
    """
    socket.send(str(phi))


def recv_meas_cmd(socket):
    """Receive the angle to measure the next qubit in."""
    return float(socket.recv())


def send_meas_outcome(socket, outcome):
    """Send the outcome (0 or 1) of the latest measurement to the client."""
    socket.send(str(outcome))


def recv_meas_outcome(socket):
    """Receive the measurement outcome (0 or 1) of the server's
    last measurement.
    """
    return int(socket.recv(maxsize=1))
