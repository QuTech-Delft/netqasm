from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from netqasm.sdk.config import LogConfig


@dataclass
class AppConfig:
    app_name: str
    node_name: str
    main_func: Callable
    log_config: Optional[LogConfig]
    inputs: Dict[str, Any]


def default_app_config(app_name: str, main_func: Callable) -> AppConfig:
    return AppConfig(
        app_name=app_name,
        node_name=app_name,
        main_func=main_func,
        log_config=None,
        inputs={},
    )
