import logging
from dataclasses import dataclass
from typing import Any

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException

from src.models.device import Device, ConnectionStatus

logger = logging.getLogger(__name__)


@dataclass
class DeviceConnection:
    """封装 Netmiko 连接生命周期：建立 → 执行命令 → 收集输出 → 断开。"""

    device: Device
    device_type: str = "hp_comware"
    timeout: int = 60

    def __post_init__(self) -> None:
        self._connection: Any = None

    def connect(self) -> bool:
        params = {
            "device_type": self.device_type,
            "host": self.device.ip,
            "username": self.device.username,
            "password": self.device.password,
            "timeout": self.timeout,
        }
        try:
            self._connection = ConnectHandler(**params)  # type: ignore[arg-type]
            self.device.hostname = self._connection.find_prompt().strip("<>")
            self.device.status = ConnectionStatus.SUCCESS
            return True
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            self.device.status = ConnectionStatus.ERROR
            self.device.error_message = str(exc)
            return False
        except Exception as exc:
            self.device.status = ConnectionStatus.ERROR
            self.device.error_message = f"Unexpected: {exc}"
            return False

    def execute_commands(self, commands: list[str]) -> dict[str, str]:
        if not self._connection:
            return {}
        outputs: dict[str, str] = {}
        for cmd in commands:
            try:
                outputs[cmd] = self._connection.send_command(cmd)
            except Exception as exc:
                logger.warning("Command '%s' failed on %s: %s", cmd, self.device.ip, exc)
                outputs[cmd] = ""
        return outputs

    def disconnect(self) -> None:
        if self._connection:
            self._connection.disconnect()
