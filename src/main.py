"""园区网自动化安全评估系统 — CLI 入口。

流水线：加载配置 → 并发连接采集 → 角色识别 → 规则评估 → 生成报告
"""

import argparse
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
from src.reporter.config_backup import ConfigBackup

logger = logging.getLogger(__name__)

# 采集所需的 H3C Comware 命令列表
COLLECT_COMMANDS = [
    "display version",
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
            logger.warning("无设备配置，退出。")
            return

        # 1. 并发连接采集
        logger.info("=" * 50)
        logger.info("阶段 1: 正在连接 %d 台设备…", len(devices))
        rate_limiter = RateLimiter(settings.batch_delay)
        scheduler = TaskScheduler(settings.max_workers, rate_limiter)

        def make_task(dev):
            def _task():
                conn = DeviceConnection(dev, settings.device_type, settings.command_timeout, settings.source_ip)
                if conn.connect():
                    dev.collected_outputs = conn.execute_commands(COLLECT_COMMANDS)
                    conn.disconnect()
                return dev
            return _task

        devices = scheduler.run_all([make_task(d) for d in devices])

        failed = [d for d in devices if d.collected_outputs == {}]
        online = [d for d in devices if d.collected_outputs != {}]

        for d in online:
            logger.info("  ✓ %s (%s) 连接成功", d.ip, d.hostname)
        if failed:
            logger.warning("%d 台设备不可达:", len(failed))
            for d in failed:
                logger.warning("  ✗ %s — %s", d.ip, d.error_message or "未知错误")

        if not online:
            logger.error("无可用设备，评估终止。")
            return

        # 2. 角色识别
        logger.info("=" * 50)
        logger.info("阶段 2: 正在识别 %d 台设备角色…", len(online))
        identifier = RoleIdentifier()
        role_count: dict[str, int] = {}
        for dev in online:
            role = identifier.identify(dev)
            role_count[role.value] = role_count.get(role.value, 0) + 1
        logger.info("角色分布: %s", role_count)

        # 3. 安全评估
        logger.info("=" * 50)
        logger.info("阶段 3: 正在评估 %d 台设备…", len(online))
        rule_engine = RuleEngine()
        risk_calc = RiskCalculator(settings.high_risk_threshold, settings.medium_risk_threshold)
        results = []
        for dev in online:
            failed_items = rule_engine.evaluate(dev, rules)
            result = risk_calc.calculate(dev, failed_items)
            results.append(result)

            # 逐设备打印扣分明细
            if failed_items:
                items_desc = ", ".join(f"{f.rule_id}({f.desc}, -{f.weight})" for f in failed_items)
                logger.info("  %s [%s] 得分=%d 风险=%s → 扣分项: %s",
                            dev.ip, dev.role.value, result.score, result.risk_level, items_desc)
            else:
                logger.info("  %s [%s] 得分=%d 风险=%s → 全部通过 ✓",
                            dev.ip, dev.role.value, result.score, result.risk_level)

        # 4. 报告输出 + 配置备份
        logger.info("=" * 50)
        logger.info("阶段 4: 正在生成报告…")
        ExcelReporter(settings.output_dir).generate(results)
        JsonReporter(settings.output_dir).generate(results)
        ConfigBackup(settings.output_dir).save(online)

        # 5. 摘要
        self._print_summary(results)

    @staticmethod
    def _print_summary(results) -> None:
        if not results:
            return
        high = sum(1 for r in results if r.risk_level == "high")
        medium = sum(1 for r in results if r.risk_level == "medium")
        low = sum(1 for r in results if r.risk_level == "low")
        avg = sum(r.score for r in results) / len(results)

        logger.info("=" * 50)
        logger.info("评估摘要")
        logger.info("  设备总数: %d", len(results))
        logger.info("  平均得分: %.1f / 100", avg)
        logger.info("  高风险: %d 台  |  中风险: %d 台  |  低风险: %d 台", high, medium, low)
        if high:
            high_ips = [r.device_ip for r in results if r.risk_level == "high"]
            logger.info("  高风险设备: %s", ", ".join(high_ips))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H3C 园区网自动化安全评估系统")
    parser.add_argument("-c", "--config", default="", metavar="DIR",
                        help="自定义配置目录路径")
    parser.add_argument("--debug", action="store_true",
                        help="启用 DEBUG 级别日志")
    return parser.parse_args()


def main():
    args = parse_args()
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # 抑制 paramiko 的传输层日志（正常情况不需要看到 SSH 握手细节）
    if not args.debug:
        logging.getLogger("paramiko.transport").setLevel(logging.WARNING)

    AssessmentPipeline(args.config).run()


if __name__ == "__main__":
    main()
