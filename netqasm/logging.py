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

_INSTR_LOG_FIELD_DELIM = ' : '
_INSTR_LOG_HDR_DELIM = '='


def _setup_instr_logger_formatter():
    """Instruction logger used by for example the Executioner"""
    hdrs = [
        _InstrLogHeaders.WCT,
        _InstrLogHeaders.SIT,
        _InstrLogHeaders.SID,
        _InstrLogHeaders.PRC,
        _InstrLogHeaders.INS,
    ]
    fields = [f"{hdr.value}{_INSTR_LOG_HDR_DELIM}%({_INSTR_LOGGER_FIELDS[hdr]})s" for hdr in hdrs]
    # Add name of logger and log message
    fields = ['%(name)s'] + fields + ['%(message)s']
    formatter = logging.Formatter(_INSTR_LOG_FIELD_DELIM.join(fields))
    return formatter


_setup_netqasm_logger()
