import logging
import socket
from dataclasses import dataclass, field
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
    global_source_ip: str = ""

    _connection: Any = field(default=None, init=False)

    def connect(self) -> bool:
        # 设备级 source_ip 优先于全局设置
        source_ip = self.device.source_ip or self.global_source_ip

        params: dict[str, Any] = {
            "device_type": self.device_type,
            "host": self.device.ip,
            "username": self.device.username,
            "password": self.device.password,
            "timeout": self.timeout,
        }

        if source_ip:
            try:
                sock = socket.create_connection(
                    (self.device.ip, 22),
                    timeout=self.timeout,
                    source_address=(source_ip, 0),
                )
                params["sock"] = sock
                logger.info("Bound to source IP %s → %s", source_ip, self.device.ip)
            except OSError as exc:
                self.device.status = ConnectionStatus.ERROR
                self.device.error_message = f"Source IP bind failed: {exc}"
                return False

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
