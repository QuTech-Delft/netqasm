import pytest
import logging

from netqasm.processor import Processor
from netqasm.parser import Parser


@pytest.mark.parametrize("subroutine_str, expected_address, expected_output", [
    (
        """
        # NETQASM 1.0
        # APPID 0
        # DEFINE op h
        # DEFINE q q0
        qalloc q!
        init q!
        op! q! // this is a comment
        meas q! m
        // this is also a comment
        beq m 0 EXIT
        x q!
        EXIT:
        qfree q!
        """,
        0,
        0,
    ),
    (
        """
        # NETQASM 1.0
        # APPID 0
        store m 0
        LOOP:
        beq m 10 EXIT
        add m m 1
        beq 0 0 LOOP
        EXIT:
        """,
        0,
        10,
    ),
])
def test_processor(subroutine_str, expected_address, expected_output):
    logging.basicConfig(level=logging.DEBUG)
    subroutine = Parser(subroutine_str).subroutine

    app_id = 0
    processor = Processor()
    processor.init_new_application(app_id=app_id, max_qubits=1)
    for _ in range(10):
        list(processor.execute_subroutine(subroutine=subroutine))
        assert processor._shared_memories[app_id][expected_address] == expected_output
