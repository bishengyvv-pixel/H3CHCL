from dataclasses import dataclass, field


@dataclass
class Rule:
    id: str
    desc: str
    check_cmd: str
    regex: str
    weight: int
    match_type: str = "find"  # "find"=regex匹配则通过; "not_find"=regex匹配则扣分
    fix_template: str = ""
    applicable_roles: list[str] = field(default_factory=list)
