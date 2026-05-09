"""园区网自动化安全评估系统 — CLI 入口。

流水线：加载配置 → 并发连接采集 → 角色识别 → 规则评估 → 生成报告
"""

import logging
import sys
from pathlib import Path

from src.config.loader import ConfigLoader
from src.connector.connection import DeviceConnection
from src.engine.scheduler import TaskScheduler
from src.engine.rate_limiter import RateLimiter
from src.identifier.role_identifier import RoleIdentifier
from src.evaluator.rule_engine import RuleEngine
from src.evaluator.risk_calculator import RiskCalculator
from src.reporter.excel_reporter import ExcelReporter
from src.reporter.json_reporter import JsonReporter

logger = logging.getLogger(__name__)

# 采集所需的 H3C Comware 命令列表
COLLECT_COMMANDS = [
    "display current-configuration",
    "display local-user",
    "display stp",
    "display dhcp snooping",
    "display acl all",
    "display vlan",
]


class AssessmentPipeline:
    """编排完整评估流程的顶层入口。"""

    def __init__(self, resource_dir: str = "") -> None:
        loader = ConfigLoader(resource_dir)
        self._devices = loader.load_devices()
        self._rules = loader.load_rules()
        self._settings = loader.load_settings()

    def run(self) -> None:
        devices = self._devices
        rules = self._rules
        settings = self._settings

        if not devices:
            logger.warning("No devices configured. Exiting.")
            return

        # 1. 并发连接采集
        logger.info("Phase 1: Connecting to %d device(s)…", len(devices))
        rate_limiter = RateLimiter(settings.batch_delay)
        scheduler = TaskScheduler(settings.max_workers, rate_limiter)

        def make_task(dev):
            def _task():
                conn = DeviceConnection(dev, settings.device_type, settings.command_timeout)
                if conn.connect():
                    dev.collected_outputs = conn.execute_commands(COLLECT_COMMANDS)
                    conn.disconnect()
                return dev
            return _task

        devices = scheduler.run_all([make_task(d) for d in devices])

        failed = [d for d in devices if d.collected_outputs == {}]
        if failed:
            logger.warning("%d device(s) unreachable, reason:", len(failed))
            for d in failed:
                logger.warning("  %s — %s", d.ip, d.error_message or "unknown error")
        online = [d for d in devices if d.collected_outputs != {}]

        # 2. 角色识别
        logger.info("Phase 2: Identifying roles for %d device(s)…", len(online))
        identifier = RoleIdentifier()
        for dev in online:
            identifier.identify(dev)

        # 3. 安全评估
        logger.info("Phase 3: Evaluating %d device(s)…", len(online))
        rule_engine = RuleEngine()
        risk_calc = RiskCalculator(settings.high_risk_threshold, settings.medium_risk_threshold)
        results = []
        for dev in online:
            failed_items = rule_engine.evaluate(dev, rules)
            result = risk_calc.calculate(dev, failed_items)
            results.append(result)

        # 4. 报告输出
        logger.info("Phase 4: Generating reports…")
        ExcelReporter(settings.output_dir).generate(results)
        JsonReporter(settings.output_dir).generate(results)

        logger.info("Assessment complete. %d device(s) evaluated.", len(results))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    resource_dir = sys.argv[1] if len(sys.argv) > 1 else ""
    AssessmentPipeline(resource_dir).run()


if __name__ == "__main__":
    main()
