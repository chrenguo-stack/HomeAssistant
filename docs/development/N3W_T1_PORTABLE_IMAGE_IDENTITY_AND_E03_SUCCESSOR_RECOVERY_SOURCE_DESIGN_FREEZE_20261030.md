# N3-W T1 Portable Image Identity 与 E03 Successor Recovery Source Design Freeze

日期：2026-10-30

状态：

```text
DESIGN_STATUS=FROZEN
SOURCE_REPAIR_STARTED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
OLD_AUTHORIZATION_REPLAY=false
LIVE_RECOVERY_AUTHORIZED=false
```

设计 Gate：

```text
N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_DESIGN_FREEZE_20261030_01
```

基线 authority：

```text
PR725_HEAD=614c08a397462850f0167b77c9da45ae69a323ad
LIVE_EXECUTOR_BLOB=c46a2a180ce62d54d6d1eb3c0e296f9c55bef0f5
SSH_TRANSPORT_BLOB=dec4c9159195e2008094d94fef3fc76c4b977e46
TARGET_SOURCE_HEAD=f8876fd87165df731d792690a8288867c3eeef55
TARGET_ARTIFACT_RUN_ID=40880705472
TARGET_ARTIFACT_ID=12900601779
TARGET_ARTIFACT_SHA256=c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183
TARGET_MANAGER_TAR_SHA256=d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5
```

上位评审：
`docs/development/N3W_T1_MAINTENANCE_IDENTITY_REVIEW_20261030.md`

正式生产路线：
`docs/adr/0010-t1-per-device-fresh-armbian-automated-product-deployment.md`

---

## 1. 设计结论

本 Gate 冻结以下决策：

1. 当前问题不能以“把 expected image ID 从 config digest 改成 manifest digest”关闭。
2. 正式拆分：
   - Release Content Identity；
   - Host-local Object Binding；
   - Production Deployment & Health Contract。
3. 建立一个主机侧、标准库 Python 的 Portable Image Identity 公共内核。
4. 建立一个最小、可恢复的 Host Maintenance Transaction 模型。
5. 当前 E03 不续跑旧 transaction；使用新的、单独授权的 successor recovery transaction。
6. 原 E03 transaction、旧 authorization 和已加载 candidate 保留为不可改写的历史证据。
7. Golden Master / Final Seal / clone production route 已被 ADR-0010 退役，不重新迁移进生产路线。
8. P0 必须同时关闭：
   - 已知 single-.Id cross-store false STOP；
   - B1 transaction authority binding；
   - B2 unknown Compose overwrite；
   - B3 crash/power-loss + service-owner race；
   - B4 insufficient runtime/MQTT acceptance。
9. P0 不等待全仓迁移完成；但从 P0 起禁止新增私有 image-identity validator。

---

## 2. 非目标

P0 不做：

- Kubernetes 或外部编排平台；
- A/B root filesystem；
- 新数据库集群或事件平台；
- Golden Master 复活；
- 全仓历史 executor 一次性重写；
- Docker/Compose/Armbian 大版本升级；
- 自动 destructive DB rollback；
- T1 live recovery；
- 旧 authorization replay。

---

## 3. 当前 E03 事实边界

当前已归档事实：

```text
OLD_TRANSACTION_STATUS=CLAIMED
OLD_TRANSACTION_PHASE=AUTHORIZATION_CLAIMED
OLD_AUTHORIZATION_CONSUMED=true
OLD_REPLAY_ALLOWED=false

PRODUCTION_SERVICE_CUTOVER_OCCURRED=false
CURRENT_MANAGER=predecessor
HOMEASSISTANT=predecessor
BROKER=continuous
E03_COMMIT_CLASSIFICATION=DEFINITELY_NOT_COMMITTED
```

目标 Manager tar 已进入 T1 Docker image store。

已证明：

```text
artifact config digest
= sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4

artifact OCI manifest digest
= sha256:7751d48316836a50189490fc0c3bf6cdaf5ff741a3f638610887bf6b9ac5d5e8

T1 containerd-store target-tag Id
= sha256:7751d48316836a50189490fc0c3bf6cdaf5ff741a3f638610887bf6b9ac5d5e8
```

因此：

```text
ARTIFACT_CORRUPTION=false
ROOT_CAUSE=EXECUTOR_CROSS_IMAGE_STORE_IMAGE_ID_CONTRACT_FALSE_NEGATIVE
```

但这只证明当前已知 target image 的 identity false STOP；不能放宽成“任意不同 .Id 均可接受”。

---

## 4. 三层合同

### 4.1 Release Content Identity

回答：

> 目标内容是否确实来自批准的 release？

authority 来自可信 release contract 及其指向的 artifact 内容，不依赖目标 Docker 本地表示。

P0 最小字段：

```text
release_id
source_head
source_tree

archive_sha256
archive_size_bytes

platform
config_digest
manifest_digest?
index_digest?
deployment_ref

deployment_contract_sha256
state_contract
```

规则：

- tar SHA256 + size 绑定交付字节；
- config digest 必须对原始 config bytes 计算；
- manifest/index 只在 artifact 实际存在时绑定；
- manifest/index 必须引用冻结 config 与 layer graph；
- ordered RootFS diff_ids 从已验证 config/content graph 验证；
- Config contract 从可信 config 派生，用于行为语义与诊断；
- deployment_ref/tag 不是安全身份；
- GitHub run/artifact ID 是 provenance，不是离线启动时的必要网络依赖。

不得用 Docker inspect 合成 JSON 代替原始 config bytes 的 digest authority。

### 4.2 Host-local Object Binding

回答：

> 在这一台 host/store epoch 上，哪个本地对象对应已验证 release？

可以包含：

```text
docker_image_id
container_image
tag_current_target
container_id
started_at
restart_count
store_representation
store_capability
```

这些字段允许用于同 host continuity、rollback 定位和运行对象绑定。

禁止将它们单独外推成跨 host release identity。

### 4.3 Production Deployment & Health Contract

回答：

> 正确 release 是否以正确配置在提供真实业务？

至少包括：

```text
Compose binding
systemd owner
network/mount contract
listeners
runtime restart state
Manager MQTT
Home Assistant MQTT
Broker continuity
state/schema compatibility
E03 reconciliation result
service stability window
```

---

## 5. Portable Image Identity V1 公共组件

计划新增主机侧公共模块：

```text
tools/n3w_t1_portable_image_identity.py
```

只使用 Python 标准库，不依赖 Manager 已启动。

职责拆分为三个逻辑层，不新增三个 daemon：

### 5.1 Pure artifact parser

不得执行 subprocess、网络或生产写入。

职责：

- 解析 release image record；
- 流式 SHA256；
- 安全读取 Docker archive / OCI layout；
- 计算/验证 config digest；
- 计算/验证 manifest/index digest；
- 验证 descriptor size/digest；
- 验证唯一 linux/arm64 target；
- 验证 config -> ordered diff_ids；
- 派生 versioned Config contract。

必须 fail closed：

- duplicate tar member；
- path traversal；
- symlink/hardlink 冒充安全成员；
- duplicate JSON key；
- missing blob；
- digest mismatch；
- size mismatch；
- ambiguous platform；
- unsupported layout；
- resource limit exceeded。

### 5.2 Docker observation adapter

只做有界读取。

输出规范化 observation，而不是给出 release verdict：

```json
{
  "reference": "...",
  "runtime_id": "sha256:...",
  "platform": "linux/arm64",
  "rootfs_diff_ids": ["sha256:..."],
  "config_contract": {},
  "descriptor_digest": null,
  "store_representation": "..."
}
```

必须区分：

```text
NOT_FOUND
DAEMON_UNAVAILABLE
PERMISSION_DENIED
TIMEOUT
MALFORMED_RESPONSE
```

不能把所有 inspect 非零退出折叠成“不存在”。

### 5.3 Verifier

返回稳定 schema：

```text
VERIFIED
MISMATCH
UNSUPPORTED_REPRESENTATION
UNAVAILABLE
```

VERIFIED 要求：

1. artifact release identity 已独立验证；
2. 目标 tag/reference 绑定的本地对象能映射回 artifact-owned config/manifest/index identity；
3. platform exact；
4. ordered RootFS exact；
5. Config semantic contract exact；
6. 输出 host-local binding。

允许已证明的 classic/containerd 表示差异。

禁止：

```text
build-side docker .Id == target-side docker .Id
```

作为唯一跨主机判据。

---

## 6. 与现有 release contract 的关系

不建立第二套平行 release authority。

优先扩展或引用：

```text
tools/n3w_t1_production_v2_contract.py
```

现有：

```text
gh.n3w-t1-production-v2-release/1
```

保持旧 schema 原义，不原地重新解释历史 release。

P0 可新增 versioned image-set 子合同或 release schema successor。

要求：

- canonical material 定义唯一；
- release_id 不自引用；
- public-safe evidence 与 private host binding 分离；
- 将 Compose/unit deployment contract 纳入 release binding；
- 正式离线发行后续引入独立签名/envelope，不把“同目录 manifest + tar 自洽”误当 publisher trust。

---

## 7. Maintenance Transaction V1

计划新增公共模块：

```text
tools/n3w_t1_maintenance_transaction.py
```

首版使用 root-owned 0600 原子 JSON；不引入新数据库。

### 7.1 持久状态

正常：

```text
PREPARING
READY
APPLYING
VERIFYING
COMMITTED
```

异常：

```text
ROLLING_BACK
ROLLED_BACK
BLOCKED
ABORTED
```

PRECHECK 是只读动作，不需要持久状态。

### 7.2 三种 ID 分开

```text
authorization_id
transaction_id
execution_session_id
```

authorization：

- 只 claim 一次；
- 绑定 target host；
- 绑定 source/current release；
- 绑定 target release；
- 绑定 executor/module authority；
- 绑定允许动作和 rollback 范围；
- 绑定预定义 resume policy；
- 不等于 SSH session。

transaction：

- 持有 durable state；
- 可被多个 execution session 查询；
- 只有授权范围预定义允许时才能 resume。

execution session：

- 某一次连接/进程尝试；
- 断线不等于 transaction 失败或重新授权。

### 7.3 每次 mutation 的 operation record

每次写动作执行：

```text
lock
→ read reality
→ validate transaction/release/host/executor
→ persist operation intent
→ fsync record + parent
→ execute
→ read reality independently
→ persist completion
```

每个 operation 至少记录：

```text
generation
operation_seq
operation_type
before_fingerprint
intended_after_fingerprint
observed_after_fingerprint
status
last_error_code
```

重入规则：

- reality == before：动作尚未发生，可按 policy 执行；
- reality == intended_after：动作已发生，只补记；
- reality neither before nor after：BLOCKED；
- 不允许用“当前未知文件 SHA”临时授权覆盖。

---

## 8. B1 — Transaction authority binding

当前 R10 `remote-apply` 只检查：

```text
status=CLAIMED
authorization_consumed=true
replay_allowed=false
```

P0 修复要求：

每一个 mutation entry 都必须验证：

```text
transaction schema/version
transaction_id
exact allowed phase
authorization_id/hash
authorization consumed/no-replay
host binding
current/source release
target release/artifact
executor/module authority
operation scope
global maintenance lock
reality prestate
```

旧 transaction schema：

- 不允许 silent reinterpret；
- 必须显式 migration，或由 successor recovery 读取为 immutable predecessor evidence；
- 当前 E03 采用后者。

---

## 9. B2 — Unknown Compose must never be overwritten

冻结 before/after：

```text
compose_before_sha256
compose_candidate_sha256
```

只有：

```text
current == before
```

时允许执行 publish。

只有已证明本 transaction 写出 candidate 后，rollback 才允许：

```text
current == candidate
→ restore before
```

若：

```text
current != before
and current != candidate
```

必须：

```text
BLOCKED_UNKNOWN_COMPOSE
```

禁止写。

不得再出现：

```text
atomic_replace(COMPOSE, original, sha_of_unknown_current)
```

这种用当前未知内容作为临时写授权的路径。

---

## 10. B3 — Crash/power-loss 与 service owner

现有风险：

```text
publish candidate Compose
→ stop n3wfc4-services-activation.service
```

存在 candidate 已可被 owner 读取但 owner 尚未受控的窗口。

P0 新顺序：

```text
acquire global maintenance lock
→ persist APPLY intent
→ establish activation gate
→ stop Manager+HA owner
→ prove Manager+HA stopped
→ prove Broker allowed continuity
→ re-check Compose before
→ publish candidate Compose
→ verify candidate
→ start Manager+HA owner
→ VERIFYING
```

关键要求：

- activation gate 必须是可持久恢复的 host-level mechanism；
- boot 时 recovery 判断必须先于 production application activation；
- SSH 只负责发起/查看，不承担 transaction 生命周期；
- process kill、SSH disconnect、daemon restart、host reboot 都不能依赖 Python `except` 才恢复。

P0 source repair 必须冻结最小 activation-gate 实现；不得只在文档里承诺。

---

## 11. B4 — Readiness 与 Acceptance 分开

readiness：

- 有界等待；
- 正常 starting/connecting 状态返回 WAIT；
- 明确 fatal drift 立即 FAIL。

acceptance：

- 严格；
- 只有所有业务合同通过才能 COMMIT。

E03 successor 至少验证：

```text
systemd owner active and stable
Manager exact release binding
HA expected release binding
Broker continuity
expected listeners
Manager authenticated MQTT session
HA authenticated MQTT session
process/socket ownership
bounded stability window

E03 attempt:
state=EXPIRED
phase=TERMINAL
cleanup_state=COMPLETE
terminal_reason=expired
unresolved_count=0
registration_count=0
pairing/session terminal state expected
credential counts unchanged at zero
```

若无已注册节点：

```text
REAL_NODE_TELEMETRY=NOT_APPLICABLE
```

不得伪造实节点 continuity。

需要使用受控非生产 probe 或现有认证会话证据证明 MQTT 链路。

---

## 12. Current / Candidate / Previous

保留三个逻辑角色，不保存三套完整 tar。

```text
CURRENT
CANDIDATE
PREVIOUS
```

规则：

- CURRENT = 最后 COMMITTED release；
- CANDIDATE = 当前 transaction 正在 stage/apply 的 release；
- PREVIOUS = 唯一保留的、已证明可回退 release；
- APPLYING/VERIFYING 时“实际运行对象”可能与 CURRENT pointer 不同，查询必须同时展示 observed reality；
- current/previous/candidate record 原子更新；
- transaction 引用的 image 禁止自动 prune；
- 正常情况下成功 load/verify 后可删除 T1 普通 tar 副本；
- 本次 E03 candidate 和 forensic evidence 在 successor closure 前保留。

---

## 13. DB/state migration 边界

P0 E03：

```text
SCHEMA_MIGRATION_REQUIRED=false
MANUAL_SQLITE_EDIT=false
OLD_DB_RESTORE=false
```

E03 由 repaired Manager startup reconciliation 前向协调。

通用 V1：

- 普通 app update 优先无 schema change；
- release 声明 readable/writable schema compatibility；
- migration 有 versioned migration_id；
- 活跃 WAL SQLite 不允许直接复制主文件作为“一致备份”；
- destructive contract 延后到 previous rollback window 结束；
- image rollback 与 DB rollback 分开；
- 有业务写入/credential revoke 后默认不自动恢复旧 DB。

---

## 14. App / Docker / OS 生命周期

正式拆分：

```text
APP_MAINTENANCE
HOST_RUNTIME_MAINTENANCE
OS_MAINTENANCE
```

共享：

- global maintenance lock；
- host compatibility profile；
- durable transaction framework。

但不允许 app update 顺手：

- 升级 Docker；
- 切换 image store；
- 升级 Armbian。

image-store backend 属于 compatibility/host-local metadata，不属于 release identity。

---

## 15. E03 Successor Recovery V1

计划新增专用入口，但必须复用公共 identity/transaction 模块：

```text
tools/n3w_t1_r10_e03_successor_recovery.py
```

它不是新的私有 validator。

### 15.1 predecessor evidence

successor plan 必须冻结：

```text
old authorization hash
old transaction raw SHA256
old transaction semantic fields
old executor blob
old source/pr head

same target artifact
new executor/module authority
new transaction_id
new authorization_id after explicit approval
target host binding
allowed actions
rollback policy
service owner contract
```

### 15.2 preauthorization read-only rebind

新的 live authorization 之前必须证明：

- predecessor transaction 原始 bytes 未变；
- predecessor 仍 CLAIMED/AUTHORIZATION_CLAIMED；
- predecessor authorization consumed/no-replay；
- target candidate Portable Image Identity VERIFIED；
- candidate 未被 retag/replaced；
- production Compose still exact predecessor；
- service owner exact；
- predecessor Manager exact；
- HA exact；
- Broker exact and continuous；
- E03 still uncommitted；
- no unexpected credentials；
- rollback previous object available；
- disk/capacity sufficient；
- no other maintenance transaction active。

任一未知：

```text
STOP_PREAUTH
```

且不 claim successor authorization。

### 15.3 successor claim

只有新的明确授权后：

- 创建全新 transaction path/id；
- 不删除 predecessor transaction；
- predecessor record 保持原始字节；
- 建立单独 disposition record 或 successor backlink；
- 语义：

```text
PREDECESSOR_DISPOSITION=
ABORTED_PRECUTOVER_STAGED_IMAGE_RETAINED

SUCCESSOR_TRANSACTION_ID=<new>
```

不能宣称 predecessor “没有修改过 T1”，因为 image load 已发生。

### 15.4 successor apply

candidate 已 VERIFIED 时：

```text
NO_DOCKER_LOAD=true
NO_DOCKER_TAG=true
NO_DOCKER_RMI=true
```

顺序：

```text
lock
→ persist intent
→ activation gate
→ stop Manager+HA
→ prove stopped
→ rebind Broker continuity
→ revalidate Compose before
→ publish exact candidate binding
→ start Manager+HA
→ bounded readiness
→ strict acceptance
→ COMMIT
```

### 15.5 rollback

只回滚可证明的本 transaction mutation。

允许：

- candidate Compose -> exact before；
- candidate app group -> exact previous runtime；
- 仅在 state compatibility 明确允许时启动 previous。

未知：

```text
BLOCKED
```

不写 Compose、DB、credentials。

---

## 16. 失败信息与 public evidence

不得再把所有 post-claim 异常折叠成只有：

```text
postclaim_failure
```

public-safe result 至少保留：

```text
transaction_id_sha256
stage
operation
reason_code
last_proven_state
authorization_consumed
replay_allowed
mutation_observed
recovery_class
```

禁止输出：

- T1 地址；
- host key raw/private locator；
- secret/password/token；
- DB 原始身份；
- credentials。

---

## 17. P0 测试冻结

### 17.1 Portable identity

必须 PASS：

- exact classic-store representation；
- exact containerd manifest representation；
- exact index representation（若 producer 产生）；
- same config / valid different runtime representation；
- exact tag already loaded -> reuse；
- artifact config/manifest/index graph exact。

必须 FAIL：

- wrong tar SHA；
- wrong size；
- wrong config；
- same RootFS but changed Cmd；
- same RootFS but changed Env；
- wrong platform；
- wrong manifest->config edge；
- wrong index child；
- ambiguous platform；
- missing blob；
- duplicate tar member；
- path traversal；
- symlink/hardlink unsafe member；
- duplicate JSON key；
- invalid digest/size；
- wrong existing tag content。

状态区分：

- image not found；
- Docker daemon unavailable；
- permission denied；
- timeout；
- malformed inspect。

### 17.2 B1 transaction binding

拒绝：

- wrong phase；
- wrong authorization hash；
- wrong transaction id；
- wrong host；
- wrong release；
- wrong artifact；
- wrong executor/module；
- wrong action scope；
- second active transaction；
- predecessor transaction 被修改。

### 17.3 B2 Compose

验证：

- before -> write candidate；
- candidate -> idempotent readback；
- unknown -> BLOCKED/no write；
- rollback only candidate -> before；
- unknown during rollback -> BLOCKED/no write。

### 17.4 B3 fault injection

每个关键 mutation 前后模拟：

- process kill；
- SSH disconnect；
- daemon restart；
- host reboot boundary；
- transaction write/fsync failure；
- disk full；
- activation owner unexpected start；
- repeated execution session；
- candidate already applied but completion record missing。

必须收敛：

- exact before；
- exact after；
- BLOCKED。

不得出现第三种被自动覆盖的现实状态。

### 17.5 B4 runtime acceptance

覆盖：

- Manager MQTT delayed then ready；
- HA MQTT delayed then ready；
- MQTT never ready；
- wrong authenticated identity；
- duplicate/incorrect socket；
- service container running but MQTT absent；
- transient listener readiness；
- restart_count drift；
- startup reconciliation delayed；
- E03 cleanup incomplete；
- no real nodes -> telemetry NOT_APPLICABLE。

---

## 18. 真实双 store Gate

P1 前必须存在至少一条真实 Docker daemon matrix：

```text
classic image store
containerd image store
```

对同一 exact tar 进行：

```text
load
inspect
create
container inspect
portable verifier
```

不能只用 mocked `.Id` 字符串宣称 cross-store closure。

P0 可先以现有历史实机证据 + isolated tests 开发，但进入通用生产 authority 前必须完成真实矩阵。

---

## 19. 全仓调用点迁移

A～E 分类：

```text
A artifact/release identity
B host-local continuity
C container continuity
D rollback binding
E logging/fingerprint
```

P0/P1 起新增 CI 规则：

- 新的跨 host release identity 校验必须调用公共 module；
- 禁止新 executor/workflow 内嵌私有 validator；
- 受控例外必须登记 owner、用途、移除条件；
- 静态规则是门禁，不声称替代语义审计。

Golden Master / Seal / R2C：

```text
RETIRED_REFERENCE_ONLY
```

不为统一而重新实现。

---

## 20. Source Repair planned files

P0 source repair 预计最小文件集：

```text
tools/n3w_t1_portable_image_identity.py
tools/n3w_t1_maintenance_transaction.py
tools/n3w_t1_r10_e03_successor_recovery.py

tests/tools/test_n3w_t1_portable_image_identity.py
tests/tools/test_n3w_t1_maintenance_transaction.py
tests/tools/test_n3w_t1_r10_e03_successor_recovery.py

tools/n3w_t1_r10_e03_manager_successor_refresh_live.py
tests/tools/test_n3w_t1_r10_e03_manager_successor_refresh_live.py

tools/n3w_t1_production_v2_contract.py
tests/tools/test_n3w_t1_production_v2_contract.py

docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
```

旧 R10 executor 的修改目标：

- 禁止继续作为 live recovery authority；
- 将已知 single-.Id / B2 等错误路径加 regression tests；
- successor 完成后归档；
- 不让旧 consumed transaction 通过修改后的旧 executor 被续跑。

---

## 21. P0 exit criteria

设计后续 source repair 只有同时满足以下条件才可进入 live preauthorization：

```text
PORTABLE_IMAGE_IDENTITY_SOURCE=PASS
TRANSACTION_BINDING_B1=PASS
UNKNOWN_COMPOSE_B2=PASS
CRASH_OWNER_B3=PASS
MQTT_ACCEPTANCE_B4=PASS

SUCCESSOR_RECOVERY_SOURCE=PASS
OLD_AUTHORIZATION_REPLAY_TEST=PASS
PREDECESSOR_RECORD_IMMUTABILITY_TEST=PASS
NO_PRIVATE_VALIDATOR_REGRESSION=PASS

FOCUSED_CI=PASS
INDEPENDENT_SOURCE_REVIEW=PASS
NEW_FALSE_PASS_PATH=NONE_FOUND
NEW_FALSE_STOP_PATH=NONE_FOUND_WITHIN_SUPPORTED_CONTRACT
```

然后才允许单独 Gate：

```text
E03_SUCCESSOR_RECOVERY_READONLY_PREAUTH
```

仍需重新读取真实 T1，不能复用 2026-10-30 当前现场读数作为未来授权依据。

---

## 22. 当前冻结结论

```text
PORTABLE_IDENTITY_V1=DESIGN_FROZEN
MAINTENANCE_TRANSACTION_V1=DESIGN_FROZEN
E03_SUCCESSOR_RECOVERY_V1=DESIGN_FROZEN

OLD_E03_TRANSACTION=IMMUTABLE_EVIDENCE
OLD_AUTHORIZATION=CONSUMED_NO_REPLAY
CURRENT_T1_ACTION=NONE

GOLDEN_MASTER_PRODUCTION_ROUTE=RETIRED_BY_ADR0010
SOURCE_REPAIR_REQUIRED=true
```

下一 Gate：

```text
NEXT_ONE_GATE=
N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_REPAIR_20261030_01
```

该 Gate 才允许修改源代码和测试；仍不自动授权 T1 access、live mutation、board access、workflow dispatch 或 merge。
