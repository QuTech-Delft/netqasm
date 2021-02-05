from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LogConfig:
    track_lines: bool = False
    log_subroutines_dir: Optional[str] = None
    comm_log_dir: Optional[str] = None
    app_dir: Optional[str] = None
    lib_dirs: Optional[List[str]] = None
    log_dir: Optional[str] = None
    split_runs: bool = True
