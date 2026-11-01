# 温室环境监测系统（ESP32-C6）
# N3-W / KF-089 — Board A 双槽观测固件归一化完成、正常启动 Postcheck 前
# 新会话交接文档 V1.0 — 2026-09-07

```text
HANDOFF_STANDARD_VERSION=1.0
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> Formal process authority is the exact historical standard at commit `4300890dff0ce63d5a547df21426e287d084d9ee`:  
> `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`  
> `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`  
> Current `main` may not contain those historical files. Read them from the exact authority commit.  
> If this handoff conflicts with exact repository/runtime/live evidence, stop and rebind to the higher authority first.

---

## 0. 会话切换结论

本轮已完成 KF-089 observability firmware 的 Board A Direct baseline、durable diagnostic session binding，以及 app0-only 归一化。当前 Board A 的 app0/app1 已精确为同一个 schema-v3 observability image；partition table、otadata、product NVS、app1 均在 app0 mutation 前后保持一致。

本轮停止点不是 product failure。Board A 在 app0 写入后仍处于 ROM Download Mode，远端 T1 未观察到应用启动；下一步必须先由现场释放 BOOT/GPIO9，再进行一次正常启动和 remote-T1 postcheck。

```text
CURRENT_STAGE=KF089_PHYSICAL_CLOSURE
CURRENT_STOP_POINT=BOARD_A_DUAL_SLOT_NORMALIZED_ROM_MODE_POSTCHECK_PENDING
NEXT_ONE_GATE=KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不得重新执行 Board A app0 写入，也不得重新做已经 PASS 的 Direct baseline / durable snapshot binding。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护产品路线与 exact source/artifact authority；
- 维护 Board A 已闭合证据与 consumed authorization replay guard；
- 设计唯一 next gate、scope、STOP 条件；
- 根据 Codex closure 做 PASS / FAIL / STOP 分类；
- 区分 product、runtime、infrastructure、CI、physical-harness/operator state；
- PASS 后只决定 Board B 下一阶段，不自动执行。

### 1.2 Codex 低阶执行职责

- 机械执行本文第 12 节 exact DSL；
- 只使用已安装工具；
- T1 只读；
- 不打开串口；
- 不读写 Flash/NVS；
- 不自行重放 Board A app0 mutation；
- 第一处 substantive mismatch 后 fail-closed STOP；
- 返回第 13 节结构化 closure。

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
高阶模型：rebind / gate / adjudication
        ↓
用户：完成需要人工现场动作的 BOOT/GPIO9 release
        ↓
Codex：机械执行正常启动 + remote-T1 postcheck
        ↓
高阶模型：复核 closure / 决定 Board B 下一阶段
```

---

## 2. Product North Star

当前产品路线：

```text
N3W_THREE_BOARD_T1_REAL_WORLD_PATH_FAILOVER_VALIDATION
→ KF089_PHYSICAL_CLOSURE
→ prove autonomous Relay acquisition after Direct is unavailable
```

最终目标：

```text
Provisioned N3-W node:
Direct preferred
→ Direct unavailable
→ node-local bounded discovery
→ authenticated Relay acquisition
→ Relay telemetry
→ later Direct recovery
```

当前不得进入：

```text
BOARD_B_REFRESH_BEFORE_BOARD_A_POSTCHECK_PASS
THREE_BOARD_RETEST_BEFORE_BOARD_B_OBSERVABILITY_BASELINE_PASS
FULL_CUSTOM_RADIO_OWNERSHIP_FSM_WITHOUT_NEW_PHYSICAL_EVIDENCE
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact product source

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=QUERY_GITHUB_FRESH
PRODUCT_SOURCE_AUTHORITY=483ff1c662dc74d6e12529e27a69819e68160f9e
PRODUCT_SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
LAST_PRODUCT_SOURCE_CHANGE=PR_370
```

At the 2026-09-07 alignment point, comparison from `483ff1c...` through repository main `3f3deb6...` showed only `docs/development/` descendants. Documentation commits do not change the product-source authority. Freshly rebind main in the new chat.

### 3.2 Exact physical artifact

```text
FIRMWARE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
FIRMWARE_SIZE=1114144
DIAGNOSTIC_SCHEMA_VERSION=3
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
DIAGNOSTIC_KEY=snapshot
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

### 3.3 Board A frozen slot state

```text
BOARD_A_SELECTED_SLOT=1
BOARD_A_APP0_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
BOARD_A_APP1_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS
APP0_UNUSED_TAIL_ERASED=true
```

### 3.4 Mutation-preservation authority

```text
PRE_PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
POST_PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

PRE_OTADATA_SHA256=062f79dd9748aef0e56afddd5db3112af00549478e9d478e38137d5f3232f3a3
POST_OTADATA_SHA256=062f79dd9748aef0e56afddd5db3112af00549478e9d478e38137d5f3232f3a3

PRE_NVS_SHA256=b132280e337fac8b8cbbbf547fab33c28e12069fd96ce19ef072398cf385063d
POST_NVS_SHA256=b132280e337fac8b8cbbbf547fab33c28e12069fd96ce19ef072398cf385063d

PARTITION_TABLE_PRESERVED=PASS
OTADATA_PRESERVED=PASS
NVS_PRESERVED_DURING_MUTATION=PASS
APP1_PRESERVED=PASS
```

### 3.5 Target runtime authority

```text
REMOTE_T1_AUTHORITY_FOUND=PASS
REMOTE_T1_SSH_BINDING=PASS
REMOTE_T1_RUNTIME_BINDING=PASS
T1_MANAGER_RUNNING=true
T1_BROKER_RUNNING=true
REMOTE_T1_LIVE_OBSERVER_AVAILABLE=true
REMOTE_T1_OBSERVER_TYPE=MANAGER_CANONICAL_ACCEPTANCE
```

Private host/address/identity material must remain private.

---

## 4. Current Live Baseline

At handoff:

```text
BOARD_A_CURRENT_MODE=ROM_DOWNLOAD_MODE
BOARD_A_APPLICATION_RUNNING=false
BOARD_A_POSTCHECK_EXECUTED=false
BOARD_A_BOOT_GPIO9_RELEASE_REQUIRED=true

BOARD_A_DIRECT_BASELINE=PASS
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS

REMOTE_T1_RUNTIME_LAST_PROVEN=PASS
REMOTE_T1_RUNTIME_REQUIRES_FRESH_READONLY_REBIND=true

BOARD_B_OBSERVABILITY_REFRESH=NOT_EXECUTED

SERIAL_OPEN=false
FLASH_WRITE=false
NVS_WRITE=false
T1_MUTATION=false
AP_MUTATION=false
```

The exact physical state “BOOT/GPIO9 is currently released” is **not** yet proven. That is the first operator/preclaim condition of the next gate.

---

## 5. Proven Current Facts

```text
KF089_STARTUP_GATE_REPAIR=PASS
TARGET_RUNTIME_READY_PHYSICAL=PASS

BOARD_A_T1_ACCEPTANCE_BINDING=PASS
BOARD_A_DURABLE_DIAG_BINDING=PASS
BOARD_A_DIRECT_BASELINE=PASS

BOARD_A_DIAG_BOOT_SESSION=11540229135812002993
BOARD_A_T1_BOOT_SESSION=11540229135812002993
BOARD_A_DIAG_SESSION_BINDING=PASS
SESSION_ATTRIBUTION=PASS

BOARD_A_DIRECT_CHANNEL=11
BOARD_A_DIRECT_CHANNEL_HINT=11
BOARD_A_SCAN_ATTEMPTS=0
BOARD_A_SCAN_FAILURES=0

BOARD_A_ADVERTISEMENT_ATTEMPTS=1304
BOARD_A_ADVERTISEMENT_SUBMIT_SUCCESS=1304
BOARD_A_ADVERTISEMENT_SUBMIT_FAILURE=0
BOARD_A_BROADCAST_COMPLETION_COUNT=1304
BOARD_A_BROADCAST_COMPLETION_SUCCESS=1304
BOARD_A_BROADCAST_COMPLETION_FAILURE=0

BOARD_A_APP0_EXACT_OBSERVABILITY=PASS
BOARD_A_APP1_EXACT_OBSERVABILITY=PASS
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS

PRODUCT_NVS_MUTATION=false
PRODUCT_FAILURE=false
```

The Direct baseline T1 window was:

```text
T1_DIRECT_ACCEPTED_COUNT=18
T1_DIRECT_REJECTED_COUNT=0
T1_DIRECT_DUPLICATE_COUNT=0
T1_SEQ_FIRST=435
T1_SEQ_LAST=452
T1_INGRESS_SOURCE=direct
```

### Inference / interpretation kept separate

```text
INFERENCE_POSTCHECK_ZERO_TELEMETRY_REASON=application_not_started_while_board_remained_in_ROM
```

This interpretation is strongly consistent with the observed ROM state, but the next gate must still explicitly confirm BOOT/GPIO9 release before normal boot.

---

## 6. Current Root Cause / Blockers

### Blocker A — Board A normal postcheck has not run

```text
ROOT_CAUSE=BOARD_REMAINED_IN_ROM_DOWNLOAD_MODE_AT_POSTCHECK_BOUNDARY
PROVEN_BY=ROM_RESPONSE_PLUS_ZERO_REMOTE_T1_APPLICATION_TELEMETRY
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
PRODUCT_FAILURE=false
```

The current blocker is an operator/physical-state boundary, not a source defect.

### Blocker B — KF-089 Relay acquisition remains open

```text
KF089_AUTONOMOUS_RELAY_DISCOVERY=NOT_PROVEN
KF089_AUTHENTICATED_RELAY_ACQUISITION=NOT_PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

Board A postcheck must close before Board B observability refresh and the next battery-only Relay diagnostic execution.

---

## 7. Closed / Forbidden Routes

Unless new direct counter-evidence appears, do not re-enter:

```text
REPLAY_BOARD_A_APP0_NORMALIZATION=CLOSED:app0/app1 exact readback PASS and mutation authorization consumed
REPEAT_BOARD_A_DURABLE_DIRECT_BASELINE=CLOSED:T1+schema-v3 boot-session binding already PASS
HARDCODE_DIRECT_CHANNEL_1=CLOSED:current valid home/direct channel 11 independently proven
LOCALHOST_AS_T1_AUTHORITY=CLOSED:real remote T1 authority recovered
REUSED_NATIVE_USB_SERIAL_COLLECTOR_AS_PASSIVE_ORACLE=CLOSED:serial open triggered reset
LEGACY_APP_CONTAMINATION_ROUTE=CLOSED:old application slots were purged and current Board A both slots are exact observability firmware
PRODUCT_SOURCE_REPAIR_NOW=CLOSED:no current evidence justifies another source change
BOARD_B_ACCESS_BEFORE_BOARD_A_POSTCHECK_PASS=FORBIDDEN
```

---

## 8. Authorization Ledger

### 8.1 Durable diagnostic execution

```text
AUTHORIZATION=N3W_KF089_BOARD_A_DIRECT_ROM_ENTRY_AND_DURABLE_DIAG_READ_20260907_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
```

### 8.2 Board A app0 normalization

```text
AUTHORIZATION=N3W_KF089_BOARD_A_APP0_NORMALIZATION_AND_POSTCHECK_20260907_01
CLAIMED=true
CONSUMED=true
RESULT=APP0_MUTATION_PASS_POSTCHECK_NOT_EXECUTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=N3W_KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK_20260907_01
```

Do not replay the app0 erase/write under any circumstance merely because the original combined task closure was terminal `FAIL`.

### 8.3 Next gate authorization

The user explicitly requested: release BOOT/GPIO9, confirm, then continue normal startup postcheck.

```text
AUTHORIZATION=N3W_KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK_20260907_01
GRANTED=true
CLAIMED=false
CONSUMED=false
RESULT=PENDING
REPLAY_PERMITTED=false
```

This authorization covers only the exact non-flash physical postcheck gate in sections 10–13.

---

## 9. Rollback Authority

The next gate performs no persistent firmware/NVS/T1/source mutation.

```text
ROLLBACK_BASELINE=BOARD_A_BOTH_SLOTS_EXACT_OBSERVABILITY_SELECTED_SLOT_1
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
ROLLBACK_AUTHORITY=NOT_APPLICABLE:NO_PERSISTENT_MUTATION_IN_NEXT_GATE
NORMAL_PATH_RESTART_ALLOWED=ONE_FULL_POWER_CYCLE_WITH_BOOT_RELEASED
SECOND_ATTEMPT_ALLOWED=false
```

If the normal application postcheck fails:

```text
AUTO_REPAIR=false
AUTO_RETRY=false
FLASH_WRITE=false
RETURN_TO_HIGH_LEVEL_MODEL=true
STOP=true
```

Do not “rollback” by reflashing; both application slots are already exact.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK
```

### 10.1 Purpose

Release Board A BOOT/GPIO9 from the intentional ROM-download state, perform exactly one clean normal boot, and prove through the actual remote T1 that the normalized Board A returns to stable Direct runtime while preserving its existing identity/security state.

### 10.2 Frozen inputs

```text
EXPECTED_FIRMWARE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS
EXPECTED_SELECTED_SLOT=1
BOARD_A_DIRECT_BASELINE=PASS
EXPECTED_DIRECT_CHANNEL_ENVIRONMENT=11
REMOTE_T1_OBSERVER_TYPE=MANAGER_CANONICAL_ACCEPTANCE
```

### 10.3 Required proof / operations

```text
1. operator confirms BOOT/GPIO9 fully released;
2. full Board A power-off, then one normal power-on with BOOT not pressed;
3. do not open serial and do not enter ROM intentionally;
4. fresh read-only rebind of actual remote T1;
5. observe up to 90 s for Board A canonical Direct telemetry;
6. prove >=6 accepted, 0 rejected, 0 duplicates, direct ingress, monotonic seq, single boot session;
7. read-only verify no pairing retrigger and existing identity/credential/key/peer-trust generations are unchanged;
8. STOP and return structured closure.
```

### 10.4 PASS

```text
BOARD_A_RELEASE_BOOT_AND_POSTCHECK=PASS
BOARD_A_NORMAL_APPLICATION_BOOT=PASS
BOARD_A_POSTCHECK_DIRECT_ACCEPTED>=6
BOARD_A_POSTCHECK_REJECTED=0
BOARD_A_POSTCHECK_DUPLICATE=0
BOARD_A_EXISTING_IDENTITY_PRESERVED=true
PAIRING_RETRIGGERED=false
READY_FOR_BOARD_B_OBSERVABILITY_REFRESH=true
```

### 10.5 FAIL / STOP

If BOOT release is unconfirmed:

```text
RESULT=STOP_PENDING_OPERATOR
```

If one clean normal boot produces no acceptable T1 evidence within 90 s:

```text
BOARD_A_RELEASE_BOOT_AND_POSTCHECK=FAIL_APPLICATION_POSTCHECK_NOT_OBSERVED
READY_FOR_BOARD_B_OBSERVABILITY_REFRESH=false
STOP=true
```

If rejected/duplicate/session/identity state contradicts baseline:

```text
BOARD_A_RELEASE_BOOT_AND_POSTCHECK=FAIL_RUNTIME_OR_IDENTITY_INVARIANT
READY_FOR_BOARD_B_OBSERVABILITY_REFRESH=false
STOP=true
```

Codex must not automatically retry or enter Board B.

---

## 11. Hard Allowed / Forbidden Scope

Default:

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- operator release of Board A BOOT/GPIO9;
- one full Board A power-cycle for normal application boot;
- Board A power/USB connection required for that normal boot;
- remote T1 SSH/read-only Manager/Broker observation;
- private identity matching and sanitized closure generation;
- bounded local evidence-file write if required for the closure.
```

### FORBIDDEN

```text
- FLASH_READ
- FLASH_WRITE
- FLASH_ERASE
- NVS_READ
- NVS_WRITE
- OTADATA_WRITE
- BOOTLOADER_WRITE
- PARTITION_TABLE_WRITE
- APP0_WRITE
- APP1_WRITE
- FACTORY_IMAGE_FLASH
- SERIAL_OPEN
- intentional ROM entry after the operator releases BOOT
- second automatic power-cycle/retry
- Board B access
- T1/Broker/Manager/HomeAssistant mutation or restart
- AP mutation
- source/GitHub mutation by Codex physical executor
- pairing/credential/application-key/peer-trust mutation
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=sanitized_private_execution_evidence_only
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required.

Mechanically compile this DSL into the minimum necessary commands
using already-installed tools, then execute exactly this bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not retry.
Do not enter Board B.
Do not replay app0 flash normalization.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

TASK=N3W_KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK_20260907_01
AUTHORIZATION=N3W_KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK_20260907_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

Before claim require explicit operator state:

BOARD_A_BOOT_GPIO9_RELEASED=true

If not explicitly confirmed:
RESULT=STOP_PENDING_OPERATOR
STOP.

On first physical normal-power action:
AUTHORIZATION_CLAIMED=true

At the end of this one-shot gate:
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

============================================================
1. FROZEN INPUTS
============================================================

PRODUCT_SOURCE_AUTHORITY=
483ff1c662dc74d6e12529e27a69819e68160f9e

PRODUCT_SOURCE_TREE=
300b8fae886c954fe888edee17d6810e3c979bdc

BOARD_A_APP0_SHA256=
efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d

BOARD_A_APP1_SHA256=
efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d

BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS
EXPECTED_SELECTED_SLOT=1

REMOTE_T1_AUTHORITY_PREVIOUS=PASS
REMOTE_T1_OBSERVER_TYPE=MANAGER_CANONICAL_ACCEPTANCE

============================================================
2. HARD SCOPE
============================================================

BOARD_A_ACCESS=true
BOARD_A_POWER_CYCLE=true

SERIAL_OPEN=false
FLASH_READ=false
FLASH_WRITE=false
FLASH_ERASE=false
NVS_READ=false
NVS_WRITE=false
OTADATA_WRITE=false

BOARD_B_ACCESS=false

T1_READ_ONLY=true
T1_MUTATION=false
BROKER_MUTATION=false
MANAGER_MUTATION=false
HOMEASSISTANT_MUTATION=false
AP_MUTATION=false

PAIRING_MUTATION=false
CREDENTIAL_MUTATION=false
APPLICATION_KEY_MUTATION=false
PEER_TRUST_MUTATION=false

AUTO_RETRY=false

============================================================
3. OPERATOR RELEASE PRECLAIM
============================================================

Require explicit confirmation:

BOARD_A_BOOT_GPIO9_RELEASED=true
BOARD_A_BOOT_BUTTON_NOT_HELD=true

Do not infer release merely from elapsed time.

If confirmation absent:
STOP_PENDING_OPERATOR.

============================================================
4. ONE CLEAN NORMAL BOOT
============================================================

With BOOT/GPIO9 released:

- remove all Board A power sources;
- wait a bounded few seconds for full power-down;
- reconnect normal lab power/USB without pressing BOOT or RESET;
- perform no second power cycle.

Output:

BOARD_A_NORMAL_BOOT_POWER_CYCLE=EXECUTED

Do not open serial.

============================================================
5. FRESH REMOTE T1 REBIND
============================================================

Recover actual remote T1 authority.
Do not use localhost as substitute.

Require:

REMOTE_T1_AUTHORITY_FOUND=PASS
REMOTE_T1_RUNTIME_BINDING=PASS
REMOTE_T1_LIVE_OBSERVER_AVAILABLE=true

No service restart.

============================================================
6. POSTCHECK WINDOW
============================================================

Observe exact Board A private identity for up to 90 seconds.

Record:

POSTCHECK_WINDOW_START=
POSTCHECK_WINDOW_END=

POSTCHECK_T1_DIRECT_ACCEPTED=
POSTCHECK_T1_DIRECT_REJECTED=
POSTCHECK_T1_DIRECT_DUPLICATE=
POSTCHECK_T1_SEQ_FIRST=
POSTCHECK_T1_SEQ_LAST=
POSTCHECK_T1_INGRESS_SOURCE=
POSTCHECK_SINGLE_BOOT_SESSION=

PASS telemetry requirements:

POSTCHECK_T1_DIRECT_ACCEPTED>=6
POSTCHECK_T1_DIRECT_REJECTED=0
POSTCHECK_T1_DIRECT_DUPLICATE=0
POSTCHECK_T1_INGRESS_SOURCE=direct
POSTCHECK_SINGLE_BOOT_SESSION=true
sequence monotonically advances

============================================================
7. PRODUCT-STATE READONLY INVARIANTS
============================================================

Using existing read-only Manager authority verify:

PAIRING_RETRIGGERED=false
BOARD_A_EXISTING_IDENTITY_PRESERVED=true
CREDENTIAL_GENERATION_UNCHANGED=true
APPLICATION_KEY_EPOCH_UNCHANGED=true
PEER_TRUST_GENERATION_UNCHANGED=true

Do not expose raw identity or secret material.

============================================================
8. ADJUDICATION
============================================================

If telemetry and state invariants all pass:

BOARD_A_NORMAL_APPLICATION_BOOT=PASS
BOARD_A_RELEASE_BOOT_AND_POSTCHECK=PASS
READY_FOR_BOARD_B_OBSERVABILITY_REFRESH=true
RESULT=PASS
NEXT_ROUTE=KF089_OBSERVABILITY_BOARD_B_REFRESH_AND_DURABLE_DIRECT_BASELINE

Otherwise:

BOARD_A_RELEASE_BOOT_AND_POSTCHECK=FAIL_<EXACT_CLASS>
READY_FOR_BOARD_B_OBSERVABILITY_REFRESH=false
RESULT=FAIL
NEXT_ROUTE=STOP

No repair.
No retry.
No Board B access.

============================================================
9. HARD STOP
============================================================

Return the exact structured closure and STOP.
```

---

## 13. Expected Closure

```text
=== N3W KF089 BOARD A RELEASE BOOT + POSTCHECK CLOSURE ===

TASK=N3W_KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK_20260907_01

AUTHORIZATION=
AUTHORIZATION_GRANTED=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=
REPLAY_PERMITTED=false

BOARD_A_BOOT_GPIO9_RELEASED=
BOARD_A_BOOT_BUTTON_NOT_HELD=
BOARD_A_NORMAL_BOOT_POWER_CYCLE=

REMOTE_T1_AUTHORITY_FOUND=
REMOTE_T1_RUNTIME_BINDING=
REMOTE_T1_LIVE_OBSERVER_AVAILABLE=

POSTCHECK_WINDOW_START=
POSTCHECK_WINDOW_END=

POSTCHECK_T1_DIRECT_ACCEPTED=
POSTCHECK_T1_DIRECT_REJECTED=
POSTCHECK_T1_DIRECT_DUPLICATE=
POSTCHECK_T1_SEQ_FIRST=
POSTCHECK_T1_SEQ_LAST=
POSTCHECK_T1_INGRESS_SOURCE=
POSTCHECK_SINGLE_BOOT_SESSION=

PAIRING_RETRIGGERED=
BOARD_A_EXISTING_IDENTITY_PRESERVED=
CREDENTIAL_GENERATION_UNCHANGED=
APPLICATION_KEY_EPOCH_UNCHANGED=
PEER_TRUST_GENERATION_UNCHANGED=

SERIAL_OPEN=false
FLASH_READ=false
FLASH_WRITE=false
NVS_READ=false
NVS_WRITE=false
BOARD_B_ACCESS=false
T1_MUTATION=false
AP_MUTATION=false

BOARD_A_NORMAL_APPLICATION_BOOT=
BOARD_A_RELEASE_BOOT_AND_POSTCHECK=
READY_FOR_BOARD_B_OBSERVABILITY_REFRESH=

PRODUCT_FAILURE=
RESULT=
NEXT_ROUTE=

=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=KF089_OBSERVABILITY_BOARD_B_REFRESH_AND_DURABLE_DIRECT_BASELINE
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true
```

Board B flash/ROM/NVS work requires a separately bounded physical authorization and fresh Board B identity/partition/artifact rebind.

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
BOARD_B_ACCESS=false
```

Do not modify product source from a single failed postcheck without further classification.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
```

Reason: the current “still in ROM until BOOT/GPIO9 is released” boundary is covered by existing `KF-088` physical-harness ROM/GPIO9 guard and does not allocate a new failure ID. The earlier intrusive serial-open behavior is retained in the current-state/progress archives and maps to existing flash/boot/serial oracle-separation guards; this handoff introduces no new root-cause claim.

---

## 16. New Chat Start Prompt

```text
阅读《N3W_KF089_BOARD_A_DUAL_SLOT_NORMALIZED_POSTCHECK_PREEXECUTION_NEW_CHAT_HANDOFF_V1.0_20260907.md》。

同时读取：

1. exact handoff standard authority：
   4300890dff0ce63d5a547df21426e287d084d9ee

   - docs/development/NEW_CHAT_HANDOFF_STANDARD.md
   - docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

2. current main：
   - docs/development/N3W_CURRENT_STATE.md
   - docs/development/N3W_CURRENT_STATE_INDEX.md
   - docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
   - docs/development/N3W_KF089_BOARD_A_APP0_NORMALIZATION_PROGRESS_20260907.md

继续“温室环境监测系统（ESP32-C6）”。

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false

必须每次先写：
主线任务
支线任务
当前任务

当前只进入：
NEXT_ONE_GATE=KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK

Board A 已经完成：
BOARD_A_DIRECT_BASELINE=PASS
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS

当前 Board A 仍停在 ROM Download Mode；不得重放 app0 flash。
下一步必须先要求/确认现场已释放 BOOT/GPIO9，随后只执行一次正常 power-cycle 和 remote-T1 postcheck。

用户已经明确授权这个 exact release + normal-boot + read-only-T1 postcheck gate；
不得自动扩展到 Board B。

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

禁止：
serial open、Flash/NVS 读写、app0/app1 写入、T1/Manager/Broker/HA mutation、AP mutation、Board B access、自动 retry。

PASS 后只返回高阶模型裁决；不要自动进入 Board B。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=KF089_PHYSICAL_CLOSURE
CURRENT_STOP_POINT=BOARD_A_DUAL_SLOT_NORMALIZED_ROM_MODE_POSTCHECK_PENDING

PRODUCT_SOURCE_AUTHORITY=483ff1c662dc74d6e12529e27a69819e68160f9e
PRODUCT_SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
FIRMWARE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d

KF089_STARTUP_GATE_REPAIR=PASS
BOARD_A_DIRECT_BASELINE=PASS
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS
BOARD_A_CURRENT_MODE=ROM_DOWNLOAD_MODE
BOARD_A_POSTCHECK=PENDING_BOOT_GPIO9_RELEASE

SOURCE_DEFECT_PROVEN=false
PRODUCT_FAILURE=false
CURRENT_BLOCKER=OPERATOR_RELEASE_BOOT_THEN_NORMAL_APP_POSTCHECK

BOARD_B_OBSERVABILITY_REFRESH=NOT_EXECUTED
KF089_AUTONOMOUS_RELAY_ACQUISITION=OPEN

NEXT_ONE_GATE=KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

HANDOFF_STANDARD_VERSION=1.0
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
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
