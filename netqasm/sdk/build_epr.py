from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple

from netqasm.qlink_compat import BellState, EPRRole, EPRType, RandomBasis, TimeUnit
from netqasm.sdk.build_types import T_PostRoutine
from netqasm.sdk.futures import Array, Future, NoValueError


class EprMeasBasis(Enum):
    X = 0
    Y = auto()
    Z = auto()
    MX = auto()
    MY = auto()
    MZ = auto()


@dataclass
class EntRequestParams:
    remote_node_id: int
    epr_socket_id: int
    number: int
    post_routine: Optional[T_PostRoutine]
    sequential: bool
    time_unit: TimeUnit = TimeUnit.MICRO_SECONDS
    max_time: int = 0
    expect_phi_plus: bool = True
    min_fidelity_all_at_end: Optional[int] = None
    max_tries: Optional[int] = None
    random_basis_local: Optional[RandomBasis] = None
    random_basis_remote: Optional[RandomBasis] = None
    rotations_local: Tuple[int, int, int] = (0, 0, 0)
    rotations_remote: Tuple[int, int, int] = (0, 0, 0)


# Indices of Create Request arguments in serialized NetQASM array
SER_CREATE_IDX_TYPE = 0
SER_CREATE_IDX_NUMBER = 1
SER_CREATE_IDX_RANDOM_BASIS_LOCAL = 2
SER_CREATE_IDX_RANDOM_BASIS_REMOTE = 3
SER_CREATE_IDX_MINIMUM_FIDELITY = 4
SER_CREATE_IDX_TIME_UNIT = 5
SER_CREATE_IDX_MAX_TIME = 6
SER_CREATE_IDX_PRIORITY = 7
SER_CREATE_IDX_ATOMIC = 8
SER_CREATE_IDX_CONSECUTIVE = 9
SER_CREATE_IDX_PROBABILITY_DIST_LOCAL1 = 10
SER_CREATE_IDX_PROBABLIITY_DIST_LOCAL2 = 11
SER_CREATE_IDX_PROBABILITY_DIST_REMOTE1 = 12
SER_CREATE_IDX_PROBABLIITY_DIST_REMOTE2 = 13
SER_CREATE_IDX_ROTATION_X_LOCAL1 = 14
SER_CREATE_IDX_ROTATION_Y_LOCAL = 15
SER_CREATE_IDX_ROTATION_X_LOCAL2 = 16
SER_CREATE_IDX_ROTATION_X_REMOTE1 = 17
SER_CREATE_IDX_ROTATION_Y_REMOTE = 18
SER_CREATE_IDX_ROTATION_X_REMOTE2 = 19

# Length of NetQASM array for serialized Create Requests.
SER_CREATE_LEN = SER_CREATE_IDX_ROTATION_X_REMOTE2 + 1

# Indices of EPR Keep results in serialized NetQASM array
SER_RESPONSE_KEEP_IDX_TYPE = 0
SER_RESPONSE_KEEP_IDX_CREATE_ID = 1
SER_RESPONSE_KEEP_IDX_LOGICAL_QUBIT_ID = 2
SER_RESPONSE_KEEP_IDX_DIRECTONIALITY_FLAG = 3
SER_RESPONSE_KEEP_IDX_SEQUENCE_NUMBER = 4
SER_RESPONSE_KEEP_IDX_PURPOSE_ID = 5
SER_RESPONSE_KEEP_IDX_REMOTE_NODE_ID = 6
SER_RESPONSE_KEEP_IDX_GOODNESS = 7
SER_RESPONSE_KEEP_IDX_GOODNESS_TIME = 8
SER_RESPONSE_KEEP_IDX_BELL_STATE = 9

# Length of NetQASM array for EPR Keep results.
SER_RESPONSE_KEEP_LEN = SER_RESPONSE_KEEP_IDX_BELL_STATE + 1

# Indices of EPR Measure results in serialized NetQASM array
SER_RESPONSE_MEASURE_IDX_TYPE = 0
SER_RESPONSE_MEASURE_IDX_CREATE_ID = 1
SER_RESPONSE_MEASURE_IDX_MEASUREMENT_OUTCOME = 2
SER_RESPONSE_MEASURE_IDX_MEASUREMENT_BASIS = 3
SER_RESPONSE_MEASURE_IDX_DIRECTONIALITY_FLAG = 4
SER_RESPONSE_MEASURE_IDX_SEQUENCE_NUMBER = 5
SER_RESPONSE_MEASURE_IDX_PURPOSE_ID = 6
SER_RESPONSE_MEASURE_IDX_REMOTE_NODE_ID = 7
SER_RESPONSE_MEASURE_IDX_GOODNESS = 8
SER_RESPONSE_MEASURE_IDX_BELL_STATE = 9

# Length of NetQASM array for EPR Measure results.
SER_RESPONSE_MEASURE_LEN = SER_RESPONSE_MEASURE_IDX_BELL_STATE + 1


def serialize_request(tp: EPRType, params: EntRequestParams) -> List[Optional[int]]:
    """Convert an EntRequestParams object into a list of values that can be put
    in a NetQASM array."""
    array: List[Optional[int]] = [None for i in range(SER_CREATE_LEN)]

    array[SER_CREATE_IDX_TYPE] = tp.value
    array[SER_CREATE_IDX_NUMBER] = params.number

    # Only when max_time is 0, explicitly initialize the relavant array elements.
    # If it is max_time 0, these array element will be None.
    if params.max_time != 0:
        array[SER_CREATE_IDX_TIME_UNIT] = params.time_unit.value
        array[SER_CREATE_IDX_MAX_TIME] = params.max_time

    if tp == EPRType.M or tp == EPRType.R:
        # Only write when non-zero.
        if params.rotations_local != (0, 0, 0):
            array[SER_CREATE_IDX_ROTATION_X_LOCAL1] = params.rotations_local[0]
            array[SER_CREATE_IDX_ROTATION_Y_LOCAL] = params.rotations_local[1]
            array[SER_CREATE_IDX_ROTATION_X_LOCAL2] = params.rotations_local[2]
        if params.rotations_remote != (0, 0, 0):
            array[SER_CREATE_IDX_ROTATION_X_REMOTE1] = params.rotations_remote[0]
            array[SER_CREATE_IDX_ROTATION_Y_REMOTE] = params.rotations_remote[1]
            array[SER_CREATE_IDX_ROTATION_X_REMOTE2] = params.rotations_remote[2]
        if params.random_basis_local:
            array[SER_CREATE_IDX_RANDOM_BASIS_LOCAL] = params.random_basis_local.value
        if params.random_basis_remote:
            array[SER_CREATE_IDX_RANDOM_BASIS_REMOTE] = params.random_basis_remote.value

    return array


def deserialize_epr_keep_results(
    request: EntRequestParams, array: Array
) -> List[EprKeepResult]:
    """Convert values in a NetQASM array into EprKeepResult objects."""
    assert len(array) == request.number * SER_RESPONSE_KEEP_LEN
    results: List[EprKeepResult] = []
    for i in range(request.number):
        base = i * SER_RESPONSE_KEEP_LEN
        results.append(
            EprKeepResult(
                qubit_id=array.get_future_index(
                    base + SER_RESPONSE_KEEP_IDX_LOGICAL_QUBIT_ID
                ),
                remote_node_id=array.get_future_index(
                    base + SER_RESPONSE_KEEP_IDX_REMOTE_NODE_ID
                ),
                generation_duration=array.get_future_index(
                    base + SER_RESPONSE_KEEP_IDX_GOODNESS
                ),
                raw_bell_state=array.get_future_index(
                    base + SER_RESPONSE_KEEP_IDX_BELL_STATE
                ),
            )
        )
    return results


def deserialize_epr_measure_results(
    request: EntRequestParams, array: Array, role: EPRRole
) -> List[EprMeasureResult]:
    """Convert values in a NetQASM array into EprMeasureResult objects."""
    assert len(array) == request.number * SER_RESPONSE_MEASURE_LEN
    results: List[EprMeasureResult] = []
    for i in range(request.number):
        base = i * SER_RESPONSE_MEASURE_LEN
        results.append(
            EprMeasureResult(
                raw_measurement_outcome=array.get_future_index(
                    base + SER_RESPONSE_MEASURE_IDX_MEASUREMENT_OUTCOME
                ),
                measurement_basis_local=request.rotations_local,
                measurement_basis_remote=request.rotations_remote,
                post_process=(request.expect_phi_plus and role == EPRRole.RECV),
                remote_node_id=array.get_future_index(
                    base + SER_RESPONSE_MEASURE_IDX_REMOTE_NODE_ID
                ),
                generation_duration=array.get_future_index(
                    base + SER_RESPONSE_MEASURE_IDX_GOODNESS
                ),
                raw_bell_state=array.get_future_index(
                    base + SER_RESPONSE_MEASURE_IDX_BELL_STATE
                ),
            )
        )
    return results


@dataclass
class EprKeepResult:
    qubit_id: Future
    remote_node_id: Future
    generation_duration: Future
    raw_bell_state: Future

    @property
    def bell_state(self) -> BellState:
        assert self.raw_bell_state.value is not None
        return BellState(self.raw_bell_state.value)


def rotation_to_basis(rotations: Tuple[int, int, int]) -> Optional[EprMeasBasis]:
    if rotations == (0, 24, 0):
        return EprMeasBasis.X
    elif rotations == (8, 0, 0):
        return EprMeasBasis.Y
    elif rotations == (0, 0, 0):
        return EprMeasBasis.Z
    elif rotations == (0, 8, 0):
        return EprMeasBasis.MX
    elif rotations == (24, 0, 0):
        return EprMeasBasis.MY
    elif rotations == (16, 0, 0):
        return EprMeasBasis.MZ
    else:
        return None


def basis_to_rotation(basis: EprMeasBasis) -> Tuple[int, int, int]:
    if basis == EprMeasBasis.X:
        return (0, 24, 0)
    elif basis == EprMeasBasis.Y:
        return (8, 0, 0)
    elif basis == EprMeasBasis.Z:
        return (0, 0, 0)
    elif basis == EprMeasBasis.MX:
        return (0, 8, 0)
    elif basis == EprMeasBasis.MY:
        return (24, 0, 0)
    elif basis == EprMeasBasis.MZ:
        return (16, 0, 0)
    else:
        assert False, f"invalid EprMeasBasis {basis}"


@dataclass
class EprMeasureResult:
    raw_measurement_outcome: Future
    measurement_basis_local: Tuple[int, int, int]
    measurement_basis_remote: Tuple[int, int, int]
    post_process: bool
    remote_node_id: Future
    generation_duration: Future
    raw_bell_state: Future

    @property
    def measurement_outcome(self) -> int:
        """Get the measurement outcome, possibly post-processed.

        The outcome is post-processed only if the EPR create request indicated
        that the produced Bell state should be the Phi+ state, while the physically
        produced Bell state actually was another Bell state. In this case, the outcome
        is post-processed such that the statistics are *as if* the Phi+ state was
        produced and measured.

        Post-processing involves classical bit flips based on the physical Bell
        state produced and the measurement basis specified. If a Phi+ (or Phi_00)
        Bell state was actually produced physically, no post-processing is applied.
        If another Bell state was produced, a bit flip may be applied such that
        it looks like the Phi+ state was produced after all.

        If no post-processing is desired, use the `raw_measurement_outcome` instead.

        :return: post-processed measurement outcome
        """
        try:
            if not self.post_process:
                return int(self.raw_measurement_outcome)

            # else
            local = rotation_to_basis(self.measurement_basis_local)
            remote = rotation_to_basis(self.measurement_basis_remote)
            if local != remote:
                raise RuntimeError(
                    f"The local and remote measurement bases are not equal "
                    f"(local={local}, remote={remote}. Post-processed measurement "
                    f"outcome is not available. Use `raw_measurement_outcome` in "
                    f"combination with `measurement_basis_local` to interpret the "
                    f"outcome instead."
                )
            # We have local == remote.
            if local is None:  # not one of X, Y, Z
                raise RuntimeError(
                    f"The measurement basis is not one of X, Y, or Z (instead it is "
                    f"{local}. Post-processed measurement outcome is not available. "
                    f"Use `raw_measurement_outcome in combination with "
                    f"`measurement_basis_local` to interpet the outcome instead."
                )

            # This may raise a NoValueError
            m = int(self.raw_measurement_outcome)
            assert m == 0 or m == 1

            # Correct for Bell flips.
            if self.bell_state == BellState.PHI_MINUS:
                # correct for Z-gate applied to Phi+
                if local in [
                    EprMeasBasis.X,
                    EprMeasBasis.MX,
                    EprMeasBasis.Y,
                    EprMeasBasis.MY,
                ]:
                    m = m ^ 1
            elif self.bell_state == BellState.PSI_PLUS:
                # correct for X-gate applied to Phi+
                if local in [
                    EprMeasBasis.Y,
                    EprMeasBasis.MY,
                    EprMeasBasis.Z,
                    EprMeasBasis.MZ,
                ]:
                    m = m ^ 1
            elif self.bell_state == BellState.PSI_MINUS:
                # correct for X-gate and Z-gate applied to Phi+
                if local in [
                    EprMeasBasis.X,
                    EprMeasBasis.MX,
                    EprMeasBasis.Z,
                    EprMeasBasis.MZ,
                ]:
                    m = m ^ 1

            return m

        except NoValueError:
            raise ValueError(
                "The `measurement_outcome` property can only be used after "
                "the subroutine that produces this outcome has been flushed. "
                "This is because classical post-processing is done which can only "
                "happen when the outcome is available. "
                "To use the outcome as a future (without post-processing), use "
                "the `raw_measurement_outcome` attribute."
            )

    @property
    def bell_state(self) -> BellState:
        assert self.raw_bell_state.value is not None
        return BellState(self.raw_bell_state.value)
