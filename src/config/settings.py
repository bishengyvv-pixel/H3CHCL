from dataclasses import dataclass, field


@dataclass
class Settings:
    """全局可覆盖的运行时设置，优先读取 YAML，其次使用以下默认值。"""

    max_workers: int = 5
    batch_delay: float = 2.0
    retry_count: int = 3
    retry_delay: float = 1.0
    command_timeout: int = 60
    device_type: str = "hp_comware"
    source_ip: str = ""

    # 风险等级阈值
    high_risk_threshold: int = 60
    medium_risk_threshold: int = 85

    # 输出目录
    output_dir: str = "output"
