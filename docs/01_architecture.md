# 架构设计

## 1. 系统分层

```
┌─────────────────────────────────────────────────────────┐
│                      CLI (main.py)                       │
│              流水线编排 · 参数解析 · 日志控制              │
├─────────────────────────────────────────────────────────┤
│  config/          connector/         engine/             │
│  配置加载          SSH连接管理        并发调度             │
│  ├ loader.py      ├ connection.py    ├ scheduler.py      │
│  └ settings.py    └ retry.py         └ rate_limiter.py   │
├─────────────────────────────────────────────────────────┤
│  identifier/              evaluator/                     │
│  角色识别                  安全评估                       │
│  └ role_identifier.py     ├ rule_engine.py               │
│                           └ risk_calculator.py            │
├─────────────────────────────────────────────────────────┤
│  reporter/                                              │
│  报告输出                                                │
│  ├ excel_reporter.py  ├ json_reporter.py                 │
│  └ pdf_reporter.py                                      │
├─────────────────────────────────────────────────────────┤
│  models/                                                │
│  数据载体: Device · Rule · AssessmentResult              │
└─────────────────────────────────────────────────────────┘
```

## 2. 数据流

```
resources/                    main.py                    output/
──────────                    ───────                    ───────
devices.yaml ──┐
               ├──► ConfigLoader ──► AssessmentPipeline
rules.yaml ────┤                        │
               │                ┌───────┴────────┐
settings.yaml ─┘                ▼                    ▼
                          TaskScheduler        RuleEngine
                          (ThreadPool)         (Regex)
                               │                    │
                          DeviceConnection     RiskCalculator
                          (Netmiko SSH)        (加权计分)
                               │                    │
                               ▼                    ▼
                          collected_outputs    AssessmentResult
                               │                    │
                               ▼                    ▼
                          RoleIdentifier       ExcelReporter
                          (特征评分)           JsonReporter
```

## 3. 分层职责

### 3.1 CLI 层 — `main.py`

**职责**：编排评估流水线，解析命令行参数，控制日志级别。

```
main()
 ├── parse_args()        # argparse 解析 --debug / -c
 ├── logging.basicConfig # 日志配置（INFO / DEBUG）
 └── AssessmentPipeline.run()
      ├── Phase 1: 并发连接 + 命令采集
      ├── Phase 2: 角色识别
      ├── Phase 3: 规则评估 + 风险计分
      ├── Phase 4: 报告生成
      └── Phase 5: 摘要输出
```

**对外依赖**：无上层依赖，引用所有下层模块。

### 3.2 配置层 — `config/`

**loader.py** — 负责将 YAML 文件反序列化为数据对象：
- `load_devices()` → `list[Device]`
- `load_rules()` → `list[Rule]`
- `load_settings()` → `Settings`

**settings.py** — 全局运行参数 dataclass，含默认值。

### 3.3 连接层 — `connector/`

**connection.py** — Netmiko SSH 生命周期管理：
- `connect()` — 建立连接（支持源 IP 绑定）、获取 hostname
- `execute_commands()` — 批量执行 `display` 命令并收集输出
- `disconnect()` — 断开连接

**源 IP 绑定原理**：
```python
sock = socket.create_connection(
    (host, 22), timeout=timeout,
    source_address=(source_ip, 0)  # 0 = 随机源端口
)
```
预绑 socket 通过 `params["sock"]` 传入 Netmiko ConnectHandler。

**retry.py** — 装饰器 `retry_on_failure(max_attempts=3, delay=1.0)`。

### 3.4 引擎层 — `engine/`

**scheduler.py** — `TaskScheduler.run_all()`：
- 使用 `ThreadPoolExecutor(max_workers)` 并发提交任务
- `as_completed()` 收集结果，捕获异常不中断其他任务
- 每个 future 完成时调用 `RateLimiter.tick()`

**rate_limiter.py** — `RateLimiter.tick()`：
- `time.sleep(batch_delay)` 减轻 HCL 模拟器 CPU 压力

### 3.5 识别层 — `identifier/`

**role_identifier.py** — 两步判定：

**步骤1：设备类型判定**（`display version` 输出）
```
正则匹配路由器型号 (MSR/SR/CR/AR/Router) → ROUTER
```

**步骤2：交换机分层评分**（`display current-configuration` 输出）

```
L3得分 = BGP×4 + OSPF×2 + VRRP×2 + (VLAN接口≥5)×3 + (VLAN接口≥2)×1
L2得分 = (access端口≥10)×3 + (access端口≥5)×2 + edged×2 + dhcp×2

L3 ≥ 5                  → 核心层
L3 ≥ 2 且 L2 = 0        → 汇聚层（纯三层，无接入特征）
L3 ≥ 2 且 L2 ≥ 1        → 接入层（三层+二层特征 = 三层接入交换机）
L2 ≥ 1                  → 接入层（纯二层）
其他                     → 未知
```

### 3.6 评估层 — `evaluator/`

**rule_engine.py** — 规则匹配引擎：
- 过滤适用规则（`applicable_roles` 匹配设备角色，空列表 = 通用）
- 取对应 `check_cmd` 的采集输出 → `re.search(regex, output)`
- `match_type="find"` → 未匹配则扣分；`match_type="not_find"` → 匹配则扣分

**risk_calculator.py** — 加权计分：
```
score = 100 - Σ(failed_items.weight)
score = max(score, 0)

if score < 60 or 命中致命项 → high
elif score < 85 → medium
else → low
```

### 3.7 报告层 — `reporter/`

- **ExcelReporter** — 三页：仪表盘 + 角色分析 + 设备详情（含饼图/柱状图）
- **JsonReporter** — `{ generated_at, summary, devices[] }`
- **PdfReporter** — 预留桩代码

### 3.8 模型层 — `models/`

纯 dataclass，零业务逻辑，作为层间数据传输载体：
- **Device** — ip, username, password, source_ip, hostname, role, status, collected_outputs
- **Rule** — id, desc, check_cmd, regex, weight, match_type, applicable_roles
- **AssessmentResult** — device_ip, hostname, role, score, risk_level, failed_items

## 4. 设计原则

| 原则 | 体现 |
|------|------|
| **单一职责** | 每层只做一件事：连接不管评估，识别不管报告 |
| **依赖方向** | CLI → 各层 → models，无反向依赖，无跨层调用 |
| **数据载体分离** | models/ 中纯 dataclass 传数据，各层不直接依赖具体实现 |
| **配置驱动** | 设备清单、规则库、运行参数全部 YAML 化，无需改代码 |
| **容错优先** | 单台设备失败不影响其他设备，异常兜底不崩溃 |
