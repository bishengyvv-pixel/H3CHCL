import re
import logging
from typing import Optional

from src.models.assessment_result import FailedItem
from src.models.device import Device
from src.models.rule import Rule

logger = logging.getLogger(__name__)


class RuleEngine:
    """针对单台设备执行规则匹配：逐条规则取对应命令输出 → Regex 匹配 → 生成 FailedItem。"""

    def evaluate(self, device: Device, rules: list[Rule]) -> list[FailedItem]:
        failed: list[FailedItem] = []
        applicable = [r for r in rules if self._rule_applies(r, device.role.value)]
        for rule in applicable:
            output = device.collected_outputs.get(rule.check_cmd, "")
            matched = self._regex_match(rule.regex, output)

            # find:   正则匹配 → 通过；未匹配 → 扣分
            # not_find: 正则匹配 → 命中风险项 → 扣分；未匹配 → 通过
            is_failure = (rule.match_type == "find" and not matched) or \
                         (rule.match_type == "not_find" and matched)

            if is_failure:
                failed.append(FailedItem(
                    rule_id=rule.id,
                    desc=rule.desc,
                    weight=rule.weight,
                    fix_template=rule.fix_template,
                ))
        return failed

    @staticmethod
    def _rule_applies(rule: Rule, role: str) -> bool:
        if not rule.applicable_roles:
            return True  # 通用规则
        return role in rule.applicable_roles

    @staticmethod
    def _regex_match(pattern: str, text: str) -> bool:
        try:
            return re.search(pattern, text, re.IGNORECASE) is not None
        except re.error as exc:
            logger.warning("无效的正则表达式 '%s': %s", pattern, exc)
            return False
