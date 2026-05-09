import re
import logging

from src.models.device import Device, DeviceRole

logger = logging.getLogger(__name__)

# 接入层特征：大量 access 端口 / stp edged-port
_ACCESS_PATTERNS = [
    re.compile(r"port\s+link-type\s+access", re.IGNORECASE),
    re.compile(r"stp\s+edged-port", re.IGNORECASE),
]

# 汇聚/核心特征：Vlan-interface + OSPF/BGP/VRRP
_CORE_PATTERNS = [
    re.compile(r"interface\s+Vlan-interface", re.IGNORECASE),
    re.compile(r"ospf\s+", re.IGNORECASE),
    re.compile(r"bgp\s+", re.IGNORECASE),
    re.compile(r"vrrp\s+vrid", re.IGNORECASE),
]


class RoleIdentifier:
    """基于设备 running-config 特征判定角色（接入 / 汇聚 / 核心）。"""

    def identify(self, device: Device) -> DeviceRole:
        config_text = self._get_config_text(device)
        if not config_text:
            return DeviceRole.UNKNOWN

        access_hits = sum(1 for p in _ACCESS_PATTERNS if p.search(config_text))
        core_hits = sum(1 for p in _CORE_PATTERNS if p.search(config_text))

        if core_hits >= 2:
            device.role = DeviceRole.CORE
        elif core_hits == 1:
            device.role = DeviceRole.AGGREGATION
        elif access_hits >= 1:
            device.role = DeviceRole.ACCESS
        else:
            device.role = DeviceRole.UNKNOWN

        logger.info("Device %s identified as %s", device.ip, device.role.value)
        return device.role

    @staticmethod
    def _get_config_text(device: Device) -> str:
        key = "display current-configuration"
        return device.collected_outputs.get(key, "")
