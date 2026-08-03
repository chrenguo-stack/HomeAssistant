# ADR-0006：C06-B1 小时投影核心与 Host-only 适配器合同

- 状态：已接受（host-only 源码与证据）
- 授权门：`D1-C06B1-HOST-ONLY-PROJECTION-CORE-AND-ADAPTER-CONTRACT-STACKED-DRAFT-CREATION-20260803-01`
- stacked base：PR #261 精确 HEAD `d0e00d264d41755101c80ad37a1f6fa661892276`
- 前置：ADR-0005、ADR-0005 终审补充、技术路线 V0.7
- 明确排除：真实 Home Assistant 写入、T1、生产 Broker、DLI 累计统计、`relative_only` 时间重建

## 1. 背景

C06-A 已把历史补发与实时 canonical telemetry 隔离，并把绝对时间记录持久化到
`manager/manager-state.sqlite3`。每个存在绝对时间记录的 `(NODE_ID, UTC 小时)` 都会建立
`c06_projection_outbox`，晚到的新记录会重新打开该小时，而完全重复记录不会重新打开任务。

C06-B1 只完成 Manager 内部的小时投影核心、可靠任务状态和适配器合同。它不调用 Home Assistant，
不保存 HA 管理员令牌，不写 `home-assistant_v2.db`，也不改变当前 MQTT、Discovery、canonical、
凭据或匿名模式。

## 2. 决策

### 2.1 复用同一可移植 Manager 状态数据库

C06-B1 必须使用 C06-A 已存在的：

```text
/var/lib/greenhouse-manager/manager/manager-state.sqlite3
```

不得创建第二个 SQLite 文件。`ProjectionStore` 只有在 C06-A 的
`c06_history_records` 和 `c06_projection_outbox` 已存在时才允许初始化，并继续执行绝对路径、
可移植角色、最终路径和祖先符号链接以及 0600/0700 权限检查。

C06-B1 使用独立迁移表 `c06b1_schema_migrations`，当前版本为 1。它新增：

```text
c06_projection_jobs
```

该表以 `(node_id, sample_hour, projection_version)` 为主键，并外键关联 C06-A outbox；C06-A
清理 outbox 时，C06-B1 job 必须级联删除。

### 2.2 C06-A outbox 与 C06-B1 job 的同步

C06-A outbox 继续承担“这个小时需要投影”的基础事实。C06-B1 job 承担执行状态：

```text
pending
leased
retry
blocked
completed
```

数据库触发器在以下情况创建或重新打开 job：

- C06-A 首次创建 pending outbox；
- 晚到新记录把同一小时 outbox 重新置为 pending。

重新打开时：

- `revision` 加一；
- 旧租约和 claim 清除；
- 旧 hash、payload、适配器信息和错误清除；
- job 回到 `pending`。

C06-A 已保证完全重复记录不更新 outbox，因此完全重复不能增加 revision。

### 2.3 原子领取、租约和崩溃恢复

领取使用 SQLite `BEGIN IMMEDIATE`。一次只能由一个 worker 取得同一 job。领取后：

- state 变为 `leased`；
- attempts 加一；
- 保存 `claimed_by` 和 `lease_until`。

`pending`、已到期 `retry` 和租约已过期的 `leased` 可以被领取。`blocked` 和 `completed` 不可领取。
worker 崩溃后，另一个 worker 只有在租约到期后才能重新取得任务。

任何完成、重试或阻塞操作都必须同时匹配：

```text
node_id + sample_hour + projection_version + revision + claimed_by + leased
```

晚到记录在适配器执行期间增加 revision 后，旧 worker 的完成结果必须返回 stale，不能完成新 revision。

### 2.4 初版投影范围

C06-B1 只处理 Discovery 中 `state_class=measurement` 的数值传感器：

- 空气温度、湿度、CO₂、光照度；
- 土壤温度、水分、电导率；
- VPD、露点、绝对湿度；
- PPFD；
- 电池电压和电量。

每个小时、每个测量项输出：

```text
mean
min
max
samples
```

投影实体通过现有稳定 `unique_id` 表达：

```text
{NODE_ID}_{measurement_key}
```

C06-B1 不冻结最终 HA `entity_id`，因为用户可能在 Home Assistant 内改名。真实适配器必须在后继阶段
通过 `unique_id` 解析实体。

### 2.5 质量过滤

初版质量策略为 `ok-only/1`：

- 只有 `quality[measurement_key] == "ok"` 才允许进入聚合；
- `warming`、`stale`、`fault`、`not_present` 和缺失质量全部排除；
- `null`、布尔值和非有限数值排除；
- 没有合格样本时不产生 0、不插值、不复制上一小时。

每个投影保存审计计数：present、accepted、excluded_quality、invalid_or_null 和 missing。

### 2.6 时间质量和分桶

只允许 `trusted` 与 `estimated` 记录参与小时投影。每条记录的 `sampled_at` 在 UTC 中必须与被领取的
`sample_hour` 一致，否则 job 进入 `blocked`，等待数据或合同修复。

`relative_only` 不进行绝对时间重建，也不按 Manager `received_at` 强行分桶。其支持需要独立 ADR。

### 2.7 DLI 和累计值边界

`dli_today_mol_m2_d` 是 `total_increasing`，`dli_yesterday_mol_m2_d` 也不是普通 measurement。
C06-B1 不投影 DLI，不生成 `state`、`sum` 或 `last_reset`。累计值、日切换和重置语义必须单独设计。

### 2.8 确定性 payload 和 hash

投影 payload Schema：

```text
gh.c06-hourly-projection/1
```

hash 使用排序、无 NaN 的规范 JSON 计算 SHA-256，并覆盖：

- node/hour/version/revision；
- 算法版本和质量策略；
- 原始记录计数与审计计数；
- 每个 series 的元数据、样本数、mean/min/max；
- `relative_only`、DLI 和真实 HA 写入关闭状态。

同一 revision、同一原始记录集合必须产生完全相同的 hash。

### 2.9 适配器合同

适配器只允许返回：

```text
verified
retry
blocked
```

`verified` 必须返回被验证的 exact projection hash。hash 不一致视为 retry，不能完成 outbox。

- `retry`：暂时不可用，可按指数退避重试；
- `blocked`：实体、单位或合同问题，需要修复或新源记录重新打开；
- 未捕获的适配器异常默认保留任务并进入 retry。

本阶段唯一实现是 `FakeProjectionAdapter`：

- 不访问网络；
- 不调用 Home Assistant；
- 不写 HA 数据库；
- 只记录收到的投影并按脚本返回 host-only 结果。

### 2.10 完成语义

只有适配器返回 `verified` 且 exact hash 一致后，Manager 才可以在同一 SQLite 事务中：

1. 把 C06-B1 job 置为 `completed`；
2. 保存 payload、hash、适配器 kind/version 和验证时间；
3. 把 C06-A outbox 置为 `completed`。

WebSocket“已接收”或未来 HA Recorder“已排队”不能直接作为完成证明。真实适配器必须在后继阶段完成
写后读回核验。

## 3. 不变量

1. C06-B1 不覆盖 canonical 当前状态；
2. C06-B1 不发布 retained MQTT 消息；
3. C06-B1 不连接 Home Assistant；
4. C06-B1 不直接写 Home Assistant 数据库；
5. C06-B1 不创建第二个 Manager 数据库；
6. 完全重复记录不增加投影 revision；
7. 晚到新记录必须增加 revision 并使旧完成结果 stale；
8. worker 崩溃后只有租约到期才可重新领取；
9. hash 未被 exact 验证时不得完成 outbox；
10. blocked 任务不得静默删除；
11. `relative_only` 不重建绝对时间；
12. DLI 不按普通 measurement 聚合；
13. 本 ADR 不授权 Ready、merge、release、tag、deployment 或版本激活。

## 4. Host-only 验收

至少覆盖：

- C06-A 前置表缺失时失败关闭；
- 复用 `manager/manager-state.sqlite3` 且无第二数据库；
- 既有 pending outbox 迁移；
- 两连接竞争领取；
- 租约到期重领；
- retry 到期前不可领取、到期后可领取；
- blocked 持久化；
- raw/outbox 清理级联；
- 完全重复不重开；
- 晚到记录 revision 增加；
- 旧 revision 完成被拒绝；
- quality=ok 过滤；
- mean/min/max 与样本数；
- trusted/estimated 允许、relative_only 排除；
- DLI 排除；
- 确定性 hash；
- 适配器 hash mismatch 重试；
- retry 后幂等成功；
- 无合格样本的验证 no-op；
- 现有 C06-A 存储与终审回归；
- exact PR #261 base/ref、merge-base 和祖先关系；
- secret-free Artifact 内部 `SHA256SUMS` 校验。

## 5. 后继边界

C06-B2 才允许设计和实现 Home Assistant 自定义集成、`unique_id` 到实体映射、Recorder 正式导入、
单位和 state class 核验、写后读回以及应用级 ACK。C06-B3 才允许在隔离的临时 Home Assistant 中
进行真实写入验证。T1 和生产环境仍需更晚的独立授权门。
