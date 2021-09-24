import logging

import pytest

from netqasm.backend.executor import Executor
from netqasm.lang.encoding import RegisterName
from netqasm.lang.operand import Register
from netqasm.lang.parsing import parse_text_subroutine
from netqasm.logging.glob import set_log_level
from netqasm.sdk.shared_memory import SharedMemoryManager


@pytest.mark.parametrize(
    "subroutine_str, expected_register, expected_output",
    [
        (
            """
        # NETQASM 1.0
        # APPID 0
        # DEFINE op h
        # DEFINE q Q0
        # DEFINE m M0
        set $q 0
        qalloc $q
        init $q
        $op $q // this is a comment
        meas $q $m
        // this is also a comment
        beq $m 0 EXIT
        x $q
        EXIT:
        qfree $q
        """,
            Register(RegisterName.M, 0),
            0,
        ),
        (
            """
        # NETQASM 1.0
        # APPID 0
        # DEFINE i R0
        set $i 0
        LOOP:
        beq $i 10 EXIT
        add $i $i 1
        beq 0 0 LOOP
        EXIT:
        """,
            Register(RegisterName.R, 0),
            10,
        ),
    ],
)
def test_executor(subroutine_str, expected_register, expected_output):
    set_log_level(logging.DEBUG)
    subroutine = parse_text_subroutine(subroutine_str)

    print(subroutine)

    SharedMemoryManager.reset_memories()

    app_id = 0
    executor = Executor()
    # Consume the generator
    executor.init_new_application(app_id=app_id, max_qubits=1)
    for _ in range(10):
        list(executor.execute_subroutine(subroutine=subroutine))
        assert executor._get_register(app_id, expected_register) == expected_output


@pytest.mark.parametrize(
    "subroutine_str, error_type, error_line",
    [
        (
            """
        # NETQASM 0.0
        # APPID 0
        set R0 1
        add R0 R0 R0
        set R1 0
        addm R0 R0 R0 R1
        """,
            RuntimeError,
            3,
        ),
        (
            """
        # NETQASM 0.0
        # APPID 0
        set Q0 0
        qalloc Q0
        qalloc Q0
        """,
            RuntimeError,
            2,
        ),
    ],
)
def test_failing_executor(subroutine_str, error_type, error_line):
    set_log_level(logging.DEBUG)
    subroutine = parse_text_subroutine(subroutine_str)

    print(subroutine)

    SharedMemoryManager.reset_memories()

    app_id = 0
    executor = Executor()
    executor.init_new_application(app_id=app_id, max_qubits=1)

    with pytest.raises(error_type) as exc:
        executor.consume_execute_subroutine(subroutine=subroutine)

    print(f"Exception: {exc.value}")
    assert str(exc.value).startswith(f"At line {error_line}")


if __name__ == "__main__":
    subroutine_str = """
        # NETQASM 1.0
        # APPID 0
        # DEFINE i R0
        set $i 0
        LOOP:
        beq $i 10 EXIT
        add $i $i 1
        beq 0 0 LOOP
        EXIT:
        """
    expected_register = Register(RegisterName.R, 0)
    expected_output = 10

    test_executor(subroutine_str, expected_register, expected_output)

    subroutine_str = """
        # NETQASM 0.0
        # APPID 0
        set R0 1
        add R0 R0 R0
        set R1 0
        addm R0 R0 R0 R1
        """
    error_type = RuntimeError
    error_line = 3

    test_failing_executor(subroutine_str, error_type, error_line)
