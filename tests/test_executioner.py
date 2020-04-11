import pytest
import logging

from netqasm.encoding import RegisterName
from netqasm.subroutine import Register
from netqasm.executioner import Executioner
from netqasm.parsing import parse_text_subroutine


@pytest.mark.parametrize("subroutine_str, expected_register, expected_output", [
    (
        """
        # NETQASM 1.0
        # APPID 0
        # DEFINE op h
        # DEFINE q Q0
        # DEFINE m M0
        set q! 0
        qalloc q!
        init q!
        op! q! // this is a comment
        meas q! m!
        // this is also a comment
        beq m! 0 EXIT
        x q!
        EXIT:
        qfree q!
        """,
        Register(RegisterName.M, 0),
        0,
    ),
    (
        """
        # NETQASM 1.0
        # APPID 0
        # DEFINE i R0
        set i! 0
        LOOP:
        beq i! 10 EXIT
        add i! i! 1
        beq 0 0 LOOP
        EXIT:
        """,
        Register(RegisterName.R, 0),
        10,
    ),
])
def test_executioner(subroutine_str, expected_register, expected_output):
    logging.basicConfig(level=logging.DEBUG)
    subroutine = parse_text_subroutine(subroutine_str)

    print(subroutine)

    app_id = 0
    executioner = Executioner()
    executioner.init_new_application(app_id=app_id, max_qubits=1)
    for _ in range(10):
        list(executioner.execute_subroutine(subroutine=subroutine))
        assert executioner._get_register(app_id, expected_register) == expected_output
