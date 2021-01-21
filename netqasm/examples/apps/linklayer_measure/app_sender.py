# from netqasm.sdk import Qubit
from netqasm.sdk.epr_socket import EPRSocket, EPRType, EPRMeasBasis
from netqasm.sdk.external import NetQASMConnection
# from netqasm.sdk.futures import Register


def main(app_config=None, phi=0., theta=0.):
    log_config = app_config.log_config

    epr_socket = EPRSocket("receiver")

    sender = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket],
        return_arrays=False,
    )

    num_pairs = 10

    # with sender:
    #     outcomes = sender.new_array(num_pairs)
    #     ones_count = sender.new_register()

    #     def post_create(conn, q, pair):
    #         outcome = outcomes.get_future_index(pair)
    #         m = q.measure(outcome)
    #         ones_count.add(m)

    #     # Create EPR pair
    #     epr_socket.create(
    #         number=num_pairs,
    #         tp=EPRType.K,
    #         sequential=True,
    #         post_routine=post_create,
    #     )
    # print(f"ones_count EPRType.K: {ones_count}")

    with sender:
        ones_count = sender.new_register()

        # rotx1 = 17
        # roty = 5
        # rotx2 = 26
        # outcomes = epr_socket.create(number=num_pairs, tp=EPRType.M, rotations_local=(
        #     rotx1, roty, rotx2), rotations_remote=(0, 0, 0))

        # for outcome in outcomes:
        #     ones_count.add(outcome.measurement_outcome)

        outcomes = epr_socket.create(number=num_pairs, tp=EPRType.M,
                                     basis_local=EPRMeasBasis.Y, basis_remote=EPRMeasBasis.Y)

        for outcome in outcomes:
            ones_count.add(outcome.measurement_outcome)

    print(ones_count)


if __name__ == "__main__":
    main()
