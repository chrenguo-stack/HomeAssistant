# 温室环境监测系统（ESP32-C6）
# N3-W / KF-096 / PR #437 Same-Boot Direct -> Relay Physical Validation
# 新会话交接文档 V1.0 — 2026-09-19

```text
HANDOFF_STANDARD_VERSION=1.0
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

本文按 exact historical handoff authority `4300890dff0ce63d5a547df21426e287d084d9ee` 中的 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md` 与 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` 编写。fresh exact repository/runtime/physical evidence 如与本文冲突，以更高 authority 为准并先停止执行、完成 rebind。

---

## 0. 会话切换结论

本轮因上下文已经较长，在 PR #437 exact artifact 完成 Board B 写入且 post-write Direct baseline 取得 PASS 后切换新会话。下一会话不重新复盘整个 KF-096 历史，只从同一 boot 的 Direct -> Relay 物理验证开始。

```text
CURRENT_STAGE=PR437_BOARD_B_POSTWRITE_DIRECT_BASELINE_COMPLETE
CURRENT_STOP_POINT=READY_FOR_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION
NEXT_ONE_GATE=N3W_KF096_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260919_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
PHYSICAL_AUTHORIZATION_REQUIRED=true

HANDOFF_READY_FOR_NEW_CHAT=true
```

下一 gate 尚未因为本交接而自动获得执行授权。新会话必须先 fresh rebind，再请求该物理 gate 的明确授权。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 N3-W product route、PR #437 exact source/artifact/runtime authority；
- 设计本 gate 的物理边界、证据口径、PASS/FAIL/STOP；
- 区分产品失败、日志 oracle 失败、T1/runtime 问题与人工物理操作问题；
- 保持 KF-092/KF-094/KF-095/KF-096 的既有 disposition；
- 不因新会话重新发明 executor/framework。

### 1.2 Codex 低阶执行职责

- 机械执行最小 Git/SSH/Docker/read-only SQL/shell 观察；
- 仅在用户明确授权后进入物理移动步骤；
- 第一处 substantive mismatch 后 fail-closed STOP；
- 返回结构化 closure；
- 不扩大 scope、不自动修复、不自动重刷、不自动合并 PR #437。

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

本 gate 不需要新建通用 executor。优先使用短、可审计、只读命令和人工物理步骤。

### 1.4 标准交互循环

```text
高阶模型：fresh rebind / gate 设计 / 请求物理授权
        ↓
用户：批准 exact physical gate
        ↓
Codex/终端：只读 T1 observation + operator physical move
        ↓
高阶模型：复核 closure / PASS|FAIL|STOP
```

---

## 2. Product North Star

```text
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
CURRENT_BRANCH=KF096_PR437_PHYSICAL_VALIDATION
KF096_STATUS=OPEN
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

最终目标是在 ESP32-C6 单射频约束下证明 Direct / Relay / Direct recovery 的真实运行连续性，而不是只证明源码或 CI。

当前不得进入：

```text
PR437_MERGE
NEW_SOURCE_REPAIR
BOARD_A_FIRMWARE_OR_NVS_MUTATION
T1_MANAGER_BROKER_DYNSEC_CREDENTIAL_MUTATION
RELAY_TO_DIRECT_FAILBACK
GENERAL_FRAMEWORK_REWRITE
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant

REPOSITORY_MAIN_AT_HANDOFF_ALIGNMENT_START=
0ea13c9f9f76fdf7fb79ec82393408ab144b4e18

REPOSITORY_MAIN_TREE_AT_HANDOFF_ALIGNMENT_START=
c2bd54b4eccb16170ad34929e170cf67bd5e624d

REPOSITORY_MAIN_REQUIRES_FRESH_READONLY_REBIND=true

MERGED_PRODUCT_SOURCE_AUTHORITY=
d1b5c3acbd32cca95483743ffe2edba9aa3f904f
```

文档对齐可能使 main 在交接后前进；新会话必须读取 fresh main，但不得用 documentation-only main 前进替换 PR #437 exact product-source authority。

### 3.2 Candidate / artifact / image

```text
CANDIDATE_PR=437
CANDIDATE_STATE_AT_HANDOFF=OPEN_DRAFT

CANDIDATE_SOURCE_HEAD=
cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c

CANDIDATE_SOURCE_TREE=
b459fae0a054d45b0d09e60bffae9769e060a5c0

ARTIFACT_RUN_ID=35414060819
ARTIFACT_ID=10575077512
ARTIFACT_NAME=n3w-pr437-boardb-exact-source

ARTIFACT_ZIP_SIZE=727532
ARTIFACT_ZIP_SHA256=
b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814

APPLICATION_SIZE=1139600
APPLICATION_SHA256=
407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb

OTADATA_SIZE=8192
OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

MANIFEST_SHA256=
98a6dec323e8057a30d6b1e332d549fe54288f3b45fcbbbf460292871f7a91a0
```

### 3.3 Successor / deployment material

```text
DEPLOYED_BOARD_B_SOURCE_HEAD=
cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c

DEPLOYED_BOARD_B_SOURCE_TREE=
b459fae0a054d45b0d09e60bffae9769e060a5c0

PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS
```

### 3.4 Target host / runtime authority

```text
T1_TARGET=PRIVATE
T1_MANAGER_OBSERVER=PASS_AT_LAST_WINDOW
MANAGER_RESTART_COUNT_AT_LAST_WINDOW=0
T1_RUNTIME_MUTATION_THIS_ROUTE=false

BOARD_A_ROLE=STATIONARY_RELAY_GATEWAY
BOARD_A_POWER_AND_LOCATION_REQUIRES_FRESH_RECHECK=true

BOARD_B_LAST_PROVEN_PATH=direct
BOARD_B_POWER_SOURCE_REQUIRES_FRESH_RECHECK=true
BOARD_B_LOCATION_REQUIRES_FRESH_RECHECK=true

RAW_BOARD_IDENTITY_PUBLIC=false
RAW_T1_LOCATOR_PUBLIC=false
```

---

## 4. Current Live Baseline

交接前最后一个 authoritative live window 来自 Manager canonical durable state：

```text
OBSERVATION_SECONDS=90

BOARD_B_CANONICAL_CURSOR_BEFORE=FOUND
BOARD_B_CANONICAL_CURSOR_AFTER=FOUND

BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SOURCE_AFTER=direct

BOARD_B_SEQ_BEFORE=1370
BOARD_B_SEQ_AFTER=1388
BOARD_B_SEQ_DELTA=18

BOARD_B_SAME_BOOT=true
BOARD_B_CANONICAL_ADVANCED=true
BOARD_B_LAST_SOURCE_DIRECT=true
BOARD_B_CANONICAL_DIRECT_BASELINE=PASS

MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_STARTED_AT_UNCHANGED=true
MANAGER_RESTART_COUNT_UNCHANGED=true
```

该窗口证明 PR #437 写后 Direct 运行正常，但新会话开始时不能假设板卡供电、位置和 T1 runtime 从未变化，必须做最小 fresh read-only recheck。

```text
BOARD_ACCESS_AT_HANDOFF=false
SERIAL_OPEN=false
FLASH_WRITE_AFTER_DEPLOYMENT=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
PR437_MERGE=false
```

---

## 5. Proven Current Facts

### 5.1 PR #437 source / CI / artifact

```text
PR437_FINAL_SOURCE_REVIEW=PASS
PR437_NEW_SOURCE_BLOCKER_FOUND=false
PR437_HEAD_CI=11_OF_11_PASS
PR437_EXACT_ARTIFACT_BUILD=PASS
PR437_EXACT_ARTIFACT_BINDING=PASS
```

### 5.2 Board B deployment

```text
ARTIFACT_DOWNLOAD=PASS
ARTIFACT_INNER_BINDING=PASS
SECURITY_STATE=PASS
FLASH_SIZE=8MB
PARTITION_TABLE_BINDING=PASS

APPLICATION_WRITE=PASS
OTADATA_WRITE=PASS

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false

APPLICATION_READBACK_HASH_VERIFY=NOT_EXECUTED
OTADATA_READBACK_HASH_VERIFY=NOT_EXECUTED
```

### 5.3 Physical identity exception

```text
AUTOMATED_BOARD_IDENTITY_MATCH=FAIL
OPERATOR_TARGET_CONFIRMATION=PASS
OPERATOR_IDENTITY_OVERRIDE=true
IDENTITY_OVERRIDE_REUSABLE=false
RAW_BOARD_IDENTITY_PUBLIC=false
```

该事实必须原样保留。不能在新会话中改写成 automated identity PASS，也不能把本次人工 override 继承到未来 Flash/NVS mutation。

### 5.4 Post-write Direct liveness

```text
PR437_POSTWRITE_DIRECT_BASELINE=PASS
BOARD_B_CANONICAL_DIRECT_BASELINE=PASS
BOARD_B_SEQ_DELTA_90S=18
BOARD_B_SAME_BOOT=true
MANAGER_RESTART_COUNT_UNCHANGED=true
```

### 5.5 Manager INFO log oracle

第一轮基于 INFO 行的观察得到零匹配，但 canonical durable state 随后证明 Direct 正常：

```text
MANAGER_INFO_LOG_ORACLE=FALSE_NEGATIVE
KF010_GUARD_APPLIES=true
PRODUCT_DIRECT_PATH_FAILURE=false
```

因此新会话不得把 “没有 `Accepted simplified N3-W telemetry` INFO 行” 单独当成 no-publish/no-acceptance。

---

## 6. Current Root Cause / Blockers

### Blocker A — PR #437 物理往返链路尚未验证

```text
PR437_DIRECT_TO_RELAY=NOT_EXECUTED
PR437_RELAY_STEADY_STATE_CONTINUITY=NOT_EXECUTED
PR437_RELAY_TO_DIRECT_FAILBACK=NOT_EXECUTED
KF096_STATUS=OPEN
```

本次下一 gate 只处理第一项：把已经 PASS 的 Direct 基线推进到 same-boot Relay。

### Blocker B — 自动 Board B identity authority 与当前实体板不一致

```text
AUTOMATED_IDENTITY_MISMATCH=PROVEN
PRODUCT_RUNTIME_DEFECT_PROVEN_BY_THIS=false
CURRENT_PHYSICAL_TARGET_OPERATOR_CONFIRMED=true
FUTURE_MUTATION_OVERRIDE_AUTHORITY=false
```

这不是本 gate 的功能性阻塞项，因为下一 gate 不写 Flash/NVS；但它必须保留为审计事实，未来任何 board mutation 必须重新设计/授权 target binding。

### Non-blocking unresolved historical items

```text
INITIAL_DIRECT_FAILURE_TRIGGER=UNRESOLVED
MQTT_PROTOCOL_ERROR_ROOT_CAUSE=UNRESOLVED
```

它们不阻止当前 same-boot Direct -> Relay gate。

---

## 7. Closed / Forbidden Routes

除非出现新的 direct counter-evidence，不得重新进入：

```text
KF092=CLOSED_PASS
PR428_ARTIFACT=FROZEN_HISTORICAL_NOT_FOR_DEPLOYMENT
PR431_ARTIFACT=FROZEN_HISTORICAL_NOT_FOR_PR437_VALIDATION
PR425_REFLASH=FORBIDDEN_IN_CURRENT_ROUTE
SERIAL_AS_PASSIVE_RUNTIME_ORACLE=CLOSED
BOARD_IDENTITY_AUTOMATED_PASS=FORBIDDEN_CLAIM
IDENTITY_OVERRIDE_REUSE=FORBIDDEN
BOARD_A_MUTATION=FORBIDDEN
T1_RUNTIME_MUTATION=FORBIDDEN
PR437_MERGE=FORBIDDEN_WITHOUT_EXPLICIT_AUTHORIZATION
AUTO_REPAIR_AFTER_FAILURE=FORBIDDEN
AUTO_RETRY_AFTER_SUBSTANTIVE_PHYSICAL_FAILURE=FORBIDDEN
AUTO_RELAY_TO_DIRECT_AFTER_THIS_GATE=FORBIDDEN
```

---

## 8. Authorization Ledger

### Historical read-only preflight

```text
AUTHORIZATION=N3W_KF096_PR437_BOARD_B_WRITE_PREFLIGHT_20260919_01
CLAIMED=false
CONSUMED=false
RESULT=FAIL_CLOSED:AUTOMATED_BOARD_IDENTITY_MISMATCH
REPLAY_PERMITTED=NOT_APPLICABLE:read-only gate
```

### Consumed Board B write authorization

```text
AUTHORIZATION=N3W_KF096_PR437_BOARD_B_OPERATOR_CONFIRMED_DIRECT_WRITE_20260919_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

该 authorization 永久不可重放。

### Completed post-write Direct baseline

```text
AUTHORIZATION=N3W_KF096_PR437_BOARD_B_POSTWRITE_DIRECT_BASELINE_20260919_01
CLAIMED=false
CONSUMED=false
RESULT=PASS
REPLAY_PERMITTED=NOT_APPLICABLE:read-only observation
```

### Proposed next physical authorization

```text
PROPOSED_AUTHORIZATION=
N3W_KF096_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260919_01

GRANTED=false
```

“放到新对话继续”不等于已经授权物理移动/测试。新会话先 fresh rebind，再请求明确授权。

---

## 9. Rollback Authority

下一 gate 不进行软件/持久化 mutation，因此：

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:NO_SOFTWARE_MUTATION_PLANNED
FLASH_ROLLBACK=false
T1_ROLLBACK=false
BOARD_A_ROLLBACK=false
```

物理测试若中断，恢复动作仅为停止测试并将 Board B 返回正常 Wi-Fi 覆盖位置。若为了可移动供电需要先重新建立 battery Direct baseline，可以在获得本 gate 明确授权后进行；一旦 baseline 建立，Direct -> Relay 移动期间不得再 power-cycle/reboot。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=
N3W_KF096_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260919_01
```

### 10.1 Purpose

只回答一个问题：

**已部署 PR #437 的 Board B，能否从 fresh Direct baseline 在不重启的情况下切换到 Board A Relay，并由 Manager canonical state 接受 Relay telemetry。**

这一步是后续 Relay steady-state / Relay -> Direct recovery 测试的前置状态建立，不在本 gate 内验证完整 failback。

### 10.2 Frozen inputs

```text
PR437_HEAD=
cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c

PR437_TREE=
b459fae0a054d45b0d09e60bffae9769e060a5c0

ARTIFACT_ID=10575077512
APPLICATION_SHA256=
407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb

BOARD_A_ROLE=STATIONARY_RELAY_GATEWAY
T1_OBSERVER=MANAGER_CANONICAL_DURABLE_STATE
```

### 10.3 Pre-execution rebind

授权前只允许：

1. fresh read repository main and PR #437 state/head；
2. fresh read current-state/index/handoff；
3. fresh read T1 Manager running/restart state；
4.确认 Board A、Board B 当前供电/位置；
5.确认如何让 Board B 在同一 boot 下完成从 Direct 位置到 Relay 位置的移动。

如果 Board B 当前无法在不断电条件下移动，可以在授权后先建立一个新的 battery-powered Direct baseline；“same boot”从该 fresh baseline 开始计算。

### 10.4 Authorized operations after explicit approval

1. 建立 fresh Board B Direct canonical baseline；
2. 记录 public-safe boot-session hash、当前 Direct seq/time；
3. 确认 Board A stationary Relay gateway；
4. 仅移动 Board B 到已验证 Relay 场景；
5. 移动后不 reboot / power-cycle Board B；
6. read-only 观察 T1 Manager canonical cursor，直到首次 Relay acceptance 或 bounded timeout；
7. 首次 Relay 后再观察至少两个后续 Relay sequence advancement，确认不是一次性偶发；
8. 记录最后 Direct、第一 Relay、same-boot、seq gap、Manager-visible gap、Manager restart state；
9. STOP。

### 10.5 PASS

```text
PREMOVE_DIRECT_BASELINE=PASS
BOARD_A_STATIONARY_RELAY_GATEWAY_CONFIRMED=true
BOARD_B_REBOOT_AFTER_BASELINE=false

MANAGER_CANONICAL_RELAY_ACCEPTANCE=PASS
SAME_BOOT_DIRECT_TO_RELAY=true
BOARD_B_LAST_SOURCE_RELAY=true
POST_RELAY_SEQ_ADVANCEMENT=PASS

MANAGER_RESTART_COUNT_UNCHANGED=true
T1_RUNTIME_MUTATION=false

PR437_SAME_BOOT_DIRECT_TO_RELAY_RESULT=PASS
```

必须报告实际 timing/seq，不得只给 PASS。

### 10.6 FAIL / STOP

以下任一成立即 STOP：

```text
FAIL_NO_FRESH_DIRECT_BASELINE
FAIL_BOARD_A_RELAY_GATEWAY_NOT_READY
FAIL_BOARD_B_REBOOT_DURING_TRANSITION
FAIL_NO_MANAGER_CANONICAL_RELAY_WITHIN_BOUNDED_WINDOW
FAIL_RELAY_ONLY_SINGLE_FRAME_WITHOUT_ADVANCEMENT
FAIL_MANAGER_RESTART_OR_RUNTIME_DRIFT
FAIL_EVIDENCE_INSUFFICIENT
```

INFO log absence单独不构成 FAIL；优先使用 canonical durable state。

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED after explicit physical-test authorization

```text
manual Board B portable-power setup if needed
manual Board B movement
manual Board A stationary-state confirmation
read-only T1 SSH/Docker inspection
read-only Manager canonical SQLite observation
read-only GitHub/source lookup
bounded local evidence parsing
```

### FORBIDDEN

```text
Board B Flash/erase/NVS/otadata mutation
Board B identity normalization
reuse of consumed write authorization
reuse of identity override as future mutation authority
Board A firmware/NVS mutation
T1 Manager/Broker/DynSec/credential/TLS mutation
application serial open
PR437 source change
PR437 merge
automatic physical retry after substantive failure
automatic Relay steady-state/failback execution after PASS
```

---

## 12. Codex DSL Execution Contract

```text
EXECUTOR=task-appropriate minimum commands
EXECUTION_METHOD=GitHub read-only + T1 SSH read-only + operator physical movement

PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

LIVE_RUNTIME_MUTATION=false
BOUNDED_LOCAL_EVIDENCE_PARSING=true
APPLICATION_SERIAL_OPEN=false
FLASH_WRITE=false
```

推荐 Manager canonical durable-state observer，而不是依赖单一 INFO log。命令必须避免输出 raw NODE_ID、raw board identity、private T1 locator 或 credentials。

---

## 13. Expected Closure

```text
=== N3W KF096 PR437 SAME-BOOT DIRECT TO RELAY PHYSICAL VALIDATION CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

REPOSITORY_MAIN=
PR437_HEAD=
PR437_ARTIFACT_BINDING=

BOARD_A_STATIONARY_RELAY_GATEWAY_CONFIRMED=
BOARD_B_POWER_MODE=
PREMOVE_DIRECT_BASELINE=
PREMOVE_BOOT_SESSION_SHA256=
PREMOVE_DIRECT_TIME=
PREMOVE_DIRECT_SEQ=

MOVE_START_TIME=
FIRST_RELAY_TIME=
FIRST_RELAY_SEQ=
POST_RELAY_LAST_TIME=
POST_RELAY_LAST_SEQ=

SAME_BOOT_DIRECT_TO_RELAY=
BOARD_B_REBOOT_AFTER_BASELINE=
MANAGER_VISIBLE_GAP_MS=
MISSING_SEQUENCE_RANGE=
MISSING_SEQUENCE_COUNT=
POST_RELAY_SEQ_ADVANCEMENT=

MANAGER_RESTART_COUNT_BEFORE=
MANAGER_RESTART_COUNT_AFTER=
MANAGER_RESTART_COUNT_UNCHANGED=

MANAGER_INFO_LOG_ORACLE=
MANAGER_CANONICAL_RELAY_ACCEPTANCE=

BOARD_B_FLASH_MUTATION=false
BOARD_A_MUTATION=false
T1_RUNTIME_MUTATION=false
APPLICATION_SERIAL_OPEN=false
PR437_MERGE=false

PR437_SAME_BOOT_DIRECT_TO_RELAY_RESULT=
KF096_STATUS=OPEN

NEXT_ROUTE=
STOP=true

=== END ===
```

不得在 closure 中声称本 gate 没有证明的 Relay steady-state、Relay -> Direct failback 或完整 KF-096 closure。

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=
N3W_KF096_PR437_RELAY_CONTINUITY_AND_DIRECT_FAILBACK_REVIEW

AUTO_EXECUTE_AFTER_PASS=false
```

回到高阶模型，依据实际 Direct -> Relay gap 与 Relay 起始状态设计下一个 gate。不要自动移动 Board B 回 Wi-Fi 并把它冒充 Relay -> Direct 验收。

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
AUTO_REFLASH=false
AUTO_MERGE=false
STOP_AND_REVIEW=true
```

---

## 15. KNOWN_FAILURES Updates

```text
KF010_LOG_ORACLE_GUARD=EXERCISED_AND_PRESERVED
KF092_STATUS=CLOSED_PASS
KF094_STATUS=OPEN
KF095_STATUS=GUARDED
KF096_STATUS=OPEN

NEW_KNOWN_FAILURE_REQUIRED=false
```

本轮没有证据支持新增产品 Known Failure。自动 Board B identity mismatch + operator override 作为当前执行审计事实保留，不改写现有 repository identity guard。

---

## 16. New Chat Start Prompt

```text
阅读《N3W_KF096_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_NEW_CHAT_HANDOFF_V1.0_20260919.md》。

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #437
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_KF096_PR437_POSTWRITE_DIRECT_BASELINE_ALIGNMENT_20260919.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W / KF-096。

每次回复先写：
主线任务：N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
支线任务：KF-096 PR #437 Direct recovery liveness repair
当前任务：N3W_KF096_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260919_01

必须先承认：
- PR #437 exact artifact 已由 operator-confirmed target override 写入 Board B；
- automated Board B identity comparison 当时 FAIL，不能改写为 PASS，也不能复用该 override；
- write authorization 已 consumed，禁止重放；
- PR #437 post-write Direct baseline 已由 Manager canonical durable state PASS；
- 90 秒内 seq 1370 -> 1388，same boot，source=direct，Manager restart count 保持 0；
- 之前 Manager INFO log 0-match 已按 KF-010 归类为 false-negative oracle，不是产品 Direct failure；
- PR #437 仍 OPEN_DRAFT，禁止自动 merge；
- KF-096 仍 OPEN；
- Direct -> Relay、Relay steady-state、Relay -> Direct 尚未在 PR #437 上完成。

当前只进入：
NEXT_ONE_GATE=N3W_KF096_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260919_01

新会话先做最小 fresh read-only rebind 和现场状态确认，然后向我请求该 physical gate 的明确授权。
未授权前不要移动/重启 Board B，不操作 Board A，不打开应用串口，不改 T1/Broker/Manager/DynSec，不刷机，不修改或合并 PR #437。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=PR437_BOARD_B_POSTWRITE_DIRECT_BASELINE_COMPLETE
CURRENT_STOP_POINT=READY_FOR_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION

PR437_STATE=OPEN_DRAFT
PR437_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
PR437_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0

PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS
PR437_PHYSICAL_VALIDATION=IN_PROGRESS

AUTOMATED_BOARD_IDENTITY_MATCH=FAIL
OPERATOR_IDENTITY_OVERRIDE=true
IDENTITY_OVERRIDE_REUSABLE=false

WRITE_AUTHORIZATION_CONSUMED=true
WRITE_AUTHORIZATION_REPLAY_PERMITTED=false

BOARD_B_LAST_PROVEN_PATH=direct
BOARD_B_LAST_PROVEN_SEQ=1388
BOARD_B_LAST_PROVEN_SAME_BOOT=true
MANAGER_LAST_PROVEN_RESTART_COUNT=0

KF096_STATUS=OPEN
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED

NEXT_ONE_GATE=
N3W_KF096_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260919_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
PHYSICAL_AUTHORIZATION_REQUIRED=true
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
