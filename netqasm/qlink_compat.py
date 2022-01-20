# qlink-layer 0.1.0

from collections import namedtuple
from enum import Enum, auto
from typing import Union

import qlink_interface as qlink_1_0


class EPRType(Enum):
    K = 0
    M = auto()
    R = auto()


class EPRRole(Enum):
    CREATE = 0
    RECV = auto()


# Supported request types (create and keep, measure directly, and remote state preparation)
class RequestType(Enum):
    K = EPRType.K.value
    M = EPRType.M.value
    R = EPRType.R.value
    RECV = auto()
    STOP_RECV = auto()


# Types of replies from the link layer protocol
class ReturnType(Enum):
    OK_K = EPRType.K.value
    OK_M = EPRType.M.value
    OK_R = EPRType.R.value
    ERR = auto()
    CREATE_ID = auto()


# Error messages
class ErrorCode(Enum):
    UNSUPP = 0
    NOTIME = auto()
    NORES = auto()
    TIMEOUT = auto()
    REJECTED = auto()
    OTHER = auto()
    EXPIRE = auto()
    CREATE = auto()


# Choice of random bases sets
class RandomBasis(Enum):
    NONE = 0
    XZ = auto()
    XYZ = auto()
    CHSH = auto()


# Bases return from link layer about which basis was randomly chosen
class Basis(Enum):
    Z = 0
    X = auto()
    Y = auto()
    ZPLUSX = auto()
    ZMINUSX = auto()


# What Bell state is generated
class BellState(Enum):
    PHI_PLUS = 0  # |00> + |11>
    PHI_MINUS = auto()  # |00> - |11>
    PSI_PLUS = auto()  # |01> + |10>
    PSI_MINUS = auto()  # |01> - |10>


# Unit for max_time argument
class TimeUnit(Enum):
    MICRO_SECONDS = 0
    MILLI_SECONDS = 1
    SECONDS = 2


# CREATE message to the link layer for entanglement generation
LinkLayerCreate = namedtuple(
    "LinkLayerCreate",
    [
        "remote_node_id",
        "purpose_id",
        "type",
        "number",
        "random_basis_local",
        "random_basis_remote",
        "minimum_fidelity",
        "time_unit",
        "max_time",
        "priority",
        "atomic",
        "consecutive",
        "probability_dist_local1",
        "probability_dist_local2",
        "probability_dist_remote1",
        "probability_dist_remote2",
        "rotation_X_local1",
        "rotation_Y_local",
        "rotation_X_local2",
        "rotation_X_remote1",
        "rotation_Y_remote",
        "rotation_X_remote2",
    ],
)
LinkLayerCreate.__new__.__defaults__ = (  # type: ignore
    0,
    0,
    RequestType.K,
    1,
    RandomBasis.NONE,
    RandomBasis.NONE,
) + (0,) * (len(LinkLayerCreate._fields) - 6)

# RECV message to the link layer to allow for entanglement generation with a remote node
LinkLayerRecv = namedtuple(
    "LinkLayerRecv",
    [
        "type",
        "remote_node_id",
        "purpose_id",
    ],
)
LinkLayerRecv.__new__.__defaults__ = (RequestType.RECV,) + (0,) * (  # type: ignore
    len(LinkLayerRecv._fields) - 1
)

# RECV message to the link layer to stop allowing for entanglement generation with a remote node
LinkLayerStopRecv = namedtuple(
    "LinkLayerStopRecv",
    [
        "type",
        "remote_node_id",
        "purpose_id",
    ],
)
LinkLayerStopRecv.__new__.__defaults__ = (RequestType.STOP_RECV,) + (0,) * (  # type: ignore
    len(LinkLayerStopRecv._fields) - 1
)

# OK message from the link layer of successful generation of entanglement that is kept in memory
LinkLayerOKTypeK = namedtuple(
    "LinkLayerOKTypeK",
    [
        "type",
        "create_id",
        "logical_qubit_id",
        "directionality_flag",
        "sequence_number",
        "purpose_id",
        "remote_node_id",
        "goodness",
        "goodness_time",
        "bell_state",
    ],
)
LinkLayerOKTypeK.__new__.__defaults__ = (ReturnType.OK_K,) + (0,) * (  # type: ignore
    len(LinkLayerOKTypeK._fields) - 1
)

# OK message from the link layer of successful generation of entanglement that is measured directly
LinkLayerOKTypeM = namedtuple(
    "LinkLayerOKTypeM",
    [
        "type",
        "create_id",
        "measurement_outcome",
        "measurement_basis",
        "directionality_flag",
        "sequence_number",
        "purpose_id",
        "remote_node_id",
        "goodness",
        "bell_state",
    ],
)
LinkLayerOKTypeM.__new__.__defaults__ = (ReturnType.OK_M,) + (0,) * (  # type: ignore
    len(LinkLayerOKTypeM._fields) - 1
)

# OK message from the link layer of successful generation of entanglement that was used for remote state preparation
# (to creator node)
LinkLayerOKTypeR = namedtuple(
    "LinkLayerOKTypeR",
    [
        "type",
        "create_id",
        "measurement_outcome",
        "directionality_flag",
        "sequence_number",
        "purpose_id",
        "remote_node_id",
        "goodness",
        "bell_state",
    ],
)
LinkLayerOKTypeR.__new__.__defaults__ = (ReturnType.OK_R,) + (0,) * (  # type: ignore
    len(LinkLayerOKTypeR._fields) - 1
)

# Error message from the link layer
LinkLayerErr = namedtuple(
    "LinkLayerErr",
    [
        "type",
        "create_id",
        "error_code",
        "use_sequence_number_range",
        "sequence_number_low",
        "sequence_number_high",
        "origin_node_id",
    ],
)
LinkLayerErr.__new__.__defaults__ = (ReturnType.ERR,) + (0,) * (  # type: ignore
    len(LinkLayerErr._fields) - 1
)


def get_creator_node_id(local_node_id, create_request):
    """Returns the node ID of the node that submitted the given create request"""
    if create_request.directionality_flag == 1:
        return create_request.remote_node_id
    else:
        return local_node_id


T_LinkLayerResponse = Union[
    LinkLayerOKTypeK, LinkLayerOKTypeM, LinkLayerOKTypeR, LinkLayerErr
]

T_LinkLayer_1_0_Response = Union[
    qlink_1_0.ResCreateAndKeep, qlink_1_0.ResMeasureDirectly, qlink_1_0.ResError
]


def request_to_qlink_1_0(
    request: Union[LinkLayerCreate, LinkLayerRecv]
) -> qlink_1_0.ReqCreateBase:
    if request.type == RequestType.K:
        assert isinstance(request, LinkLayerCreate)
        return qlink_1_0.ReqCreateAndKeep(
            remote_node_id=request.remote_node_id,
            minimum_fidelity=request.minimum_fidelity,
            time_unit=request.time_unit,
            max_time=request.max_time,
            purpose_id=request.purpose_id,
            number=request.number,
            priority=request.priority,
            atomic=request.atomic,
            consecutive=request.consecutive,
        )

    elif request.type == RequestType.M:
        assert isinstance(request, LinkLayerCreate)
        return qlink_1_0.ReqMeasureDirectly(
            remote_node_id=request.remote_node_id,
            minimum_fidelity=request.minimum_fidelity,
            time_unit=request.time_unit,
            max_time=request.max_time,
            purpose_id=request.purpose_id,
            number=request.number,
            priority=request.priority,
            atomic=request.atomic,
            consecutive=request.consecutive,
            random_basis_local=qlink_1_0.RandomBasis(request.random_basis_local.value),
            random_basis_remote=qlink_1_0.RandomBasis(
                request.random_basis_remote.value
            ),
            x_rotation_angle_local_1=request.rotation_X_local1,
            y_rotation_angle_local=request.rotation_Y_local,
            x_rotation_angle_local_2=request.rotation_X_local2,
            x_rotation_angle_remote_1=request.rotation_X_remote1,
            y_rotation_angle_remote=request.rotation_Y_remote,
            x_rotation_angle_remote_2=request.rotation_X_remote2,
            probability_distribution_parameter_local_1=request.probability_dist_local1,
            probability_distribution_parameter_remote_1=request.probability_dist_remote1,
            probability_distribution_parameter_local_2=request.probability_dist_local2,
            probability_distribution_parameter_remote_2=request.probability_dist_remote2,
        )
    elif request.type == RequestType.RECV:
        assert isinstance(request, LinkLayerRecv)
        return qlink_1_0.ReqReceive(
            remote_node_id=request.remote_node_id, purpose_id=request.purpose_id
        )
    else:
        raise ValueError(f"Cannot convert request {request} to qlink-interface 1.0")


def response_from_qlink_1_0(response: T_LinkLayer_1_0_Response) -> T_LinkLayerResponse:
    if isinstance(response, qlink_1_0.ResCreateAndKeep):
        return LinkLayerOKTypeK(
            type=ReturnType.OK_K,
            create_id=response.create_id,
            logical_qubit_id=response.logical_qubit_id,
            directionality_flag=response.directionality_flag,
            sequence_number=response.sequence_number,
            purpose_id=response.purpose_id,
            remote_node_id=response.remote_node_id,
            goodness=response.goodness,
            goodness_time=response.time_of_goodness,
            bell_state=response.bell_state,
        )
    elif isinstance(response, qlink_1_0.ResMeasureDirectly):
        return LinkLayerOKTypeM(
            type=ReturnType.OK_M,
            create_id=response.create_id,
            measurement_outcome=response.measurement_outcome,
            measurement_basis=Basis(response.measurement_basis.value),
            directionality_flag=response.directionality_flag,
            sequence_number=response.sequence_number,
            purpose_id=response.purpose_id,
            remote_node_id=response.remote_node_id,
            goodness=response.goodness,
            bell_state=response.bell_state,
        )
    elif isinstance(response, qlink_1_0.ResError):
        return LinkLayerErr(
            type=ReturnType.ERR,
            create_id=response.create_id,
            error_code=response.error_code,
            use_sequence_number_range=response.use_sequence_number_range,
            sequence_number_low=response.sequence_number_low,
            sequence_number_high=response.sequence_number_high,
            origin_node_id=response.origin_node_id,
        )
    else:
        raise ValueError(f"Cannot convert response {response} from qlink-interface 1.0")
