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

    分层评分策略（OSPF 普遍存在，不能单靠它判核心）：
      L3 得分 = has_bgp*4 + has_ospf*2 + has_vrrp*2 + (vlan_if>=5)*3 + (vlan_if>=2)*1
      L2 得分 = (access_port>=10)*3 + (access_port>=5)*2 + has_edged*2 + has_dhcp*2

      核心层: L3 ≥ 5  (OSPF/BGP + 多VLAN接口 + VRRP)
      汇聚层: L3 ≥ 2  (有动态路由但L3特征不强)
      接入层: L2 ≥ 1  (纯二层特征，无动态路由)
      未知:    其他
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

        # 分层评分
        l3_score = 0
        if has_bgp:   l3_score += 4
        if has_ospf:  l3_score += 2
        if has_vrrp:  l3_score += 2
        if vlan_if_cnt >= 5: l3_score += 3
        elif vlan_if_cnt >= 2: l3_score += 1

        l2_score = 0
        if access_port_cnt >= 10: l2_score += 3
        elif access_port_cnt >= 5: l2_score += 2
        if has_edged: l2_score += 2
        if has_dhcp:  l2_score += 2

        logger.info(
            "%s: access端口=%d vlan接口=%d ospf=%s bgp=%s vrrp=%s edged=%s dhcp=%s → L3=%d L2=%d",
            device.ip, access_port_cnt, vlan_if_cnt,
            has_ospf, has_bgp, has_vrrp, has_edged, has_dhcp,
            l3_score, l2_score,
        )

        if l3_score >= 5:
            device.role = DeviceRole.CORE
        elif l3_score >= 2:
            device.role = DeviceRole.AGGREGATION
        elif l2_score >= 1:
            device.role = DeviceRole.ACCESS
        else:
            device.role = DeviceRole.UNKNOWN

        logger.info("设备 %s 识别为 %s", device.ip, device.role.value)
        return device.role

    @staticmethod
    def _get_config_text(device: Device) -> str:
        key = "display current-configuration"
        return device.collected_outputs.get(key, "")
