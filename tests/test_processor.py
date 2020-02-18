import pytest
import logging

from netqasm.processor import Processor, OutputData


@pytest.mark.parametrize("subroutine, expected_output", [
    (
        """
        # NETQASM 1.0
        # APPID 0
        # DEFINE op h
        # DEFINE q @0
        creg(1) m
        qreg(1) q!
        init q!
        op! q! // this is a comment
        meas q! m
        output m
        beq m[0] 0 EXIT
        x q!
        EXIT:
        // this is also a comment
        """,
        [OutputData(1, [0])],
    ),
    (
        """
        # NETQASM 1.0
        # APPID 0
        creg(1) m
        LOOP:
        beq m[0] 10 EXIT
        add m[0] m[0] 1
        beq 0 0 LOOP
        EXIT:
        output m
        // this is also a comment
        """,
        [OutputData(0, [10])],
    ),
])
def test_processor(subroutine, expected_output):
    logging.getLogger().setLevel(logging.DEBUG)
    print(subroutine)

    processor = Processor()
    processor.execute_subroutine(subroutine=subroutine)
    output_data = processor.output_data
    print(f"Out-data: {output_data}")
    assert output_data == expected_output
