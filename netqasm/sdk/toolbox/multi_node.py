from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Optional, Tuple, Union

from netqasm.sdk.qubit import Qubit

if TYPE_CHECKING:
    from netqasm.sdk import epr_socket as esck
    from netqasm.sdk import futures
    from netqasm.sdk.classical_communication import socket


class _Role(Enum):
    start = auto()
    middle = auto()
    end = auto()


def create_ghz(
    down_epr_socket: Optional[esck.EPRSocket] = None,
    up_epr_socket: Optional[esck.EPRSocket] = None,
    down_socket: Optional[socket.Socket] = None,
    up_socket: Optional[socket.Socket] = None,
    do_corrections: bool = False,
) -> Tuple[Qubit, Union[futures.Future, futures.RegFuture, int]]:
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
    down_epr_socket : :class:`.sdk.epr_socket.esck.EPRSocket`
        The esck.EPRSocket to be used for receiving EPR pairs from downstream.
    up_epr_socket : :class:`.sdk.epr_socket.esck.EPRSocket`
        The esck.EPRSocket to be used for create EPR pairs upstream.
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
        assert up_epr_socket is not None
        # Start role
        role = _Role.start
        q = up_epr_socket.create_keep()[0]
        assert isinstance(q, Qubit)
        conn = up_epr_socket.conn
        m = 0
    else:
        assert down_epr_socket is not None
        q = down_epr_socket.recv_keep()[0]
        assert isinstance(q, Qubit)
        conn = down_epr_socket.conn
        if up_epr_socket is None:
            # End role
            role = _Role.end
            m = 0
        else:
            # Middle role
            role = _Role.middle
            q_up: Qubit = up_epr_socket.create_keep()[0]  # type: ignore
            # merge the states by doing half a Bell measurement
            q.cnot(q_up)
            m = q_up.measure()

    # Flush the subroutine
    conn.flush()

    if do_corrections:
        if role == _Role.start:
            assert up_socket is not None
            up_socket.send(str(0))
        else:
            assert down_socket is not None
            corr = int(down_socket.recv(maxsize=1))
            if corr == 1:
                q.X()
            if role == _Role.middle:
                assert up_socket is not None
                corr = (corr + m) % 2
                up_socket.send(str(corr))
        m = 0

    return q, m
