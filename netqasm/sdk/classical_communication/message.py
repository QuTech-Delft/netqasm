from dataclasses import dataclass


@dataclass
class StructuredMessage:
    header: str
    payload: str
