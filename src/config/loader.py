from pathlib import Path
from typing import Any

import yaml

from src.models.rule import Rule
from src.models.device import Device
from src.config.settings import Settings


class ConfigLoader:
    """负责加载 devices / rules / settings 三类 YAML 配置。"""

    def __init__(self, resource_dir: Path | str = "") -> None:
        if not resource_dir:
            resource_dir = Path(__file__).resolve().parent.parent / "resources"
        self._resource_dir = Path(resource_dir)

    # ---------- devices ----------
    def load_devices(self, filename: str = "devices.yaml") -> list[Device]:
        data = self._read_yaml(filename)
        return [Device(ip=d["ip"], username=d["username"], password=d["password"])
                for d in data.get("devices", [])]

    # ---------- rules ----------
    def load_rules(self, filename: str = "rules.yaml") -> list[Rule]:
        data = self._read_yaml(filename)
        rules: list[Rule] = []
        for role_name, role_cfg in data.get("roles", {}).items():
            for item in role_cfg.get("items", []):
                rules.append(Rule(
                    id=item["id"],
                    desc=item["desc"],
                    check_cmd=item["check_cmd"],
                    regex=item["regex"],
                    weight=item["weight"],
                    fix_template=item.get("fix_template", ""),
                    applicable_roles=item.get("applicable_roles", []),
                ))
        return rules

    # ---------- settings ----------
    def load_settings(self, filename: str = "settings.yaml") -> Settings:
        data = self._read_yaml(filename)
        if not data:
            return Settings()
        return Settings(
            max_workers=data.get("max_workers", 5),
            batch_delay=data.get("batch_delay", 2.0),
            retry_count=data.get("retry_count", 3),
            retry_delay=data.get("retry_delay", 1.0),
            command_timeout=data.get("command_timeout", 60),
            device_type=data.get("device_type", "hp_comware"),
            high_risk_threshold=data.get("high_risk_threshold", 60),
            medium_risk_threshold=data.get("medium_risk_threshold", 85),
            output_dir=data.get("output_dir", "output"),
        )

    # ---------- helpers ----------
    def _read_yaml(self, filename: str) -> dict[str, Any]:
        filepath = self._resource_dir / filename
        if not filepath.exists():
            return {}
        with open(filepath, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
