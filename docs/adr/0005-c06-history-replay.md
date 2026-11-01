# ADR-0005：C-06 历史遥测补发协议与 Manager 原始存储

- 状态：已接受
- 初始实现授权门：`D1-C06-HISTORY-REPLAY-PROTOCOL-STORAGE-AND-HOST-ONLY-STACKED-DRAFT-CREATION-20260803-01`
- 复核修复授权门：`D1-C06A-PR261-READ-ONLY-REVIEW-FINDINGS-REMEDIATION-AND-HOST-ONLY-REVALIDATION-20260803-01`
- stacked base：PR #260 精确 HEAD `d628b896314efd0aff58da151e3669eb7fe21d44`
- 修复前 reviewed HEAD：PR #261 `dac038c3595c80ac7d1a0666795effbbab4a4e4e`
- 关联：ADR-0002（节点 ACL）、ADR-0003（节点身份与耐久退役）、ADR-0004（系统初始化与可移植恢复）、C-06、C-07

## 背景

实时 canonical telemetry 只表达当前状态。节点离线期间保存的历史记录不能通过实时 topic
回灌，否则会造成 retained 当前状态回退、Home Assistant 面板显示旧值，并把实时序列与历史序列
错误地耦合。

本 ADR 冻结 C06-A：独立 MQTT 协议、Manager 原始历史存储、分页确认、断点续传、离线时间质量、
有界异步处理和未来小时投影 outbox。真实 Home Assistant 历史写入属于后继 C06-B，不在本决策内。

## 决策

### 1. 独立 MQTT 通道与既有 ACL 对齐

节点发布：

```text
gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/history
```

Manager 确认：

```text
gh/v1/{SYSTEM_ID}/out/node/{NODE_ID}/history/ack
```

ACK 使用 ADR-0002 已冻结的节点下行 `out/node/<node_id>/#` ACL，不新增 `command/node` 权限。
两者均使用 QoS 1，必须 `retain=false`。历史消息不得发布到 `/state/`，不得生成 availability、
diagnostic 或 Home Assistant Discovery 消息。

### 2. 批次页协议

历史页 Schema 为 `gh.history-replay.batch/1`。必需字段：

- `node_id`：必须与 topic 中的 NODE_ID 一致；
- `batch_id`：节点生成的 8～64 字符稳定批次标识；
- `page_index`：从 0 开始；
- `page_count`：1～4096，且 `page_index < page_count`；
- `records`：每页 1～256 条。

每条记录必须包含：

- `boot_id`、`seq`：组成节点内稳定记录身份；
- `uptime_ms`、`sampled_at`、`time_quality`、`time_anchor`；
- `cap_hash`、`measurements`、`quality`、`power`；
- 可选 `fw_version`。

同一个 `(NODE_ID, batch_id)` 的所有页面必须声明完全相同的 `page_count`。

### 3. 历史时间质量与离线时钟

`time_quality` 只有三种状态：

1. `trusted`：`sampled_at` 必须为带时区的 RFC 3339 绝对时间，`time_anchor=null`；
2. `estimated`：`sampled_at` 必须为绝对时间，`time_anchor` 必须包含最近可信锚点的
   `sampled_at` 和 `uptime_ms`；Manager 使用当前记录 `uptime_ms` 验证推算结果，容差 1 秒；
3. `relative_only`：用于冷启动后尚未取得可信时间的离线样本，`sampled_at=null`、
   `time_anchor=null`，仅保存 `boot_id + seq + uptime_ms` 的相对顺序。

绝对时间默认最多允许比 Manager 接收时间快 300 秒，可配置 0～86400 秒。绝对时间早于当前原始历史
保留窗口的页面整页拒绝，不能返回误导性的 `committed=true`。`relative_only` 记录按 Manager
`received_at` 保留，不创建小时投影 outbox；其未来绝对时间重建不属于 C06-A。

RFC 3339 解析必须接受 Schema 允许的合法大小写形式，并在入库前规范化为 UTC 毫秒 `Z` 表示。

### 4. Canonical 测量与质量合同复用

历史记录的 `measurements`、`quality` 和 `power` 以
`gh.telemetry-1.schema.json` 的对应属性为规范来源。运行时加载历史 Schema 时必须注入 canonical
定义，静态历史 Schema 副本必须通过测试与 canonical 定义逐项相等。历史补发不得接受实时
telemetry 会拒绝的湿度、百分比、CO₂、照度、土壤水分、电导率等越界值。

### 5. 身份、重复、冲突与 SQLite 原子性

记录稳定键：

```text
(NODE_ID, boot_id, seq)
```

页稳定键：

```text
(NODE_ID, batch_id, page_index)
```

处理规则：

1. 同一页键和同一规范化 payload 重试，返回 `duplicate` ACK；
2. 同一页键对应不同 payload，拒绝整页；
3. 同一批次不同页面声明不同 `page_count`，拒绝整页；
4. 同一记录键和同一规范化记录内容再次出现，作为记录级重复；
5. 同一记录键对应不同内容，拒绝整页并回滚；
6. 页到达顺序和 `seq` 大小不与 canonical telemetry 比较；
7. 一页内重复记录键直接拒绝。

每次页面提交在冲突预检之前执行 SQLite `BEGIN IMMEDIATE`，因此多个进程或多个连接不能同时在旧快照
上完成“记录不存在”判断。插入被忽略时必须重新核对已存在记录的 SHA-256，不能把跨连接内容冲突
误报为 accepted。

### 6. ACK 与精确续传

ACK Schema 为 `gh.history-replay.ack/1`，返回原始 `batch_id`、`page_index`、`page_count`，以及：

- `status`：`accepted`、`duplicate` 或 `rejected`；
- `committed`：已耐久提交或已存在时为 `true`，拒绝时为 `false`；
- `records_total`、`inserted_records`、`duplicate_records`；
- `next_page_index`；
- `processed_at`；
- 拒绝时的 `reason`。

`accepted` 或 `duplicate` 后，`next_page_index` 必须是当前批次中**最小的未提交页号**；所有页面均已
提交时才为 `null`。因此先收到最后一页不能错误返回完成。`rejected` 页面保持
`next_page_index == page_index`，防止节点越过未提交页。

Manager 只有在 SQLite 事务成功提交，或确认同一页已耐久存在后，才发送 `committed=true`。
数据库错误返回内部 `retry` 状态并且不发送 ACK，节点必须重试当前页。

### 7. Manager 可移植存储与权限

C06-A 必须复用 PR #260 十角色清单中的 Manager 状态文件：

```text
/var/lib/greenhouse-manager/manager/manager-state.sqlite3
```

相对可移植角色路径为：

```text
manager/manager-state.sqlite3
```

不得在 `/var/lib/greenhouse-manager/manager-state.sqlite3` 创建第二个未纳入备份的数据库。
路径必须为绝对路径，不得为符号链接；最终 `manager` 目录模式为 `0700`，数据库模式为 `0600`。

所有表使用 `c06_` 前缀，避免接管 registration、credential、retirement 表：

- `c06_schema_migrations`；
- `c06_history_pages`；
- `c06_history_records`；
- `c06_projection_outbox`。

Schema 版本 2 增加 `time_quality`、可空 `sampled_at/sample_hour` 和 `time_anchor_json`，并从 reviewed
HEAD 的版本 1 幂等前向迁移；已有版本 1 记录按 `trusted` 迁入。迁移不得修改、删除或重命名其他
Manager 表，也不得使用共享数据库的全局 `PRAGMA user_version`。

### 8. 保留、投影 outbox 与容量边界

原始历史默认保存 7 天，可配置 1～30 天。绝对时间记录按 `sampled_at` 清理，`relative_only` 按
Manager `received_at` 清理，页元数据按 `committed_at` 清理。

清理投影 outbox 时，只有对应 `(node_id, sample_hour)` 已不存在任何原始记录才允许删除任务。
同一小时内一条过期记录被删除、另一条仍有效时，outbox 必须保留。只有新插入的绝对时间记录才创建
或重新打开投影任务；完全重复记录不得重新打开已完成任务。

默认容量边界：

- 全库最多 250000 条原始记录，可配置 1024～2000000；
- SQLite 有效页面最多 256 MiB，可配置 1 MiB～2 GiB；
- 达到容量时整页拒绝并保持当前页游标，不允许部分写入。

### 9. 有界异步 worker 与流量隔离

MQTT 回调只执行 topic、租约状态和有界队列准入，不同步执行 JSON Schema、SQLite 或 5 秒
`busy_timeout`。单个 C-06 worker 串行处理历史页并在耐久提交后发布 ACK，避免历史流量阻塞实时
telemetry、配对和 canonical 恢复。

默认边界：

- 队列容量 64，可配置 1～1024；
- 每节点每分钟最多 60 页，可配置 1～600；
- 周期清理间隔 300 秒，可配置 30～86400 秒；
- payload 最多 262144 字节，可配置 4096～1048576 字节；
- 每页最多 256 条；
- SQLite `busy_timeout` 5 秒。

队列满或节点速率超限时不发送 ACK，节点保留当前页并稍后重试。即使没有新历史页，worker 也必须按
周期执行保留清理。

### 10. 身份和退役约束

当 Manager 已加载 registration registry 时，历史入口仅接受 `NodeIdLeaseState.ACTIVE`：
retiring、retired 或未分配 NODE_ID 均拒绝。未加载 registry 时保持当前 telemetry 入口的兼容
行为，不在 C06-A 内擅自关闭匿名或改变 M2 认证策略。

### 11. C06-B 边界

C06-A 不调用 Home Assistant API，也不写 Home Assistant 数据库。C06-B 才负责：

- 小时聚合算法；
- 质量过滤；
- 迟到记录重算；
- `relative_only` 时间重建方案（若后续决定支持）；
- Home Assistant 写入适配器；
- outbox 完成与重试状态。

### 12. Host-only 证据绑定

C-06 GitHub Actions 必须在 pull request 事件中核验：

- stacked base ref；
- PR #260 精确 base SHA；
- merge base 等于该精确 SHA；
- reviewed HEAD `dac038c...` 是当前修复 HEAD 的祖先。

证据报告必须记录修复授权门、reviewed HEAD、source ref/SHA、base ref/SHA、精确基线核验结果、
可移植相对路径、Schema 版本、异步队列隔离、最小缺失页游标和 ACK ACL 命名空间。Artifact 内
`SHA256SUMS` 使用解压根目录可直接校验的相对文件名，并在上传前执行 `sha256sum -c`。

## 不变量

1. 历史补发绝不覆盖 canonical 当前状态；
2. 历史补发绝不产生 retained 消息；
3. ACK 不能先于耐久提交；
4. 记录冲突不能部分写入；
5. Manager 重启后重复页仍然可识别；
6. 最后一页先到不能把未完成批次标记为完成；
7. 拒绝页不能推动节点越过当前页；
8. 完全重复记录不能重新打开已完成投影任务；
9. 保留清理不能删除仍有有效记录的小时 outbox；
10. C-06 数据必须位于 PR #260 已声明的可移植 Manager 状态角色内；
11. C06-A 不连接真实 Home Assistant、T1、生产 Broker 或板卡；
12. 本 ADR 不授权 Ready、merge、release、tag 或 deployment。

## Host-only 验收

必须覆盖：Schema、canonical 测量范围复用、topic、正式节点 ACL 命名空间、retain、页几何、批次
`page_count` 一致性、最小缺失页、重复、冲突、乱序、重启续传、SQLite v1→v2 迁移、既有 Manager
表保留、两个独立连接竞争、绝对/估算/相对时间、未来偏差、过期时间、RFC 3339 合法大小写、私有路径
权限、保留窗口边界小时、投影 outbox 幂等性、inactive NODE_ID、队列上限、速率限制、周期清理、
记录/数据库容量、数据库失败不 ACK、canonical/Discovery 隔离，以及现有 ingest、MQTT、C-07、M2、
H0/H1、路线图、配对、M0 和公共仓库安全回归。
