from __future__ import annotations

import math
import os
from typing import Any, Dict, Generator, final

import netsquid as ns
from netqasm.lang.ir import BreakpointAction, BreakpointRole
from netqasm.sdk.qubit import Qubit
from netqasm.sdk.toolbox import set_qubit_state
from netsquid.qubits import ketstates, operators, qubitapi
from pydynaa import EventExpression
from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    LinkConfig,
    NVLinkConfig,
    NVQDeviceConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

PI = math.pi
PI_OVER_2 = math.pi / 2


class SenderProgram(Program):
    PEER = "receiver"

    def __init__(
        self,
        theta: float,
        phi: float,
        meas_epr_first: bool,
    ):
        self._theta = theta
        self._phi = phi
        self._meas_epr_first = meas_epr_first

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="sender_program",
            parameters={
                "theta": self._theta,
                "phi": self._phi,
                "meas_epr_first": self._meas_epr_first,
            },
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        start_time = ns.sim_time()
        q = Qubit(conn)
        set_qubit_state(q, self._phi, self._theta)

        e = epr_socket.create()[0]
        conn.insert_breakpoint(
            BreakpointAction.DUMP_GLOBAL_STATE, BreakpointRole.RECEIVE
        )
        q.cnot(e)

        if self._meas_epr_first:
            m2 = e.measure()
            q.H()
            m1 = q.measure()
        else:
            q.H()
            m1 = q.measure()
            m2 = e.measure()

        yield from conn.flush()

        m1, m2 = int(m1), int(m2)

        csocket.send_int(m1)
        csocket.send_int(m2)

        conn.insert_breakpoint(
            BreakpointAction.DUMP_GLOBAL_STATE, BreakpointRole.RECEIVE
        )
        yield from conn.flush()

        end_time = ns.sim_time()
        return {"m1": m1, "m2": m2, "start_time": start_time, "end_time": end_time}


class ReceiverProgram(Program):
    PEER = "sender"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="receiver_program",
            parameters={},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        start_time = ns.sim_time()

        e = epr_socket.recv()[0]
        conn.insert_breakpoint(
            BreakpointAction.DUMP_GLOBAL_STATE, BreakpointRole.CREATE
        )
        yield from conn.flush()

        m1 = yield from csocket.recv_int()
        m2 = yield from csocket.recv_int()

        if m2 == 1:
            e.X()
        if m1 == 1:
            e.Z()

        conn.insert_breakpoint(
            BreakpointAction.DUMP_GLOBAL_STATE, BreakpointRole.CREATE
        )
        e.measure()
        yield from conn.flush()

        end_time = ns.sim_time()

        all_states = GlobalSimData.get_last_breakpoint_state()
        state = all_states["receiver"][0]
        return {"state": state, "start_time": start_time, "end_time": end_time}


def do_teleportation(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    theta: float = 0.0,
    phi: float = 0.0,
    compile_version: str = "None",
    log_level: str = "WARNING",
) -> float:
    LogManager.set_log_level(log_level)

    meas_epr_first = True if compile_version == "meas_epr_first" else False
    sender_program = SenderProgram(theta=theta, phi=phi, meas_epr_first=meas_epr_first)
    receiver_program = ReceiverProgram()

    client_results, server_results = run(
        cfg,
        {"sender": sender_program, "receiver": receiver_program},
        num_times=num_times,
    )

    durations = []
    for c_result, s_result in zip(client_results, server_results):
        start_time = min(c_result["start_time"], s_result["start_time"])
        end_time = max(c_result["end_time"], s_result["end_time"])
        durations.append(end_time - start_time)

    final_states = [r["state"] for r in server_results]
    # print(f"final states: {final_states}")
    # print(f"durations: {durations}")

    q = qubitapi.create_qubits(1)[0]
    rot_theta = operators.create_rotation_op(theta, (0, 1, 0))
    rot_phi = operators.create_rotation_op(phi, (0, 0, 1))
    qubitapi.operate(q, rot_theta)
    qubitapi.operate(q, rot_phi)
    fidelities = [qubitapi.fidelity(q, f, squared=True) for f in final_states]
    return fidelities, durations
