import math
from typing import Any, Dict, Union

from netqasm.lang.operand import Template
from netqasm.logging.glob import set_log_level
from netqasm.runtime.application import default_app_instance
from netqasm.sdk.epr_socket import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket, simulate_application
from netqasm.sdk.futures import Future, RegFuture

PRECOMPILE: bool = True


def run_client(alpha: float, theta1: float, r1: int, use_rsp: bool) -> Dict[str, Any]:
    epr_socket = EPRSocket("server")
    csocket = Socket("client", "server")
    conn = NetQASMConnection("client", epr_sockets=[epr_socket])

    with conn:
        outcome: Union[Future, RegFuture]

        if use_rsp:
            # Compute the final rotation angle based on theta1 to be a multiple of pi / 16 in the
            # range [0, 32)
            t1 = (16 + round(theta1 * 16 / math.pi)) % 32
            result = epr_socket.create_rsp(rotations_local=(0, 8, t1))[0]
            outcome = result.raw_measurement_outcome
        else:
            epr = epr_socket.create_keep()[0]
            epr.rot_Z(angle=theta1)
            epr.H()
            outcome = epr.measure(store_array=False)

    p1 = int(outcome)

    delta1 = alpha - theta1 + (p1 + r1) * math.pi

    csocket.send(str(delta1))

    return {"p1": p1}


def run_server(use_rsp: bool) -> Dict[str, Any]:
    epr_socket = EPRSocket("client")
    csocket = Socket("server", "client")
    conn = NetQASMConnection("server", epr_sockets=[epr_socket])

    with conn:
        if use_rsp:
            epr = epr_socket.recv_rsp()[0]
        else:
            epr = epr_socket.recv_keep()[0]

        conn.flush()

        if PRECOMPILE:
            epr.rot_Z(n=Template("delta1_numerator"), d=4)
            epr.H()
            outcome = epr.measure(store_array=False)
            subroutine = conn.compile()

            delta1 = float(csocket.recv())
            numerator = int(delta1 / (math.pi / 16))
            subroutine.instantiate(
                conn.app_id, arguments={"delta1_numerator": numerator}
            )
            conn.commit_subroutine(subroutine)

        else:
            delta1 = float(csocket.recv())
            epr.rot_Z(angle=delta1)

            epr.H()
            outcome = epr.measure(store_array=False)

    m2 = int(outcome)

    return {"m2": m2}


if __name__ == "__main__":
    set_log_level("INFO")

    app_instance = default_app_instance(
        [
            ("client", run_client),
            ("server", run_server),
        ]
    )

    use_rsp = False
    app_instance.program_inputs = {
        "client": {"alpha": 0, "theta1": 0, "r1": 0, "use_rsp": use_rsp},
        "server": {"use_rsp": use_rsp},
    }
    results = simulate_application(
        app_instance,
        use_app_config=False,
    )
    print(results)
