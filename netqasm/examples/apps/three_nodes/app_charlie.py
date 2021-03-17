from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection

from netqasm.logging.glob import get_netqasm_logger

logger = get_netqasm_logger()


def main(app_config):
    epr_socket_alice = EPRSocket(
        remote_app_name="alice",
        epr_socket_id=0,
        remote_epr_socket_id=1
    )
    epr_socket_bob = EPRSocket(
        remote_app_name="bob",
        epr_socket_id=1,
        remote_epr_socket_id=1
    )

    charlie = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket_alice, epr_socket_bob]
    )
    with charlie:
        epr_alice = epr_socket_alice.recv()[0]
        m_alice = epr_alice.measure()

        charlie.flush()

        epr_bob = epr_socket_bob.recv()[0]
        m_bob = epr_bob.measure()

    logger.info(f"charlie:  m_alice:  {m_alice}")
    logger.info(f"charlie:  m_bob:    {m_bob}")
