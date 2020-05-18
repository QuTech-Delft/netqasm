import logging
from enum import Enum

NETQASM_LOGGER = "NetQASM"


def get_netqasm_logger(sub_logger=None):
    logger = logging.getLogger(NETQASM_LOGGER)
    if sub_logger is None:
        return logger
    if isinstance(sub_logger, str):
        return logger.getChild(sub_logger)
    else:
        raise TypeError(f"sub_logger should be None or str, not {type(sub_logger)}")

    return logger


def set_log_level(level):
    logger = get_netqasm_logger()
    logger.setLevel(level)


def _setup_netqasm_logger():
    logger = get_netqasm_logger()
    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    syslog = logging.StreamHandler()
    syslog.setFormatter(formatter)
    logger.addHandler(syslog)
    logger.propagate = False


_LOG_FIELD_DELIM = ', '
_LOG_HDR_DELIM = '='


class _InstrLogHeaders(Enum):
    WCT = "WCT"  # Wall clock time
    SIT = "SIT"  # Simulated time
    SID = "SID"  # Subroutine ID
    PRC = "PRC"  # Program counter
    HLN = "HLN"  # Host line number
    INS = "INS"  # Instruction


_INSTR_LOGGER_FIELDS = {
    _InstrLogHeaders.WCT: "asctime",
    _InstrLogHeaders.SIT: "sim_time",
    _InstrLogHeaders.SID: "subroutine_id",
    _InstrLogHeaders.PRC: "program_counter",
    _InstrLogHeaders.HLN: "host_lineno",
    _InstrLogHeaders.INS: "instruction",
}


def _setup_instr_logger_formatter():
    """Instruction logger used by for example the Executioner"""
    hdrs = [
        _InstrLogHeaders.WCT,
        _InstrLogHeaders.SIT,
        _InstrLogHeaders.SID,
        _InstrLogHeaders.PRC,
        _InstrLogHeaders.INS,
    ]
    fields = [f"{hdr.value}{_LOG_HDR_DELIM}%({_INSTR_LOGGER_FIELDS[hdr]})s" for hdr in hdrs]
    # Add name of logger and log message
    fields = ['%(name)s'] + fields + ['%(message)s']
    formatter = logging.Formatter(_LOG_FIELD_DELIM.join(fields))
    return formatter


class _CommLogHeaders(Enum):
    WCT = "WCT"  # Wall clock time
    HLN = "HLN"  # Host line number
    OP = "OP"    # Operation (SEND, RECV, ...)


_COMM_LOGGER_FIELDS = {
    _CommLogHeaders.WCT: "asctime",
    _CommLogHeaders.HLN: "host_lineno",
    _CommLogHeaders.OP: "socket_op"
}


def setup_comm_logger_formatter():
    """Classical communication logger used by ThreadSocket"""
    hdrs = [
        _CommLogHeaders.WCT,
        _CommLogHeaders.HLN,
        _CommLogHeaders.OP
    ]
    fields = [f"{hdr.value}{_LOG_HDR_DELIM}%({_COMM_LOGGER_FIELDS[hdr]})s" for hdr in hdrs]
    # Add name of logger and log message
    fields = ['%(name)s'] + fields + ['%(message)s']
    formatter = logging.Formatter(_LOG_FIELD_DELIM.join(fields))
    return formatter


_setup_netqasm_logger()
