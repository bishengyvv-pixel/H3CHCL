# H3C 园区网自动化安全评估系统

基于 Python 的自动化工具，针对 **H3C Comware V7** 架构的园区网络进行全层级安全风险摸排。自动采集设备配置、识别设备角色、量化评估风险，输出专业加固建议报告。

## 核心能力

- **自动化采集** — 通过 SSH 并发连接 H3C 交换机/路由器，批量执行 `display` 命令采集配置
- **智能角色识别** — 基于特征评分自动判定设备角色（路由器 / 核心层 / 汇聚层 / 接入层）
- **分角色安全评估** — 按角色加载检测规则，正则匹配 + 加权计分，输出量化风险等级
- **可视化报告** — Excel 仪表盘 + JSON 结构化数据，含扣分明细与加固建议

## 架构概览

```
src/
├── main.py                  # CLI 入口，编排完整评估流水线
├── models/                  # 数据模型（Device / Rule / AssessmentResult）
├── config/                  # YAML 配置加载（设备清单 / 规则 / 全局设置）
├── connector/               # SSH 连接管理（Netmiko + 重试 + 源IP绑定）
├── engine/                  # 并发调度（ThreadPoolExecutor + 批次限速）
├── identifier/              # 设备角色识别（路由器型号匹配 + L2/L3 特征评分）
├── evaluator/               # 安全评估（Regex 规则匹配 + 加权计分）
├── reporter/                # 报告输出（Excel / JSON / PDF）
└── resources/               # 运行时配置文件
    ├── devices.yaml         #   设备清单
    ├── rules.yaml           #   安全检测规则库
    └── settings.yaml        #   全局运行参数
```

详细架构说明见 [docs/01_architecture.md](docs/01_architecture.md)。

## 快速开始

### 环境要求

- Python 3.9+
- 目标设备：H3C Comware V7（交换机 / 路由器），已开启 SSH

### 安装

```bash
pip install netmiko pyyaml openpyxl
```

### 配置

**1. 填写设备清单** — [src/resources/devices.yaml](src/resources/devices.yaml)

```yaml
devices:
  - ip: "172.16.255.1"
    username: "admin"
    password: "your_password"
    # source_ip: "192.168.1.100"  # 多网卡环境指定出口IP
```

**2. 调整运行参数** — [src/resources/settings.yaml](src/resources/settings.yaml)

```yaml
max_workers: 5       # 并发连接数（HCL模拟器建议≤5）
batch_delay: 2.0     # 每批次休眠秒数（防CPU过载）
source_ip: ""        # 全局出口IP（留空则不绑定）
```

**3. 按需调整规则** — [src/resources/rules.yaml](src/resources/rules.yaml)

### 运行

```bash
cd H3C-HCL
python -m src.main
```

```bash
# 排查模式（显示SSH握手细节）
python -m src.main --debug

# 自定义配置目录
python -m src.main -c /path/to/configs
```

### 输出

| 文件 | 路径 | 说明 |
|------|------|------|
| Excel 报告 | `output/assessment_report.xlsx` | 仪表盘 + 角色分析 + 设备扣分明细 |
| JSON 数据 | `output/assessment_*.json` | 结构化数据，含 summary + devices |

## 评估流程

```
阶段1: 并发SSH连接 → 采集7条display命令输出
阶段2: 机型识别 → L2/L3特征评分 → 判定角色
阶段3: 按角色加载规则 → Regex匹配 → 加权计分
阶段4: 生成Excel + JSON报告
```

## 风险等级

| 等级 | 条件 | 颜色标识 |
|------|------|----------|
| 高风险 | 总分 < 60 或命中致命项 | 红色 |
| 中风险 | 60 ≤ 总分 < 85 | 黄色 |
| 低风险 | 总分 ≥ 85 | 绿色 |

## 文档

- [架构设计](docs/01_architecture.md) — 系统分层与数据流
- [模块详解](docs/02_modules.md) — 各模块职责与实现
- [规则系统](docs/03_rules.md) — 检测规则与评分模型
- [配置指南](docs/04_configuration.md) — 配置文件详解

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.9+ |
| SSH通信 | Netmiko (`hp_comware`) |
| 并发框架 | `concurrent.futures.ThreadPoolExecutor` |
| 配置存储 | YAML |
| 报告格式 | Excel (openpyxl) / JSON |
