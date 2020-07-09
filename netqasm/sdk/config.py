from dataclasses import dataclass
from typing import List


@dataclass
class LogConfig:
    track_lines: bool = False
    log_subroutines_dir: str = None
    comm_log_dir: str = None
    app_dir: str = None
    lib_dirs: List[str] = None
