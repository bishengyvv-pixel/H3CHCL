# 开发任务清单 — H3C 园区网自动化安全评估系统

## 立即交付
- [ ] **P0** 安装依赖：`pip install netmiko pyyaml openpyxl`
- [ ] **P0** 填写 `resources/devices.yaml` 添加目标设备 IP/凭据

## 待完善
- [ ] **P1** `connector/retry.py` — 装饰器接入 `DeviceConnection.connect()`，目前重试逻辑未与 connection 集成调用
- [ ] **P1** `engine/scheduler.py` — 如设备量超 20 台，增加批次分组（chunk）避免线程风暴
- [ ] **P1** `evaluator/rule_engine.py` — 支持多行 Regex 匹配（`re.DOTALL`），部分 H3C 输出为分页格式
- [ ] **P1** `identifier/role_identifier.py` — 接入层 `port link-type access` 计数阈值优化，防止单端口误判
- [ ] **P2** `evaluator/risk_calculator.py` — `FATAL_RULE_IDS` 改为从 `rules.yaml` 中 `critical: true` 字段读取
- [ ] **P2** `reporter/pdf_reporter.py` — 用 `reportlab` 实现完整 PDF 输出（仪表盘 + 设备详情 + 加固建议）
- [ ] **P2** `reporter/excel_reporter.py` — 首页增加"最薄弱 TOP5"排行榜
- [ ] **P3** `config/loader.py` — 增加 schema 校验，yaml 缺少必填字段时给出明确报错
- [ ] **P3** `connector/connection.py` — 支持 SSH 密钥认证（补充 `key_file` 参数）
- [ ] **P3** `main.py` — 敏感凭据不打印到日志，`collected_outputs` 写入日志时脱敏
- [ ] **P3** 单元测试覆盖：`rule_engine` / `risk_calculator` / `role_identifier`
