from dataclasses import dataclass, field


@dataclass
class FailedItem:
    rule_id: str
    desc: str
    weight: int
    fix_template: str


@dataclass
class AssessmentResult:
    device_ip: str
    hostname: str = ""
    role: str = "unknown"
    score: int = 100
    risk_level: str = "low"
    failed_items: list[FailedItem] = field(default_factory=list)
