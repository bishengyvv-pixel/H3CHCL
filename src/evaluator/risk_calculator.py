import logging

from src.models.assessment_result import AssessmentResult, FailedItem
from src.models.device import Device

logger = logging.getLogger(__name__)


class RiskCalculator:
    """加权计分 + 风险等级判定。

    总分 100，按 failed_items 的 weight 逐项扣分。
    - 高风险：总分 < 60 或命中"致命项"
    - 中风险：60 ≤ 总分 < 85
    - 低风险：总分 ≥ 85
    """

    FATAL_RULE_IDS = {"AUTH_01"}  # 核心层弱口令等致命项

    def __init__(self, high_threshold: int = 60, medium_threshold: int = 85) -> None:
        self._high = high_threshold
        self._medium = medium_threshold

    def calculate(self, device: Device, failed_items: list[FailedItem]) -> AssessmentResult:
        score = 100 - sum(item.weight for item in failed_items)
        score = max(score, 0)

        is_fatal = any(item.rule_id in self.FATAL_RULE_IDS for item in failed_items)

        if score < self._high or is_fatal:
            risk_level = "high"
        elif score < self._medium:
            risk_level = "medium"
        else:
            risk_level = "low"

        logger.info("Device %s → score=%d risk=%s", device.ip, score, risk_level)

        return AssessmentResult(
            device_ip=device.ip,
            hostname=device.hostname,
            role=device.role.value,
            score=score,
            risk_level=risk_level,
            failed_items=failed_items,
        )
