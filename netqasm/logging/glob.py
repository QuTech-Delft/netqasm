import logging

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


def get_log_level(effective=True):
    if effective:
        return get_netqasm_logger().getEffectiveLevel()
    else:
        return get_netqasm_logger().level


def _setup_netqasm_logger():
    logger = get_netqasm_logger()
    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    syslog = logging.StreamHandler()
    syslog.setFormatter(formatter)
    logger.addHandler(syslog)
    logger.propagate = False


_setup_netqasm_logger()
