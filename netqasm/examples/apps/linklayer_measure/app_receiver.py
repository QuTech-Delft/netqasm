from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket, get_qubit_state
from netqasm.sdk.toolbox.sim_states import qubit_from, to_dm, get_fidelity
from netqasm.sdk.epr_socket import EPRType


def main(app_config=None):
    log_config = app_config.log_config

    epr_socket = EPRSocket("sender")

    receiver = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket]
    )

    num_pairs = 10

    # with receiver:
    #     outcomes = receiver.new_array(num_pairs)
    #     ones_count = receiver.new_register()

    #     def post_create(conn, q, pair):
    #         outcome = outcomes.get_future_index(pair)
    #         m = q.measure(outcome)
    #         ones_count.add(m)

    #     epr_socket.recv(
    #         number=num_pairs,
    #         tp=EPRType.K,
    #         sequential=True,
    #         post_routine=post_create,
    #     )

    # print(f"ones_count EPRType.K: {ones_count}")

    with receiver:
        ones_count = receiver.new_register()
        outcomes = epr_socket.recv(number=num_pairs, tp=EPRType.M)
        # outcomes = epr_socket.recv(number=num_pairs, tp=EPRType.M)

        for outcome in outcomes:
            ones_count.add(outcome.measurement_outcome)

    # print(ones_count)


if __name__ == "__main__":
    main()
