import re
import logging

from src.models.device import Device, DeviceRole

logger = logging.getLogger(__name__)

# 接入层特征：大量 access 端口 / stp edged-port / dhcp-snooping
_ACCESS_PORT_RE = re.compile(r"port\s+link-type\s+access", re.IGNORECASE)
_EDGED_PORT_RE = re.compile(r"stp\s+edged-port", re.IGNORECASE)
_DHCP_SNOOPING_RE = re.compile(r"dhcp-snooping", re.IGNORECASE)

# 三层特征
_VLAN_IF_RE = re.compile(r"^interface\s+Vlan-interface", re.IGNORECASE | re.MULTILINE)
_OSPF_RE = re.compile(r"ospf\s+\d+", re.IGNORECASE)
_BGP_RE = re.compile(r"bgp\s+\d+", re.IGNORECASE)
_VRRP_RE = re.compile(r"vrrp\s+vrid", re.IGNORECASE)


class RoleIdentifier:
    """基于设备 running-config 特征判定角色（接入 / 汇聚 / 核心）。

    判定优先级：
      - 运行 BGP/OSPF（动态路由） → 核心层
      - 配置 VRRP 或 ≥5 个 Vlan-interface → 汇聚层
      - 大量 access 端口或 stp edged-port → 接入层
      - 其他 → 未知
    """

    def identify(self, device: Device) -> DeviceRole:
        config_text = self._get_config_text(device)
        if not config_text:
            return DeviceRole.UNKNOWN

        # 计数统计
        access_port_cnt = len(_ACCESS_PORT_RE.findall(config_text))
        vlan_if_cnt = len(_VLAN_IF_RE.findall(config_text))

        has_ospf = _OSPF_RE.search(config_text) is not None
        has_bgp = _BGP_RE.search(config_text) is not None
        has_vrrp = _VRRP_RE.search(config_text) is not None
        has_edged = _EDGED_PORT_RE.search(config_text) is not None
        has_dhcp = _DHCP_SNOOPING_RE.search(config_text) is not None

        logger.debug(
            "%s: access端口=%d vlan接口=%d ospf=%s bgp=%s vrrp=%s edged=%s dhcp=%s",
            device.ip, access_port_cnt, vlan_if_cnt, has_ospf, has_bgp, has_vrrp, has_edged, has_dhcp,
        )

        if has_bgp or has_ospf:
            device.role = DeviceRole.CORE
        elif has_vrrp or vlan_if_cnt >= 5:
            device.role = DeviceRole.AGGREGATION
        elif access_port_cnt >= 5 or has_edged or has_dhcp:
            device.role = DeviceRole.ACCESS
        else:
            device.role = DeviceRole.UNKNOWN

        logger.info("设备 %s 识别为 %s", device.ip, device.role.value)
        return device.role

    @staticmethod
    def _get_config_text(device: Device) -> str:
        key = "display current-configuration"
        return device.collected_outputs.get(key, "")
