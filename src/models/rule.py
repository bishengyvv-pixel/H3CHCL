from dataclasses import dataclass, field


@dataclass
class Rule:
    id: str
    desc: str
    check_cmd: str
    regex: str
    weight: int
    fix_template: str = ""
    applicable_roles: list[str] = field(default_factory=list)
