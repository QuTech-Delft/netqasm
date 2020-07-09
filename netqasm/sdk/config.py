from dataclasses import dataclass
from typing import List


@dataclass
class LogConfig:
    track_lines: bool
    log_subroutines_dir: str
    comm_log_dir: str
    app_dir: str
    lib_dirs: List[str]


def default_log_config():
    return LogConfig(
        track_lines=False,
        log_subroutines_dir=None,
        comm_log_dir=None,
        app_dir=None,
        lib_dirs=[],
    )
