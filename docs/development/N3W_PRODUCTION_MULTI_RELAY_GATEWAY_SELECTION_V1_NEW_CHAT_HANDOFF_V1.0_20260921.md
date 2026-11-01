# 温室环境监测系统（ESP32-C6）
# N3-W Production Multi-Relay Gateway Selection V1
# 新会话交接文档 V1.0 — 2026-09-21

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> Formal process authority is the exact historical handoff authority at commit
> `4300890dff0ce63d5a547df21426e287d084d9ee`:
>
> - `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`
> - `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`
>
> Fresh exact repository/runtime/physical evidence overrides this handoff if later evidence proves drift.

---

## 0. 会话切换结论

本轮已经完成 production successor 的 de-harness、F1.0-RC2 整机集成、真实 telemetry bridge、完整编译、binary de-harness proof、exact artifact build/binding，以及 main 上的 durable progress alignment。

随后启动 Board B production 写前只读 preflight 准备，并在 PR #469 中建立新的 production-specific preflight executor。PR #469 的 dedicated preflight CI 已 PASS；Public repository safety CI 因测试文件中两处 synthetic MAC-looking fixture 被安全扫描拒绝而 FAIL。本轮不修复，不访问实板。

本轮最后完成了两个新的产品场景源码复核：

1. A/B Relay 角色交换：当前源码结构是对称的，任意 Direct+MQTT 节点可成为 Relay，但尚缺反向实机验收。
2. A/B 同时 Direct、C 需要 Relay：当前实现没有 Gateway 择优，实际是“先收到并成功握手的合法 Relay 胜出”。

用户已经确认下一版 Gateway Selection 方向：

- 不做动态负载均衡；
- 不做健康 Gateway 间的主动漫游；
- 使用 bounded candidate window 收集候选；
- RSSI 明显更强者优先；
- RSSI 差值 <= 3 dB 时按 `HASH(C.NODE_ID || RELAY.NODE_ID)` 做稳定决胜；
- hash 极端碰撞时用 Relay NODE_ID 字典序做最终确定性 tie-break；
- 一旦 active Relay 健康，保持 sticky，不因 RSSI 波动切换；
- active Relay 真实失效后才回到 Discovery 重新选择。

```text
CURRENT_STAGE=N3W_PRODUCTION_MULTI_RELAY_ROLE_AND_GATEWAY_SELECTION_REVIEW
CURRENT_STOP_POINT=GATEWAY_SELECTION_V1_DIRECTION_APPROVED; SOURCE_DESIGN_NOT_YET_FROZEN
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不重新复盘 KF-096 或 PR #437 全历史，只从 Gateway Selection V1 的 source-design gate 开始，同时保留 PR #469 的独立 CI/content-safety blocker。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 N3-W 产品路线与单射频边界；
- 维护 production successor / exact artifact / PR #469 authority；
- 把用户已批准的多 Gateway 规则冻结成最小源码合同；
- 明确 candidate window、RSSI 数据路径、stable-hash primitive、候选更新策略与 failure/reselection 行为；
- 保持“不主动漫游、不动态负载均衡”的稳定性边界；
- 设计 changed-file allowlist、回归测试和后续物理验收；
- 根据 Codex closure 做 PASS / FAIL / STOP 分类。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL contract；
- fresh rebind exact repository/source/PR state；
- 只读检查当前 runtime / tests / protocol；
- 如 gate 明确允许，仅提交 design/contract 文档；
- 第一处 substantive mismatch 后 fail-closed STOP；
- 不自行扩大到源码修复、CI repair、Board 操作或物理测试。

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

### 1.4 标准交互循环

```text
高阶模型：source design / exact contract
        ↓
Codex：fresh read-only source review / bounded docs archive
        ↓
高阶模型：复核 design closure
        ↓
下一门才允许 source repair
```

---

## 2. Product North Star

当前产品路线：

```text
N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

最终产品目标：

```text
同一 production firmware 可用于 A/B/C 等节点；
任意具备 Direct+MQTT 的节点可作为单跳 Relay Gateway；
失去 Direct 的节点能在多个合法 Relay 中稳定、确定地选择一个 Gateway；
Gateway 健康时不主动漫游；
Gateway 失效时重新 Discovery / selection；
保持 Direct -> Relay -> Direct 单射频安全、Option-B latest-state delivery contract、Manager canonical telemetry。
```

当前明确不进入：

```text
DYNAMIC_LOAD_BALANCING
PROACTIVE_RSSI_ROAMING
MULTI_HOP_MESH
RELAY_TO_RELAY_FORWARDING
OPTION_C_EVERY_SAMPLE_DURABLE_DELIVERY
FROZEN_PR437_LAB_SOURCE_MODIFICATION
BOARD_FLASH_WITHOUT_NEW_EXPLICIT_PHYSICAL_AUTHORIZATION
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN=
ac0707e9cde2f6f0e3db6d793b3f86fa8030bd91

MAIN_TREE=
5585c54cd126df56b5a8053c8c751050c139413e
```

Main current-state authority:

```text
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/N3W_PRODUCTION_DEHARNESS_AND_EXACT_ARTIFACT_PROGRESS_ALIGNMENT_20260921.md
```

### 3.2 Current production successor source

```text
PRODUCTION_SUCCESSOR_MERGED=false

SOURCE_BRANCH=
feature/n3w-production-telemetry-bridge-20260921

SOURCE_HEAD=
c1b3d9d016d06c21c9ff7070c0043163739565ca

SOURCE_TREE=
0c857fb0f830239717a2e937d176903a6acae8ac
```

Independent product core:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/
```

Frozen PR #437 lab component remains separate and must not be modified:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/
firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
```

### 3.3 Exact production artifact

```text
EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS

ARTIFACT_ID=10644667734
ARTIFACT_NAME=n3w-production-f1rc2-c1b3d9d-exact-source

GITHUB_ARTIFACT_SHA256=
02fbe69f78511f33dec150dee635925dd4decf81048de3adfc6db8af4acc7a72

RELEASE_BUNDLE=
n3w-production-f1rc2-c1b3d9d-exact-source.zip

RELEASE_BUNDLE_SHA256=
93d830368b74e0dae904a9f5c4450378694575c68b917e749b480455662ff065

FIRMWARE_BIN_SHA256=
8bcd89aaf0be64188f8f98a64795fe78d573ae82dd2dd360c7ff459f80e58efa

FIRMWARE_FACTORY_BIN_SHA256=
434a3996ea8dc74c4a356f54d8a9405202f17b500680a66f5d49a2089cf67774

ARTIFACT_EXPIRES_AT=2026-10-21T14:34:41Z
```

Same-source rebuilds are not interchangeable with this artifact.

### 3.4 Board B preflight PR

```text
PR469_STATE=OPEN
PR469_MERGED=false
PR469_MERGEABLE=true

PR469_HEAD=
d9f6a4d33b8354053e736c71e887b176236a79d9

PR469_BASE=
ac0707e9cde2f6f0e3db6d793b3f86fa8030bd91

PR469_DEDICATED_PREFLIGHT_CI_RUN=35616545967
PR469_DEDICATED_PREFLIGHT_CI=PASS

PR469_PUBLIC_REPOSITORY_SAFETY_RUN=35616545975
PR469_PUBLIC_REPOSITORY_SAFETY=FAIL
```

Public-safety failure evidence:

```text
FAIL_CLASS=CI_CONTENT_SAFETY
FAILED_STEP=Scan tracked files without echoing matches
REASON=synthetic MAC-looking literals in test_executor.py
LOCATIONS=lines 124 and 194 at observed PR469 HEAD
PRODUCT_DEFECT_PROVEN=false
PREFLIGHT_LOGIC_DEFECT_PROVEN=false
```

### 3.5 Currently deployed Board B

```text
CURRENTLY_DEPLOYED_BOARD_B_SOURCE=
4270f24a92a87dd5239d781ebba624c2f34b7fc2

CURRENTLY_DEPLOYED_BOARD_B_ARTIFACT_ID=
10619047221

CURRENTLY_DEPLOYED_BOARD_B_APPLICATION_SHA256=
b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
```

Production successor has not been flashed.

---

## 4. Current Live Baseline

Current live physical/runtime facts are historical unless fresh-read in the next physical gate.

```text
PRODUCTION_SUCCESSOR_BOARD_A_DEPLOYMENT=NOT_EXECUTED
PRODUCTION_SUCCESSOR_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PRODUCTION_SUCCESSOR_PHYSICAL_ACCEPTANCE=NOT_EXECUTED

BOARD_ACCESS=false
USB_ACCESS=false
APPLICATION_SERIAL_OPEN=false
FLASH_WRITE=false
NVS_MUTATION=false
RF_EXECUTION=false
T1_MUTATION=false
```

Historical role convention:

```text
BOARD_A_DEFAULT_ROLE=STATIONARY_RELAY_GATEWAY
BOARD_B_DEFAULT_ROLE=PRIMARY_DEVICE_UNDER_TEST
```

This is a test convention, not a product role restriction.

Current Board A firmware/source identity is not freshly rebound in this handoff and must not be guessed.

```text
BOARD_A_CURRENT_FIRMWARE_REQUIRES_FRESH_READONLY_REBIND=true
BOARD_A_CURRENT_POWER_LOCATION_REQUIRES_FRESH_REBIND=true
BOARD_B_CURRENT_POWER_LOCATION_REQUIRES_FRESH_REBIND=true
```

---

## 5. Proven Current Facts

### 5.1 Role symmetry in current production source

The current product runtime is not hard-coded as “A Relay / B Child”.

In the production component loop:

```text
runtime_.set_relay_capable(mqtt_connected())
```

A node that is in Direct and has MQTT is therefore relay-capable.

The same runtime:

- broadcasts `SimpleRelayDiscovery`;
- accepts authenticated Child Challenge while `DIRECT && relay_capable`;
- installs encrypted peers;
- tracks up to `max_relay_children=8`;
- forwards Child compact telemetry to Manager ingress;
- can itself become `RELAY_ACTIVE` when Direct is lost and another Relay is authenticated.

Therefore:

```text
A_CAN_RELAY_B=SUPPORTED_BY_SOURCE
B_CAN_RELAY_A=SUPPORTED_BY_SOURCE
ROLE_SYMMETRY_PHYSICAL_ACCEPTANCE=NOT_YET_PROVEN
```

### 5.2 Current multi-Gateway behavior

Current `handle_discovery_` accepts a valid Relay only when:

```text
path == DISCOVERY
pending_challenge == false
packet valid
peer_trust_generation matches
relay_node_id != self
packet channel == receive channel
```

After the first accepted Discovery, it immediately sends a Challenge and creates `pending_challenge_`. Other Discovery packets are rejected while that challenge is pending.

After Accept:

```text
active_relay_ = selected relay
```

Therefore current effective behavior is:

```text
GATEWAY_SELECTION_CURRENT=
FIRST_VALID_DISCOVERY_THAT_COMPLETES_HANDSHAKE
```

There is no candidate ranking by:

```text
RSSI
load
relay child count
latency
historical success rate
fixed priority
NODE_ID order
```

### 5.3 RSSI plumbing gap

The ESP-NOW driver captures receive metadata including:

```text
metadata.rssi_dbm
metadata.channel
```

but current `SimpleProductRuntime::on_radio_receive(...)` receives source/data/size/channel only. RSSI does not participate in current Gateway selection.

```text
RX_RSSI_AVAILABLE_AT_DRIVER=true
RX_RSSI_USED_FOR_GATEWAY_SELECTION=false
```

### 5.4 User-approved Gateway Selection V1 direction

```text
DYNAMIC_LOAD_BALANCING=false
PROACTIVE_ROAMING=false

RSSI_EQUIVALENT_BAND_DB=3

PRIMARY_SELECTION=RSSI
EQUAL_QUALITY_TIE_BREAK=STABLE_HASH_OF_CHILD_AND_RELAY_NODE_ID
FINAL_HASH_COLLISION_TIE_BREAK=RELAY_NODE_ID_LEXICOGRAPHIC

ACTIVE_RELAY_HEALTHY=STICKY_NO_SWITCH
ACTIVE_RELAY_FAILED=RETURN_TO_DISCOVERY_AND_RESELECT
```

The exact candidate-window duration, candidate RSSI update rule, hash primitive/serialization, and selected-candidate handshake-failure behavior are intentionally left for the next source-design gate to freeze from exact source constraints.

### 5.5 Production artifact and de-harness

```text
PRODUCT_CORE_DEHARNESS=PASS
F1RC2_TARGET_CONFIG=PASS
REAL_SENSOR_TELEMETRY_BRIDGE=PASS
FULL_FIRMWARE_COMPILE=PASS
BINARY_DEHARNESS_PROOF=PASS
EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS

PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false
```

---

## 6. Current Root Cause / Blockers

### Blocker A — Multi-Gateway selection is first-arrival driven

```text
ROOT_CAUSE=
Discovery immediately challenges the first accepted Relay and locks out other candidates through pending_challenge.

PROVEN_BY=
current production source c1b3d9d... / n3w_simple_product_runtime.cpp

SOURCE_DEFECT_PROVEN=true
RUNTIME_FAILURE_PROVEN=false
```

This is a product-policy gap, not evidence that current single-Relay operation is broken.

### Blocker B — RSSI exists below runtime but is not part of selection

```text
ROOT_CAUSE=
ESP-NOW RX metadata captures RSSI, but runtime discovery selection receives no RSSI input.

SOURCE_DEFECT_PROVEN=true
PHYSICAL_FAILURE_PROVEN=false
```

### Blocker C — Role symmetry lacks reverse physical acceptance

```text
SOURCE_ROLE_SYMMETRY=SUPPORTED
A_AS_RELAY_B_AS_CHILD=HISTORICALLY_PROVEN
B_AS_RELAY_A_AS_CHILD=NOT_YET_FORMALLY_PROVEN
```

This is a physical acceptance gap, not a proven source defect.

### Blocker D — PR #469 public repository safety failure

```text
PR469_DEDICATED_PREFLIGHT_CI=PASS
PR469_PUBLIC_REPOSITORY_SAFETY=FAIL

FAIL_CLASS=CI_CONTENT_SAFETY
CAUSE=synthetic test fixtures resemble MAC addresses
PRODUCT_DEFECT_PROVEN=false
BOARD_PREFLIGHT_EXECUTED=false
```

This blocks merging PR #469 but does not block the next host/source-only Gateway Selection design gate.

---

## 7. Closed / Forbidden Routes

Unless new direct counter-evidence appears:

```text
DYNAMIC_RELAY_LOAD_BALANCING=FORBIDDEN_CURRENT_SCOPE
PROACTIVE_RSSI_ROAMING=FORBIDDEN_CURRENT_SCOPE
HEALTHY_ACTIVE_RELAY_RESELECTION=FORBIDDEN_CURRENT_SCOPE

MULTI_HOP_ESPNOW_MESH=FORBIDDEN
RELAY_TO_RELAY_FORWARDING=FORBIDDEN

FROZEN_PR437_COMPONENT_MODIFICATION=FORBIDDEN
FROZEN_PR437_PHASE4_GENERIC_MODIFICATION=FORBIDDEN

HISTORICAL_BOARD_B_IDENTITY_HASH_REUSE=FORBIDDEN
HISTORICAL_OPERATOR_IDENTITY_OVERRIDE_REUSE=FORBIDDEN

SAME_SOURCE_REBUILD_AS_BOUND_ARTIFACT_REPLACEMENT=FORBIDDEN

BOARD_FLASH_WITHOUT_FRESH_TARGET_PREFLIGHT_AND_EXPLICIT_AUTHORIZATION=FORBIDDEN
AUTO_PHYSICAL_TEST_AFTER_SOURCE_CI=FORBIDDEN
```

Do not reinterpret old “Board A = Relay” test convention as a product role constraint.

---

## 8. Authorization Ledger

### Historical PR #437 Board B write authorization

```text
AUTHORIZATION=N3W_KF096_PR437_BOARD_B_OPERATOR_CONFIRMED_DIRECT_WRITE_20260919_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

### Current production Board B preflight

```text
AUTHORIZATION=N3W_PRODUCTION_BOARD_B_WRITE_TARGET_PREFLIGHT_20260921_01
BOARD_ACCESS_EXECUTED=false
FLASH_WRITE=false
RESULT=EXECUTOR_PREPARED; PR469_CI_PARTIAL_PASS_WITH_SAFETY_FAILURE
REPLAY_PERMITTED=NOT_APPLICABLE:physical execution not started
```

### Gateway Selection V1 source-design gate

User explicitly approved the proposed policy and requested execution in the next chat.

```text
AUTHORIZATION=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01
GRANTED=true
CLAIMED=false
CONSUMED=false
SCOPE=HOST/GITHUB SOURCE DESIGN ONLY
BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
```

This does not authorize product-source implementation, board flashing, RF testing, or PR #469 repair beyond the design gate.

---

## 9. Rollback Authority

The next ONE gate is source-design only.

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:SOURCE_DESIGN_GATE
LIVE_RUNTIME_MUTATION=false
BOARD_MUTATION=false
PRODUCT_SOURCE_MUTATION=false
```

A bounded design-document commit on a dedicated branch may be abandoned if incorrect.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01
```

### 10.1 Purpose

Freeze an implementation-ready Gateway Selection V1 contract from the exact production source without modifying product code. The design must preserve existing single-radio recovery and Relay stability while replacing first-arrival selection with bounded RSSI-based candidate selection and deterministic equal-RSSI tie breaking.

### 10.2 Frozen inputs

```text
SOURCE_HEAD=c1b3d9d016d06c21c9ff7070c0043163739565ca
SOURCE_TREE=0c857fb0f830239717a2e937d176903a6acae8ac

RSSI_EQUIVALENT_BAND_DB=3
DYNAMIC_LOAD_BALANCING=false
PROACTIVE_ROAMING=false
ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true

EQUAL_QUALITY_TIE_BREAK=
HASH(CHILD_NODE_ID || RELAY_NODE_ID)

FINAL_COLLISION_TIE_BREAK=
RELAY_NODE_ID_LEXICOGRAPHIC
```

### 10.3 Required proof / operations

```text
1. Fresh rebind main, production successor source, PR469, and current state docs.
2. Read exact discovery / challenge / accept / RX metadata / recovery code.
3. Freeze candidate collection state and lifecycle.
4. Freeze exact candidate-window duration with latency justification.
5. Freeze how repeated advertisements update candidate RSSI.
6. Freeze exact stable-hash primitive and byte/string serialization.
7. Freeze candidate identity key and dedup semantics.
8. Freeze behavior when selected candidate Challenge/Accept fails or times out.
9. Prove healthy active Relay cannot be replaced solely by better RSSI.
10. Prove active Relay failure still returns to existing Discovery/reselection path.
11. Define changed-file allowlist for the later source-repair gate.
12. Define unit/source-contract regression matrix including:
    - one Relay;
    - two Relays, clear RSSI winner;
    - two Relays within 3 dB;
    - exact RSSI tie;
    - stable deterministic result across advertisement order;
    - selected Relay handshake failure;
    - active Relay healthy while stronger candidate appears;
    - active Relay failure then reselection;
    - A/B role symmetry.
13. Archive the frozen design to GitHub on a dedicated design/docs branch.
14. STOP. Do not modify production source.
```

### 10.4 PASS

```text
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN=PASS

CANDIDATE_WINDOW_FROZEN=true
RSSI_SELECTION_FROZEN=true
STABLE_HASH_TIE_BREAK_FROZEN=true
NO_PROACTIVE_ROAMING_PROVEN_BY_DESIGN=true
FAILURE_RESELECTION_FROZEN=true
SOURCE_REPAIR_ALLOWLIST_FROZEN=true
REGRESSION_MATRIX_FROZEN=true

READY_FOR_GATEWAY_SELECTION_V1_SOURCE_REPAIR=true
```

### 10.5 FAIL

Examples:

```text
FAIL_SOURCE_AUTHORITY_DRIFT
FAIL_CANDIDATE_WINDOW_CONFLICTS_WITH_SINGLE_RADIO_RECOVERY
FAIL_NO_SAFE_RSSI_PLUMBING
FAIL_TIE_BREAK_NOT_DETERMINISTIC
FAIL_DESIGN_INTRODUCES_PROACTIVE_ROAMING
FAIL_EXISTING_RELAY_FAILURE_PATH_BROKEN
```

Any substantive failure:

```text
READY_FOR_GATEWAY_SELECTION_V1_SOURCE_REPAIR=false
AUTO_REPAIR=false
STOP=true
```

---

## 11. Hard Allowed / Forbidden Scope

Default:

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- GitHub fresh read-only source/PR/CI inspection
- exact source comparison
- current protocol/test inspection
- bounded reasoning and source-design work
- creation of one public-safe Gateway Selection V1 design document on a dedicated branch
- source/test changed-file allowlist definition
- no-op local/static analysis as needed
```

### FORBIDDEN

```text
- production C++/Python/YAML source changes
- PR469 repair
- PR469 merge
- PR463-PR467 merge
- Board A/B/C USB/serial access
- ROM/esptool board access
- Flash/NVS write or erase
- RF execution
- T1/Broker/Manager/DynSec mutation
- active Gateway roaming implementation
- dynamic load balancing
- multi-hop behavior
- automatically entering SOURCE_REPAIR after design PASS
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_REPOSITORY_DOC_WRITE=true
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required.

Mechanically compile this DSL into the minimum necessary commands
using already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair PR469.
Do not modify production source.
Do not access any board.
Do not retry a substantive failure.
Do not enter SOURCE_REPAIR.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

EXECUTION_ID=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01

AUTHORIZATION_GRANTED=true
AUTHORIZATION_SCOPE=HOST/GITHUB SOURCE DESIGN ONLY

============================================================
1. FROZEN INPUTS
============================================================

REPOSITORY=chrenguo-stack/HomeAssistant
EXPECTED_MAIN=ac0707e9cde2f6f0e3db6d793b3f86fa8030bd91

PRODUCTION_SOURCE=
c1b3d9d016d06c21c9ff7070c0043163739565ca

PRODUCTION_TREE=
0c857fb0f830239717a2e937d176903a6acae8ac

RSSI_EQUIVALENT_BAND_DB=3
DYNAMIC_LOAD_BALANCING=false
PROACTIVE_ROAMING=false
ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true

============================================================
2. FRESH REBIND
============================================================

Read current main.
Read current production successor branch/head/tree.
Read PR469 state and CI.
Read:
- N3W_CURRENT_STATE.md
- N3W_CURRENT_STATE_INDEX.md
- this handoff

If material source authority drift is found:
  output FAIL_SOURCE_AUTHORITY_DRIFT
  STOP

============================================================
3. EXACT SOURCE REVIEW
============================================================

Read exact production source for:
- SimpleProductRuntime discovery/challenge/accept
- SimpleProductComponent RX buffering/drain
- EspNowDriver RX metadata
- LocalPathController Relay failure/recovery
- existing tests around Relay discovery and selection
- protocol one-hop rules

Confirm:
- current first-valid behavior;
- RSSI available at driver;
- RSSI absent from current selection;
- active Relay failure exit path;
- no current proactive roaming.

============================================================
4. FREEZE V1 SELECTION CONTRACT
============================================================

Define exactly:
- candidate structure;
- candidate dedup key;
- bounded collection-window duration;
- start/end conditions;
- RSSI update rule;
- >3 dB winner rule;
- <=3 dB equivalent rule;
- exact stable hash primitive;
- exact serialization of child and relay NODE_ID into hash input;
- final collision tie-break;
- selected-candidate Challenge/Accept timeout/failure handling;
- transition back to candidate collection or Discovery;
- active Relay stickiness;
- active Relay failure/reselection boundary.

The design must not use dynamic load information.

============================================================
5. STABILITY PROOF
============================================================

Prove by source/state-machine reasoning that:
- a healthy active Relay is not replaced because another Relay has stronger RSSI;
- Relay selection runs only while selecting/reselecting in Discovery;
- existing Direct recovery probe behavior remains independent;
- existing Option-B telemetry queue semantics remain unchanged;
- no second active Relay is introduced;
- no multi-hop behavior is introduced.

============================================================
6. SOURCE-REPAIR PLAN
============================================================

Freeze:
- exact changed-file allowlist;
- exact tests to add/modify;
- backward-compatibility expectations;
- A/B role-symmetry regression cases;
- three-node A/B Direct + C Relay candidate tests;
- physical acceptance plan outline for later gates.

Do not edit those product files in this gate.

============================================================
7. ARCHIVE
============================================================

Create/update one public-safe design document under docs/development/.
Commit only the design document on a dedicated docs/design branch.

Do not modify CURRENT_STATE in this gate unless the high-level model
explicitly asks after reviewing the closure.

============================================================
8. HARD STOP
============================================================

Return the exact structured closure.
Do not enter SOURCE_REPAIR.
Do not repair PR469.
Do not access boards.
```

---

## 13. Expected Closure

```text
=== N3W PRODUCTION MULTI RELAY GATEWAY SELECTION V1 SOURCE DESIGN CLOSURE ===

EXECUTION_ID=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01

AUTHORIZATION_GRANTED=
SOURCE_HEAD=
SOURCE_TREE=
SOURCE_REBIND=

CURRENT_SELECTION_CLASSIFICATION=
RX_RSSI_AVAILABLE=
RX_RSSI_CURRENTLY_USED_FOR_SELECTION=

CANDIDATE_WINDOW_MS=
CANDIDATE_DEDUP_KEY=
CANDIDATE_RSSI_UPDATE_RULE=

RSSI_EQUIVALENT_BAND_DB=3
CLEAR_WINNER_RULE=
EQUAL_QUALITY_RULE=
STABLE_HASH_PRIMITIVE=
STABLE_HASH_INPUT_ENCODING=
FINAL_COLLISION_RULE=

ACTIVE_RELAY_STICKY_WHILE_HEALTHY=
PROACTIVE_ROAMING=
DYNAMIC_LOAD_BALANCING=
ACTIVE_RELAY_FAILURE_RESELECTION=

CHALLENGE_FAILURE_BEHAVIOR=
CHALLENGE_TIMEOUT_BEHAVIOR=

CHANGED_FILE_ALLOWLIST=
REGRESSION_TEST_MATRIX=
PHYSICAL_ACCEPTANCE_FOLLOWUP=

PR469_STATE=
PR469_DEDICATED_CI=
PR469_PUBLIC_SAFETY_CI=
PR469_MUTATION=false

PRODUCT_SOURCE_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false

N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN=
READY_FOR_GATEWAY_SELECTION_V1_SOURCE_REPAIR=
NEXT_ROUTE=

STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_20260921_01

AUTO_EXECUTE_AFTER_PASS=false
PRODUCT_SOURCE_MUTATION_REQUIRES_NEXT_GATE=true
BOARD_AUTHORIZATION_REQUIRED=false
```

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

PR #469 的 safety failure 作为独立路线处理，不得在 Gateway Selection design gate 中顺手修。

---

## 15. KNOWN_FAILURES Updates

本轮发现两个需要保留的事实，但在本 handoff 中不抢占新的 KF ID：

```text
KNOWN_FAILURES_UPDATE_REQUIRED=DEFERRED_TO_NEXT_DESIGN_OR_REPAIR_GATE
```

候选条目：

```text
A. Multi-Relay first-arrival gateway selection lacks deterministic quality policy.
DOMAIN=PRODUCT
ROOT_CAUSE=PROVEN_FROM_SOURCE
STATUS=OPEN

B. PR469 public-safety scanner rejects synthetic MAC-looking test literals.
DOMAIN=CI
ROOT_CAUSE=PROVEN_FROM_CI
STATUS=OPEN
```

正式分配 ID 前必须 fresh-read current `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`，避免冲突。

---

## 16. New Chat Start Prompt

直接复制以下内容到新会话：

```text
阅读：

docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_NEW_CHAT_HANDOFF_V1.0_20260921.md

同时读取 exact historical handoff authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- feature/n3w-production-telemetry-bridge-20260921
- PR #469
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_PRODUCTION_DEHARNESS_AND_EXACT_ARTIFACT_PROGRESS_ALIGNMENT_20260921.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
支线任务：Production Multi-Relay Gateway Selection V1
当前任务：N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01

必须承认：
- 当前 production successor source 为 c1b3d9d016d06c21c9ff7070c0043163739565ca；
- exact production artifact 10644667734 已完成 build/binding，但未写入 Board A/B；
- PR #469 dedicated readonly-preflight CI PASS，但 Public repository safety CI 因 synthetic MAC-looking test fixtures FAIL；
- A/B Relay 角色在源码上对称，但 B-as-Gateway/A-as-Child 尚未正式实机验收；
- 当前多 Gateway 选择实际是 first-valid-discovery / first-successful-handshake；
- 用户已批准 Gateway Selection V1 方向：
  RSSI 优先；
  RSSI 差值 <=3 dB 时使用 HASH(C.NODE_ID || RELAY.NODE_ID) 稳定决胜；
  hash 碰撞再按 Relay NODE_ID 字典序；
  不做动态负载均衡；
  健康 active Relay 不主动漫游；
  active Relay 失效后才重新 Discovery / selection。

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false

当前只进入：
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01

该 gate 只冻结 implementation-ready source design：
- candidate window；
- RSSI update rule；
- stable hash primitive / input encoding；
- Challenge/Accept failure behavior；
- no-proactive-roaming proof；
- source changed-file allowlist；
- regression test matrix。

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

不得修改 production source，不得修 PR #469，不得访问实板，不得自动进入 SOURCE_REPAIR。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=
N3W_PRODUCTION_MULTI_RELAY_ROLE_AND_GATEWAY_SELECTION_REVIEW

CURRENT_STOP_POINT=
GATEWAY_SELECTION_V1_DIRECTION_APPROVED;
SOURCE_DESIGN_NOT_YET_FROZEN

MAIN=
ac0707e9cde2f6f0e3db6d793b3f86fa8030bd91

PRODUCTION_SOURCE=
c1b3d9d016d06c21c9ff7070c0043163739565ca

PRODUCTION_EXACT_ARTIFACT_ID=10644667734
PRODUCTION_RELEASE_SHA256=
93d830368b74e0dae904a9f5c4450378694575c68b917e749b480455662ff065

PR469=OPEN
PR469_DEDICATED_PREFLIGHT_CI=PASS
PR469_PUBLIC_REPOSITORY_SAFETY=FAIL_CI_CONTENT_SAFETY
PR469_BOARD_ACCESS=false

A_CAN_RELAY_B=SUPPORTED_BY_SOURCE
B_CAN_RELAY_A=SUPPORTED_BY_SOURCE
REVERSE_ROLE_PHYSICAL_ACCEPTANCE=NOT_YET_PROVEN

CURRENT_MULTI_RELAY_SELECTION=
FIRST_VALID_DISCOVERY_THAT_COMPLETES_HANDSHAKE

DESIRED_MULTI_RELAY_SELECTION=
BOUNDED_CANDIDATE_WINDOW
+ RSSI_PRIMARY
+ 3DB_EQUIVALENT_BAND
+ CHILD_RELAY_STABLE_HASH_TIE_BREAK
+ STICKY_ACTIVE_RELAY
+ RESELECT_ONLY_AFTER_FAILURE

DYNAMIC_LOAD_BALANCING=false
PROACTIVE_ROAMING=false

NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01

NEXT_GATE_AUTHORIZED=true

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
