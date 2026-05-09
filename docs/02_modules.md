# 模块详解

## 1. models/ — 数据模型层

### 1.1 device.py

```python
class DeviceRole(str, Enum):
    ROUTER      = "router"        # 路由器（MSR/SR/CR/AR 系列）
    CORE        = "core"          # 核心层交换机
    AGGREGATION = "aggregation"   # 汇聚层交换机
    ACCESS      = "access"        # 接入层交换机
    UNKNOWN     = "unknown"       # 无法识别

class ConnectionStatus(str, Enum):
    PENDING = "pending"           # 未连接
    SUCCESS = "success"           # 连接成功
    ERROR   = "error"             # 连接失败

@dataclass
class Device:
    ip: str                       # 管理IP
    username: str                 # SSH 用户名
    password: str                 # SSH 密码
    source_ip: str = ""           # 本机出口IP（多网卡环境）
    hostname: str = ""            # 设备主机名（连接后获取）
    role: DeviceRole              # 角色识别结果
    status: ConnectionStatus      # 连接状态
    error_message: str = ""       # 失败原因
    collected_outputs: dict       # {"display xxx": "output text", ...}
```

### 1.2 rule.py

```python
@dataclass
class Rule:
    id: str                       # 规则编号，如 "AUTH_01"
    desc: str                     # 中文描述
    check_cmd: str                # 采集命令，如 "display current-configuration"
    regex: str                    # 正则表达式
    weight: int                   # 扣分权重
    match_type: str = "find"      # "find"=匹配则通过 / "not_find"=匹配则扣分
    fix_template: str = ""        # 加固命令模板
    applicable_roles: list[str]   # 适用角色，空=通用
```

### 1.3 assessment_result.py

```python
@dataclass
class FailedItem:
    rule_id: str                  # 关联规则ID
    desc: str                     # 风险描述
    weight: int                   # 扣除分数
    fix_template: str             # 加固建议

@dataclass
class AssessmentResult:
    device_ip: str
    hostname: str
    role: str
    score: int = 100              # 初始100，逐项扣分
    risk_level: str = "low"       # high / medium / low
    failed_items: list[FailedItem]
```

---

## 2. config/ — 配置加载层

### 2.1 loader.py — ConfigLoader

```
ConfigLoader(resource_dir)
  ├── load_devices("devices.yaml")    → list[Device]
  ├── load_rules("rules.yaml")        → list[Rule]
  └── load_settings("settings.yaml")  → Settings
```

**实现细节**：
- `resource_dir` 默认取 `src/resources/`，可通过构造函数或 CLI `-c` 覆盖
- YAML 文件缺失不报错，返回空列表/默认 Settings
- Device 构造时 `source_ip` 可选，未填则用全局设置

### 2.2 settings.py — Settings

```python
@dataclass
class Settings:
    max_workers: int = 5          # 并发线程数
    batch_delay: float = 2.0      # 批次休眠秒数
    retry_count: int = 3          # 连接重试次数
    retry_delay: float = 1.0      # 重试间隔
    command_timeout: int = 60     # 命令执行超时
    device_type: str = "hp_comware"
    source_ip: str = ""           # 全局源IP
    high_risk_threshold: int = 60
    medium_risk_threshold: int = 85
    output_dir: str = "output"
```

---

## 3. connector/ — 连接管理层

### 3.1 connection.py — DeviceConnection

```
DeviceConnection(device, device_type, timeout, global_source_ip)
  ├── connect()
  │     ├── 设备级 source_ip > 全局 source_ip
  │     ├── 有源IP → socket.create_connection(source_address=(ip,0))
  │     ├── ConnectHandler(**params)  # Netmiko SSH
  │     └── 获取 hostname (find_prompt)
  ├── execute_commands(["display version", ...])
  │     └── {cmd: output_text, ...}
  └── disconnect()
```

**源 IP 绑定流程**：
```
1. 创建 socket
2. sock.bind((source_ip, 0))  → 绑定本机指定 IP
3. sock.connect((host, 22))   → 连接到目标设备
4. 将 sock 传入 Netmiko ConnectHandler(sock=sock)
```

**异常处理**：
- `NetmikoTimeoutException` → 连接超时
- `NetmikoAuthenticationException` → 认证失败
- `OSError` (source_ip bind) → 源IP绑定失败
- 全部捕获，设置 `device.status = ERROR`，不抛异常

### 3.2 retry.py — retry_on_failure

```python
@retry_on_failure(max_attempts=3, delay=1.0)
def connect_with_retry():
    ...
```

装饰器模式，自动在异常时重试，达到上限后抛出最后一次异常。

---

## 4. engine/ — 调度引擎层

### 4.1 scheduler.py — TaskScheduler

```python
class TaskScheduler:
    def run_all(self, tasks: Iterable[Callable]) -> list[T]:
        with ThreadPoolExecutor(max_workers=N) as executor:
            future_map = {executor.submit(t): t for t in tasks}
            for future in as_completed(future_map):
                try:
                    results.append(future.result())
                except Exception:
                    logger.error(...)
                finally:
                    rate_limiter.tick()
        return results
```

- `as_completed` 而非 `wait` — 先完成的先处理，不阻塞
- 单个任务异常不中断整个批次
- 每个 future 完成调用 `RateLimiter.tick()`

### 4.2 rate_limiter.py — RateLimiter

```python
class RateLimiter:
    def tick(self):
        time.sleep(batch_delay)  # 默认 2.0 秒
```

**设计原因**：HCL 模拟器在并发连接时 CPU 容易过载，批次间强制休眠可有效防止。

---

## 5. identifier/ — 角色识别层

### 5.1 role_identifier.py — RoleIdentifier

**特征提取正则**：

| 特征 | 正则 | 用途 |
|------|------|------|
| access 端口 | `port\s+link-type\s+access` | L2 接入特征 |
| stp edged-port | `stp\s+edged-port` | L2 边缘端口 |
| dhcp-snooping | `dhcp-snooping` | L2 安全特征 |
| Vlan-interface | `^interface\s+Vlan-interface` | L3 三层接口 |
| OSPF 进程 | `ospf\s+\d+` | L3 动态路由 |
| BGP 进程 | `bgp\s+\d+` | L3 核心路由 |
| VRRP | `vrrp\s+vrid` | L3 网关冗余 |
| 路由器型号 | `MSR\d+\|SR\d+\|CR\d+\|Router` | 设备类型 |

**路由器型号匹配**：先从 `display version` 输出匹配型号，命中即判为 ROUTER，不参与交换机评分。

---

## 6. evaluator/ — 安全评估层

### 6.1 rule_engine.py — RuleEngine

```
evaluate(device, rules):
  for rule in rules:
    if not rule_applies(role):
      continue
    output = device.collected_outputs[rule.check_cmd]
    matched = re.search(rule.regex, output)
    if (match_type=="find" and not matched) or (match_type=="not_find" and matched):
      failed.append(FailedItem(rule))
  return failed
```

### 6.2 risk_calculator.py — RiskCalculator

```
calculate(device, failed_items):
  score = 100 - sum(item.weight for item in failed_items)
  score = max(score, 0)

  is_fatal = any(item.rule_id in FATAL_RULE_IDS)
  if score < 60 or is_fatal: return "high"
  elif score < 85: return "medium"
  else: return "low"
```

**致命项**：`FATAL_RULE_IDS = {"AUTH_01"}` — 核心层弱口令直接判高风险。

---

## 7. reporter/ — 报告输出层

### 7.1 ExcelReporter

| Sheet | 内容 |
|-------|------|
| 安全仪表盘 | KPI 卡片、风险分布饼图、角色汇总表 |
| 角色安全分析 | 按角色统计：设备数/平均分/最高频扣分项 + 柱状图 |
| 设备详情 | 逐台设备扣分明细、风险等级着色、角色着色、冻结表头 |

### 7.2 JsonReporter

```json
{
  "generated_at": "2026-05-09T19:48:01",
  "summary": {
    "total_devices": 12,
    "average_score": 55.4,
    "high_risk": 8,
    "medium_risk": 3,
    "low_risk": 1
  },
  "devices": [
    {
      "device_ip": "172.16.255.1",
      "hostname": "Gateway",
      "role": "router",
      "score": 85,
      "risk_level": "low",
      "failed_items": [...]
    }
  ]
}
```

### 7.3 PdfReporter

预留桩代码，待使用 `reportlab` 或 `WeasyPrint` 实现。

---

## 8. main.py — CLI 入口

### 命令行参数

| 参数 | 说明 |
|------|------|
| `-c DIR`, `--config DIR` | 自定义配置目录 |
| `--debug` | DEBUG 级别日志 + paramiko 传输层日志 |

### 采集命令列表

```python
COLLECT_COMMANDS = [
    "display version",              # 设备型号（路由器判定）
    "display current-configuration", # 运行配置（角色识别 + 规则匹配）
    "display local-user",           # 本地用户（弱口令检测）
    "display stp",                  # STP 状态
    "display dhcp snooping",        # DHCP Snooping 状态
    "display acl all",              # ACL 配置
    "display vlan",                 # VLAN 信息
]
```
