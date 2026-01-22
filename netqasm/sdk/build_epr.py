from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from types import MappingProxyType
from typing import Final

from netqasm.qlink_compat import BellState, EPRRole, EPRType, RandomBasis, TimeUnit
from netqasm.sdk.build_types import T_PostRoutine
from netqasm.sdk.futures import Array, Future, NoValueError
from netqasm.sdk.qubit import QubitMeasureAxes


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
    post_routine: T_PostRoutine | None
    sequential: bool
    time_unit: TimeUnit = TimeUnit.MICRO_SECONDS
    max_time: int = 0
    expect_phi_plus: bool = True
    expect_psi_plus: bool = False
    min_fidelity_all_at_end: int | None = None
    max_tries: int | None = None
    random_basis_local: RandomBasis | None = None
    random_basis_remote: RandomBasis | None = None
    rotations_local: tuple[int, int, int] = (0, 0, 0)
    rotations_remote: tuple[int, int, int] = (0, 0, 0)
    axes_local: QubitMeasureAxes = QubitMeasureAxes.XYX
    axes_remote: QubitMeasureAxes = QubitMeasureAxes.XYX


class SerializedCreateRequestIndex(IntEnum):
    """Indices of Create Request arguments in serialized NetQASM array"""

    TYPE = 0
    NUMBER = 1
    RANDOM_BASIS_LOCAL = 2
    RANDOM_BASIS_REMOTE = 3
    MINIMUM_FIDELITY = 4
    TIME_UNIT = 5
    MAX_TIME = 6
    PRIORITY = 7
    ATOMIC = 8
    CONSECUTIVE = 9
    PROBABILITY_DIST_LOCAL1 = 10
    PROBABILITY_DIST_LOCAL2 = 11
    PROBABILITY_DIST_REMOTE1 = 12
    PROBABILITY_DIST_REMOTE2 = 13
    ROTATION_LOCAL_1 = 14
    ROTATION_LOCAL_2 = 15
    ROTATION_LOCAL_3 = 16
    ROTATION_REMOTE_1 = 17
    ROTATION_REMOTE_2 = 18
    ROTATION_REMOTE_3 = 19
    ROTATION_AXES_LOCAL = 20
    ROTATION_AXES_REMOTE = 21


class SerializedKeepResultIndex(IntEnum):
    """Indices of EPR Keep results in serialized NetQASM array"""

    TYPE = 0
    CREATE_ID = 1
    LOGICAL_QUBIT_ID = 2
    DIRECTIONALITY_FLAG = 3
    SEQUENCE_NUMBER = 4
    PURPOSE_ID = 5
    REMOTE_NODE_ID = 6
    GOODNESS = 7
    GOODNESS_TIME = 8
    BELL_STATE = 9


class SerializedMeasureResultIndex(IntEnum):
    """Indices of EPR Measure results in serialized NetQASM array"""

    TYPE = 0
    CREATE_ID = 1
    MEASUREMENT_OUTCOME = 2
    MEASUREMENT_BASIS = 3
    DIRECTIONALITY_FLAG = 4
    SEQUENCE_NUMBER = 5
    PURPOSE_ID = 6
    REMOTE_NODE_ID = 7
    GOODNESS = 8
    BELL_STATE = 9


def serialize_request(tp: EPRType, params: EntRequestParams) -> list[int | None]:
    """Convert an EntRequestParams object into a list of values that can be put
    in a NetQASM array."""
    array: list[int | None] = [None for _ in range(len(SerializedCreateRequestIndex))]

    array[SerializedCreateRequestIndex.TYPE] = tp.value
    array[SerializedCreateRequestIndex.NUMBER] = params.number

    # Only when max_time is non-zero, explicitly initialize the relevant array elements.
    # If it is zero, these array element will be None.
    if params.max_time != 0:
        array[SerializedCreateRequestIndex.TIME_UNIT] = params.time_unit.value
        array[SerializedCreateRequestIndex.MAX_TIME] = params.max_time

    if tp == EPRType.M or tp == EPRType.R:
        # Only write when non-zero.
        if params.rotations_local != (0, 0, 0):
            array[
                SerializedCreateRequestIndex.ROTATION_LOCAL_1
            ] = params.rotations_local[0]
            array[
                SerializedCreateRequestIndex.ROTATION_LOCAL_2
            ] = params.rotations_local[1]
            array[
                SerializedCreateRequestIndex.ROTATION_LOCAL_3
            ] = params.rotations_local[2]
        if params.rotations_remote != (0, 0, 0):
            array[
                SerializedCreateRequestIndex.ROTATION_REMOTE_1
            ] = params.rotations_remote[0]
            array[
                SerializedCreateRequestIndex.ROTATION_REMOTE_2
            ] = params.rotations_remote[1]
            array[
                SerializedCreateRequestIndex.ROTATION_REMOTE_3
            ] = params.rotations_remote[2]
        if params.random_basis_local:
            array[
                SerializedCreateRequestIndex.RANDOM_BASIS_LOCAL
            ] = params.random_basis_local.value
        if params.random_basis_remote:
            array[
                SerializedCreateRequestIndex.RANDOM_BASIS_REMOTE
            ] = params.random_basis_remote.value
        array[SerializedCreateRequestIndex.ROTATION_AXES_LOCAL] = params.axes_local
        array[SerializedCreateRequestIndex.ROTATION_AXES_REMOTE] = params.axes_remote

    return array


def deserialize_epr_keep_results(
    request: EntRequestParams, array: Array
) -> list[EprKeepResult]:
    """Convert values in a NetQASM array into EprKeepResult objects."""
    assert len(array) == request.number * len(SerializedKeepResultIndex)
    results: list[EprKeepResult] = []
    for i in range(request.number):
        base = i * len(SerializedKeepResultIndex)
        results.append(
            EprKeepResult(
                qubit_id=array.get_future_index(
                    base + SerializedKeepResultIndex.LOGICAL_QUBIT_ID
                ),
                remote_node_id=array.get_future_index(
                    base + SerializedKeepResultIndex.REMOTE_NODE_ID
                ),
                generation_duration=array.get_future_index(
                    base + SerializedKeepResultIndex.GOODNESS
                ),
                raw_bell_state=array.get_future_index(
                    base + SerializedKeepResultIndex.BELL_STATE
                ),
            )
        )
    return results


def deserialize_epr_measure_results(
    request: EntRequestParams, array: Array, role: EPRRole
) -> list[EprMeasureResult]:
    """Convert values in a NetQASM array into EprMeasureResult objects."""
    assert len(array) == request.number * len(SerializedMeasureResultIndex)
    results: list[EprMeasureResult] = []
    for i in range(request.number):
        base = i * len(SerializedMeasureResultIndex)
        results.append(
            EprMeasureResult(
                raw_measurement_outcome=array.get_future_index(
                    base + SerializedMeasureResultIndex.MEASUREMENT_OUTCOME
                ),
                measurement_basis_local=request.rotations_local,
                measurement_basis_remote=request.rotations_remote,
                post_process=(request.expect_phi_plus and role == EPRRole.RECV),
                remote_node_id=array.get_future_index(
                    base + SerializedMeasureResultIndex.REMOTE_NODE_ID
                ),
                generation_duration=array.get_future_index(
                    base + SerializedMeasureResultIndex.GOODNESS
                ),
                raw_bell_state=array.get_future_index(
                    base + SerializedMeasureResultIndex.BELL_STATE
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


_BASIS_TO_ROTATION_MAPPING: Final[
    MappingProxyType[
        QubitMeasureAxes, MappingProxyType[EprMeasBasis, tuple[int, int, int]]
    ]
] = MappingProxyType(
    {
        QubitMeasureAxes.XYX: MappingProxyType(
            {
                EprMeasBasis.X: (0, 24, 0),
                EprMeasBasis.Y: (8, 0, 0),
                EprMeasBasis.Z: (0, 0, 0),
                EprMeasBasis.MX: (0, 8, 0),
                EprMeasBasis.MY: (24, 0, 0),
                EprMeasBasis.MZ: (16, 0, 0),
            }
        ),
        QubitMeasureAxes.YZY: MappingProxyType(
            {
                EprMeasBasis.X: (24, 0, 0),
                EprMeasBasis.Y: (8, 24, 24),
                EprMeasBasis.Z: (0, 0, 0),
                # FIXME: Check with Bart what the correct decompositions are for the negative bases.
                # EprMeasBasis.MX: (0, 8, 0),
                # EprMeasBasis.MY: (24, 0, 0),
                # EprMeasBasis.MZ: (16, 0, 0),
            }
        ),
        QubitMeasureAxes.ZXZ: MappingProxyType(
            {
                EprMeasBasis.X: (24, 24, 8),
                EprMeasBasis.Y: (0, 8, 0),
                EprMeasBasis.Z: (0, 0, 0),
                # FIXME: Check with Bart what the correct decompositions are for the negative bases.
                # EprMeasBasis.MX: (0, 8, 0),
                # EprMeasBasis.MY: (24, 0, 0),
                # EprMeasBasis.MZ: (16, 0, 0),
            }
        ),
    }
)

_ROTATION_TO_BASIS_MAPPING: Final[
    MappingProxyType[
        QubitMeasureAxes, MappingProxyType[tuple[int, int, int], EprMeasBasis]
    ]
] = MappingProxyType(
    {
        axes: MappingProxyType(
            {
                rotation: basis
                for basis, rotation in _BASIS_TO_ROTATION_MAPPING[axes].items()
            }
        )
        for axes in _BASIS_TO_ROTATION_MAPPING.keys()
    }
)


def rotation_to_basis(
    rotations: tuple[int, int, int], axes: QubitMeasureAxes
) -> EprMeasBasis | None:
    return _ROTATION_TO_BASIS_MAPPING[axes].get(rotations, None)


def basis_to_rotation(
    basis: EprMeasBasis, axes: QubitMeasureAxes
) -> tuple[int, int, int]:
    return _BASIS_TO_ROTATION_MAPPING[axes][basis]


@dataclass
class EprMeasureResult:
    raw_measurement_outcome: Future
    measurement_basis_local: tuple[int, int, int]
    measurement_basis_remote: tuple[int, int, int]
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
