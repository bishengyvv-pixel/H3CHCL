# 规则系统与评分模型

## 1. 规则定义格式

每条规则使用 YAML 定义，结构如下：

```yaml
- id: "规则编号"              # 唯一标识，如 AUTH_01
  desc: "中文描述"            # 风险项名称
  check_cmd: "display xxx"    # 从哪条命令的输出中匹配
  regex: '正则表达式'         # Python re 语法
  match_type: "find"          # find=匹配则通过 | not_find=匹配则扣分
  weight: 15                  # 扣分权重（1-100）
  fix_template: "加固命令"    # 修复建议（换行用 \n）
  applicable_roles:           # 适用角色，空=通用
    - "access"
```

### match_type 说明

| 类型 | 语义 | 示例 |
|------|------|------|
| `find` | 正则命中 = 合规特征存在 = 通过 | `info-center enable` — 找到了说明日志已开启 |
| `not_find` | 正则命中 = 风险特征存在 = 扣分 | `password simple admin` — 找到了说明存在弱口令 |

---

## 2. 规则清单（16 条）

### 2.1 通用规则（6 条，所有角色适用）

| ID | 检测项 | 命令 | 类型 | 权重 |
|----|--------|------|------|------|
| AUTH_01 | 存在弱口令本地用户 | `display current-configuration` | not_find | 20 |
| LOG_01 | 日志审计未开启 | `display current-configuration` | find | 10 |
| NTP_01 | NTP 时间同步未配置 | `display current-configuration` | find | 5 |
| SSH_01 | SSH 未启用或 Telnet 未禁用 | `display current-configuration` | find | 10 |
| PWCTRL_01 | 全局密码强度控制未开启 | `display current-configuration` | find | 5 |
| IDLE_01 | Console/VTY 空闲超时未设置 | `display current-configuration` | find | 5 |

### 2.2 路由器规则（3 条）

| ID | 检测项 | 命令 | 类型 | 权重 |
|----|--------|------|------|------|
| RTR_CON_01 | Console 口未配置认证 | `display current-configuration` | find | 10 |
| RTR_VTY_01 | VTY 远程登录未绑定 ACL | `display current-configuration` | find | 10 |
| RTR_HTTP_01 | HTTP 服务未关闭 | `display current-configuration` | not_find | 5 |

### 2.3 接入层规则（5 条）

| ID | 检测项 | 命令 | 类型 | 权重 |
|----|--------|------|------|------|
| STP_01 | BPDU 保护未全局开启 | `display current-configuration` | find | 15 |
| DHCP_01 | DHCP Snooping 未开启 | `display dhcp snooping` | find | 15 |
| LOOP_01 | 环路检测未开启 | `display current-configuration` | find | 10 |
| STORM_01 | 风暴控制未配置 | `display current-configuration` | find | 10 |
| PORT_SEC_01 | 端口安全未开启 | `display current-configuration` | find | 10 |

### 2.4 汇聚层规则（3 条）

| ID | 检测项 | 命令 | 类型 | 权重 |
|----|--------|------|------|------|
| ACL_01 | 管理平面访问控制未配置 | `display acl all` | find | 15 |
| VRRP_01 | VRRP 未配置 MD5 认证 | `display current-configuration` | find | 10 |
| VTY_ACL_01 | VTY 远程登录未绑定 ACL | `display current-configuration` | find | 10 |

> 注：汇聚层规则同时适用于 `aggregation` 和 `core` 角色。

### 2.5 核心层规则（3 条）

| ID | 检测项 | 命令 | 类型 | 权重 |
|----|--------|------|------|------|
| ROUTE_01 | 路由协议未配置 MD5 认证 | `display current-configuration` | find | 15 |
| ACL_02 | SNMP 未绑定 ACL | `display current-configuration` | find | 10 |
| CPP_01 | 控制平面未配置协议限速 | `display current-configuration` | find | 10 |

---

## 3. 评分模型

### 3.1 计分公式

```
score = 100 - Σ(failed_items.weight)
score = max(score, 0)          # 不低于 0
```

### 3.2 风险等级阈值

| 等级 | 分数范围 | 附加条件 |
|------|----------|----------|
| **高风险** | score < 60 | **或** 命中致命项（如 AUTH_01） |
| **中风险** | 60 ≤ score < 85 | — |
| **低风险** | score ≥ 85 | — |

阈值可通过 `settings.yaml` 中的 `high_risk_threshold` 和 `medium_risk_threshold` 调整。

### 3.3 致命项

`FATAL_RULE_IDS = {"AUTH_01"}` — 弱口令在任何设备上命中即直接判高风险，无论分数多少。

### 3.4 规则适用逻辑

```
applicable_roles = []    → 通用规则，所有角色生效
applicable_roles = ["access"] → 仅接入层
applicable_roles = ["aggregation", "core"] → 汇聚 + 核心
applicable_roles = ["router"] → 仅路由器
applicable_roles = ["core"] → 仅核心层
```

路由器只评估通用规则 + 路由器规则，不涉及交换机的 STP/DHCP/VLAN 等检测项。

---

## 4. 自定义规则

### 添加新规则

在 `rules.yaml` 对应角色分组下添加：

```yaml
roles:
  common:           # 选择角色分组
    items:
      - id: "CUSTOM_01"
        desc: "自定义检测项"
        check_cmd: "display current-configuration"
        regex: 'your-pattern-here'
        match_type: "find"     # find 或 not_find
        weight: 10             # 扣分权重
        fix_template: "加固命令模板"
```

### 调整权重

直接修改已有规则的 `weight` 值。权重越高，对最终得分影响越大。

### 调整阈值

修改 `settings.yaml`：

```yaml
high_risk_threshold: 60    # 低于此分 = 高风险
medium_risk_threshold: 85  # 低于此分 = 中风险，≥ 此分 = 低风险
```

---

## 5. Regex 编写注意事项

### 5.1 YAML 单引号

所有正则必须使用 YAML 单引号 `'...'`，否则 `\s` `\d` 等会被 YAML 解析器当作转义字符报错。

```yaml
# ✓ 正确
regex: 'ospf\s+\d+'

# ✗ 错误 — YAML 不知道 \s 是什么
regex: "ospf\s+\d+"
```

### 5.2 不区分大小写

代码中使用 `re.IGNORECASE` 标志，正则无需额外处理大小写。如需要区分，使用 `(?-i)` 前缀。

### 5.3 多行匹配

`display current-configuration` 输出通常很长，注意：
- `^` 匹配行首时使用 `re.MULTILINE`（代码已添加）
- `[\s\S]*?` 用于跨行非贪婪匹配
- 避免 `.*` 跨行匹配导致性能问题
