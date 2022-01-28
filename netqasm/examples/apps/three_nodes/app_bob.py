from netqasm.logging.glob import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection

logger = get_netqasm_logger()


def main(app_config=None):
    epr_socket_alice = EPRSocket(
        remote_app_name="alice", epr_socket_id=0, remote_epr_socket_id=0
    )
    epr_socket_charlie = EPRSocket(
        remote_app_name="charlie", epr_socket_id=1, remote_epr_socket_id=1
    )

    bob = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket_alice, epr_socket_charlie],
    )
    with bob:
        epr_alice = epr_socket_alice.recv_keep()[0]
        m_alice = epr_alice.measure()

        bob.flush()

        epr_charlie = epr_socket_charlie.create_keep()[0]
        m_charlie = epr_charlie.measure()

    logger.info(f"bob:      m_alice:  {m_alice}")
    logger.info(f"bob:      m_charlie:{m_charlie}")


if __name__ == "__main__":
    main()
