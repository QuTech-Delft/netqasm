from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection

from netqasm.logging import get_netqasm_logger

logger = get_netqasm_logger()


def main(app_config):
    epr_socket_alice = EPRSocket(
        remote_node_name="alice",
        epr_socket_id=0,
        remote_epr_socket_id=1
    )
    epr_socket_bob = EPRSocket(
        remote_node_name="bob",
        epr_socket_id=1,
        remote_epr_socket_id=1
    )

    node_name = app_config.node_name
    if node_name is None:
        node_name = app_config.app_name

    charlie = NetQASMConnection(
        node_name=node_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket_alice, epr_socket_bob]
    )
    with charlie:
        epr_alice = epr_socket_alice.recv()[0]
        m_alice = epr_alice.measure()

        # Flush but don't wait since we don't know which EPR we get first
        charlie.flush(block=False)

        epr_bob = epr_socket_bob.recv()[0]
        m_bob = epr_bob.measure()

        # Flush second subroutine and wait for first
        charlie.flush()
        charlie.block()

    logger.info(f"charlie:  m_alice:  {m_alice}")
    logger.info(f"charlie:  m_bob:    {m_bob}")


if __name__ == "__main__":
    main()
