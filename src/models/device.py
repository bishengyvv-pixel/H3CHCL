from dataclasses import dataclass, field
from enum import Enum


class DeviceRole(str, Enum):
    UNKNOWN = "unknown"
    ROUTER = "router"
    ACCESS = "access"
    AGGREGATION = "aggregation"
    CORE = "core"


class ConnectionStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class Device:
    ip: str
    username: str
    password: str
    source_ip: str = ""
    hostname: str = ""
    role: DeviceRole = DeviceRole.UNKNOWN
    status: ConnectionStatus = ConnectionStatus.PENDING
    error_message: str = ""
    collected_outputs: dict = field(default_factory=dict)
