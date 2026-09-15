# 温室环境监测系统（ESP32-C6）
# N3-W / KF-092 Relay MAC Delivery Feedback Source Repair
# 新会话交接文档 V1.0 — 2026-09-15

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
REPOSITORY_VERSIONED_EXECUTOR=true
NEXT_ONE_GATE_ONLY=true
```

> 本文符合 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`。  
> exact repository/runtime/live evidence 如与本文冲突，以 fresh exact evidence 为准并 fail-closed STOP。  
> 本文只授权并交接 KF-092 source/host-test/CI 修复，不授权任何板卡/T1 live mutation。

---

## 0. 会话切换结论

本轮已完成 KF-091 Home Assistant/Broker TLS DNS alias 修复并恢复 FC4 Home Assistant MQTT TLS session；随后在 Board B Relay-only 验收中发现 Relay 数据会出现“正常 → 一段时间完全消失 → 无人工干预又恢复”的间歇性现象。进一步 source review 已证明 KF-092 firmware-runtime 缺陷：实际 ESP-NOW asynchronous MAC delivery completion 没有进入 Relay path failure hysteresis。

用户已明确授权 KF-092 source repair，但要求把该授权带到新对话执行；当前硬件、T1 与现场状态全部保持不变。

```text
CURRENT_STAGE=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
CURRENT_STOP_POINT=KF092_SOURCE_DEFECT_PROVEN_BEFORE_SOURCE_MUTATION
NEXT_ONE_GATE=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新调查 Home Assistant、KF-091、DynSec 或板卡位置，而是 fresh rebind repository 后直接开始已授权的 KF-092 source repair。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 North Star、source authority、gate、authorization 与 rollback；
- 由高阶模型设计并编写项目代码；
- 维护 callback/task ownership 与 path-state concurrency 边界；
- 评审 source delta，判定 tests/CI closure；
- 不把 field-causation inference 提升为 physical proof；
- PASS 后只提出下一 physical validation stage，不自动执行。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL contract；
- Git branch/worktree、build/test/CI、diff/hash/evidence capture；
- mutation 只在已授权 source scope 内；
- 第一处 substantive authority/scope failure fail-closed STOP；
- 返回结构化 closure；
- 不自行设计代码、不扩大修复、不访问板卡/T1 live runtime。

```text
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
HIGH_LEVEL_MODEL_WRITES_EXECUTION_CODE=true
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
```

### 1.3 DSL execution semantics

```text
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR_BY_CODEX=false
DESIGN_CHANGE_BY_CODEX=false
```

### 1.4 标准交互循环

```text
高阶模型 fresh rebind + authored repair delta
→ 已存在用户 source-repair authorization
→ Codex exact mechanical execution/test/CI
→ high-level model adjudication
→ STOP
```

---

## 2. Product North Star

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

当前 broader acceptance：

```text
ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=NOT_YET_CLOSED
ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=PENDING
ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

KF-092 修复目标不是重新设计 N3-W，而是恢复既有 local path controller 的真实 delivery-feedback 闭环：

```text
RELAY_ACTIVE
-> actual MAC delivery failures
-> existing relay_failures_to_discovery hysteresis
-> DISCOVERY
-> authenticated Relay reacquisition
```

当前不得进入：

```text
BOARD_DEPLOYMENT
USB_SERIAL_FLASH_NVS_ACCESS
T1_LIVE_MUTATION
HOME_ASSISTANT_RECONFIGURE
BROKER_DYNSEC_TLS_CREDENTIAL_MUTATION
PHYSICAL_FAILOVER_VALIDATION
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant
EXPECTED_MAIN_AT_HANDOFF=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
DOC_ALIGNMENT_PR=410
DOC_ALIGNMENT_BRANCH=docs/n3w-multinode-relay-ha-mqtt-alignment-20260915
DOC_ALIGNMENT_PR_MERGED=false
```

新会话第一步必须 fresh query `main`. 若 main 已漂移，必须比较 KF-092 relevant source；material source drift 时 STOP，而不是盲目基于旧 SHA 修改。

### 3.2 Deployed board source authority

```text
BOARD_FIRMWARE_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
```

Fresh review 已确认 current repository code 仍包含同一 defect class；新 source-repair branch 应基于 fresh current main，而不是回退到 deployed firmware source commit。

### 3.3 Relevant source paths

```text
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_espnow_driver.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.h
```

Tests may be modified/added only under relevant N3-W host/unit-test paths.

### 3.4 Target runtime authority

No live target is required for this gate.

```text
TARGET_HOST=REPOSITORY_HOST_ONLY
LIVE_T1_TARGET=OUT_OF_SCOPE
BOARD_TARGET=OUT_OF_SCOPE
SUCCESSOR_AUTHORITY=NOT_APPLICABLE:SOURCE_REPAIR_ONLY
```

---

## 4. Current Live Baseline

Physical/live state is intentionally frozen and must not be changed by the next gate.

```text
MANAGER_STATE=RUNNING_LAST_EXACT_EVIDENCE
BROKER_STATE=RUNNING_LAST_EXACT_EVIDENCE
HOMEASSISTANT_STATE=RUNNING_LAST_EXACT_EVIDENCE
HOMEASSISTANT_AUTHORITY=fc4-homeassistant
HA_MQTT_8883_SESSION_OBSERVED=true

BOARD_A_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_A_LAST_RUNTIME_ROLE=DIRECT

BOARD_B_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_B_RELAY_ONLY_WINDOW_PROVEN=true
BOARD_B_RELAY_RUNTIME=INTERMITTENT

BOARD_C_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_C_AP_ASSOCIATED_OPERATOR_CONFIRMED=true
BOARD_C_DIRECT_PATH_REAL=true

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
T1_LIVE_MUTATION=false
```

The next source-repair gate does not require a T1/board rebind and must not perform one.

---

## 5. Proven Current Facts

### 5.1 Frozen Relay acceptance

```text
MAINLINE_ITEM_1=PASS
SIMULTANEOUS_BC_RELAY_VIA_A=PROVEN
WINDOW_ACCEPTED_RELAY_COUNT=82
WINDOW_REJECTED_RELAY_COUNT=0
WINDOW_DUPLICATE_RELAY_COUNT=0
UNIQUE_CHILD_ROUTES=2
UNIQUE_GATEWAYS=1
```

### 5.2 KF-091 closure

```text
KF091_STATUS=CLOSED_PASS
AUTHORIZATION=FC4_HOME_ASSISTANT_BROKER_TLS_SAN_ALIAS_REPAIR_MUTATION_20260915_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
RESULT=PASS

COMPOSE_SOURCE_POST_SHA256=d3a2bb681db523d4414e64fd26d49074d76c90ac5265493f18ec760494472f60
BROKER_RECREATE_COUNT_EXACT=1
FC4_HA_TLS_SAN_DNS_RESOLVED=true
FC4_HA_TLS_HOSTNAME_VERIFIED=true
HA_MQTT_8883_SESSION_OBSERVED=true
```

No HA MQTT config, certificate, CA, credentials, DynSec, Manager config, or board mutation was required.

### 5.3 Board B intermittent Relay evidence

```text
FRESH_RELAY_ONLY_WINDOW_DIRECT=0
FRESH_RELAY_ONLY_WINDOW_RELAY=27

LATER_180S_DIRECT=0
LATER_180S_RELAY=0

LOOKBACK_ACCEPTED_RELAY=56
LOOKBACK_REJECTED=0

LATER_RELAY_RUN_COUNT=16
LATER_RELAY_RUN_START=2026-09-15T03:06:35Z
LATER_RELAY_RUN_END_AT_CAPTURE=2026-09-15T03:08:00Z
```

Proven classification:

```text
BOARD_B_PERMANENT_RUNTIME_LOSS=false
BOARD_B_RELAY_RUNTIME=INTERMITTENT
FIXED_RELAY_SESSION_LIFETIME_PROVEN=false
```

### 5.4 KF-092 source defect

```text
KF092_STATUS=OPEN
KF092_DOMAIN=FIRMWARE_RUNTIME
SOURCE_DEFECT_PROVEN=true
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
```

Current source behavior:

```text
send_telemetry()
-> send_encrypted_peer()
-> EspNowDriver::send()
-> esp_now_send(...) synchronous submit result
-> path_.note_relay_result(sync_submit_result)
```

Actual unicast delivery result arrives asynchronously through ESP-NOW send callback and currently goes only to diagnostics.

Therefore actual MAC failure does not currently increment the existing Relay failure hysteresis.

### 5.5 Inference kept separate

```text
INFERENCE_KF092_CAUSED_OBSERVED_BOARD_B_INTERMITTENCE=STRONGLY_INDICATED
PHYSICAL_CAUSATION_PROVEN=false
```

Do not upgrade this to `PROVEN` until post-fix physical validation.

---

## 6. Current Root Cause / Blockers

### Blocker A — KF-092 Relay delivery feedback disconnect

```text
ROOT_CAUSE=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
PROVEN_BY=SOURCE_REVIEW
SOURCE_DEFECT_PROVEN=true
RUNTIME_FIELD_CAUSATION_PROVEN=false
```

The path controller currently treats `esp_now_send(...) == ESP_OK` submission acceptance as success, while the later MAC delivery callback is diagnostics-only.

### Blocker B — broader HA Relay entity update remains unclosed

```text
HA_TLS_TRANSPORT_BLOCKER=CLOSED
HA_MQTT_SESSION_OBSERVED=true
ITEM_2_ENTITY_UPDATE=NOT_YET_CLOSED
CURRENT_REASON=RELAY_ONLY_SOURCE_BECAME_INTERMITTENT_BEFORE_FINAL_ATTRIBUTION
```

Do not investigate Item 2 further until KF-092 source repair and later physical revalidation.

---

## 7. Closed / Forbidden Routes

```text
KF091_TLS_DNS_BINDING=CLOSED_PASS
HA_MQTT_TARGET_CHANGE=CLOSED_NOT_REQUIRED
TLS_CERT_ROTATION=CLOSED_NOT_REQUIRED
CREDENTIAL_ROTATION=CLOSED_NOT_REQUIRED
DYNSEC_REPAIR_FOR_CURRENT_BLOCKER=CLOSED_NOT_REQUIRED
DISABLE_TLS_HOSTNAME_VERIFICATION=FORBIDDEN
BOARD_C_AS_RELAY_ONLY_HA_ORACLE=CLOSED:AP_ASSOCIATED_DIRECT_PATH_REAL
FIXED_300S_RELAY_SESSION_LIFETIME=CLOSED_NOT_PROVEN
BOARD_B_PERMANENT_POWER_OR_RUNTIME_LOSS=CLOSED_BY_AUTONOMOUS_RELAY_RESUMPTION
REPLAY_KF091_LIVE_MUTATION_AUTHORIZATION=FORBIDDEN
REPLAY_ID24_ID25_ID26=FORBIDDEN
```

---

## 8. Authorization Ledger

Historical consumed live mutation:

```text
AUTHORIZATION=FC4_HOME_ASSISTANT_BROKER_TLS_SAN_ALIAS_REPAIR_MUTATION_20260915_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=KF091_CLOSED_PASS
```

Current source repair authorization carried into next chat:

```text
AUTHORIZATION=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
GRANTED=true
CLAIMED=false
CONSUMED=false
RESULT=PENDING
REPLAY_PERMITTED=true
SUPERSEDED_BY=NONE
```

Interpretation: this is an unused authorization, not a replay. It may be claimed once in the new chat after exact repository/source rebind succeeds. Once claimed by first source mutation, it becomes consumed even if the repair transaction later fails.

Authorized scope:

```text
SOURCE_MUTATION=true
HOST_TEST_MUTATION=true
CI_CONFIG_MUTATION=ONLY_IF_STRICTLY_REQUIRED_BY_EXISTING_TEST_INTEGRATION
DOCUMENTATION_MUTATION=true
GITHUB_BRANCH_PR_MUTATION=true
BOARD_ACCESS=false
T1_LIVE_MUTATION=false
```

---

## 9. Rollback Authority

This gate mutates repository source only.

```text
ROLLBACK_BASELINE=FRESH_CURRENT_MAIN_AT_NEW_CHAT_REBIND
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
ROLLBACK_AUTHORITY_PATH_OR_ID=BASE_COMMIT_TREE_PLUS_PRECHANGE_BLOB_SHAS
NORMAL_PATH_RESTART_ALLOWED=false
ROLLBACK_ONLY_RESTART_LIMIT=0
SECOND_ATTEMPT_ALLOWED=false_AFTER_AUTHORIZATION_CLAIM
```

Before first source mutation, capture:

```text
BASE_MAIN_SHA
BASE_MAIN_TREE
WORKTREE_CLEAN=true
RELEVANT_SOURCE_BLOB_SHAS
RELEVANT_TEST_BLOB_SHAS
```

Rollback order:

```text
stop further writes
-> restore changed repository files to exact prechange blobs / discard repair branch commits
-> verify base/source blob equality
-> verify no live runtime/board mutation occurred
-> STOP
```

Rollback failure:

```text
ROLLBACK_INCOMPLETE=true
MANUAL_RECOVERY_REQUIRED=true
```

No T1/board rollback authority is needed because those targets are forbidden in this gate.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
```

### 10.1 Purpose

Repair the proven source defect so that actual asynchronous ESP-NOW unicast delivery completions, not synchronous submit acceptance, drive the existing Relay failure hysteresis in normal component-loop context while preserving callback/task safety and all existing Direct/Relay architecture contracts.

### 10.2 Frozen inputs

```text
EXPECTED_MAIN_AT_HANDOFF=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
DEPLOYED_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
RELAY_FAILURES_TO_DISCOVERY_DEFAULT=2
```

### 10.3 Required repair / proof

```text
1. Fresh rebind main and relevant source; stop on material drift.
2. Create bounded repair branch from fresh current main.
3. High-level model authors minimal completion-feedback repair.
4. Wi-Fi callback only enqueues bounded unicast completion metadata/state.
5. Normal loop drains completion state.
6. Only current active-Relay destination completion may affect Relay hysteresis.
7. Immediate synchronous submission failure counts as failure.
8. Synchronous ESP_OK submission does not count as delivery success.
9. Broadcast completion cannot affect child Relay path.
10. Stale completion for previous Relay is ignored.
11. Existing threshold of two actual failures drives RELAY_ACTIVE -> DISCOVERY.
12. Actual success after one failure resets hysteresis.
13. Existing Direct path and Relay->Direct recovery tests remain passing.
14. Add/strengthen host tests covering all above contracts.
15. Run relevant test suites and repository-required CI.
16. Commit source repair and open/update a dedicated source PR.
17. Update KF-092/current-state docs as part of repair closure if needed.
18. STOP before any board deployment/physical validation.
```

### 10.4 PASS

```text
KF092_SOURCE_REPAIR=PASS
ACTUAL_UNICAST_COMPLETION_DRIVES_RELAY_HYSTERESIS=true
CALLBACK_DIRECT_RUNTIME_MUTATION=false
TWO_ACTUAL_FAILURES_TO_DISCOVERY_TEST=PASS
STALE_AND_BROADCAST_COMPLETION_GUARDS=PASS
RELEVANT_HOST_TESTS=PASS
CI=PASS
READY_FOR_KF092_PHYSICAL_VALIDATION_AUTHORIZATION=true
```

### 10.5 FAIL

```text
KF092_SOURCE_REPAIR=FAIL_<EXACT_CLASS>
READY_FOR_KF092_PHYSICAL_VALIDATION_AUTHORIZATION=false
AUTO_REPAIR=false
AUTO_RETRY=false
STOP=true
```

Codex/high-level model must not automatically enter board deployment or physical validation.

---

## 11. Hard Allowed / Forbidden Scope

Default:

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- fresh read-only Git/GitHub source rebind
- create one bounded source-repair branch
- high-level-model-authored source changes inside KF-092 allowlist
- relevant host/unit test changes
- build/test/CI execution
- repository documentation updates for KF-092 closure
- commit/push/open PR for the repair
```

### FORBIDDEN

```text
- T1 SSH/live mutation
- Broker/Manager/Home Assistant/DynSec mutation
- board power changes
- USB/serial access
- Flash/NVS/OTA
- RF experiment
- MQTT test publish / extra subscriber
- credential/certificate changes
- unrelated refactor
- changing path thresholds merely to hide the defect
- direct path-state mutation from Wi-Fi callback task
- physical deployment after source PASS
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_REPOSITORY_WRITE=true
BOUNDED_WRITE_SCOPE=KF092_SOURCE_HOST_TEST_CI_DOCS_ONLY
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order exact executor and result reporter.

This handoff is an executable DSL protocol.
A separately supplied Bash/Python executor is not required unless the high-level model explicitly supplies one.

Mechanically compile only the allowed operations into minimum necessary commands.
Do not author project code.
Do not expand scope.
Do not repair live runtime.
Do not access boards.
Do not retry after authorization claim unless a new authorization is supplied.
Do not enter physical validation.
```

```text
============================================================
0. AUTHORIZATION
============================================================
AUTHORIZATION=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
GRANTED=true
CLAIMED=false
CONSUMED=false

Do not claim until fresh repository/source rebind and repair delta allowlist are established.
First repository source mutation claims and consumes the authorization.

============================================================
1. FRESH REPOSITORY REBIND
============================================================
fetch origin/main
resolve fresh main SHA/tree
require clean source workspace or isolated fresh worktree
inspect relevant source and tests
compare against frozen defect contract
if material authority drift changes the defect or repair design: STOP

============================================================
2. PRECHANGE ROLLBACK BINDING
============================================================
record base main SHA/tree
record relevant source/test blob SHAs
record clean-worktree status
no live target access

============================================================
3. REPAIR BRANCH
============================================================
create bounded KF-092 repair branch from fresh current main
no unrelated merge/rebase

============================================================
4. SOURCE MUTATION
============================================================
apply only high-level-model-authored repair delta
callback side: bounded completion enqueue only
normal-loop side: destination-bound completion drain and hysteresis update
preserve current path policy thresholds
preserve Direct/Relay architecture

============================================================
5. TESTS
============================================================
prove success completion behavior
prove one failure behavior
prove two actual failures -> DISCOVERY
prove immediate submit failure behavior
prove success resets prior failure
prove stale old-Relay completion ignored
prove broadcast completion ignored
prove callback task does not directly mutate path state
run existing relevant N3-W suites

============================================================
6. SOURCE REVIEW / CI
============================================================
require diff allowlist
require no board/T1/live config files changed
commit repair
push branch
open/update source PR
run required CI

============================================================
7. HARD STOP
============================================================
return structured closure
no board deployment
no physical validation
no T1 mutation
```

---

## 13. Expected Closure

```text
=== N3W KF092 RELAY MAC DELIVERY FEEDBACK SOURCE REPAIR CLOSURE ===

EXECUTION_ID=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
AUTHORIZATION=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
AUTHORIZATION_CLAIMED=<true|false>
AUTHORIZATION_CONSUMED=<true|false>

FRESH_MAIN_SHA=
FRESH_MAIN_TREE=
SOURCE_BINDING=PASS|FAIL
PRECHANGE_WORKTREE_CLEAN=
REPAIR_BRANCH=
REPAIR_COMMIT=
SOURCE_PR=

SOURCE_DEFECT_RECONFIRMED=true|false
CALLBACK_DIRECT_RUNTIME_MUTATION=false
ACTUAL_UNICAST_COMPLETION_FEEDBACK_IMPLEMENTED=true|false
ACTIVE_RELAY_DESTINATION_BINDING_IMPLEMENTED=true|false
IMMEDIATE_SUBMIT_FAILURE_HANDLED=true|false
BROADCAST_COMPLETION_GUARD=PASS|FAIL
STALE_COMPLETION_GUARD=PASS|FAIL
TWO_ACTUAL_FAILURES_TO_DISCOVERY_TEST=PASS|FAIL
SUCCESS_RESETS_FAILURE_HYSTERESIS_TEST=PASS|FAIL
RELEVANT_HOST_TESTS=PASS|FAIL
CI=PASS|FAIL|NOT_RUN

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_MUTATION=false
RF_EXECUTION=false

KF092_SOURCE_REPAIR=PASS|FAIL_<CLASS>
READY_FOR_KF092_PHYSICAL_VALIDATION_AUTHORIZATION=true|false
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=KF092_POST_REPAIR_BOARD_DEPLOYMENT_AND_PHYSICAL_VALIDATION_DESIGN
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true
```

Source/CI PASS does not prove field causation and does not authorize flashing any board.

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

If authorization had already been claimed, it is consumed and must not be silently reused.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
```

KF-091:

```text
KF_ID=KF-091
DOMAIN=INFRASTRUCTURE
SYMPTOM=FC4 Home Assistant could not resolve certificate-authoritative Broker TLS name
ROOT_CAUSE=BROKER_SHARED_NETWORK_MISSING_ALIAS_FOR_EXISTING_TLS_DNS_SAN
FIX_OR_GUARD=durable existing-SAN Broker network alias + full TLS namespace verification
STATUS=CLOSED_PASS
```

KF-092:

```text
KF_ID=KF-092
DOMAIN=FIRMWARE_RUNTIME
SYMPTOM=Relay child can become Manager-silent and later resume without operator intervention
ROOT_CAUSE=actual asynchronous ESP-NOW unicast completion does not feed Relay path hysteresis; synchronous submit acceptance is used instead
FIX_OR_GUARD=bounded callback completion handoff to normal loop + active-destination binding + host regressions
STATUS=OPEN_SOURCE_REPAIR_AUTHORIZED
```

Central `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` on current main predates KF-091/KF-092. Dedicated KF records plus current-state docs are the current authority for these IDs until the central table is updated in the source-repair documentation closure. This lag is explicit and must not be interpreted as ID availability.

---

## 16. New Chat Start Prompt

```text
阅读《N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_NEW_CHAT_HANDOFF_V1.0_20260915.md》。

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #410 documentation alignment branch
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_DEFECT_20260915.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
支线任务：修复 Relay MAC delivery feedback 与 LocalPathController 断链
当前任务：N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01

本阶段继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
REPOSITORY_VERSIONED_EXECUTOR=true

用户已授权：
AUTHORIZATION=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
GRANTED=true
CLAIMED=false
CONSUMED=false

该授权带入本新会话，不需要重新询问同一 source-repair 授权。
先 fresh rebind repository/source authority；若无 material drift，直接开始 source/host-test/CI 修复。

当前硬件、T1、Broker、Manager、Home Assistant 与板卡物理状态全部保持不变。

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
T1_LIVE_MUTATION=false

不得访问 USB/serial/Flash/NVS/RF，不得部署固件，不得重放 consumed authorization，不得重新进入已关闭 KF-091/Home Assistant TLS 修复路线。

只进入：
NEXT_ONE_GATE=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01

source/CI PASS 后必须 STOP，等待新的 physical validation authorization。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
CURRENT_STOP_POINT=KF092_SOURCE_DEFECT_PROVEN_BEFORE_SOURCE_MUTATION

KF091_STATUS=CLOSED_PASS
HA_MQTT_8883_SESSION_OBSERVED=true

BOARD_A_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_B_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_B_RELAY_RUNTIME=INTERMITTENT
BOARD_C_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_C_AP_ASSOCIATED_OPERATOR_CONFIRMED=true

SOURCE_DEFECT_PROVEN=true
CURRENT_BLOCKER=KF092_ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
FIELD_CAUSATION=STRONGLY_INDICATED_NOT_YET_PHYSICALLY_PROVEN

AUTHORIZATION=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

LIVE_SYSTEM_STATE=UNCHANGED_BY_HANDOFF
NEXT_ONE_GATE=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01

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
