# 温室环境监测系统（ESP32-C6）— N3-W
# P4 新版 Manager 空白业务状态部署：一次性执行器与失败回退
# 新会话交接文档 V1.0 — 2026-10-09

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文符合 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`，模板 authority 为
> `4300890dff0ce63d5a547df21426e287d084d9ee`。
> 如本文与 fresh repository/runtime/live evidence 冲突，以 exact repository/runtime/live evidence 为准并 STOP 后 rebind。
> 本文不包含 T1 私网地址、真实 Host Source、Setup Secret、MQTT credential、raw NODE_ID 或其他私密运行材料。

---

## 0. 会话切换结论

当前会话已经完成两项关键收敛：

1. 旧 Manager 的三持久数据源一致性冷备份、隔离恢复和原版 Manager 恢复已真实 `CLOSED_PASS`；
2. 用户已明确放弃旧设备在 **Manager** 中的历史配对关系，产品路线从“迁移旧 5 个身份/credential/replay/relay keys”正式切换为“**新版 Manager + 三个全新空白 RW 数据源**”。

用户同时明确要求停止繁琐、重复、分散的人工验证。ESP32-C6 已长期断电，当前未接传感器；没有在线发送端时不得继续用 90 秒静默遥测窗口消耗时间。

下一会话**不要重新复盘或重做已经通过的备份/遥测检查**，直接从一次性空白 Manager 部署执行器的源码与失败回退测试开始。

```text
CURRENT_STAGE=N3W_P4_T1_CLEAN_MANAGER_STATE_FRESH_DEPLOYMENT_SOURCE_PREPARATION
CURRENT_STOP_POINT=FRESH_STATE_ROUTE_SELECTED_SOURCE_CONTRACT_READY_EXECUTOR_NOT_IMPLEMENTED
NEXT_ONE_GATE=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR_AND_ROLLBACK_TEST
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 P4 产品首次配对路线和“Manager-only 空白业务状态”边界；
- fresh rebind main / PR #540 / PR #539 / PR #538 / PR #522 与 current state/index；
- 设计一次性 Manager-only 部署 transaction、rollback、授权边界和 PASS/FAIL；
- 区分 source/test 成功、T1 live deployment 成功和板端首次配对成功；
- 防止重新引入旧数据迁移、重复冷备份、重复静默 telemetry probe；
- 不把测试框架复杂度扩张成并行产品架构。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL；
- 本门仅执行 GitHub/source/test/CI 范围工作；
- mutation 只能发生在后续**新的明确生产替换授权**之后；
- 第一处 substantive failure fail-closed STOP；
- 不自行进入 T1、不访问板卡、不清理 Broker、不部署 Manager；
- 不自动设计或执行下一 gate。

### 1.3 DSL execution semantics

```text
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false
```

本门最终要实现的生产切换属于有原子顺序/失败回退要求的 transaction，**允许为未来 live gate 编写一个 exact audited one-shot executor**；但当前 NEXT_ONE_GATE 仍为 source-only，不运行它。

### 1.4 标准交互循环

```text
高阶模型：source / transaction / rollback 设计
        ↓
Codex：GitHub 源码实现 + synthetic failure tests + CI
        ↓
高阶模型：独立复核 closure
        ↓
用户：另行批准一次 live Manager replacement
        ↓
未来 live gate：一次 Mac Terminal 启动 → 单次 PASS/STOP 报告
```

---

## 2. Product North Star

当前产品路线：

```text
T1 保留 Broker/TLS/网络/系统服务身份
→ 部署 exact P4 Manager
→ Manager 使用 3 个全新、互相独立、空白 RW 持久目录
→ 新 Manager preboot registration/credential/replay 业务基线为 0
→ 后续 clean-product 首次正常启动
→ 私有 QR ↔ fresh PENDING 绑定
→ 单独授权 Setup Secret import
→ 首次配对、MQTT、Wi-Fi/ESP-NOW 真实验收
```

最终阶段目标：

```text
真正 clean-product ESP32-C6 在新版 P4 Manager 空白状态上完成首次正常启动与首次配对，
建立新的 NODE_ID / MQTT credentials / N3-W application keys，
随后完成产品级 Direct / Relay / Manager / Broker / HA 端到端验收。
```

当前不得进入：

```text
OLD_MANAGER_IDENTITY_MIGRATION
LEGACY_5_IDENTITY_BASELINE_REUSE
BROKER_FACTORY_RESET_OR_DYNSEC_BULK_DELETE
HOMEASSISTANT_HISTORY_RESET
BOARD_FIRST_NORMAL_BOOT
SETUP_SECRET_IMPORT
REAL_NODE_TELEMETRY_ACCEPTANCE
OLD_BOARD_AS_FAKE_CLEAN_PRODUCT
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
TREE=ee977996a4c962097684519841dce2e3bcba23f2

PR540=OPEN_DRAFT
PR540_BRANCH=tools/n3w-p4-manager-consistent-cold-backup-20261009
PR540_HANDOFF_PARENT=fbfc2c8e20de489141027fbfc1ea10263be9b052
PR540_PARENT_CI=13_OF_13_PASS

PR539_HEAD=f110e4fb77489426f34b25c67ebb5ffe55270ae4
PR538_HEAD=3d86d6bfaf361dc3a3d7295d046f541a544d552d
PR538_CI=12_OF_12_PASS
PR522_HEAD=58107b36fc20ccbef014d13cbfb708186395441c
```

`PR540_HANDOFF_PARENT` 是创建本文前的 exact PR #540 HEAD。本文提交会自然推进 PR #540 HEAD；新会话必须 fresh rebind，不能要求 HEAD 仍等于 parent。

### 3.2 Candidate / artifact / image

```text
CANDIDATE_REF=n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d
CANDIDATE_SOURCE_PR=538
CANDIDATE_SOURCE_SHA=3d86d6bfaf361dc3a3d7295d046f541a544d552d
CANDIDATE_ARCH=linux/arm64
CANDIDATE_T1_LOCAL_BUILD=PROVEN_PRESENT
CANDIDATE_ISOLATED_CLI_AND_EXPIRY_GUARDS=PASS
CANDIDATE_IMMUTABLE_IMAGE_ID=PRIVATE_RUNTIME_AUTHORITY_REQUIRES_FRESH_READONLY_REBIND_BEFORE_LIVE_DEPLOY
```

### 3.3 Successor / deployment material

```text
DECISION_AUTHORITY=docs/development/N3W_P4_T1_CLEAN_STATE_MANAGER_DEPLOYMENT_SIMPLIFICATION_PROPOSAL_20261009.md
CUTOVER_DESIGN=docs/development/N3W_P4_T1_MANAGER_SINGLE_WINDOW_CUTOVER_DESIGN_20261009.md
FRESH_STATE_CONTRACT=tools/execution_packages/n3w/p4_manager_cold_backup/fresh_state_contract.py
FRESH_STATE_TEST=tools/execution_packages/n3w/p4_manager_cold_backup/test_fresh_state_contract.py
RUNTIME_PARITY_CONTRACT=tools/execution_packages/n3w/p4_manager_cold_backup/cutover_contract.py
ZERO_BASELINE_BRIDGE=tools/execution_packages/n3w/auto_safe_fallback/p4_private_qr_pending_identity_binder/bridge_handoff.py
ZERO_BASELINE_BRIDGE_TEST=tools/execution_packages/n3w/auto_safe_fallback/p4_private_qr_pending_identity_binder/test_bridge_handoff.py
FULL_ONE_SHOT_DEPLOY_EXECUTOR=NOT_YET_IMPLEMENTED
```

### 3.4 Target host / runtime authority

```text
TARGET_HOST=PRIVATE_T1_HOST
TARGET_ARCH=linux/arm64
LIVE_MANAGER_CONTAINER=greenhouse-manager
LIVE_BROKER_CONTAINER=n3wfc4-broker-1
LIVE_MANAGER_RUNTIME_RECREATE_AUTHORITY=CURRENT_DOCKER_INSPECT_NOT_HISTORICAL_COMPOSE
EXPECTED_MANAGER_BIND_COUNT=6
EXPECTED_RW_STATE_BIND_COUNT=3
EXPECTED_RO_SECRET_BIND_COUNT=3
```

真实 Host Source、Env secret、镜像 ID、备份路径随机尾部继续只留 T1 root-private。

---

## 4. Current Live Baseline

最后 direct T1 evidence：

```text
OLD_MANAGER_R5_ONE_SHOT_COLD_BACKUP=CLOSED_PASS
THREE_RW_SOURCE_COLD_BACKUP=PASS
ISOLATED_RESTORE_AND_BUSINESS_SEMANTICS=PASS
ORIGINAL_MANAGER_RESTARTED=PASS
BROKER_UNCHANGED=PASS

POST_BACKUP_90S_MANAGER_BROKER_RUNTIME_STABLE=true
POST_BACKUP_MQTT_TCP_CONNECTED_BOTH_SAMPLES=true
REPLAY_TUPLES_BEFORE=475
REPLAY_TUPLES_AFTER=475
REPLAY_TUPLES_DELTA=0
POST_BACKUP_APP_TELEMETRY=DEFERRED_NO_ONLINE_NODE
```

当前物理事实：

```text
ESP32_C6_POWERED=false
ESP32_C6_POWERED_OFF_FOR_LONG_TIME=true
SENSOR_CONNECTED=false
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

Runtime 元数据边界：

```text
MANAGER_STATE=LAST_PROVEN_RUNNING_AFTER_R5_RECOVERY
MANAGER_RUNTIME_REVISION_LAST_OBSERVED=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
MANAGER_NETWORK_MODE_LAST_PROVEN=host
MANAGER_PORTS_LAST_PROVEN=none
MANAGER_BIND_COUNT_LAST_PROVEN=6

BROKER_STATE=LAST_PROVEN_RUNNING_UNCHANGED
BROKER_TLS_TCP_8883=LAST_PROVEN_AVAILABLE
BROKER_RESTART_BY_R5=false

HOMEASSISTANT_STATE=NOT_MUTATED_BY_CURRENT_ROUTE
PAIRING_SOCKET_LAST_PROVEN_PRESENT=true
```

新会话在**任何未来 live mutation 授权前**必须做一次集中 fresh read-only rebind，不需要恢复逐项人工 checklist：

```text
MANAGER_EXACT_CURRENT_STATE_REQUIRES_FRESH_READONLY_REBIND=true
BROKER_EXACT_CURRENT_STATE_REQUIRES_FRESH_READONLY_REBIND=true
CANDIDATE_IMMUTABLE_IMAGE_ID_REQUIRES_FRESH_READONLY_REBIND=true
```

---

## 5. Proven Current Facts

```text
R5_REAL_COLD_BACKUP_AND_OLD_MANAGER_RESTORE=CLOSED_PASS
REPEAT_R5_BACKUP_REQUIRED=false

NO_ONLINE_ESP32_TELEMETRY_SOURCE=true
SILENT_90S_TELEMETRY_PROBE_REPEAT_REQUIRED=false

USER_ACCEPTED_DISCARD_OLD_MANAGER_PAIRING_RELATIONS=true
DEPLOYMENT_DIRECTION=CLEAN_MANAGER_ONLY_THREE_EMPTY_RW_SOURCES
LEGACY_REGISTRATION_MIGRATION=SKIPPED
LEGACY_CREDENTIAL_MIGRATION=SKIPPED
LEGACY_REPLAY_MIGRATION=SKIPPED
LEGACY_RELAY_KEY_MIGRATION=SKIPPED

OLD_MANAGER_AND_PRIVATE_R5_BACKUP=RETAIN_UNCHANGED
BROKER_TLS_NETWORK_SYSTEM_ID_AND_SERVICE_SECRETS=KEEP
BROKER_FACTORY_RESET=false

OLD_COMPOSE_MANAGER_BIND_COUNT=3
LIVE_MANAGER_BIND_COUNT=6
OLD_COMPOSE_RECREATE_AUTHORITY=false
LIVE_DOCKER_INSPECT_RECREATE_AUTHORITY=true

NEW_P4_PREBOOT_EXPECTED_REGISTRATION_COUNT=0
NEW_P4_PREBOOT_EXPECTED_CREDENTIAL_COUNT=0
NEW_P4_PREBOOT_EXPECTED_REPLAY_COUNT=0
NEW_P4_PREBOOT_EXPECTED_RELAY_KEYS=0

PREVIOUS_FIVE_IDENTITY_SNAPSHOT=HISTORICAL_NOT_NEW_PREBOOT_AUTHORITY
FRESH_STATE_SOURCE_CONTRACT=IMPLEMENTED
FRESH_STATE_SYNTHETIC_TESTS=10
ZERO_IDENTITY_QR_BINDER_PATH=IMPLEMENTED
ZERO_IDENTITY_QR_BINDER_ADDITIONAL_TESTS=3
PR540_HANDOFF_PARENT_CI=13_OF_13_PASS
```

Source evidence from exact PR #538 also proves the registration, credential-lifecycle and replay stores include writable empty-database initialization logic.

Inference/risk, not direct fresh runtime fact:

```text
INFERENCE_LEGACY_BROKER_DYNSEC_ACL_OR_RETAINED_MAY_REMAIN=true
INFERENCE_FULL_T1_FACTORY_RESET=false
```

因此本路线是 **fresh Manager business state**，不是整机/整 Broker 恢复出厂。

---

## 6. Current Root Cause / Blockers

### Blocker A — 完整一次性 fresh Manager 部署执行器尚未实现

```text
ROOT_CAUSE=ROUTE_CHANGED_FROM_LEGACY_DATA_MIGRATION_TO_EMPTY_MANAGER_STATE
PROVEN_BY=USER_DECISION_AND_CURRENT_PR540_SOURCE
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
FULL_ONE_SHOT_EXECUTOR=NOT_IMPLEMENTED
FAILURE_RECOVERY_TEST_MATRIX=NOT_COMPLETE
```

当前唯一真正 blocker 是：需要把已冻结的空白状态合同、live Docker inspect runtime parity、old-container parked rollback、systemd rescue 合并成**一个 exact audited deploy transaction**并做失败注入测试。

### Blocker B — live replacement 还没有新授权

```text
LIVE_MANAGER_REPLACEMENT_AUTHORIZED=false
READY_TO_REQUEST_LIVE_AUTHORIZATION=false
REASON=SOURCE_EXECUTOR_AND_ROLLBACK_TEST_GATE_NOT_CLOSED
```

### 非 blocker，但必须保持边界

```text
LEGACY_BROKER_RESIDUE_CLEANUP=OUT_OF_SCOPE_NOT_DEPLOYMENT_BLOCKER
REAL_SENSOR_DATA=NOT_REQUIRED_FOR_MANAGER_DEPLOY
REAL_NODE_TELEMETRY=DEFERRED_UNTIL_BOARD_ONLINE
```

---

## 7. Closed / Forbidden Routes

除非有新的 direct counter-evidence，下一会话不得重新进入：

```text
LEGACY_5_IDENTITY_MANAGER_MIGRATION=CLOSED_BY_USER_DECISION
LEGACY_CREDENTIAL_REPLAY_RELAY_KEY_MIGRATION=CLOSED_BY_USER_DECISION
OLD_FIVE_IDENTITY_PREBOOT_BASELINE_REUSE=FORBIDDEN_FOR_FRESH_MANAGER

REPEAT_R5_COLD_BACKUP=CLOSED_ALREADY_PASS
REPEAT_NO_NODE_90S_TELEMETRY_PROBE=CLOSED_NO_ONLINE_SOURCE

HISTORICAL_3_MOUNT_COMPOSE_MANAGER_RECREATE=FORBIDDEN
DIRECT_NEW_MANAGER_WRITE_TO_OLD_RW_SOURCES=FORBIDDEN
DELETE_OLD_MANAGER_OR_OLD_DATA_BEFORE_NEW_ACCEPTANCE=FORBIDDEN

BROKER_FACTORY_RESET=OUT_OF_SCOPE
DYNSEC_BULK_DELETE=OUT_OF_SCOPE
HA_HISTORY_RESET=OUT_OF_SCOPE

LEGACY_IMPORT_CLI_AS_P4_QR_FLOW=FORBIDDEN
OLD_DEVICE_AS_FAKE_CLEAN_PRODUCT=FORBIDDEN
AUTO_BOARD_BOOT_AFTER_MANAGER_DEPLOY=FORBIDDEN

FRAGMENTED_OPERATOR_PREFLIGHT_LOOP=CLOSED_BY_WORKFLOW_DECISION
```

---

## 8. Authorization Ledger

### 8.1 已消费：R5 旧 Manager 冷备份窗口

```text
AUTHORIZATION=ONE_OLD_MANAGER_STOP_COLD_BACKUP_AND_ORIGINAL_RESTART
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
```

不得用此授权停止 Manager 做新版部署。

### 8.2 产品路线决策：放弃旧 Manager 配对关系

```text
AUTHORIZATION=LEGACY_MANAGER_PAIRING_CONTINUITY_WAIVER
CLAIMED=true
CONSUMED=NOT_APPLICABLE_PERSISTENT_PRODUCT_DECISION
RESULT=APPROVED
REPLAY_PERMITTED=NOT_APPLICABLE
SUPERSEDED_BY=CLEAN_MANAGER_ONLY_ROUTE
```

该决定允许 source/design 按空白 Manager 路线推进；**不授权**删除旧数据/Broker 账号/设备 NVS 或 live replacement。

### 8.3 旧 P3/P4 实体/只读授权

```text
AUTHORIZATION=HISTORICAL_P3_P4_BOARD_AND_PREBOOT_GATES
CLAIMED=true
CONSUMED=true
RESULT=HISTORICAL_SCOPED_PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=FRESH_MANAGER_REBASE_REQUIRED
```

### 8.4 尚未授予：生产 Manager 替换

```text
PROPOSED_AUTHORIZATION=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY
GRANTED=false
READY_FOR_NEW_AUTHORIZATION=false
```

### 8.5 尚未授予：产品首次启动与 Setup Secret

```text
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
```

---

## 9. Rollback Authority

当前 NEXT_ONE_GATE 是 source-only：

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:SOURCE_ONLY_GATE
LIVE_RUNTIME_MUTATION=false
```

但未来 live deploy executor 必须按以下 rollback authority 设计：

```text
FUTURE_ROLLBACK_BASELINE=EXACT_CURRENT_OLD_MANAGER_CONTAINER_PLUS_UNMODIFIED_ORIGINAL_THREE_RW_SOURCES
OLD_MANAGER_PRIVATE_INSPECT_ARCHIVE=EXISTS_ROOT_PRIVATE
OLD_MANAGER_IMAGE_TAR_AND_SHA256=PASS_HISTORICAL_R5_AUTHORITY
R5_COLD_BACKUP=EXISTS_ROOT_PRIVATE_CLOSED_PASS

FRESH_PRECHANGE_DATA_BACKUP_REQUIRED=false
REASON_NEW_MANAGER_WRITES_ONLY_THREE_NEW_EMPTY_RW_SOURCES=true
FRESH_PRECHANGE_RUNTIME_INSPECT_REQUIRED=true

OLD_CONTAINER_DELETE_ALLOWED=false
OLD_RW_SOURCE_WRITE_BY_CANDIDATE_ALLOWED=false
BROKER_RESTART_ALLOWED=false
SECOND_ATTEMPT_ALLOWED=false
```

未来 rollback 顺序：

```text
identify exact candidate
→ stop candidate if started
→ move/remove only exact candidate name binding
→ restore parked original greenhouse-manager name
→ start exact original container using unchanged original 3 RW sources
→ verify old Manager health/runtime + Broker unchanged
→ preserve failed fresh-state directories/private evidence
→ STOP
```

Rollback failure：

```text
ROLLBACK_INCOMPLETE=true
MANUAL_RECOVERY_REQUIRED=true
AUTO_RETRY=false
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR_AND_ROLLBACK_TEST
```

### 10.1 Purpose

在 PR #540 内实现并独立复核一个**未来生产可用但当前绝不执行**的一次性 Manager-only fresh-state deploy executor：使用 exact P4 candidate 和 current live runtime contract，创建三空白 RW source，park 原 Manager，启动新 Manager；任一步失败必须恢复原 container + 原数据。完成完整 synthetic failure/recovery test matrix 和 CI 后 STOP，才有资格向用户申请一次 live replacement 授权。

### 10.2 Frozen inputs

```text
SOURCE_MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
CANDIDATE_SOURCE=3d86d6bfaf361dc3a3d7295d046f541a544d552d
PR540_BRANCH=tools/n3w-p4-manager-consistent-cold-backup-20261009

DECISION_DOC=docs/development/N3W_P4_T1_CLEAN_STATE_MANAGER_DEPLOYMENT_SIMPLIFICATION_PROPOSAL_20261009.md
FRESH_STATE_CONTRACT=tools/execution_packages/n3w/p4_manager_cold_backup/fresh_state_contract.py
CUTOVER_CONTRACT=tools/execution_packages/n3w/p4_manager_cold_backup/cutover_contract.py
ZERO_BASELINE_BRIDGE=tools/execution_packages/n3w/auto_safe_fallback/p4_private_qr_pending_identity_binder/bridge_handoff.py

EXPECTED_FRESH_PREBOOT_COUNTS=0_0_0_AND_EMPTY_RELAY_KEY_DIR
OLD_DATA_MIGRATION=false
BROKER_MUTATION=false
BOARD_ACCESS=false
```

### 10.3 Required proof / operations

```text
1. fresh rebind repository main + PR #540/#539/#538/#522 + current state/index + decision docs.
2. Confirm current source still encodes clean-manager decision; do not reopen legacy migration.
3. Implement exact future deploy transaction, preferably in the existing p4_manager_cold_backup execution-package family rather than a new framework.
4. Executor must keep live T1 untouched in this gate; all runtime commands are authored/tested only.
5. Pre-live executor logic must:
   a. bind exact current Manager/Broker/candidate image at runtime;
   b. reject historical Compose as recreate authority;
   c. derive all 6 current live binds from current docker inspect;
   d. preserve 3 RO secret sources readonly;
   e. create 3 distinct empty persistent RW sources, never nested/overlapping old sources;
   f. prepare ownership/mode for actual Manager uid/gid without broad chmod;
   g. prove stopped shadow runtime/security parity before old Manager stop;
   h. create root-private atomic transaction-state file.
6. Mutation transaction logic must:
   a. require an explicit future --permit-live-manager-replacement or equivalent nonreplayable grant;
   b. stop and park old Manager, never delete it;
   c. never copy old Manager registration/credential/replay/relay-key content into fresh roots;
   d. create candidate from current live Config/HostConfig contract + exact immutable candidate image ID;
   e. start candidate with rollback-safe restart policy until postflight passes;
   f. validate health/pairing socket/P4 readonly CLI/fresh schemas and zero baseline;
   g. prove Broker identity/restart/start timestamp unchanged and Manager TLS TCP path present;
   h. not require replay growth while ESP32-C6 are powered off;
   i. only after host-side PASS persist final restart policy and private manifest.
7. Rollback logic must restore the exact parked old container with untouched old sources; no obsolete Compose recreation and no old-data overwrite.
8. Add failure-injection/synthetic tests for at minimum:
   candidate image mismatch;
   6-mount/runtime parity drift;
   nonempty fresh root;
   wrong uid/gid/mode;
   source overlap;
   Broker drift;
   shadow create/parity failure;
   old Manager stop failure;
   park/rename failure;
   candidate create failure;
   candidate start failure;
   health/pairing socket/zero-baseline failure;
   systemd/main executor interruption;
   rollback candidate identity mismatch;
   old Manager restart failure;
   false PASS when no actual transaction started.
9. Update CI path coverage so all executor/rollback tests run on PR #540.
10. High-level independent source review of the exact resulting HEAD.
11. Record closure in current state/index and PR #540/#522.
12. STOP. Do not access T1 or ask for live replacement authorization until the source gate itself is PASS.
```

### 10.4 PASS

```text
FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR=PASS
ROLLBACK_EXECUTOR=PASS
FAILURE_INJECTION_TESTS=PASS
FRESH_ZERO_BASELINE_CONTRACT=PASS
OLD_MANAGER_UNTOUCHED_ROLLBACK_CONTRACT=PASS
BROKER_NONMUTATION_CONTRACT=PASS
PR540_CURRENT_HEAD_CI=ALL_PASS
INDEPENDENT_SOURCE_REVIEW=PASS
LIVE_T1_MUTATION=false
READY_FOR_P4_FRESH_MANAGER_LIVE_AUTHORIZATION_DESIGN=true
STOP=true
```

### 10.5 FAIL

```text
FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR=FAIL_<EXACT_CLASS>
READY_FOR_P4_FRESH_MANAGER_LIVE_AUTHORIZATION_DESIGN=false
LIVE_T1_MUTATION=false
AUTO_REPAIR=false
AUTO_LIVE_RETRY=false
STOP=true
```

Codex 不得自动进入生产切换 gate。

---

## 11. Hard Allowed / Forbidden Scope

Default：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- GitHub read/rebind
- PR #540 branch source/test/doc changes required by NEXT_ONE_GATE
- host-only/local synthetic unit tests
- GitHub Actions CI
- exact candidate source inspection
- current docs/current-state/KNOWN_FAILURES read
- PR comments / progress alignment
```

### FORBIDDEN

```text
- T1 SSH or live Docker execution in this source-only gate
- docker stop/start/rm/rename/create against production T1
- Broker restart/recreate/config change
- Broker DynSec cleanup
- old Manager DB/credential/replay/relay-key migration
- old Manager data deletion
- R5 backup deletion
- board power/USB/serial/flash/NVS/RF access
- real QR capture
- real Setup Secret import
- first product normal boot
- PR merge unless separately authorized
- automatic transition into live deployment
```

Repository writes are allowed only on the active PR branch:

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
REPOSITORY_SOURCE_WRITE=true
REPOSITORY_WRITE_SCOPE=PR540_BRANCH_ONLY
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required for this source gate.
The source gate itself MAY author the exact future live deploy executor because
the future mutation requires audited transaction/recovery ordering.

Mechanically compile this DSL into the minimum necessary repository/test commands.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not access T1.
Do not access any board.
Do not repair unrelated PRs.
Do not merge.
Do not enter live deployment.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================
GATE=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR_AND_ROLLBACK_TEST
LIVE_AUTHORIZATION_REQUIRED=false
LIVE_MANAGER_REPLACEMENT_AUTHORIZATION_GRANTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

============================================================
1. FROZEN INPUTS
============================================================
REPOSITORY=chrenguo-stack/HomeAssistant
SOURCE_MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
CANDIDATE_SOURCE=3d86d6bfaf361dc3a3d7295d046f541a544d552d
ACTIVE_BRANCH=tools/n3w-p4-manager-consistent-cold-backup-20261009
DECISION=CLEAN_MANAGER_ONLY_THREE_EMPTY_RW_SOURCES
LEGACY_MANAGER_STATE_MIGRATION=false
BROKER_MUTATION=false

============================================================
2. FRESH REBIND
============================================================
Read exact current:
- main
- PR #540, #539, #538, #522
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- clean-state decision doc
- single-window cutover design doc
- fresh_state_contract.py + tests
- cutover_contract.py + tests
- bridge_handoff.py + tests

If route, source or CI materially drifted:
REPORT_DRIFT
STOP

============================================================
3. IMPLEMENT FUTURE ONE-SHOT EXECUTOR
============================================================
Stay inside PR540 source/test scope.
Reuse existing execution-package family.
Implement exact preflight → stopped-shadow → authorized transaction →
fresh zero-state postflight → old-container rollback.

Never implement:
- old data migration into new roots
- obsolete Compose recreation
- Broker cleanup
- board/secret import actions

============================================================
4. FAILURE RECOVERY TEST MATRIX
============================================================
Run synthetic tests for all listed failure points.
A test must prove:
- no false PASS;
- no old-source write;
- Broker nonmutation contract;
- exact old-container restore intent;
- no automatic second attempt.

============================================================
5. CI + INDEPENDENT SOURCE REVIEW
============================================================
Run targeted tests.
Observe PR540 current-head CI.
Review exact diff for unrelated drift and secret/public-safety regression.

If any substantive failure:
FAIL_CLOSED
STOP

============================================================
6. RECORD SOURCE CLOSURE
============================================================
Update current state/index and PR records with public-safe exact HEAD/CI/test counts.
No live T1 claims.

============================================================
7. HARD STOP
============================================================
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
LIVE_DEPLOY_AUTHORIZATION_REQUESTED=false

Return structured closure only.
```

---

## 13. Expected Closure

```text
=== N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR_AND_ROLLBACK_TEST CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=SOURCE_ONLY_NO_LIVE_AUTH_REQUIRED
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

REPOSITORY_MAIN=
PR540_HEAD=
PR540_CI=

CANDIDATE_SOURCE_BINDING=
CLEAN_MANAGER_ROUTE_BINDING=

FRESH_MANAGER_ONE_SHOT_EXECUTOR=
ROLLBACK_EXECUTOR=
FAILURE_INJECTION_TEST_COUNT=
FAILURE_INJECTION_TESTS=
ZERO_IDENTITY_PREBOOT_CONTRACT=
OLD_SOURCE_NONWRITE_CONTRACT=
OLD_CONTAINER_RESTORE_CONTRACT=
BROKER_NONMUTATION_CONTRACT=
PUBLIC_REPOSITORY_SAFETY=

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
SETUP_SECRET_IMPORTED=false
MANAGER_REPLACED=false
BROKER_RESTART=false

GATE_RESULT=
READY_FOR_P4_FRESH_MANAGER_LIVE_AUTHORIZATION_DESIGN=
NEXT_ROUTE=

STOP=true
=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=N3W_P4_T1_FRESH_MANAGER_LIVE_DEPLOY_AUTHORIZATION_AND_SINGLE_EXECUTION_PREPARATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true
```

PASS 后只准备/请求**一次**生产 Manager replacement 授权，不自动停止原 Manager。

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
LIVE_T1_MUTATION=false
```

---

## 15. KNOWN_FAILURES Updates

本轮路线简化本身不是新事故：

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
NEW_KF_ALLOCATED=false
```

仍需遵守既有相关 guards：

```text
KF045_CONTAINER_VS_HOST_DB_PATH_DOMAIN=GUARDED
KF048_PRIVATE_STATE_UID_GID_MOUNT_AUTHORITY=GUARDED
KF070_COMPOSE_RECREATE_ORACLE=GUARDED
KF086_MANAGER_STATE_PUBLIC_SAFE_AUTHORITY=GUARDED
KF098_LIVE_MANAGER_RECREATE_FROM_ACTUAL_RUNTIME_CONTRACT=HISTORICAL_GUARD
```

如 NEXT_ONE_GATE 的 executor/failure tests 发现新的真实 root cause，再决定是否新增/更新 KF，不预分配编号。

---

## 16. New Chat Start Prompt

新会话可直接粘贴：

```text
阅读：

docs/development/N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR_NEW_CHAT_HANDOFF_V1.0_20261009.md

同时读取 exact handoff process authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #540
- PR #539
- PR #538
- PR #522
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_P4_T1_CLEAN_STATE_MANAGER_DEPLOYMENT_SIMPLIFICATION_PROPOSAL_20261009.md
- docs/development/N3W_P4_T1_MANAGER_SINGLE_WINDOW_CUTOVER_DESIGN_20261009.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3-W 产品级首次配对与安全恢复验收
支线任务：P4 新版 Manager 全新部署
当前任务：N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR_AND_ROLLBACK_TEST

必须先承认：
- 用户已明确放弃旧设备在 Manager 中的历史配对关系；
- 新版 Manager 使用 3 个全新空白 RW 数据源，不迁移旧 registration/credential/replay/relay keys；
- T1/Broker/TLS/网络/system identity 保留；
- 旧 Manager、旧原始数据和 R5 root-private backup 保留用于回退；
- old Compose 的 3 mounts 不是 Manager recreate authority；future recreation 必须来自 current live Docker inspect 6-mount contract；
- R5 真实冷备份/隔离恢复/旧 Manager 恢复已经 CLOSED_PASS，不重复；
- ESP32-C6 已长期断电，当前没有传感器，不重复无发送端的 90 秒 telemetry 等待；
- 旧五身份 preboot baseline 已成为历史，不得用于 fresh Manager；fresh preboot 期待 0/0/0 + empty relay-keys；
- production Manager replacement 尚未授权；
- board first normal boot / Setup Secret import 均未授权。

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

当前只进入：
NEXT_ONE_GATE=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR_AND_ROLLBACK_TEST

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

本门只允许 GitHub/source/test/CI。
不得 SSH T1、不得停止/替换 Manager、不得动 Broker、不得访问实板。
先完成 one-shot clean Manager deploy executor + rollback failure tests + exact-head source review；
PASS 后 STOP，再单独申请一次 live production replacement 授权。

用户明确不希望继续繁琐的逐项人工验证；后续真实部署目标应为“一次命令、内部自动检查、一个 PASS/STOP 结果”。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=N3W_P4_T1_CLEAN_MANAGER_STATE_FRESH_DEPLOYMENT_SOURCE_PREPARATION
CURRENT_STOP_POINT=CLEAN_ROUTE_SELECTED_FRESH_SOURCE_AND_ZERO_BASELINE_CONTRACT_READY_EXECUTOR_PENDING

SOURCE_DEFECT_PROVEN=false
CURRENT_BLOCKER=FULL_FRESH_MANAGER_ONE_SHOT_DEPLOY_AND_ROLLBACK_EXECUTOR_NOT_IMPLEMENTED

LIVE_SYSTEM_STATE=OLD_MANAGER_RESTORED_LAST_PROVEN_RUNNING_BROKER_UNCHANGED_BOARDS_POWERED_OFF
R5_COLD_BACKUP_AND_RESTORE=CLOSED_PASS

USER_WAIVED_LEGACY_MANAGER_PAIRING_CONTINUITY=true
FRESH_MANAGER_PREBOOT_BASELINE=REGISTRATION_0_CREDENTIAL_0_REPLAY_0_RELAY_KEYS_EMPTY
OLD_MANAGER_AND_OLD_DATA_RETAIN=true
BROKER_FACTORY_RESET=false

NEXT_ONE_GATE=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_DEPLOY_EXECUTOR_AND_ROLLBACK_TEST

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_STANDARD_VERSION=1.0
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.0

EXECUTION_MODEL_EXPLICIT=PASS
HIGH_LEVEL_CODEX_ROLE_BOUNDARY=PASS
DSL_EXECUTION_SEMANTICS_EXPLICIT=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS

PROVEN_FACTS_SEPARATED_FROM_INFERENCE=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS

ALLOWED_FORBIDDEN_SCOPE_EXPLICIT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS

HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
