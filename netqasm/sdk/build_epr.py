from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from netqasm.qlink_compat import BellState, EPRType, RandomBasis, TimeUnit
from netqasm.sdk.build_types import T_PostRoutine
from netqasm.sdk.futures import Array, Future


@dataclass
class EntRequestParams:
    remote_node_id: int
    epr_socket_id: int
    number: int
    post_routine: Optional[T_PostRoutine]
    sequential: bool
    time_unit: TimeUnit = TimeUnit.MICRO_SECONDS
    max_time: int = 0
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


def deserialize_epr_keep_results(num_pairs: int, array: Array) -> List[EprKeepResult]:
    """Convert values in a NetQASM array into EprKeepResult objects."""
    assert len(array) == num_pairs * SER_RESPONSE_KEEP_LEN
    results: List[EprKeepResult] = []
    for i in range(num_pairs):
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
    num_pairs: int, array: Array
) -> List[EprMeasureResult]:
    """Convert values in a NetQASM array into EprMeasureResult objects."""
    assert len(array) == num_pairs * SER_RESPONSE_MEASURE_LEN
    results: List[EprMeasureResult] = []
    for i in range(num_pairs):
        base = i * SER_RESPONSE_MEASURE_LEN
        results.append(
            EprMeasureResult(
                measurement_outcome=array.get_future_index(
                    base + SER_RESPONSE_MEASURE_IDX_MEASUREMENT_OUTCOME
                ),
                measurement_basis=array.get_future_index(
                    base + SER_RESPONSE_MEASURE_IDX_MEASUREMENT_BASIS
                ),
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


@dataclass
class EprMeasureResult:
    measurement_outcome: Future
    measurement_basis: Future
    remote_node_id: Future
    generation_duration: Future
    raw_bell_state: Future

    @property
    def bell_state(self) -> BellState:
        assert self.raw_bell_state.value is not None
        return BellState(self.raw_bell_state.value)
