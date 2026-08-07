# ADR-0005 补充：C06-A 只读终审阻断项收敛

- 状态：已接受
- 主 ADR：`docs/adr/0005-c06-history-replay.md`
- 授权门：`D1-C06A-PR261-FINAL-REVIEW-BLOCKERS-REMEDIATION-AND-HOST-ONLY-REVALIDATION-20260803-01`
- stacked base：PR #260 精确 HEAD `d628b896314efd0aff58da151e3669eb7fe21d44`
- final-reviewed predecessor：PR #261 `ffdfbc3dc64620881ea0732d0d964623439d0bba`

## 背景

PR #261 的第一轮复核修复已经解决可移植数据库默认路径、ACK ACL、最小缺失页、
SQLite 跨连接原子性、历史时间质量、投影 outbox 保留边界、canonical Schema 复用和
异步 worker 等问题。随后只读终审又发现：超大 `uptime_ms` 可触发时间算术溢出、
单项处理或维护异常可终止 worker、队列前缺少 payload/QoS 边界、速率状态可随 NODE_ID
数量增长、数据库角色和悬空符号链接仍可被绕过，以及数据库字节容量缺少真实覆盖。

本补充冻结这些阻断项的最终收敛合同。主 ADR 中未被本补充替换的内容继续有效。

## 决策

### 1. 离线时间算术安全边界

历史记录和时间锚点的 `uptime_ms` 统一限制为：

```text
0 <= uptime_ms <= 315576000000
```

该上限相当于十个儒略年，远高于预期节点连续运行时间，同时确保 Manager 的
`timedelta` 算术处于明确边界内。JSON Schema 和运行时必须使用同一上限。

运行时在进行 `anchor_time + (uptime_ms - anchor_uptime_ms)` 前必须再次验证类型和范围，
并捕获 `OverflowError`、`ValueError` 及其他时间验证异常。任何异常均转化为当前页面的
确定性拒绝，不能逃逸到 MQTT worker。

### 2. worker 异常隔离和可观测性

每个历史工作项必须形成独立异常边界：

- 页面处理抛出未预期异常时，生成内部 `retry` 结果，不发送 ACK；
- ACK/结果回调抛出异常时记录失败，但不得终止 worker；
- 周期清理抛出 SQLite 或文件系统异常时记录失败、推迟下一次维护并继续处理后续页面；
- worker 暴露 `is_alive`、累计失败次数、最后失败阶段和异常类型；
- Manager 主循环发现 worker 非存活时记录状态并重新启动。

坏页面、一次发布失败或一次数据库锁超时不得造成历史补发永久静默停止。

### 3. 入队前 payload 和 QoS 边界

MQTT 回调在复制 payload 或创建队列项前必须检查：

- payload 字节数不超过 `GH_HISTORY_MAX_PAYLOAD_BYTES`；
- 历史页面发布 QoS 必须为 1。

超限 payload 或 QoS 0/2 页面不进入队列、不执行 JSON/SQLite，也不发送 ACK；节点保留当前页
并按协议重新发送。订阅端使用 QoS 1 不视为对发布端 QoS 的替代验证。

### 4. 速率状态的全局边界

每节点一分钟页面速率之外，Manager 还必须限制速率跟踪状态本身：

- `GH_HISTORY_RATE_STATE_CAPACITY` 默认 1024，可配置 1～65536；
- `GH_HISTORY_RATE_STATE_TTL_S` 默认 3600 秒，可配置 1～86400 秒；
- 新 NODE_ID 在状态容量已满时返回内部 `rate_state_full`，不创建状态、不入队、不 ACK；
- 超过 TTL 未活动的 NODE_ID 状态在下一次准入检查时清除；
- 队列已满的页面不得遗留新的 NODE_ID 速率状态。

由此，匿名兼容阶段不断变化 NODE_ID 不能造成无界字典增长。

### 5. 可移植数据库角色和符号链接

启用 C06-A 时，`GH_HISTORY_DB_PATH` 必须：

1. 为绝对路径；
2. 最后两个路径组成部分精确等于 `manager/manager-state.sqlite3`；
3. 最终路径不是符号链接；
4. 任一祖先路径不是符号链接。

不同 host-only 测试根目录可以使用，只要保持相同的可移植角色相对路径。生产默认仍为：

```text
/var/lib/greenhouse-manager/manager/manager-state.sqlite3
```

符号链接检查不得依赖 `Path.exists()`，因为悬空符号链接也必须失败关闭。`Settings.validate()`
和 `HistoryStore` 均执行角色及链接检查，避免通过直接构造运行时对象绕过配置验证。

### 6. 数据库字节容量真实验证

Host-only 测试必须实际扩展 SQLite 文件的有效页面数，使其超过配置的最小 1 MiB 边界，
随后提交一个有效历史页，并验证：

- 返回容量拒绝；
- 错误原因明确为数据库字节容量；
- `c06_history_records` 没有部分写入；
- 不产生 `committed=true` ACK。

仅验证记录数量上限不能替代该测试。

### 7. 证据字段精确性

最终 Artifact 使用 `gh.c06-history-replay-host-only-report/3`，明确区分：

- 第一轮 reviewed predecessor `dac038c...`；
- final-reviewed predecessor `ffdfbc3...`；
- 当前 source SHA；
- 两个 predecessor 的真实祖先核验结果；
- 精确 PR #260 base/merge-base 核验；
- uptime 拒绝、worker 异常隔离、速率状态边界、入队前 payload/QoS、可移植角色、
  悬空符号链接和真实数据库字节容量验证结果。

祖先核验布尔值只有在 workflow 实际执行 `git merge-base --is-ancestor` 成功后才允许写入报告，
不得仅因报告包含 SHA 字符串而声明为 true。

## 新增不变量

1. 合法或恶意 JSON 整数不能通过时间算术终止历史 worker；
2. 单个工作项、结果回调或维护失败不能终止后续历史处理；
3. 超限 payload 在进入内存队列前即被拒绝；
4. 历史入口只接受发布 QoS 1；
5. NODE_ID 速率状态数量和生命周期均有明确上限；
6. C-06 数据库不能离开 `manager/manager-state.sqlite3` 可移植角色；
7. 最终路径和任一祖先的悬空或有效符号链接均失败关闭；
8. 数据库字节容量必须由真实 SQLite 页面测试证明；
9. 本补充仍不授权 C06-B、真实 Home Assistant 历史写入、生产操作、Ready、merge、release、tag、deployment 或版本激活。

## Host-only 验收

必须覆盖：超大 `uptime_ms`、运行时 OverflowError 防护、页面处理异常、结果回调异常、维护锁失败、
worker 存活状态、超限 payload 不入队、QoS 0 不入队、NODE_ID 状态容量、状态 TTL 清理、
非可移植绝对路径、最终悬空符号链接、祖先悬空符号链接、真实数据库字节容量、精确 stacked base、
两个 reviewed predecessor 祖先关系、既有 C06-A 协议和全部适用回归工作流。
