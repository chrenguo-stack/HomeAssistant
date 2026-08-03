# ADR-0005：C-06 历史遥测补发协议与 Manager 原始存储

- 状态：已接受
- 授权门：`D1-C06-HISTORY-REPLAY-PROTOCOL-STORAGE-AND-HOST-ONLY-STACKED-DRAFT-CREATION-20260803-01`
- stacked base：PR #260 精确 HEAD `d628b896314efd0aff58da151e3669eb7fe21d44`
- 关联：ADR-0003（节点身份与耐久退役）、ADR-0004（系统初始化与可移植恢复）、C-06、C-07

## 背景

实时 canonical telemetry 只表达当前状态。节点离线期间保存的历史记录不能通过实时 topic
回灌，否则会造成 retained 当前状态回退、Home Assistant 面板显示旧值，并把实时序列与历史序列
错误地耦合。

本 ADR 冻结 C06-A：独立 MQTT 协议、Manager 原始历史存储、分页确认、断点续传和未来小时投影
outbox。真实 Home Assistant 历史写入属于后继 C06-B，不在本决策内。

## 决策

### 1. 独立 MQTT 通道

节点发布：

```text
gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/history
```

Manager 确认：

```text
gh/v1/{SYSTEM_ID}/command/node/{NODE_ID}/history/ack
```

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
- `uptime_ms`、`sampled_at`、`cap_hash`；
- `measurements`、`quality`、`power`；
- 可选 `fw_version`。

`sampled_at` 是历史发生时间，必须带时区。节点不得提供 Manager 所有的 `received_at`。

### 3. 身份、重复和冲突

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
3. 同一记录键和同一规范化记录内容再次出现，作为记录级重复；
4. 同一记录键对应不同内容，拒绝整页并回滚；
5. 页到达顺序和 `seq` 大小不与 canonical telemetry 比较；
6. 一页内重复记录键直接拒绝。

### 4. ACK 与精确续传

ACK Schema 为 `gh.history-replay.ack/1`，返回原始 `batch_id`、`page_index`、`page_count`，以及：

- `status`：`accepted`、`duplicate` 或 `rejected`；
- `committed`：已耐久提交或已存在时为 `true`，拒绝时为 `false`；
- `records_total`、`inserted_records`、`duplicate_records`；
- `next_page_index`；
- `processed_at`；
- 拒绝时的 `reason`。

Manager 只有在 SQLite 事务成功提交，或确认同一页已耐久存在后，才发送 `committed=true`。
数据库错误返回内部 `retry` 状态并且不发送 ACK，节点必须重试当前页。协议不要求节点按页序发送；节点以
每页 ACK 为续传依据。

### 5. Manager 存储

C06-A 默认使用 PR #260 可移植状态根中的：

```text
/var/lib/greenhouse-manager/manager-state.sqlite3
```

不新增独立备份角色。所有表使用 `c06_` 前缀，避免接管 registration、credential、retirement
表：

- `c06_schema_migrations`；
- `c06_history_pages`；
- `c06_history_records`；
- `c06_projection_outbox`。

迁移必须幂等，能够从 Manager 0.4.98 空白状态数据库或含既有业务表的数据库前向建立，不修改、
删除或重命名其他表。不得使用共享数据库的全局 `PRAGMA user_version`。

### 6. 保留与小时投影边界

原始历史默认保存 7 天，可配置 1～30 天。提交页面时按 `sampled_at` 清理超期记录和对应的待投影
小时。页接收元数据按 `committed_at` 使用同一窗口清理。每个新记录所在的 UTC 小时写入或重新置为
`pending` 的投影 outbox。

C06-A 不调用 Home Assistant API，也不写 Home Assistant 数据库。C06-B 才负责：

- 小时聚合算法；
- 质量过滤；
- 迟到记录重算；
- Home Assistant 写入适配器；
- outbox 完成与重试状态。

### 7. 身份和退役约束

当 Manager 已加载 registration registry 时，历史入口仅接受 `NodeIdLeaseState.ACTIVE`：
retiring、retired 或未分配 NODE_ID 均拒绝。未加载 registry 时保持当前 telemetry 入口的兼容
行为，不在 C06-A 内擅自关闭匿名或改变 M2 认证策略。

### 8. 资源边界

默认边界：

- 每页最多 256 条；
- payload 最多 262144 字节，可配置 4096～1048576 字节；
- `page_count` 最多 4096；
- SQLite `busy_timeout` 5 秒；
- 单进程内使用可重入锁串行化写事务；
- 所有冲突整页回滚。

## 不变量

1. 历史补发绝不覆盖 canonical 当前状态；
2. 历史补发绝不产生 retained 消息；
3. ACK 不能先于耐久提交；
4. 记录冲突不能部分写入；
5. Manager 重启后重复页仍然可识别；
6. C06-A 不连接真实 Home Assistant、T1、生产 Broker 或板卡；
7. 本 ADR 不授权 Ready、merge、release、tag 或 deployment。

## Host-only 验收

必须覆盖：Schema、topic、retain、页几何、重复、冲突、乱序、重启续传、SQLite 幂等迁移、并发
重复、保留清理、投影 outbox、inactive NODE_ID、资源上限、数据库失败不 ACK、canonical/Discovery
隔离，以及现有 ingest、MQTT、C-07 和 H0/H1 回归。
