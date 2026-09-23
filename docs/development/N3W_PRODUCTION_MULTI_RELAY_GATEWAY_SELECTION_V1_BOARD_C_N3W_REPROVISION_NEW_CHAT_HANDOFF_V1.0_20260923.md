# 温室环境监测系统（ESP32-C6）
# N3-W Production Multi-Relay Gateway Selection V1
# Board C N3-W Reprovision
# 新会话交接文档 V1.0 — 2026-09-23

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

本文符合 exact handoff standard authority：

```text
HANDOFF_STANDARD_AUTHORITY=
4300890dff0ce63d5a547df21426e287d084d9ee

HANDOFF_STANDARD=
docs/development/NEW_CHAT_HANDOFF_STANDARD.md

HANDOFF_TEMPLATE=
docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
```

如本文与 fresh exact repository/runtime/live evidence 冲突，以 fresh exact evidence 为准，
先 STOP 并完成 rebind，不得按旧推断继续 mutation。

---

## 0. 会话切换结论

当前对话上下文已经较长，本轮在 Board C Wi-Fi 恢复闭环之后主动切换新会话。

```text
CURRENT_STAGE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_RECOVERY

CURRENT_STOP_POINT=
BOARD_C_WIFI_REPROVISION_CLOSED_PASS_AND_N3W_REPROVISION_NOT_YET_EXECUTED

NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01

CURRENT_TEST_PLAN=UNCHANGED
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTO_RETRY=false
AUTO_REFLASH=false
AUTO_ERASE=false
STOP_AND_REVIEW=true

HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新设计 Multi-Relay 物理测试，也不是重新刷 A/B/C。
只从 Board C N3-W reprovision 这一门开始。

---

## 1. 执行模式

### 1.1 高阶模型职责

高阶模型负责：

- 维护 N3-W 产品路线与当前 exact source / artifact authority；
- 维护 Multi-Relay Gateway Selection V1 的既定物理验收方案；
- 设计 Board C N3-W reprovision 的 exact gate、authorization、rollback；
- 区分 Board C provisioning-state recovery 与 product-source defect；
- 防止 pairing repair 扩展成新的产品架构或测试框架；
- 根据 exact evidence 做 PASS / FAIL / STOP；
- 不因日志缺失直接判产品失败，优先使用 durable/runtime state。

### 1.2 Codex 低阶执行职责

Codex 仅机械执行高阶模型冻结的 exact DSL：

- Git / Docker / SSH / shell / SQLite read-only inspection；
- private identity/state 的本地绑定与脱敏；
- mutation 只能发生在明确授权后的 exact 范围；
- 第一处 substantive mismatch 即 STOP；
- 不扩大 scope、不自动修复、不自动重试；
- 不跨入后续 R0/R1 物理阶段。

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
高阶模型：fresh rebind -> gate/adjudication
        ↓
exact mutation scope ready 时取得必要授权
        ↓
Codex：minimum commands -> execution -> structured closure
        ↓
高阶模型：PASS / FAIL / STOP
```

---

## 2. Product North Star

当前产品路线：

```text
CURRENT_ROUTE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1
```

本阶段最终目标仍是使用相同 production artifact，验证 A 作为 Child、
B/C 作为 Direct+MQTT Gateway candidates 时的真实多网关选择与恢复。

既定物理拓扑：

```text
CHILD_UNDER_TEST=A
GATEWAY_CANDIDATE_1=B
GATEWAY_CANDIDATE_2=C

BOARD_A_ROLE=PORTABLE_CHILD_UNDER_TEST
BOARD_B_ROLE=STATIONARY_DIRECT_RELAY_CANDIDATE
BOARD_C_ROLE=STATIONARY_DIRECT_RELAY_CANDIDATE

BOARD_A_MOVEMENT_POLICY=MOVABLE
BOARD_B_MOVEMENT_POLICY=MOVABLE
BOARD_C_MOVEMENT_POLICY=STATIONARY
BOARD_C_POWER_MODE=FIXED_STABLE_POWER
```

既定测试方案保持不变：

```text
R0=A/B/C fresh Direct rebaseline under new roles
R1=A can Relay through B alone
R2=A can Relay through C alone
R3=dual-Gateway geometry B-strong -> A selects B
R4=dual-Gateway geometry C-strong -> A selects C
R5=healthy active-Gateway stickiness
R6=active-Gateway failure -> A reselects surviving Gateway
R7=A same-boot Relay -> Direct recovery
```

当前不得进入：

```text
CURRENT_R0_TO_R7_REDESIGN=false
CURRENT_ARTIFACT_REBUILD=false
CURRENT_CHANNEL_COVERAGE_FIX=false
DYNAMIC_LOAD_BALANCING=false
PROACTIVE_ROAMING=false
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main / active progress branch

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN=
3b4a75b039a8d5d9572b4a8f7cfb1e580e7f3476

MAIN_TREE=
f19701fb432f76d6913fed38891b8cbeedeb124f

CURRENT_PROGRESS_BRANCH=
docs/n3w-production-gwsel-v1-p0-direct-baseline-20260923

CURRENT_PROGRESS_BRANCH_HEAD_AT_HANDOFF_FREEZE=
78fc93ad66147219b31d33f65f32dbab081c7e9a
```

Fresh compare at handoff preparation showed the current progress branch has substantial
post-main development history and is diverged from main. Therefore:

```text
MAIN_IS_CURRENT_PROGRESS_AUTHORITY=false
CURRENT_PROGRESS_BRANCH_IS_WORKING_AUTHORITY=true
FINAL_MAIN_ALIGNMENT_REQUIRED=true
FINAL_MAIN_ALIGNMENT_TIMING=AFTER_CURRENT_MULTI_RELAY_V1_CLOSURE
```

Do not silently fast-forward/merge/rebase this branch in the new chat merely to begin Board C reprovision.

### 3.2 Product source / tree

```text
PRODUCT_SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

PRODUCT_SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181
```

### 3.3 Exact production artifact

```text
ARTIFACT_ID=10693728323
ARTIFACT_NAME=n3w-production-gwsel-v1-r2-8c445f2-exact-source

OUTER_ARTIFACT_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

RELEASE_BUNDLE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

FIRMWARE_BIN_SIZE=1392960
FIRMWARE_BIN_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

PARTITIONS_BIN_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTADATA_INITIAL_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

OTADATA_RUNTIME_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
```

Frozen production write policy remains:

```text
OTADATA_OFFSET=0x9000
APP0_OFFSET=0x10000
APP1_OFFSET=0x3D0000
NVS_OFFSET=0x790000

NORMAL_EXACT_WRITE=
0x9000 ota_data_initial.bin
0x10000 firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
FACTORY_IMAGE_WRITE=false
FULL_FLASH_ERASE=false
```

No write is currently required.

### 3.4 Relevant documentation authorities

```text
ROLE_SWAP_PLAN=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_A_CHILD_BC_GATEWAYS_ROLE_SWAP_REPLAN_20260923.md

PHYSICAL_VALIDATION_DESIGN=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_VALIDATION_PREPARATION_R2_20260922.md

BOARD_C_WIFI_DIAGNOSIS=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_WIFI_PROVISIONING_LOSS_DIAGNOSIS_20260923.md

BOARD_C_APP1_ERASE_CLOSURE=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_APP1_STALE_IMAGE_ERASE_CLOSURE_20260923.md

BOARD_C_WIFI_REPROVISION_CLOSURE=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_WIFI_REPROVISION_CLOSURE_20260923.md

CHANNEL_COVERAGE_DEFERRED_DECISION=
docs/development/N3W_PRODUCTION_RELAY_DISCOVERY_CHANNEL_COVERAGE_FALLBACK_V1_DEFERRED_DECISION_20260923.md

CURRENT_STATE=
docs/development/N3W_CURRENT_STATE.md

CURRENT_STATE_INDEX=
docs/development/N3W_CURRENT_STATE_INDEX.md
```

### 3.5 Private/runtime authority

Private T1 locator、raw hardware ID、raw pairing ID、raw NODE_ID、credentials、setup secret、
raw Manager/Broker logs 都不得进入 public GitHub 文档。

```text
PRIVATE_T1_TARGET=REQUIRES_PRIVATE_CONTEXT_REBIND
PRIVATE_BOARD_C_HARDWARE_ID=REQUIRES_PRIVATE_CONTEXT_REBIND
PRIVATE_BOARD_C_PAIRING_ID=REQUIRES_PRIVATE_CONTEXT_REBIND
PRIVATE_SETUP_SECRET=DO_NOT_PRINT_OR_COMMIT
```

---

## 4. Current Live Baseline

交接时最后一次已证明状态：

```text
BOARD_C_POWER_STABILITY_FIX=OPERATOR_CONFIRMED
BOARD_C_USB_TO_MAC=LAST_CONFIRMED_CONNECTED
BOARD_C_RUNNING_APP_SLOT=APP0

BOARD_C_APP1_ALL_FF_AFTER_ERASE=true
BOARD_C_APP0_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

BOARD_C_WIFI_SETTINGS_LOADED=true
BOARD_C_WIFI_ASSOCIATION=PASS
BOARD_C_WIFI_IP_ASSIGNED=true
BOARD_C_FALLBACK_AP_DISABLED_AFTER_STA_CONNECT=true

BOARD_C_N3W_PROVISIONING_STATE=UNPROVISIONED
BOARD_C_N3W_REPROVISION_REQUIRED=true
```

最后 USB 日志中 N3-W 直接证据：

```text
Unprovisioned N3-W node ready for local pairing
Simplified pairing waiting code=1
```

当前没有证明：

```text
BOARD_C_N3W_MANAGER_PAIRING_RECOVERED=false
BOARD_C_CURRENT_LOGICAL_NODE_ID_PRESERVED=NOT_YET_PROVEN
BOARD_C_CURRENT_MQTT_RUNTIME_READY=NOT_YET_PROVEN
BOARD_C_CURRENT_MANAGER_CANONICAL_DIRECT=NOT_YET_PROVEN_AFTER_RECOVERY
```

新会话必须 fresh rebind：

```text
T1_MANAGER_STATE_REQUIRES_FRESH_READONLY_REBIND=true
BOARD_C_CURRENT_PAIRING_SESSION_REQUIRES_FRESH_READONLY_REBIND=true
BOARD_C_EXISTING_MANAGER_REGISTRATION_REQUIRES_FRESH_READONLY_REBIND=true
BOARD_C_USB_PRESENCE_REQUIRES_FRESH_REBIND=true
```

---

## 5. Proven Current Facts

```text
THREE_BOARD_EXACT_ARTIFACT_SYNCHRONIZATION=PASS

BOARD_A_EXACT_ARTIFACT_10693728323=PASS
BOARD_B_EXACT_ARTIFACT_10693728323=PASS
BOARD_C_EXACT_ARTIFACT_10693728323=PASS

BOARD_C_APP1_STALE_VALID_IMAGE_WAS_PRESENT=true
BOARD_C_APP1_STALE_IMAGE_ERASE=CLOSED_PASS
BOARD_C_APP1_ALL_FF_AFTER_ERASE=true

BOARD_C_APP0_EXACT_FIRMWARE_PRESERVED=true
BOARD_C_REFLASH_REQUIRED=false

BOARD_C_WIFI_REPROVISION=CLOSED_PASS
BOARD_C_N3W_PROVISIONING_STATE=UNPROVISIONED

EXACT_ARTIFACT_APPLICATION_DEFECT_FOR_WIFI_LOSS=NOT_SUPPORTED
```

The earlier Board C Wi-Fi/N3-W loss is strongly consistent with provisioning-state loss after the
factory-reset path, but brownout was not directly proven:

```text
INFERENCE_BOARD_C_FAST_POWER_CYCLE_FACTORY_RESET=
STRONGLY_SUPPORTED_NOT_DIRECTLY_PROVEN

BOARD_C_BROWNOUT_PROVEN=false
```

Exact product source facts relevant to the next gate:

```text
PAIRING_CLIENT_GENERATES_OR_LOADS_SETUP_SECRET=true
PAIRING_CLIENT_GENERATES_OR_LOADS_PAIRING_INTENT=true
PAIRING_QR_PAYLOAD_METHOD_EXISTS=true
PAIRING_QR_PAYLOAD_FORMAT=GHN3W2:<hardware_id>:<pairing_id>:<setup_secret>

PRODUCTION_COMPONENT_LOGS_HARDWARE_ID_AND_PAIRING_ID=true
PRODUCTION_DISPLAY_SETUP_QR_IS_WIFI_FALLBACK_AP_QR=true
PRODUCTION_SETUP_SECRET_OPERATOR_EXPORT_PATH=NOT_PROVEN
```

The last line is an important STOP condition for design-by-assumption:
do not assume the production artifact emits `GHN3W2` on USB just because a historical
board-lab harness did.

Manager source provides product operations for:

```text
SETUP_SECRET_IMPORT_OVER_LOCAL_IPC=true
BOUNDED_REPAIR_AUTHORIZATION=true
BOUNDED_EXISTING_IDENTITY_CREDENTIAL_RECOVERY_AUTHORIZATION=true
```

The correct choice among fresh registration / repair / existing-identity credential recovery
must be decided only after fresh Manager registration-state inspection.

---

## 6. Current Root Cause / Blockers

### Blocker A — Board C N3-W durable provisioning state absent

```text
ROOT_CAUSE_DOMAIN=BOARD_C_PERSISTED_PROVISIONING_STATE
BOARD_C_N3W_UNPROVISIONED=PROVEN
PRODUCT_FIRMWARE_REFLASH_REQUIRED=false
SOURCE_DEFECT_PROVEN=false
```

This blocks returning Board C to its role as a Direct+MQTT Gateway candidate.

### Blocker B — exact safe recovery path not yet rebound

```text
MANAGER_CURRENT_REGISTRATION_STATE=UNKNOWN_UNTIL_FRESH_REBIND
EXISTING_IDENTITY_RECOVERY_APPLICABLE=UNKNOWN_UNTIL_FRESH_REBIND
ORDINARY_REPAIR_APPLICABLE=UNKNOWN_UNTIL_FRESH_REBIND
FRESH_REGISTRATION_APPLICABLE=UNKNOWN_UNTIL_FRESH_REBIND
```

Do not create a duplicate Board C logical identity before checking Manager authority.

### Blocker C — Setup Secret acquisition surface

```text
PRODUCTION_SETUP_SECRET_EXISTS_IN_BOARD_NVS=SOURCE_SUPPORTED
PRODUCTION_SETUP_SECRET_PUBLIC_OUTPUT=NOT_PROVEN
PRODUCTION_SERIAL_GHN3W2_OUTPUT=NOT_ASSUMED
```

If the chosen recovery path requires Setup Secret import, first prove an exact safe way to obtain
the secret from the currently deployed production artifact. Do not invent a capture route.

---

## 7. Closed / Forbidden Routes

```text
BOARD_C_FULL_REFLASH_FOR_CURRENT_RECOVERY=
CLOSED:APP0 exact firmware hash already preserved

BOARD_C_FULL_FLASH_ERASE=
FORBIDDEN:not required and would enlarge damage

BOARD_C_FULL_NVS_ERASE=
FORBIDDEN:state is already unprovisioned; do not destroy more evidence/state

BOARD_C_APP1_STALE_IMAGE_RISK=
CLOSED_PASS:APP1 full readback all 0xFF

BOARD_C_WIFI_REPROVISION=
CLOSED_PASS:STA associated and IP assigned

C_AS_CHILD_ACTIVE_TEST_ROUTE=
SUPERSEDED_BY_ROLE_SWAP

CURRENT_MULTI_RELAY_TEST_PLAN_REDESIGN=
FORBIDDEN:user explicitly froze existing design

CHANNEL_COVERAGE_FIX_DURING_CURRENT_ACCEPTANCE=
DEFERRED:not part of current artifact acceptance

EXACT_3DB_PHYSICAL_CLAIM_WITHOUT_INTERNAL_RSSI_EVIDENCE=
FORBIDDEN

AUTO_RETRY_AFTER_PAIRING_FAILURE=false
AUTO_REFLASH=false
AUTO_FACTORY_RESET=false
```

Historical C-as-Child P1A/P1B evidence remains evidence only and must not replace the new A-as-Child route.

---

## 8. Authorization Ledger

### 8.1 Board C APP1 erase

```text
AUTHORIZATION=BOARD_C_APP1_STALE_IMAGE_ERASE
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

### 8.2 Board C Wi-Fi reprovision

```text
AUTHORIZATION=BOARD_C_WIFI_REPROVISION
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

### 8.3 Next gate entry

The user explicitly directed the next chat to continue with:

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01

GATE_ENTRY_REQUESTED_BY_USER=true
```

This does not silently authorize every possible mutation inside that gate.

```text
AUTHORIZATION=BOARD_C_N3W_REPROVISION_EXACT_MUTATION
CLAIMED=false
CONSUMED=false
RESULT=NOT_EXECUTED
REPLAY_PERMITTED=false

READY_FOR_READONLY_REBIND=true
EXACT_MUTATION_SCOPE_NOT_YET_FROZEN=true
```

Before any T1/Manager/Broker/Board-C NVS mutation, the high-level model must first determine the exact
recovery path and bind a finite authorization to that path.

No physical authorization from A/B/C write gates carries forward.

---

## 9. Rollback Authority

The next gate begins read-only, so the initial rebind phase needs no rollback.

If the gate later proceeds to N3-W reprovision mutation:

```text
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
HISTORICAL_SNAPSHOT_AS_ROLLBACK_AUTHORITY=false
SECOND_ATTEMPT_ALLOWED=false
AUTO_RETRY=false
```

Before mutation, snapshot only the exact state required by the chosen path, including as applicable:

- current Manager registration state for Board C hardware identity;
- current pairing session / current pointer state;
- current credential generation and stable logical NODE_ID binding;
- current Broker/DynSec target state if credential mutation is part of the exact path;
- Board C public-safe pairing/hardware digests;
- no raw secret in public evidence.

Rollback must be designed after the actual current state is known.

If mutation partially commits externally:

```text
AUTO_REPLAY=false
ROLLBACK_INCOMPLETE=true
RETURN_TO_HIGH_LEVEL_MODEL=true
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01
```

### 10.1 Purpose

Restore Board C from the proven `UNPROVISIONED` N3-W state to a valid Manager-controlled
production N3-W identity/runtime without reflashing firmware, without changing the Multi-Relay test
design, and without accidentally creating a duplicate logical node identity.

### 10.2 Frozen inputs

```text
PRODUCT_SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

PRODUCT_SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

ARTIFACT_ID=10693728323

BOARD_C_APP0_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

BOARD_C_WIFI_REPROVISION=PASS
BOARD_C_N3W_PROVISIONING_STATE=UNPROVISIONED

TARGET_POST_RECOVERY_ROLE=
STATIONARY_DIRECT_RELAY_CANDIDATE
```

### 10.3 Required proof / operations

The gate must be split internally into a read-only preclaim and, only if exact state supports it,
a bounded mutation phase.

```text
1. Fresh rebind repository/main/current progress branch and handoff authorities.
2. Fresh read-only rebind T1 Manager container/runtime health and pairing IPC authority.
3. Privately bind Board C physical hardware identity and current pairing intent.
4. Read current Manager registration/pairing state for that exact hardware identity.
5. Determine whether recovery is:
   a. existing-identity credential recovery,
   b. ordinary bounded repair,
   c. legitimate fresh first-registration,
   d. STOP for unsupported state.
6. Prove the exact setup-secret acquisition/import route if the selected path requires it.
7. Freeze mutation scope + rollback snapshot + one-shot authorization.
8. Execute exactly one approved recovery path.
9. Verify Board C becomes provisioned/runtime-ready.
10. Verify Manager canonical state sees Board C on Direct with stable identity semantics.
11. STOP.
```

Do not assume step 6 can use the USB capture helper until the current production artifact is proven
to emit the required private payload.

### 10.4 PASS

```text
BOARD_C_N3W_REPROVISION=PASS
BOARD_C_RUNTIME_READY=true
BOARD_C_DIRECT_MQTT_HEALTHY=true
BOARD_C_MANAGER_CANONICAL_DIRECT=PASS
BOARD_C_DUPLICATE_LOGICAL_IDENTITY_CREATED=false
BOARD_C_REFLASH_REQUIRED=false

READY_FOR_A_CHILD_BC_GATEWAYS_DIRECT_REBASELINE=true
STOP=true
```

### 10.5 FAIL / STOP

Examples:

```text
FAIL_MANAGER_REGISTRATION_STATE_AMBIGUOUS
FAIL_EXISTING_IDENTITY_BINDING_CONFLICT
FAIL_SETUP_SECRET_ACQUISITION_PATH_NOT_PROVEN
FAIL_PAIRING_SESSION_NOT_CURRENT
FAIL_MUTATION_SCOPE_NOT_EXACT
FAIL_ROLLBACK_BASELINE_NOT_FRESH
FAIL_BOARD_C_RUNTIME_NOT_READY
FAIL_MANAGER_CANONICAL_DIRECT_NOT_PROVEN
```

On any substantive failure:

```text
AUTO_REPAIR=false
AUTO_RETRY=false
AUTO_REFLASH=false
AUTO_ERASE=false
STOP=true
RETURN_TO_HIGH_LEVEL_MODEL=true
```

---

## 11. Hard Allowed / Forbidden Scope

Default:

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED before exact mutation authorization

```text
- GitHub read-only authority rebind
- T1 Manager/Docker/SQLite read-only inspection
- private identity binding without public disclosure
- source inspection of current pairing/recovery implementation
- public-safe hashes and structured evidence
- design of one exact bounded reprovision mutation
```

### FORBIDDEN before exact mutation authorization

```text
- Board C firmware flash
- APP0/APP1/partition-table/bootloader write
- full Flash erase
- full NVS erase
- factory reset
- arbitrary NVS edit
- Manager DB write
- Broker/DynSec credential write
- Setup Secret import
- repair authorization
- credential-recovery authorization
- pairing-session mutation
- Board A mutation
- Board B mutation
- changing R0-R7 test plan
- source repair for channel coverage
```

### Privacy boundary

```text
RAW_MAC_PUBLIC=false
RAW_HARDWARE_ID_PUBLIC=false
RAW_PAIRING_ID_PUBLIC=false
RAW_NODE_ID_PUBLIC=false
RAW_SETUP_SECRET_PUBLIC=false
RAW_CREDENTIAL_PUBLIC=false
PRIVATE_T1_LOCATOR_PUBLIC=false
RAW_PRIVATE_LOG_PUBLIC=false
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required unless the
high-level model explicitly freezes one after the read-only preclaim.

Mechanically compile this DSL into the minimum necessary commands using
already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not retry unless explicitly permitted.
Do not enter the next gate.
Do not print or commit private identity or secret material.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01

PHASE_0=READONLY_REBIND
LIVE_MUTATION=false
BOARD_MUTATION=false
T1_MUTATION=false

If exact mutation authorization has not yet been frozen:
  perform only read-only preclaim;
  return proposed exact mutation scope;
  STOP before mutation.

============================================================
1. FROZEN INPUTS
============================================================

PRODUCT_SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

PRODUCT_SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

ARTIFACT_ID=10693728323
BOARD_TARGET=C

EXPECTED_APP0_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

EXPECTED_WIFI_STATE=CONNECTED
EXPECTED_N3W_STATE=UNPROVISIONED

============================================================
2. HARD SCOPE
============================================================

READONLY_T1_INSPECTION=true
READONLY_SOURCE_INSPECTION=true
PRIVATE_IDENTITY_BINDING=true

AUTO_FLASH=false
AUTO_ERASE=false
AUTO_FACTORY_RESET=false
AUTO_MANAGER_WRITE=false
AUTO_BROKER_WRITE=false
AUTO_PAIRING_IMPORT=false
AUTO_REPAIR=false
AUTO_CREDENTIAL_RECOVERY=false
AUTO_RETRY=false

============================================================
3. FRESH AUTHORITY REBIND
============================================================

Rebind:
- repository main;
- current progress branch;
- CURRENT_STATE;
- CURRENT_STATE_INDEX;
- this handoff;
- exact product pairing source;
- Manager pairing CLI / local IPC implementation;
- KNOWN_FAILURES_AND_REGRESSION_GUARDS.

Verify no newer authority supersedes this handoff.

============================================================
4. BOARD C PRIVATE BINDING
============================================================

Bind the currently connected/identified physical Board C.

Do not publish raw MAC/hardware_id/pairing_id.

Produce only:
- BOARD_C_HARDWARE_ID_SHA256
- BOARD_C_PAIRING_ID_SHA256
- BOARD_C_N3W_STATE
- BOARD_C_WIFI_STATE

If Board C cannot be uniquely bound:
  STOP=BOARD_C_IDENTITY_NOT_UNIQUE

============================================================
5. MANAGER READONLY STATE
============================================================

Freshly identify the running Manager authority.

Read-only inspect the exact registration/pairing state for Board C hardware identity.

Determine:
- current registration exists or not;
- stable NODE_ID exists or not;
- current pairing pointer/session state;
- active credential generation if applicable;
- whether recovery-required semantics apply.

Do not write DB.
Do not authorize repair.
Do not import Setup Secret.

============================================================
6. RECOVERY CLASSIFICATION
============================================================

Return exactly one:

RECOVERY_CLASS=
EXISTING_IDENTITY_CREDENTIAL_RECOVERY
| ORDINARY_REPAIR
| FIRST_REGISTRATION
| UNSUPPORTED_STOP

Do not choose by historical assumption.

If EXISTING_IDENTITY_CREDENTIAL_RECOVERY:
  preserve stable logical NODE_ID.

If FIRST_REGISTRATION:
  first prove there is no conflicting current registration that would
  create a duplicate logical identity.

============================================================
7. SETUP SECRET PATH
============================================================

If selected path requires Setup Secret:

Prove the currently deployed production artifact has a safe exact method
to obtain the current secret.

Historical board-lab serial output is not sufficient proof.

If no exact safe acquisition route is proven:
  STOP=SETUP_SECRET_ACQUISITION_PATH_NOT_PROVEN

Never print the secret.

============================================================
8. PRE-MUTATION FREEZE
============================================================

Before any mutation, high-level model must freeze:
- exact chosen recovery path;
- exact files/DB rows/runtime state to snapshot;
- exact rollback;
- exact one-shot authorization;
- exact secret transport boundary if applicable.

If authorization is absent:
  STOP=EXACT_MUTATION_AUTHORIZATION_REQUIRED

============================================================
9. EXACT MUTATION
============================================================

Execute only the frozen recovery path.

No parallel repair.
No second attempt.
No fallback to full NVS erase.
No firmware flash.

============================================================
10. POSTCHECK
============================================================

Require:
- Board C provisioned;
- product runtime loaded;
- MQTT configured/healthy;
- Manager canonical Direct state advances;
- identity semantics match the selected recovery class;
- no duplicate logical identity;
- Manager restart/runtime drift absent unless explicitly part of frozen path.

============================================================
11. HARD STOP
============================================================

Return structured closure.
Do not execute A/B/C Direct rebaseline.
Do not start R1.
```

---

## 13. Expected Closure

```text
=== N3W PRODUCTION GWSEL V1 BOARD C N3W REPROVISION CLOSURE ===

TASK=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01

PRODUCT_SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

ARTIFACT_ID=10693728323

BOARD_C_PRIVATE_IDENTITY_BOUND=
BOARD_C_HARDWARE_ID_SHA256=
BOARD_C_PAIRING_ID_SHA256=

T1_MANAGER_FRESH_REBIND=
MANAGER_RUNTIME_HEALTH=
CURRENT_REGISTRATION_FOUND=
STABLE_LOGICAL_IDENTITY_FOUND=
PAIRING_SESSION_STATE=

RECOVERY_CLASS=
SETUP_SECRET_REQUIRED=
SETUP_SECRET_ACQUISITION_PATH_PROVEN=

EXACT_MUTATION_AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

BOARD_C_N3W_REPROVISION=
BOARD_C_RUNTIME_READY=
BOARD_C_DIRECT_MQTT_HEALTHY=
BOARD_C_MANAGER_CANONICAL_DIRECT=
BOARD_C_DUPLICATE_LOGICAL_IDENTITY_CREATED=

BOARD_C_FLASH_WRITE=
BOARD_C_FULL_NVS_ERASE=
BOARD_A_MUTATION=
BOARD_B_MUTATION=

MANAGER_MUTATION=
BROKER_MUTATION=

RESULT=
NEXT_ROUTE=

STOP=true
=== END ===
```

No raw IDs/secrets in closure.

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_A_CHILD_BC_GATEWAYS_DIRECT_REBASELINE_20260923_01

AUTO_EXECUTE_AFTER_PASS=false
```

That stage returns to the frozen physical acceptance plan:

```text
R0 -> R1 -> R2 -> R3 -> R4 -> R5 -> R6 -> R7
```

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
AUTO_REFLASH=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

---

## 15. KNOWN_FAILURES Updates

No new product known-failure ID is created by this handoff.

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
```

Relevant existing guards remain applicable, especially:

- Setup Secret capture identity/secret safety guards;
- existing-identity credential recovery guards;
- consumed authorization non-replay rules;
- logging-oracle false-negative guard.

The Relay Discovery channel coverage issue is already separately registered as a deferred product
follow-up, not as a current-gate blocker:

```text
CHANNEL_COVERAGE_BLIND_SPOT=KNOWN_DEFERRED
FOLLOWUP_ROUTE=
N3W_PRODUCTION_RELAY_DISCOVERY_FULL_CHANNEL_FALLBACK_V1

FOLLOWUP_TIMING=
AFTER_CURRENT_MULTI_RELAY_V1_PHYSICAL_ACCEPTANCE

FOLLOWUP_BEFORE_NEXT_PRODUCTION_ARTIFACT_FREEZE=true
```

This deferred item must be included in final main alignment when the current Multi-Relay V1 route closes.

---

## 16. New Chat Start Prompt

```text
阅读：

docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_NEW_CHAT_HANDOFF_V1.0_20260923.md

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- docs/n3w-production-gwsel-v1-p0-direct-baseline-20260923
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_A_CHILD_BC_GATEWAYS_ROLE_SWAP_REPLAN_20260923.md
- docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_WIFI_REPROVISION_CLOSURE_20260923.md
- docs/development/N3W_PRODUCTION_RELAY_DISCOVERY_CHANNEL_COVERAGE_FALLBACK_V1_DEFERRED_DECISION_20260923.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
支线任务：Production Multi-Relay Gateway Selection V1
当前任务：N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

当前只进入：
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01

测试方案保持既定设计不变：
A=Child under test；
B/C=Gateway candidates；
C=固定稳定供电并保持 stationary；
R0-R7 序列不变。

先进行 fresh read-only rebind，确认 Board C 在 Manager 中的当前 registration/pairing
状态，并据此判定 existing-identity credential recovery / ordinary repair /
first-registration / STOP。不得直接假设 recovery 类型。

重要：
当前 production firmware 的 setup-secret operator export surface 尚未证明。
不要因为历史 board-lab helper 支持 GHN3W2 就假设当前 production USB 会输出该 payload。

Relay Discovery 仅扫 1/6/11 的覆盖盲区已经登记：
N3W_PRODUCTION_RELAY_DISCOVERY_FULL_CHANNEL_FALLBACK_V1
在当前 Multi-Relay V1 物理验收完成后、下一版 production artifact 冻结前处理；
当前 artifact 和测试方案不得因此修改。

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTO_RETRY=false
AUTO_REFLASH=false
AUTO_ERASE=false

不重放 consumed authorization。
不自动跨越下一阶段。
```

---

## 17. Final Frozen State

```text
CURRENT_ROUTE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1

CURRENT_STAGE=
BOARD_C_N3W_RECOVERY_PREEXECUTION_HANDOFF

CURRENT_STOP_POINT=
BOARD_C_WIFI_REPROVISION_PASS_N3W_UNPROVISIONED

PRODUCT_SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

ARTIFACT_ID=10693728323

CURRENT_TEST_PLAN=UNCHANGED
CHILD_UNDER_TEST=A
GATEWAY_CANDIDATES=B,C
BOARD_C_POWER_MODE=FIXED_STABLE_POWER
BOARD_C_MOVEMENT_POLICY=STATIONARY

BOARD_C_APP1_STALE_IMAGE_ERASE=CLOSED_PASS
BOARD_C_WIFI_REPROVISION=CLOSED_PASS
BOARD_C_N3W_REPROVISION=NOT_EXECUTED

SOURCE_DEFECT_PROVEN=false
CURRENT_BLOCKER=BOARD_C_N3W_PROVISIONING_STATE_UNPROVISIONED

NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01

AFTER_PASS_NEXT_STAGE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_A_CHILD_BC_GATEWAYS_DIRECT_REBASELINE_20260923_01

CHANNEL_COVERAGE_BLIND_SPOT=KNOWN_DEFERRED
CHANNEL_COVERAGE_FIX_DURING_CURRENT_ACCEPTANCE=false

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTO_RETRY=false
AUTO_REFLASH=false
AUTO_ERASE=false

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

CURRENT_MULTI_RELAY_TEST_PLAN_UNCHANGED=PASS
CHANNEL_COVERAGE_DEFERRED_ITEM_PRESERVED=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS

HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
