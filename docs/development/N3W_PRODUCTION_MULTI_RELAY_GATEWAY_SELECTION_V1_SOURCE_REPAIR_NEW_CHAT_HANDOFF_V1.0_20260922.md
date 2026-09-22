# N3-W Production Multi-Relay Gateway Selection V1
# Source Repair
# 新会话交接文档 V1.0 — 2026-09-22

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文按 exact historical authority `4300890dff0ce63d5a547df21426e287d084d9ee` 中的
> `docs/development/NEW_CHAT_HANDOFF_STANDARD.md` 与
> `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` 编写。
> 如本文与 fresh exact repository/runtime/live evidence 冲突，以更高 authority 为准，并先停止执行、完成 rebind。

---

## 0. 会话切换结论

本轮已完成此前缺失的 A/B Relay 角色互换实机验收。Board A 与 Board B 使用同一冻结 PR #437 物理测试 artifact，反向角色
`Board B=Direct/Gateway, Board A=Relay Child` 已完成 battery-powered same-boot
`Direct -> Relay -> 600 s Relay -> Direct` 全链路，并取得 PASS。

当前对话上下文已较长；后续不再继续追加物理测试。下一会话回到已经完成并独立复核的
Production Multi-Relay Gateway Selection V1 source design，进入源码实现。

```text
CURRENT_STAGE=PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1
CURRENT_STOP_POINT=A_B_RELAY_ROLE_SWAP_PHYSICAL_ACCEPTANCE_CLOSED_PASS
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_20260922_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘 PR #437/KF-096 全历史，也不是再次执行 A/B role-swap physical route；从 source-repair gate 的 fresh rebind 开始。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 Production Multi-Relay Gateway Selection V1 产品路线与冻结设计；
- 维护 exact production-successor source authority；
- 只在冻结 allowlist 内编写产品源码/测试/CI；
- 区分 product-source failure、CI/tooling failure、物理验证缺口；
- 复核源码实现是否严格保持 no-proactive-roaming、no-dynamic-load-balancing 与 Option-B 边界；
- 根据 source-repair closure 决定后续 source review / exact artifact / physical acceptance gate；
- 不把测试框架扩展成第二套产品架构。

### 1.2 Codex 低阶执行职责

- mechanically fresh rebind GitHub authorities；
- 在明确授权后创建 exact source-repair branch；
- 执行最小 Git/source/test/CI/compile 操作；
- 机械捕获 changed-file allowlist、test/compile/CI evidence；
- 第一处 substantive authority mismatch 后 fail-closed STOP；
- 不扩大 scope、不改设计、不访问 Board/T1、不自动进入 artifact/physical gate。

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

SOURCE_REPAIR 本身允许产品源码修改，但只能发生在 section 10 冻结 allowlist 与 design contract 内。
如果实现证明需要额外产品/测试/CI 文件，必须 STOP 并回到高阶模型扩展 allowlist，不能 opportunistic edit。

### 1.4 标准交互循环

```text
高阶模型：fresh rebind / 复核设计 / 请求 exact SOURCE_REPAIR authorization
        ↓
用户：批准 N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_20260922_01
        ↓
高阶模型：编写 product source / tests / CI
        ↓
Codex：机械执行 test / compile / CI / changed-file proof
        ↓
高阶模型：源码复核 / closure / STOP
```

---

## 2. Product North Star

```text
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
CURRENT_PRODUCT_ROUTE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1

PRODUCT_TARGET=
Multiple Direct-capable Relay candidates may be discovered by one Child.
Selection is deterministic and quality-aware, but does not introduce proactive roaming or dynamic load balancing.

POLICY=
PRIMARY_RANKING=RSSI
RSSI_EQUIVALENT_BAND_DB=3
TIE_BREAK=STABLE_CHILD_RELAY_SHA256
ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true
PROACTIVE_ROAMING=false
DYNAMIC_LOAD_BALANCING=false
RESELECT_ONLY_AFTER_EXISTING_RELAY_FAILURE_TO_DISCOVERY=true
```

当前不得进入：

```text
PRODUCTION_BOARD_FLASH
PRODUCTION_T1_MUTATION
PR469_REPAIR_OR_MERGE
GATEWAY_SELECTION_PHYSICAL_ACCEPTANCE
NEW_EXACT_ARTIFACT_BUILD
PROACTIVE_RELAY_ROAMING
DYNAMIC_LOAD_BALANCING
OPTION_C_DURABLE_EVERY_SAMPLE_ARCHITECTURE
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant

FRESH_MAIN_AT_HANDOFF=
3b4a75b039a8d5d9572b4a8f7cfb1e580e7f3476

FRESH_MAIN_TREE_AT_HANDOFF=
f19701fb432f76d6913fed38891b8cbeedeb124f

MAIN_REQUIRES_FRESH_READONLY_REBIND=true
```

Important: current main does **not** contain
`firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h`.
The production product-core fork is therefore not to be sourced from main.

### 3.2 Production successor source authority

```text
PRODUCTION_SUCCESSOR_BRANCH=
feature/n3w-production-telemetry-bridge-20260921

PRODUCTION_SUCCESSOR_SOURCE_HEAD=
c1b3d9d016d06c21c9ff7070c0043163739565ca

PRODUCTION_SUCCESSOR_SOURCE_TREE=
0c857fb0f830239717a2e937d176903a6acae8ac

PRODUCTION_SUCCESSOR_MERGED=false
PRODUCTION_SUCCESSOR_DEPLOYED=false
```

This is the frozen source base for Gateway Selection V1 SOURCE_REPAIR.

The product-core runtime header blob on this branch at handoff is:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h
BLOB_SHA=a0b3fdef8df0ef88056ae053e6ef0af9a0d78a04
```

### 3.3 Gateway Selection V1 design authority

```text
SOURCE_DESIGN_BRANCH=
docs/n3w-production-multi-relay-gateway-selection-v1-source-design-20260922

SOURCE_DESIGN_HEAD=
1f628983820646ed53157cdd77d6ba39b9d5de86

SOURCE_DESIGN_TREE=
acf4f0bef9aabe8a32c7ad1bef2312f440a0a816

SOURCE_DESIGN_DOC=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260922.md

SOURCE_DESIGN_REVIEW=PASS_AFTER_DOC_CORRECTION
READY_FOR_GATEWAY_SELECTION_V1_SOURCE_REPAIR=true
AUTO_EXECUTE_SOURCE_REPAIR=false
```

The design branch is documentation-only and does not contain the production product-core fork.
Do not use it as the source-repair code base.

### 3.4 Frozen PR #437 / role-symmetry physical authority

```text
PR437_SOURCE_HEAD=
4270f24a92a87dd5239d781ebba624c2f34b7fc2

PR437_SOURCE_TREE=
a2f445bf2ea60ba9994a7a467f6492975d399c4f

PR437_ARTIFACT_ID=10619047221
PR437_ARTIFACT_ZIP_SHA256=
33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895

ROLE_SWAP_ACCEPTANCE_BRANCH=
exec/n3w-pr437-board-a-same-artifact-role-swap-20260922

ROLE_SWAP_ACCEPTANCE_HEAD=
61fc6537fa5b856e8797d21af0c40b2159176981

ROLE_SWAP_ACCEPTANCE_DOC=
docs/development/N3W_PR437_A_B_RELAY_ROLE_SWAP_PHYSICAL_ACCEPTANCE_CLOSURE_20260922.md
```

### 3.5 Existing production exact artifact

```text
PRODUCTION_SUCCESSOR_EXACT_ARTIFACT_ID=10644667734
PRODUCTION_SUCCESSOR_EXACT_ARTIFACT_SOURCE=c1b3d9d016d06c21c9ff7070c0043163739565ca
PRODUCTION_SUCCESSOR_EXACT_ARTIFACT_DEPLOYED=false
```

Once Gateway Selection V1 changes product source, this old exact artifact is **not** interchangeable with the new source and must not be used for later Gateway Selection physical acceptance. A fresh exact artifact is a later gate.

---

## 4. Current Live Baseline

Latest physical evidence at this handoff:

```text
T1_MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
MANAGER_STARTED_AT=2026-09-14T02:46:17.376354998Z

BOARD_A_LAST_PROVEN_SOURCE=direct
BOARD_A_POWER_SOURCE=battery
BOARD_A_BOOT_SESSION_SHA256=
51382692150b4a9feb6f49587fa24825b55036723b1aa5fc67a82a82201a56b1

BOARD_B_LAST_PROVEN_SOURCE=direct
BOARD_B_BOOT_SESSION_SHA256=
45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

These live values are historical-at-handoff evidence only. SOURCE_REPAIR does not require T1 or Board access.
Do not perform physical rebind unless a later physical gate explicitly needs it.

---

## 5. Proven Current Facts

### 5.1 A/B Relay role interchangeability

```text
A_AS_GATEWAY_B_AS_CHILD=HISTORICALLY_PROVEN

B_AS_GATEWAY_A_AS_CHILD_DIRECT_TO_RELAY=PASS
B_AS_GATEWAY_A_AS_CHILD_RELAY_CONTINUITY_600S=PASS
B_AS_GATEWAY_A_AS_CHILD_RELAY_TO_DIRECT=PASS
B_AS_GATEWAY_A_AS_CHILD_SAME_BOOT_ROUND_TRIP=PASS

A_B_RELAY_ROLE_INTERCHANGEABILITY=
PHYSICALLY_PROVEN_FOR_CURRENT_PR437_ARTIFACT
```

Reversed-role measured evidence:

```text
DIRECT_TO_RELAY_MOVE_START_TO_FIRST_RELAY_MS=47144
DIRECT_TO_RELAY_MANAGER_VISIBLE_GAP_MS=27652
DIRECT_TO_RELAY_MISSING_SEQUENCE_COUNT=2
DIRECT_TO_RELAY_MISSING_SEQUENCE_RANGE=179-180

RELAY_600S_EXPECTED_ROWS=121
RELAY_600S_ACCEPTED_ROWS=121
RELAY_600S_MISSING_SEQUENCE_COUNT=0
RELAY_600S_MAX_MANAGER_INTERARRIVAL_SECONDS=31.542

RELAY_TO_DIRECT_MOVE_START_TO_FIRST_DIRECT_MS=65835
RELAY_TO_DIRECT_MANAGER_VISIBLE_GAP_MS=17252
RELAY_TO_DIRECT_MISSING_SEQUENCE_COUNT=0
```

### 5.2 Reliability boundary remains unchanged

```text
OPTION_B_CONTRACT=ACTIVE
DIRECT_TO_RELAY_BOUNDARY_ZERO_LOSS=NOT_GUARANTEED
END_TO_END_EVERY_SAMPLE_DELIVERY=false
RELAY_STEADY_STATE_ZERO_MISSING_PHYSICAL_EVIDENCE=PASS
RELAY_TO_DIRECT_ZERO_MISSING_PHYSICAL_EVIDENCE=PASS
```

### 5.3 Gateway Selection V1 design is implementation-ready

```text
CANDIDATE_WINDOW_MS=6500
CANDIDATE_DEDUP_KEY=relay_node_id
CANDIDATE_RSSI_UPDATE_RULE=ARITHMETIC_MEAN
RSSI_EQUIVALENT_BAND_DB=3

STABLE_HASH_PRIMITIVE=SHA-256
STABLE_HASH_DOMAIN=N3W-GWSEL-V1

ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true
PROACTIVE_ROAMING=false
DYNAMIC_LOAD_BALANCING=false
ACTIVE_RELAY_FAILURE_RESELECTION=true

SOURCE_DESIGN_REVIEW=PASS_AFTER_DOC_CORRECTION
```

### 5.4 Source-branch topology matters

Direct GitHub evidence at handoff:

```text
greenhouse_n3w_product_core_ON_MAIN=false
greenhouse_n3w_product_core_ON_DESIGN_BRANCH=false
greenhouse_n3w_product_core_ON_PRODUCTION_SUCCESSOR=true

SOURCE_REPAIR_BRANCH_EXISTS=false
```

Therefore the later source-repair branch must be created from exact production successor
`c1b3d9d...`, not from main/design branch.

---

## 6. Current Root Cause / Blockers

### Blocker A — Multi-Relay selection is not implemented in production source

```text
ROOT_CAUSE=
Current production runtime accepts the first admissible discovery and immediately starts Challenge,
so later Relay candidates cannot participate in deterministic selection.

SOURCE_DEFECT_PROVEN=true
SOURCE_REPAIR_EXECUTED=false
```

### Blocker B — RSSI is captured by driver but dropped before runtime

```text
DRIVER_RSSI_CAPTURE=PASS
COMPONENT_RX_RING_RSSI_RETENTION=false
RUNTIME_RSSI_AVAILABLE=false
SOURCE_REPAIR_REQUIRED=true
```

### Blocker C — Future three-node physical selection remains unproven

```text
A_B_ROLE_INTERCHANGEABILITY=PASS
THREE_NODE_GATEWAY_SELECTION_PHYSICAL_ACCEPTANCE=NOT_EXECUTED
CURRENT_GATE_FOR_PHYSICAL_ACCEPTANCE=false
```

The physical blocker is downstream of source repair and exact-artifact validation; it is not a reason to access boards now.

---

## 7. Closed / Forbidden Routes

Unless new direct counter-evidence appears, do not re-enter:

```text
KF096_REOPEN=CLOSED:PR437 physical route and reverse-role physical route passed

MODIFY_FROZEN_LAB_COMPONENT=
FORBIDDEN:greenhouse_n3w_core remains frozen PR437 lab authority

MODIFY_PHASE4_OR_KF089_TESTS_FOR_PRODUCTION_SELECTION=
FORBIDDEN:those suites bind the frozen lab component, not greenhouse_n3w_product_core

PROACTIVE_RELAY_ROAMING=
FORBIDDEN:explicit product-policy decision

DYNAMIC_LOAD_BALANCING=
FORBIDDEN:explicit product-policy decision

FIRST_ADVERTISEMENT_ALWAYS_WINS=
SUPERSEDED_BY_GATEWAY_SELECTION_V1

PR469_REPAIR_MERGE_OR_DEPLOY=
OUT_OF_SCOPE

BOARD_A_OR_BOARD_B_FLASH=
OUT_OF_SCOPE

T1_MANAGER_BROKER_DYNSEC_MUTATION=
OUT_OF_SCOPE

USE_OLD_PRODUCTION_ARTIFACT_AFTER_SOURCE_CHANGE=
FORBIDDEN:new source requires a new exact artifact
```

---

## 8. Authorization Ledger

### 8.1 Historical Board A same-artifact write

```text
AUTHORIZATION=N3W_PR437_BOARD_A_SAME_ARTIFACT_WRITE
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NOT_APPLICABLE
```

### 8.2 Reverse-role physical route

```text
AUTHORIZATION=N3W_PR437_BOARD_A_SAME_BOOT_DIRECT_TO_RELAY_ROLE_SWAP_20260922_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false

AUTHORIZATION=N3W_PR437_BOARD_A_RELAY_CONTINUITY_600S_20260922_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false

AUTHORIZATION=N3W_PR437_BOARD_A_SAME_BOOT_RELAY_TO_DIRECT_FAILBACK_20260922_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

### 8.3 Proposed next source-repair authorization

```text
PROPOSED_AUTHORIZATION=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_20260922_01

GRANTED=false
READY_FOR_NEW_AUTHORIZATION=true
```

The source-design PASS and this handoff do not grant SOURCE_REPAIR mutation authority.

---

## 9. Rollback Authority

The next gate mutates only a new Git source branch. It does not mutate live firmware/T1 state.

```text
ROLLBACK_BASELINE=
c1b3d9d016d06c21c9ff7070c0043163739565ca

FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
ROLLBACK_AUTHORITY_PATH_OR_ID=exact Git commit above

LIVE_RUNTIME_ROLLBACK=NOT_APPLICABLE
BOARD_ROLLBACK=NOT_APPLICABLE

SOURCE_BRANCH_ROLLBACK=
reset/delete source-repair branch back to exact production-successor baseline

SECOND_ATTEMPT_ALLOWED=true
CONDITION=
only inside the same frozen changed-file allowlist and design contract
```

If an implementation requires allowlist expansion or design change:

```text
ROLLBACK_INCOMPLETE=false
SOURCE_REPAIR_STOP=true
RETURN_TO_HIGH_LEVEL_MODEL=true
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_20260922_01
```

### 10.1 Purpose

Implement the reviewed Gateway Selection V1 policy in the production fork
`greenhouse_n3w_product_core`, preserving the frozen PR #437 lab component and all existing
Direct/Relay ownership, Option-B delivery, active-Relay stickiness and failback semantics.

### 10.2 Frozen inputs

```text
SOURCE_BASE_HEAD=
c1b3d9d016d06c21c9ff7070c0043163739565ca

SOURCE_BASE_TREE=
0c857fb0f830239717a2e937d176903a6acae8ac

DESIGN_HEAD=
1f628983820646ed53157cdd77d6ba39b9d5de86

DESIGN_DOC=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260922.md

ROLE_SYMMETRY_PHYSICAL_AUTHORITY=
61fc6537fa5b856e8797d21af0c40b2159176981
```

### 10.3 Source changed-file allowlist

Only:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.cpp
```

New tests:

```text
tests/n3w_production/n3w_multi_relay_gateway_selection_v1_host_test.cpp
tests/n3w_production/test_multi_relay_gateway_selection_v1_contract.py
```

New CI:

```text
.github/workflows/n3w-production-multi-relay-gateway-selection-v1-ci.yml
```

No other file may be changed without STOP + explicit allowlist expansion.

### 10.4 Required implementation

The exact design document is authoritative. At minimum the source repair must implement/prove:

```text
FIRST_ADMISSIBLE_DISCOVERY_STARTS_COLLECTION_WINDOW=true
CANDIDATE_WINDOW_MS=6500

CANDIDATE_DEDUP_KEY=relay_node_id
RSSI_PLUMBING_RX_METADATA_TO_RUNTIME=true
RSSI_AGGREGATION=ARITHMETIC_MEAN
RSSI_EQUIVALENT_BAND_DB=3
RSSI_BAND_ANCHORED_TO_STRONGEST=true

STABLE_HASH=SHA-256
STABLE_HASH_INPUT=
"N3W-GWSEL-V1" + NUL + U16BE(child_len) + child_utf8 + U16BE(relay_len) + relay_utf8
HASH_WINNER=LEXICOGRAPHICALLY_SMALLER_DIGEST
HASH_COLLISION_FINAL_TIEBREAK=relay_node_id_lexicographic

CHALLENGE_TIMEOUT_CANDIDATE_FALLBACK=true
LOCAL_RADIO_CRYPTO_FAILURE_DOES_NOT_BLINDLY_FALL_THROUGH=true
INVALID_ACCEPT_DOES_NOT_FORCE_EARLY_SWITCH=true

GATEWAY_SELECTION_BUSY_GUARDS_DIRECT_RECOVERY=true

ACTIVE_RELAY_HEALTHY_NO_RESELECTION=true
PROACTIVE_ROAMING=false
DYNAMIC_LOAD_BALANCING=false
EXISTING_RELAY_FAILURE_THRESHOLD_TO_DISCOVERY_PRESERVED=true

OPTION_B_QUEUE_ORDERING_PRESERVED=true
OPTION_B_ONE_REAL_ATTEMPT_NO_APPLICATION_RESEND_PRESERVED=true
```

### 10.5 Required regression proof

Use the source-design regression matrix as exact authority. It contains 23 required cases, including:

- single Relay;
- clear RSSI winner;
- <=3 dB stable hash;
- exact mean tie;
- hash collision fallback;
- strongest-anchored non-transitive-band guard;
- advertisement order invariance;
- repeated RSSI update;
- channel refresh;
- identity conflict;
- local Challenge failure vs candidate timeout distinction;
- invalid Accept handling;
- authenticated Accept + local state failure;
- selection-busy Direct-recovery guard;
- healthy active Relay stickiness;
- active-Relay failure reselection;
- Direct recovery preservation;
- Option-B telemetry preservation;
- A/B role symmetry;
- three-node selection;
- RSSI plumbing;
- worst-phase 6500 ms candidate-window timing.

Dedicated CI must compile the current F1.0-RC2 N3-W target against
`greenhouse_n3w_product_core`.

### 10.6 Required operations

```text
1. Fresh read-only rebind main / production successor / design authority / role-swap closure.
2. Reconfirm source-repair branch does not already exist.
3. Reconfirm frozen source files/blob identities on c1b3d9d....
4. Request exact SOURCE_REPAIR authorization if not already granted in the new chat.
5. Create new source-repair branch from exact c1b3d9d....
6. Modify only frozen source/test/CI allowlist.
7. Run production host/contract regression.
8. Compile current F1.0-RC2 N3-W target against product core.
9. Run dedicated CI and relevant existing production CI.
10. Review exact diff against design and changed-file allowlist.
11. Produce structured closure.
12. STOP.
```

### 10.7 PASS

```text
SOURCE_BASE_BINDING=PASS
CHANGED_FILE_ALLOWLIST=PASS

RSSI_PLUMBING=PASS
CANDIDATE_COLLECTION_AND_RANKING=PASS
STABLE_HASH_TIEBREAK=PASS
CANDIDATE_TIMEOUT_FALLBACK=PASS
LOCAL_FAILURE_CLASSIFICATION_PRESERVED=PASS
NO_PROACTIVE_ROAMING=PASS
NO_DYNAMIC_LOAD_BALANCING=PASS
DIRECT_RECOVERY_GUARD=PASS
OPTION_B_SEMANTICS_PRESERVED=PASS

GATEWAY_SELECTION_V1_HOST_TEST=PASS
GATEWAY_SELECTION_V1_CONTRACT_TEST=PASS
F1RC2_PRODUCTION_COMPILE=PASS
DEDICATED_GATEWAY_SELECTION_CI=PASS

FROZEN_LAB_COMPONENT_CHANGED=false
FROZEN_LAB_TESTS_CHANGED=false
BOARD_ACCESS=false
T1_MUTATION=false

N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR=PASS
READY_FOR_SOURCE_REVIEW=true
```

### 10.8 FAIL / STOP

```text
FAIL_SOURCE_BASE_DRIFT
FAIL_DESIGN_AUTHORITY_DRIFT
FAIL_SOURCE_REPAIR_BRANCH_COLLISION
FAIL_CHANGED_FILE_ALLOWLIST
FAIL_RSSI_PLUMBING
FAIL_SELECTION_POLICY
FAIL_ACTIVE_RELAY_STICKINESS
FAIL_DIRECT_RECOVERY_REGRESSION
FAIL_OPTION_B_REGRESSION
FAIL_HOST_OR_CONTRACT_TEST
FAIL_F1RC2_COMPILE
FAIL_DEDICATED_CI

STOP_ALLOWLIST_EXPANSION_REQUIRED
STOP_DESIGN_CHANGE_REQUIRED
STOP_FROZEN_LAB_BOUNDARY_VIOLATION
```

Any substantive failure returns to the high-level model. No automatic artifact build, merge, board flash or physical test.

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED after explicit SOURCE_REPAIR authorization

```text
GitHub branch creation from exact c1b3d9d...
source edits inside frozen production allowlist
new production-specific tests inside frozen test allowlist
new dedicated CI workflow inside frozen CI allowlist
host test execution
F1.0-RC2 compile
GitHub CI execution
read-only exact diff/source review
documentation/evidence updates for this gate
```

### FORBIDDEN

```text
Board USB/serial/Flash/NVS access
T1 SSH/runtime mutation
Broker/Manager/DynSec/credential/TLS mutation

greenhouse_n3w_core edits
tests/n3w_phase4/** edits
tests/n3w_kf089/** edits

production exact-artifact build
production board deployment
PR469 mutation/merge
production successor merge

dynamic load balancing
proactive Relay roaming
Option-C durable every-sample implementation
scope expansion beyond frozen allowlist
```

---

## 12. Codex DSL Execution Contract

```text
EXECUTOR=task-appropriate minimum Git/source/test/compile/CI operations
EXECUTION_METHOD=GitHub + existing build/test environment

PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
T1_ACCESS=false
APPLICATION_SERIAL_OPEN=false
FLASH_WRITE=false
NVS_MUTATION=false

SOURCE_MUTATION=true
SOURCE_MUTATION_REQUIRES_EXPLICIT_GATE_AUTHORIZATION=true
```

Terminal/operator-facing shell remains subject to the established guard:

```text
PASTE_READY_COMMANDS_CONTAIN_NO_SHELL_COMMENTS=true
OPERATOR_FACING_SET_U_FORBIDDEN=true
EXPLICIT_CHECKS_REQUIRED=true
```

---

## 13. Expected Closure

```text
=== N3W PRODUCTION MULTI-RELAY GATEWAY SELECTION V1 SOURCE REPAIR CLOSURE ===

TASK=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

FRESH_MAIN=
SOURCE_BASE_HEAD=
SOURCE_BASE_TREE=
DESIGN_HEAD=
ROLE_SWAP_PHYSICAL_AUTHORITY=

SOURCE_REPAIR_BRANCH=
SOURCE_REPAIR_HEAD=
SOURCE_REPAIR_TREE=

CHANGED_FILE_COUNT=
CHANGED_FILE_ALLOWLIST=
UNEXPECTED_CHANGED_FILES=

RSSI_PLUMBING=
CANDIDATE_WINDOW_MS=
CANDIDATE_DEDUP=
RSSI_AGGREGATION=
RSSI_EQUIVALENT_BAND=
STABLE_HASH=
TIMEOUT_FALLBACK=
LOCAL_FAILURE_CLASSIFICATION=
SELECTION_BUSY_DIRECT_RECOVERY_GUARD=
ACTIVE_RELAY_STICKINESS=
PROACTIVE_ROAMING=
DYNAMIC_LOAD_BALANCING=
OPTION_B_SEMANTICS=

HOST_TEST=
CONTRACT_TEST=
F1RC2_COMPILE=
DEDICATED_CI=
OTHER_RELEVANT_CI=

FROZEN_LAB_COMPONENT_CHANGED=
FROZEN_LAB_TESTS_CHANGED=

BOARD_ACCESS=false
T1_MUTATION=false
FLASH_WRITE=false
NVS_MUTATION=false
APPLICATION_SERIAL_OPEN=false

N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR=
READY_FOR_SOURCE_REVIEW=

NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

### PASS

```text
AUTO_EXECUTE_AFTER_PASS=false
AUTO_MERGE=false
AUTO_ARTIFACT_BUILD=false
AUTO_BOARD_FLASH=false
AUTO_PHYSICAL_TEST=false
```

Return to the high-level model for exact source review. Only after source review PASS may a separate gate bind/build a new exact production artifact.

### FAIL

```text
AUTO_REPAIR_OUTSIDE_ALLOWLIST=false
AUTO_DESIGN_CHANGE=false
AUTO_MERGE=false
AUTO_DEPLOY=false
STOP_AND_REVIEW=true
```

Implementation iterations are allowed only inside the already-frozen allowlist and reviewed design. Any required boundary expansion stops the gate.

---

## 15. KNOWN_FAILURES Updates

```text
KF092_STATUS=CLOSED_PASS
KF096_STATUS=GUARDED
KF096_REOPEN=false

OPTION_B_ZERO_LOSS_GUARANTEE=false

NEW_KNOWN_FAILURE_REQUIRED=false
```

The reverse-role run adds confirming physical evidence but does not require a new Known Failure:
Direct -> Relay transition boundary loss remains inside the already documented Option-B reliability boundary.

---

## 16. New Chat Start Prompt

```text
阅读：

docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_NEW_CHAT_HANDOFF_V1.0_20260922.md

该 handoff 位于：
branch = exec/n3w-pr437-board-a-same-artifact-role-swap-20260922

同时读取 exact historical handoff authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- feature/n3w-production-telemetry-bridge-20260921
- docs/n3w-production-multi-relay-gateway-selection-v1-source-design-20260922
- PR #471
- PR #469
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260922.md
- docs/development/N3W_PR437_A_B_RELAY_ROLE_SWAP_PHYSICAL_ACCEPTANCE_CLOSURE_20260922.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
支线任务：Production Multi-Relay Gateway Selection V1
当前任务：N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_20260922_01

必须先承认：
- A/B Relay 角色互换实机验收已经 CLOSED_PASS；
- A 作为 Child / B 作为 Gateway 的 battery same-boot Direct -> Relay -> 600 s Relay -> Direct 已完整 PASS；
- 反向 Direct -> Relay 边界缺失 seq 179-180，仍属于冻结 Option-B 边界，不重开 KF-096；
- Gateway Selection V1 source design 已 review PASS；
- source repair 尚未执行、尚未授权；
- source repair 必须从 exact production successor c1b3d9d... 建 branch，不能从 main 或 design-only branch 建；
- greenhouse_n3w_core / Phase4 / KF-089 frozen-lab boundary 不得修改。

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false

先做 fresh read-only rebind；若 authority 一致，再请求：
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_20260922_01
的明确授权。

准确、安全、高效、可验证优先。
回复尽量用直白中文，GitHub 操作分阶段执行，每一步有明确停止点。
```

---

## 17. Final Frozen State

```text
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

A_B_RELAY_ROLE_SWAP_PHYSICAL_ACCEPTANCE=CLOSED_PASS
A_B_RELAY_ROLE_INTERCHANGEABILITY=PHYSICALLY_PROVEN_FOR_CURRENT_PR437_ARTIFACT

ROLE_SWAP_ACCEPTANCE_HEAD=
61fc6537fa5b856e8797d21af0c40b2159176981

PRODUCTION_SUCCESSOR_SOURCE_HEAD=
c1b3d9d016d06c21c9ff7070c0043163739565ca

PRODUCTION_SUCCESSOR_SOURCE_TREE=
0c857fb0f830239717a2e937d176903a6acae8ac

GATEWAY_SELECTION_V1_SOURCE_DESIGN_HEAD=
1f628983820646ed53157cdd77d6ba39b9d5de86

GATEWAY_SELECTION_V1_SOURCE_DESIGN_REVIEW=PASS
GATEWAY_SELECTION_V1_SOURCE_REPAIR=NOT_EXECUTED
GATEWAY_SELECTION_V1_SOURCE_REPAIR_AUTHORIZED=false

SOURCE_REPAIR_BRANCH_EXISTS=false

NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_20260922_01

AUTO_EXECUTE_NEXT_GATE=false
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
