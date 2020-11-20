from enum import Enum, auto


class _Role(Enum):
    start = auto()
    middle = auto()
    end = auto()


def create_ghz(down_epr_socket=None, up_epr_socket=None, down_socket=None, up_socket=None, do_corrections=False):
    r"""Local protocol to create a GHZ state between mutliples nodes.

    EPR pairs are generated in a line and turned into a GHZ state by performing half of a Bell measurement.
    That is, CNOT and H are applied but only the control qubit is measured.
    If `do_corrections=False` (default) this measurement outcome is returned along with the qubit to be able to know
    what corrections might need to be applied.
    If the node is at the start or end of the line, the measurement outcome 0 is always returned since there
    is no measurement performed.
    The measurement outcome indicates if the next node in the line should flip its qubit to get the standard
    GHZ state: :math:`|0\rangle^{\otimes n} + |1\rangle^{\otimes n}`.

    On the other hand if `do_corrections=True`, then the classical sockets `down_socket` and/or `up_socket`
    will be used to communicate the outcomes and automatically perform the corrections.

    Depending on if down_epr_socket and/or up_epr_socket is specified the node,
    either takes the role of the:

    * "start", which intialises the process and creates an EPR
      with the next node using the `up_epr_socket`.
    * "middle", which receives an EPR pair on the `down_epr_socket` and then
      creates one on the `up_epr_socket`.
    * "end", which receives an EPR pair on the `down_epr_socket`.

    NOTE There has to be exactly one "start" and exactly one "end" but zero or more "middle".
    NOTE Both `down_epr_socket` and `up_epr_socket` cannot be `None`.

    Parameters
    ----------
    down_epr_socket : :class:`.sdk.epr_socket.EPRSocket`
        The EPRSocket to be used for receiving EPR pairs from downstream.
    up_epr_socket : :class:`.sdk.epr_socket.EPRSocket`
        The EPRSocket to be used for create EPR pairs upstream.
    down_socket : :class:`.sdk.classical_communication.socket.Socket`
        The classical socket to be used for sending corrections, if `do_corrections = True`.
    up_socket : :class:`.sdk.classical_communication.socket.Socket`
        The classical socket to be used for sending corrections, if `do_corrections = True`.
    do_corrections : bool
        If corrections should be applied to make the GHZ in the standard form
        :math:`|0\rangle^{\otimes n} + |1\rangle^{\otimes n}` or not.

    Returns
    -------
    tuple
        Of the form `(q, m)` where `q` is the qubit part of the state and `m` is the measurement outcome.
    """
    if down_epr_socket is None and up_epr_socket is None:
        raise TypeError("Both down_epr_socket and up_epr_socket cannot be None")

    if down_epr_socket is None:
        # Start role
        role = _Role.start
        q = up_epr_socket.create()[0]
        conn = up_epr_socket._conn
        m = 0
    else:
        q = down_epr_socket.recv()[0]
        conn = down_epr_socket._conn
        if up_epr_socket is None:
            # End role
            role = _Role.end
            m = 0
        else:
            # Middle role
            role = _Role.middle
            q_up = up_epr_socket.create()[0]
            # merge the states by doing half a Bell measurement
            q.cnot(q_up)
            m = q_up.measure()

    # Flush the subroutine
    conn.flush()

    if do_corrections:
        if role == _Role.start:
            _assert_socket(up_socket)
            up_socket.send(str(0))
        else:
            _assert_socket(down_socket)
            corr = int(down_socket.recv(maxsize=1))
            if corr == 1:
                q.X()
            if role == _Role.middle:
                _assert_socket(up_socket)
                corr = (corr + m) % 2
                up_socket.send(str(corr))
        m = 0

    return q, m


def _assert_socket(socket):
    if socket is None:
        raise TypeError("A socket is needed to do corrections")
