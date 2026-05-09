import logging
from datetime import datetime
from pathlib import Path

from src.models.device import Device

logger = logging.getLogger(__name__)


class ConfigBackup:
    """将每台设备的运行配置保存为文本文件，便于审计追溯与离线分析。"""

    def __init__(self, output_dir: str | Path = "output") -> None:
        self._output_dir = Path(output_dir) / "configs"

    def save(self, devices: list[Device]) -> list[Path]:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []

        for dev in devices:
            config_text = dev.collected_outputs.get("display current-configuration", "")
            if not config_text:
                logger.warning("设备 %s 无配置数据，跳过备份。", dev.ip)
                continue

            label = dev.hostname or dev.ip.replace(".", "_")
            filename = f"{label}.txt"
            filepath = self._output_dir / filename

            header = (
                f"# 设备配置备份\n"
                f"# 备份时间: {datetime.now().isoformat()}\n"
                f"# 设备 IP:  {dev.ip}\n"
                f"# 主机名:   {dev.hostname}\n"
                f"# 角色:     {dev.role.value}\n"
                f"{'=' * 60}\n\n"
            )

            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(header)
                fh.write(config_text)

            saved.append(filepath)

        logger.info("配置备份已保存到 %s (%d 台设备)", self._output_dir, len(saved))
        return saved
