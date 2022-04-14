from netqasm.qlink_compat import BellState
from netqasm.sdk.build_epr import EprMeasBasis, EprMeasureResult, basis_to_rotation
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.futures import Future


def create_measure_result(
    outcome: int,
    basis: EprMeasBasis,
    bell_state: BellState,
    expect_phi_plus: bool,
) -> EprMeasureResult:
    conn = DebugConnection("test")

    raw_outcome = Future(conn, 0, 0)
    raw_outcome._value = outcome

    remote_node = Future(conn, 1, 0)
    remote_node._value = 0

    duration = Future(conn, 2, 0)
    duration._value = 1000

    raw_bell_state = Future(conn, 3, 0)
    raw_bell_state._value = bell_state.value

    return EprMeasureResult(
        raw_measurement_outcome=raw_outcome,
        measurement_basis_local=basis_to_rotation(basis),
        measurement_basis_remote=basis_to_rotation(basis),
        post_process=expect_phi_plus,
        remote_node_id=remote_node,
        generation_duration=duration,
        raw_bell_state=raw_bell_state,
    )


def test_x_meas():
    for m in [0, 1]:
        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.X,
            bell_state=BellState.PHI_PLUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m

        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.X,
            bell_state=BellState.PHI_MINUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m ^ 1

        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.X,
            bell_state=BellState.PSI_PLUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m

        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.X,
            bell_state=BellState.PSI_MINUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m ^ 1


def test_y_meas():
    for m in [0, 1]:
        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.Y,
            bell_state=BellState.PHI_PLUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m

        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.Y,
            bell_state=BellState.PHI_MINUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m ^ 1

        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.Y,
            bell_state=BellState.PSI_PLUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m ^ 1

        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.Y,
            bell_state=BellState.PSI_MINUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m


def test_z_meas():
    for m in [0, 1]:
        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.Z,
            bell_state=BellState.PHI_PLUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m

        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.Z,
            bell_state=BellState.PHI_MINUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m

        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.Z,
            bell_state=BellState.PSI_PLUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m ^ 1

        result = create_measure_result(
            outcome=m,
            basis=EprMeasBasis.Z,
            bell_state=BellState.PSI_MINUS,
            expect_phi_plus=True,
        )
        assert result.measurement_outcome == m ^ 1


if __name__ == "__main__":
    test_x_meas()
    test_y_meas()
    test_z_meas()
