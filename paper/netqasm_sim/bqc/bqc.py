from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Generator

import netsquid as ns
from netqasm.lang.ir import BreakpointAction
from netsquid.qubits import ketstates, operators, qubitapi
from netsquid.qubits.qubit import Qubit
from pydynaa import EventExpression
from squidasm.run.stack.config import LinkConfig, StackConfig, StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.globals import GlobalSimData
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

PI = math.pi
PI_OVER_2 = math.pi / 2


class ClientProgram(Program):
    PEER = "server"

    def __init__(
        self,
        alpha: float,
        beta: float,
        trap: bool,
        dummy: int,
        theta1: float,
        theta2: float,
        r1: int,
        r2: int,
        compile_version: str,
    ):
        self._alpha = alpha
        self._beta = beta
        self._trap = trap
        self._dummy = dummy
        self._theta1 = theta1
        self._theta2 = theta2
        self._r1 = r1
        self._r2 = r2
        self._compile_version = compile_version

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            parameters={
                "alpha": self._alpha,
                "beta": self._beta,
                "trap": self._trap,
                "dummy": self._dummy,
                "theta1": self._theta1,
                "theta2": self._theta2,
                "r1": self._r1,
                "r2": self._r2,
                "compile_version": self._compile_version,
            },
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def compile_version_None(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        start_time = ns.sim_time()

        epr1 = epr_socket.create()[0]

        # RSP
        if self._trap and self._dummy == 2:
            # remotely-prepare a dummy state
            p2 = epr1.measure(store_array=False)
        else:
            epr1.rot_Z(angle=self._theta2)
            epr1.H()
            p2 = epr1.measure(store_array=False)

        # Create EPR pair
        epr2 = epr_socket.create()[0]

        # RSP
        if self._trap and self._dummy == 1:
            # remotely-prepare a dummy state
            p1 = epr2.measure(store_array=False)
        else:
            epr2.rot_Z(angle=self._theta1)
            epr2.H()
            p1 = epr2.measure(store_array=False)

        yield from conn.flush()

        p1 = int(p1)
        p2 = int(p2)

        if self._trap and self._dummy == 2:
            delta1 = -self._theta1 + (p1 + self._r1) * math.pi
        else:
            delta1 = self._alpha - self._theta1 + (p1 + self._r1) * math.pi
        csocket.send_float(delta1)

        m1 = yield from csocket.recv_int()
        if self._trap and self._dummy == 1:
            delta2 = -self._theta2 + (p2 + self._r2) * math.pi
        else:
            delta2 = (
                math.pow(-1, (m1 + self._r1)) * self._beta
                - self._theta2
                + (p2 + self._r2) * math.pi
            )
        csocket.send_float(delta2)

        conn.insert_breakpoint(BreakpointAction.DUMP_GLOBAL_STATE)
        yield from conn.flush()

        end_time = ns.sim_time()
        return {"p1": p1, "p2": p2, "start_time": start_time, "end_time": end_time}

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        if self._compile_version == "None":
            return (yield from self.compile_version_None(context))
        else:
            raise ValueError


class ServerProgram(Program):
    PEER = "client"

    def __init__(self, compile_version: str):
        self._compile_version = compile_version

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            parameters={"compile_version": self._compile_version},
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def compile_version_None(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        start_time = ns.sim_time()

        epr1 = epr_socket.recv()[0]
        epr2 = epr_socket.recv()[0]
        epr2.cphase(epr1)

        yield from conn.flush()

        delta1 = yield from csocket.recv_float()

        epr2.rot_Z(angle=delta1)
        epr2.H()
        m1 = epr2.measure(store_array=False)
        yield from conn.flush()

        m1 = int(m1)

        csocket.send_int(m1)

        delta2 = yield from csocket.recv_float()

        epr1.rot_Z(angle=delta2)
        epr1.H()

        conn.insert_breakpoint(BreakpointAction.DUMP_GLOBAL_STATE)
        m2 = epr1.measure(store_array=False)
        yield from conn.flush()

        # m2 = int(m2)
        # return {"m1": m1, "m2": m2}
        all_states = GlobalSimData.get_last_breakpoint_state()
        # print(f"all_states: {all_states}")
        state = all_states["server"][1]

        end_time = ns.sim_time()
        return {
            "m1": m1,
            "m2": m2,
            "state": state,
            "start_time": start_time,
            "end_time": end_time,
        }

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        if self._compile_version == "None":
            return (yield from self.compile_version_None(context))
        else:
            raise ValueError


@dataclass
class BqcResult:
    dist_0: float
    dist_1: float
    fail_rate: float
    state: Qubit
    m1: int


def expected_state(alpha: float, beta: float):
    expected = qubitapi.create_qubits(1)[0]

    if (alpha, beta) == (0, 0):
        qubitapi.assign_qstate(expected, ketstates.h0)
    elif (alpha, beta) == (0, PI_OVER_2):
        qubitapi.assign_qstate(expected, ketstates.h0)
    elif (alpha, beta) == (0, PI):
        qubitapi.assign_qstate(expected, ketstates.h0)
    elif (alpha, beta) == (0, -PI_OVER_2):
        qubitapi.assign_qstate(expected, ketstates.h0)

    elif (alpha, beta) == (PI_OVER_2, 0):
        qubitapi.assign_qstate(expected, ketstates.y0)
    elif (alpha, beta) == (PI_OVER_2, PI_OVER_2):
        qubitapi.assign_qstate(expected, ketstates.s0)
    elif (alpha, beta) == (PI_OVER_2, PI):
        qubitapi.assign_qstate(expected, ketstates.y1)
    elif (alpha, beta) == (PI_OVER_2, -PI_OVER_2):
        qubitapi.assign_qstate(expected, ketstates.s1)

    elif (alpha, beta) == (PI, 0):
        qubitapi.assign_qstate(expected, ketstates.h1)
    elif (alpha, beta) == (PI, PI_OVER_2):
        qubitapi.assign_qstate(expected, ketstates.h1)
    elif (alpha, beta) == (PI, PI):
        qubitapi.assign_qstate(expected, ketstates.h1)
    elif (alpha, beta) == (PI, -PI_OVER_2):
        qubitapi.assign_qstate(expected, ketstates.h1)

    elif (alpha, beta) == (-PI_OVER_2, 0):
        qubitapi.assign_qstate(expected, ketstates.y1)
    elif (alpha, beta) == (-PI_OVER_2, PI_OVER_2):
        qubitapi.assign_qstate(expected, ketstates.s1)
    elif (alpha, beta) == (-PI_OVER_2, PI):
        qubitapi.assign_qstate(expected, ketstates.y0)
    elif (alpha, beta) == (-PI_OVER_2, -PI_OVER_2):
        qubitapi.assign_qstate(expected, ketstates.s0)

    return expected


def computation_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
    theta2: float = 0.0,
    r1: int = 0,
    r2: int = 0,
    log_level: str = "WARNING",
    compile_version: str = "None",
) -> BqcResult:
    LogManager.set_log_level(log_level)

    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=False,
        dummy=-1,
        theta1=theta1,
        theta2=theta2,
        r1=r1,
        r2=r2,
        compile_version=compile_version,
    )
    server_program = ServerProgram(compile_version=compile_version)

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times=num_times
    )

    durations = []
    for c_result, s_result in zip(client_results, server_results):
        start_time = min(c_result["start_time"], s_result["start_time"])
        end_time = max(c_result["end_time"], s_result["end_time"])
        durations.append(end_time - start_time)

    expected = expected_state(alpha, beta)
    expected_rot_z = expected_state(alpha, beta)
    qubitapi.operate(expected_rot_z, qubitapi.ops.Z)

    # print(f"expected: {qubitapi.reduced_dm(expected)}")

    fidelities = [
        qubitapi.fidelity(
            expected if r["m1"] == 0 else expected_rot_z, r["state"], squared=True
        )
        for r in server_results
    ]
    print(f"fidelities: {fidelities}")
    return fidelities, durations


def trap_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
    theta2: float = 0.0,
    dummy: int = 1,
    compile_version: str = "None",
) -> BqcResult:
    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=True,
        dummy=dummy,
        theta1=theta1,
        theta2=theta2,
        r1=0,
        r2=0,
        compile_version=compile_version,
    )
    server_program = ServerProgram(compile_version=compile_version)

    client_results, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times=num_times
    )

    p1s = [result["p1"] for result in client_results]
    p2s = [result["p2"] for result in client_results]
    m1s = [result["m1"] for result in server_results]
    m2s = [result["m2"] for result in server_results]

    assert dummy in [1, 2]
    if dummy == 1:
        num_fails = len([(p, m) for (p, m) in zip(p1s, m2s) if p != m])
    else:
        num_fails = len([(p, m) for (p, m) in zip(p2s, m1s) if p != m])

    frac_fail = round(num_fails / num_times, 3)
    # print(f"fail rate: {frac_fail}")

    durations = []
    for c_result, s_result in zip(client_results, server_results):
        start_time = min(c_result["start_time"], s_result["start_time"])
        end_time = max(c_result["end_time"], s_result["end_time"])
        durations.append(end_time - start_time)

    last_m1 = m1s[-1]
    # return BqcResult(dist_0=-1, dist_1=-1, fail_rate=frac_fail, state=None, m1=last_m1)
    return frac_fail, durations


def test_perfect_config():
    LogManager.set_log_level("WARNING")

    cfg = StackNetworkConfig(
        stacks=[
            StackConfig.perfect_generic_config("client"),
            StackConfig.perfect_generic_config("server"),
        ],
        links=[LinkConfig.perfect_config("client", "server")],
    )

    def test_computation_round(alpha: float, beta: float, expected: Qubit):
        # Effective computation: Z^(m1) H Rz(beta) H Rz(alpha) |+>

        result = computation_round(cfg, 1, alpha=alpha, beta=beta)
        q = qubitapi.create_qubits(1)[0]
        qubitapi.assign_qstate(q, expected)
        if result.m1 == 1:
            qubitapi.operate(q, operators.Z)
        assert qubitapi.fidelity(q, result.state, squared=True) > 0.99

    test_computation_round(0, 0, ketstates.h0)
    test_computation_round(0, PI_OVER_2, ketstates.h0)
    test_computation_round(0, PI, ketstates.h0)
    test_computation_round(0, -PI_OVER_2, ketstates.h0)
    test_computation_round(PI_OVER_2, 0, ketstates.y0)
    test_computation_round(PI_OVER_2, PI_OVER_2, ketstates.s0)
    test_computation_round(PI_OVER_2, PI, ketstates.y1)
    test_computation_round(PI_OVER_2, -PI_OVER_2, ketstates.s1)
    test_computation_round(PI, 0, ketstates.h1)
    test_computation_round(PI, PI_OVER_2, ketstates.h1)
    test_computation_round(PI, PI, ketstates.h1)
    test_computation_round(PI, -PI_OVER_2, ketstates.h1)
    test_computation_round(-PI_OVER_2, 0, ketstates.y1)
    test_computation_round(-PI_OVER_2, PI_OVER_2, ketstates.s1)
    test_computation_round(-PI_OVER_2, PI, ketstates.y0)
    test_computation_round(-PI_OVER_2, -PI_OVER_2, ketstates.s0)

    num_times = 10

    # NOTE: alpha and beta are not used in the trap rounds
    for theta1 in [0, PI_OVER_2, PI, -PI_OVER_2]:
        for theta2 in [0, PI_OVER_2, PI, -PI_OVER_2]:
            for dummy in [1, 2]:
                result = trap_round(
                    cfg, num_times, theta1=theta1, theta2=theta2, dummy=dummy
                )
                assert result.fail_rate == 0


def n_trap_rounds(
    cfg_file: str,
    n: int = 1,
    theta1: float = 0.0,
    theta2: float = 0.0,
    dummy: int = 1,
    log_level: str = "WARNING",
    compile_version: str = "None",
) -> None:
    LogManager.set_log_level(log_level)

    cfg = StackNetworkConfig.from_file(cfg_file)
    error_rate, durations = trap_round(
        cfg,
        n,
        theta1=theta1,
        theta2=theta2,
        dummy=dummy,
        compile_version=compile_version,
    )
    print(f"error rate: {error_rate}")
