from netqasm.sdk.epr_socket import EPRMeasBasis, EPRSocket
from netqasm.sdk.external import NetQASMConnection


def main(app_config=None):
    log_config = app_config.log_config

    epr_socket = EPRSocket("server")

    client = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket],
        # return_arrays=False,
    )

    num_pairs = 10

    with client:
        outcomes = epr_socket.create_measure(
            number=num_pairs,
            basis_local=EPRMeasBasis.Y,
            basis_remote=EPRMeasBasis.Y,
        )

    for outcome in outcomes:
        print(f"Client: {outcome.measurement_outcome}")


if __name__ == "__main__":
    main()
