# 配置指南

## 1. 配置文件总览

```
src/resources/
├── devices.yaml      # 设备清单（必填）
├── rules.yaml        # 安全检测规则（有默认值，可按需调整）
└── settings.yaml     # 全局运行参数（全部有默认值）
```

---

## 2. devices.yaml — 设备清单

### 完整示例

```yaml
devices:
  - ip: "172.16.255.1"
    username: "admin"
    password: "your_password"
    source_ip: "192.168.1.100"    # 可选：多网卡指定出口IP

  - ip: "172.16.255.11"
    username: "admin"
    password: "your_password"
    # source_ip 不填则使用 settings.yaml 中的全局值
```

### 字段说明

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `ip` | 是 | — | 设备管理 IP |
| `username` | 是 | — | SSH 登录用户名 |
| `password` | 是 | — | SSH 登录密码 |
| `source_ip` | 否 | `""` | 本机出口 IP，优先于全局 `source_ip` |

> **注意**：密码以明文存储在本地 YAML 文件中，请确保文件权限受控。生产环境建议使用环境变量或密钥管理服务。

---

## 3. settings.yaml — 全局运行参数

### 完整示例

```yaml
# 并发与限速
max_workers: 5        # 并发线程数
batch_delay: 2.0      # 每批次任务完成后休眠秒数

# 连接
retry_count: 3        # 连接失败重试次数
retry_delay: 1.0      # 重试间隔秒数
command_timeout: 60   # 命令执行超时秒数
device_type: "hp_comware"  # Netmiko 设备类型
source_ip: ""         # 全局出口 IP，留空不绑定

# 评分阈值
high_risk_threshold: 60   # 低于此分 = 高风险
medium_risk_threshold: 85 # 低于此分 = 中风险

# 输出
output_dir: "output"  # 报告输出目录
```

### 参数调优建议

| 场景 | max_workers | batch_delay |
|------|-------------|-------------|
| HCL 模拟器（VirtualBox） | 3~5 | 2.0~3.0 |
| 物理设备（局域网） | 10~20 | 0.5~1.0 |
| 物理设备（广域网） | 5~10 | 1.0~2.0 |

> HCL 模拟器对并发连接敏感，`max_workers` 建议不超过 5，否则 VirtualBox CPU 可能过载导致设备响应超时。

---

## 4. rules.yaml — 安全检测规则

详见 [docs/03_rules.md](03_rules.md)。

---

## 5. 自定义配置目录

默认配置目录为 `src/resources/`，可通过 CLI 参数指定其他目录：

```bash
python -m src.main -c /path/to/my-configs
```

自定义目录需包含同名 YAML 文件：
```
my-configs/
├── devices.yaml
├── rules.yaml      # 可选：缺失则空规则
└── settings.yaml   # 可选：缺失则用默认值
```

---

## 6. 多网卡环境配置

当主机有多个 IP 地址时，需要指定访问设备网段的出口 IP：

```bash
# 先确认设备所在网段对应的本机 IP
ipconfig              # Windows
ifconfig              # Linux/macOS

# 方式1：全局生效（所有设备用同一个出口IP）
# settings.yaml:
source_ip: "192.168.56.1"

# 方式2：单台设备覆盖
# devices.yaml:
devices:
  - ip: "172.16.255.1"
    ...
    source_ip: "192.168.56.1"
```

优先级：设备级 `source_ip` > 全局 `source_ip`。

---

## 7. 日志控制

### 正常运行（INFO 级别）

```bash
python -m src.main
```

输出：阶段进度、连接状态、角色识别、扣分明细、摘要统计。

### 排查模式（DEBUG 级别）

```bash
python -m src.main --debug
```

额外输出：paramiko SSH 握手细节、限速器日志、角色识别特征统计。

---

## 8. 输出文件

| 文件 | 格式 | 内容 |
|------|------|------|
| `output/assessment_report.xlsx` | Excel | 仪表盘 + 角色分析 + 设备详情 |
| `output/assessment_YYYYMMDD_HHMMSS.json` | JSON | 结构化评估数据 |

每次运行**覆盖** Excel 文件，JSON 文件**带时间戳**保留历史记录。
