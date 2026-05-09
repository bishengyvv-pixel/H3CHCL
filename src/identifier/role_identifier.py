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

# 路由器型号特征：H3C 路由器型号包含 MSR / SR / CR / Router 等关键词
_ROUTER_MODEL_RE = re.compile(
    r'\b(MSR\d+|SR\d+|CR\d+|RT\d+|Router\b|Virtual[-\s]?Router|AR\d+)',
    re.IGNORECASE,
)


class RoleIdentifier:
    """基于 display version 判定路由/交换，再对交换机按 L3/L2 分层评分。

    判定流程：
      1. display version 中匹配路由器型号 → ROUTER
      2. 交换机按 L3/L2 评分：
          核心层: L3 ≥ 5
          汇聚层: L3 ≥ 2 且 L2 = 0
          接入层: L3 ≥ 2 且 L2 ≥ 1  或  L2 ≥ 1
    """

    def identify(self, device: Device) -> DeviceRole:
        # 第一步：判断设备类型（路由器 vs 交换机）
        version_text = device.collected_outputs.get("display version", "")

        if version_text and _ROUTER_MODEL_RE.search(version_text):
            device.role = DeviceRole.ROUTER
            # 提取型号用于日志
            match = _ROUTER_MODEL_RE.search(version_text)
            model = match.group(0) if match else "unknown"
            logger.info("设备 %s 识别为 router (型号匹配: %s)", device.ip, model)
            return device.role

        # 第二步：交换机角色分层
        config_text = device.collected_outputs.get("display current-configuration", "")
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
        elif l3_score >= 2 and l2_score == 0:
            device.role = DeviceRole.AGGREGATION
        elif l3_score >= 2 and l2_score >= 1:
            device.role = DeviceRole.ACCESS
        elif l2_score >= 1:
            device.role = DeviceRole.ACCESS
        else:
            device.role = DeviceRole.UNKNOWN

        logger.info("设备 %s 识别为 %s", device.ip, device.role.value)
        return device.role
