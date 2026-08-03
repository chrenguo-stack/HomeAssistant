# ADR-0006：C06-B1 小时投影核心与 Host-only 适配器合同

- 状态：已接受（host-only 源码、终审阻断项修复与证据）
- 初始授权门：`D1-C06B1-HOST-ONLY-PROJECTION-CORE-AND-ADAPTER-CONTRACT-STACKED-DRAFT-CREATION-20260803-01`
- 终审修复授权门：`D1-C06B1-PR262-READ-ONLY-REVIEW-BLOCKERS-REMEDIATION-AND-HOST-ONLY-REVALIDATION-20260803-01`
- stacked base：PR #261 精确 HEAD `d0e00d264d41755101c80ad37a1f6fa661892276`
- 前置：ADR-0005、ADR-0005 终审补充、技术路线 V0.7
- 明确排除：真实 Home Assistant 写入、T1、生产 Broker、DLI 累计统计、`relative_only` 时间重建

## 1. 背景

C06-A 已把历史补发与实时 canonical telemetry 隔离，并把绝对时间记录持久化到
`manager/manager-state.sqlite3`。绝对时间记录会为 `(NODE_ID, UTC 小时)` 建立
`c06_projection_outbox`；晚到新记录重新打开小时，完全重复记录不重新打开任务。

C06-B1 只完成 Manager 内部的小时投影核心、可靠任务状态和真实适配器之前的合同冻结。它不调用
Home Assistant，不保存 HA 管理员令牌，不写 `home-assistant_v2.db`，也不改变当前 MQTT、
Discovery、canonical、凭据或匿名模式。

只读终审发现并修复了以下问题：

- 合法但极端的 JSON 数值可能触发 `float`/`fsum` 溢出并永久 retry；
- 适配器返回后仍使用任务开始时间，且过期租约可能被旧 worker 完成；
- 没有 C06-B1 hash/readback 证据的旧 completed outbox 被错误信任；
- 新 revision 继承旧 attempts；
- blocked 缺少操作员修复后的显式恢复路径；
- stale 外部写入缺少目标侧单调 revision 合同；
- hashed payload 混入运行安全开关，且没有机器可验证 Schema；
- 专项 CI 未覆盖共享依赖路径。

## 2. 决策

### 2.1 复用同一可移植 Manager 状态数据库

C06-B1 必须使用：

```text
/var/lib/greenhouse-manager/manager/manager-state.sqlite3
```

不得创建第二个 SQLite 文件。`ProjectionStore` 仅在 C06-A 的
`c06_history_records` 和 `c06_projection_outbox` 已存在时初始化，并继续执行绝对路径、
可移植角色、最终路径与祖先符号链接以及 0600/0700 权限检查。

C06-B1 使用独立迁移表 `c06b1_schema_migrations`，当前版本为 2。执行状态表为：

```text
c06_projection_jobs
```

主键为 `(node_id, sample_hour, projection_version)`，外键关联 C06-A outbox，C06-A 清理
outbox 时 job 级联删除。

### 2.2 状态、revision 与 attempts

job 状态：

```text
pending
leased
retry
blocked
completed
```

C06-A outbox 是“该小时需要投影”的基础事实，job 是执行状态。

新源记录到达时：

- job 为 `pending`：吸收新源记录，不增加 revision，因为尚无冻结执行 generation；
- job 为 `leased`、`retry`、`blocked` 或 `completed`：revision 加一；
- 新 revision 的 attempts 重置为 0；
- 清除旧 claim、lease、hash、payload、适配器信息、验证时间和错误；
- job 回到 `pending`。

完全重复 page/record 不更新 outbox，因此不增加 revision。一个 page 内同小时的多条新记录只形成
一个新的执行 generation。

### 2.3 原子领取、有限租约与实际结算时间

领取使用 SQLite `BEGIN IMMEDIATE`。一次只能由一个 worker 取得同一 job。领取后：

- state=`leased`；
- 当前 revision 的 attempts 加一；
- 保存 `claimed_by` 和 `lease_until`。

可领取状态只有：

- `pending`；
- 已到期 `retry`；
- 租约已过期的 `leased`。

任何完成、retry 或 blocked 操作必须同时匹配：

```text
node_id
sample_hour
projection_version
revision
claimed_by
state=leased
lease_until > 实际结算时间
```

Manager 在适配器返回后重新取得实际结算时间。`verified_at`、`completed_at`、retry 基准和错误时间
均使用实际结算时间，不使用任务开始时间。

适配器合同冻结：

```text
adapter_timeout_seconds < lease_seconds
```

默认 timeout 为 30 秒、lease 为 60 秒。超过 timeout 但租约仍有效时进入 retry；超过租约时旧
worker 只能返回 stale，不能完成、retry 或 blocked。后继真实适配器如需更长操作，必须实现单独
续租合同，不能无界延长。

### 2.4 初版投影范围与数值安全包络

只处理 Discovery 中 `state_class=measurement` 的数值传感器：

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

每类测量值冻结宽松的安全包络。该包络用于防止整数转 float、非有限值和聚合溢出，不是农艺告警
阈值。超出包络、无法转为有限 float、`math.fsum` 溢出、损坏时间戳、重复源身份或 Schema
不匹配均属于确定性合同错误，job 进入 blocked，不进行无限 retry。

每小时最多 10,000 条源记录；规范 JSON payload 最大 1,048,576 字节。

### 2.5 质量过滤

质量策略为 `ok-only/1`：

- 仅 `quality[measurement_key] == "ok"` 进入聚合；
- `warming`、`stale`、`fault`、`not_present` 和缺失质量排除；
- `null`、布尔值和非数值排除；
- 没有合格样本时不产生 0、不插值、不复制上一小时。

每个测量项保存：

```text
present
accepted
excluded_quality
invalid_or_null
missing
```

### 2.6 时间质量

仅 `trusted` 与 `estimated` 参与绝对小时投影。每条记录的 `sampled_at` 必须在 UTC 中与
`sample_hour` 一致。

`relative_only` 不重建绝对时间，也不按 Manager `received_at` 强行分桶；其支持需要独立 ADR。

### 2.7 DLI 边界

`dli_today_mol_m2_d` 是 `total_increasing`，`dli_yesterday_mol_m2_d` 也不是普通
measurement。C06-B1 不投影 DLI，不生成 `state`、`sum` 或 `last_reset`。

### 2.8 中立、机器可验证的 projection payload

正式 Schema 文件：

```text
greenhouse_manager/schemas/gh.c06-hourly-projection-1.schema.json
```

Schema 标识：

```text
gh.c06-hourly-projection/1
```

payload 只包含稳定投影事实，不包含部署或运行安全状态。以下字段不允许进入 hashed payload：

```text
home_assistant_write_enabled
direct_home_assistant_database_write
relative_only_reconstruction
dli_counter_projection
```

这些安全状态属于 CI/Artifact 证据。

payload hash 使用排序、无 NaN 的规范 JSON 计算 SHA-256，覆盖：

- stable `idempotency_key`；
- node/hour/projection_version/revision；
- algorithm version 与质量策略；
- source record count；
- 按 `(boot_id, seq)` 排序后计算的 `source_set_sha256`；
- eligible/skipped 计数；
- 每个 series 的元数据、样本数、mean/min/max；
- 全部质量审计计数。

`algorithm_version=2`。算法或 hashed payload 语义变化必须增加 algorithm version；需要并行
保留旧结果时增加 projection version。

### 2.9 目标侧幂等与单调 revision 合同

稳定幂等身份：

```text
idempotency_key = NODE_ID | UTC-hour | projection-version
```

适配器只能返回：

```text
verified
retry
blocked
```

`verified` 必须同时证明：

- exact idempotency key；
- exact revision；
- exact projection hash；
- 目标端执行了单调 revision 规则。

目标端规则：

1. 目标不存在：写入 `(revision, hash, payload)`；
2. 目标 revision 小于请求 revision：以新 revision 替换；
3. 目标 revision 等于请求 revision 且 hash 相同：幂等成功；
4. 目标 revision 等于请求 revision 但 hash 不同：冲突，blocked；
5. 目标 revision 大于请求 revision：旧请求不得覆盖，返回 stale/blocked 语义；
6. timeout 后结果未知：必须先读回 exact tuple，再决定成功或 retry。

Manager 在 dispatch 前检查本地 claim；dispatch 后仍需 exact tuple 验证并再次用 revision、
claimed_by 和有效租约结算。仅本地 stale 检查不足以撤销已经发生的外部副作用，因此真实
C06-B2 适配器必须在目标侧实现上述规则。

本阶段唯一实现仍是 `FakeProjectionAdapter`：

- 不访问网络；
- 不调用 Home Assistant；
- 不写 HA 数据库；
- 在内存中模拟 exact tuple 与单调 revision 验证。

### 2.10 完成语义

只有适配器返回完整 verified tuple 后，Manager 才能在同一 SQLite 事务中：

1. 把 C06-B1 job 置为 completed；
2. 保存规范 payload、匹配的 SHA-256、适配器 kind/version 和实际验证时间；
3. 把 C06-A outbox 置为 completed。

Store 还会独立验证：

- hash 为小写 64 位 SHA-256；
- hash 与 `payload_json` 字节完全匹配；
- payload 未超过大小上限；
- claim revision/owner/lease 仍有效。

WebSocket“已接收”或 Recorder“已排队”不能作为完成证明。真实适配器必须写后读回。

### 2.11 旧 completed 数据迁移

没有以下完整证据的旧 completed job/outbox 不可信：

```text
projection_hash
payload_json
adapter_kind
adapter_version
verified_at
completed_at
```

升级时必须 fail closed：

- job 改为 pending；
- attempts 重置；
- outbox 改为 pending；
- 重新投影并验证。

已具备完整 C06-B1 证据的 completed job 在重启后保持 completed。

### 2.12 blocked 的显式恢复

blocked 不自动重试、不静默删除。操作员修复实体、单位、权限或适配器配置后，可调用 revision-safe
操作：

```text
requeue_blocked(
    node_id,
    sample_hour,
    projection_version,
    expected_revision,
    operator_reason
)
```

仅 exact expected revision 且当前仍为 blocked 时成功。操作记录：

```text
requeue_count
last_requeued_at
last_requeue_reason
```

恢复不伪造新源记录，也不增加 source revision。

## 3. 不变量

1. 不覆盖 canonical 当前状态；
2. 不发布 retained 历史消息；
3. C06-B1 不连接 Home Assistant；
4. 不直接写 Home Assistant 数据库；
5. 不创建第二个 Manager 数据库；
6. 完全重复记录不增加 revision；
7. 晚到新记录使冻结 generation 增加 revision；
8. 新 revision 不继承旧 attempts；
9. 过期租约不得结算；
10. exact tuple 未验证不得完成 outbox；
11. 低 revision 不得覆盖高 revision；
12. 同 revision、不同 hash 必须冲突；
13. blocked 不得静默删除；
14. `relative_only` 不重建绝对时间；
15. DLI 不按普通 measurement 聚合；
16. hashed payload 不包含运行安全开关；
17. 本 ADR 不授权 Ready、merge、release、tag、deployment 或版本激活。

## 4. Host-only 验收

至少覆盖：

- C06-A 前置表缺失失败关闭；
- 同一 `manager/manager-state.sqlite3`，无第二数据库；
- pending outbox 迁移；
- 缺少 C06-B1 证据的旧 completed fail-closed 重开；
- 完整 completed 在重启后保持完成；
- 两连接竞争领取；
- 租约到期重领；
- 过期租约完成/blocked 被拒绝；
- 实际结算时间和 adapter timeout；
- retry 到期前不可领取、到期后可领取；
- blocked 持久化和 revision-safe operator requeue；
- raw/outbox 清理级联；
- 完全重复不重开；
- 一个 page 多条晚到记录只建立一个新 generation；
- 新 revision attempts 重置；
- 极大整数、超大 float、损坏时间戳和重复身份进入 blocked；
- quality=ok 过滤；
- trusted/estimated 允许、relative_only 排除；
- DLI 排除；
- source-set 与 projection hash 确定性；
- 机器可验证 payload Schema；
- exact idempotency/revision/hash/monotonic tuple；
- payload hash 和大小边界；
- 无合格样本的 verified no-op；
- 现有 C06-A 存储与终审回归；
- exact PR #261 base/ref、merge-base 和祖先关系；
- secret-free Artifact 内部 `SHA256SUMS`。

## 5. CI 依赖边界

C06-B1 专项 CI 必须监听自身文件以及直接共享依赖：

```text
history_store.py
history_replay.py
ha_discovery.py
gh.telemetry-1.schema.json
gh.c06-hourly-projection-1.schema.json
history_samples.py
pyproject.toml
```

这些依赖变化时必须重新生成 C06-B1 Artifact，不能仅依赖通用 Manager CI。

## 6. 后继边界

C06-B2 才允许实现 Home Assistant 自定义集成、`unique_id` 到实体映射、Recorder 正式导入、
单位和 state class 核验、目标侧单调 revision、写后读回和应用级 ACK。

C06-B3 才允许在隔离临时 Home Assistant 中真实写入验证。T1 和生产环境仍需更晚的独立授权门。
