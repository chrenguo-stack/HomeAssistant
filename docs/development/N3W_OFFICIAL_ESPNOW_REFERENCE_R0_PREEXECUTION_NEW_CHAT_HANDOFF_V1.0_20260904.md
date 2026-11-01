# 温室环境监测系统（ESP32-C6）
# N3-W Official ESP-NOW Reference Baseline R0
# 新会话交接文档 V1.0 — 2026-09-04

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文严格按 exact handoff authority `4300890dff0ce63d5a547df21426e287d084d9ee` 中的：  
> `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`  
> `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`  
> 生成。  
> 如本文与 exact repository/runtime/live evidence 冲突，以更高 authority 为准，并先停止执行、完成 rebind。

---

## 0. 会话切换结论

本轮已完成 Board B 真实空间 cold-boot Relay 测试、诊断支线与公共归档，并由源码直接证明 KF-089：已配对节点在 Direct Wi-Fi 不可用条件下冷启动时，当前产品 startup gate 会阻止 Relay-capable N3-W runtime 初始化。

随后完成了“产品源码最小修复设计”，但用户决定在实施产品修复前，先建立一套 **Espressif 官方 ESP-NOW 原版参考基线**：同 ESP32-C6、尽可能同 exact ESP-IDF revision，先跑通官方 example，再逐层加入 Wi-Fi coexistence 和 N3-W 语义。

本轮因此在“官方 reference R0 开始前”切换会话。下一会话不要直接修改产品源码，也不要直接刷板；先执行唯一的 source/toolchain authority + host compile preclaim。

```text
CURRENT_STAGE=N3W_OFFICIAL_ESPNOW_REFERENCE_BASELINE_PREPARATION
CURRENT_STOP_POINT=BEFORE_R0_EXACT_IDF_SOURCE_AUTHORITY_AND_HOST_COMPILE_PRECLAIM
NEXT_ONE_GATE=N3W_OFFICIAL_ESPNOW_REFERENCE_R0_SOURCE_AUTHORITY_AND_HOST_COMPILE_PRECLAIM
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘全部历史，而是从上述 `NEXT_ONE_GATE` 开始。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护产品路线与架构边界；
- 维护 exact-main / upstream-IDF / artifact / runtime authority；
- 设计 gate、scope、authorization、rollback；
- 根据 Codex closure 做 PASS / FAIL / STOP 分类；
- 区分 product/runtime/infrastructure/CI/physical-harness defect；
- 决定官方 reference 结果如何回迁到产品设计；
- 防止 reference harness 或测试框架演化为第二套产品架构。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL contract；
- 运行必要的 Git/shell/toolchain/test/compile 命令；
- 使用已安装工具完成最小解析与 evidence capture；
- mutation 只能发生在明确授权边界内；
- 第一处 substantive failure 后 fail-closed STOP；
- 返回结构化 closure。

Codex 不得自行扩大 scope、修复、重放 consumed authorization、跨越下一 gate。

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

Codex 必须将 DSL 中的 `inspect / derive / resolve / verify / materialize bounded temp source / compile / hash` 等 primitive 机械翻译为最低必要命令执行。除非合同明确要求 exact supplied implementation，否则不得因为缺少预写 Bash/Python executor 而停止。

### 1.4 标准交互循环

```text
高阶模型：分析 / gate / 最小授权设计
        ↓
用户：批准需要 mutation 的 exact authorization
        ↓
Codex：DSL compile → exact execution → closure
        ↓
高阶模型：复核 closure / 决定下一步
```

当前 `NEXT_ONE_GATE` 不允许 live/board mutation，只允许 bounded local temporary build writes，因此不需要先取得两板 flash authorization。

---

## 2. Product North Star

当前产品路线：

```text
NORTH_STAR=N3W_THREE_BOARD_T1_REAL_WORLD_PATH_FAILOVER_VALIDATION

CURRENT_REFERENCE_ROUTE=
OFFICIAL_ESPNOW_REFERENCE_BASELINE
→ WIFI_ESPNOW_COEXISTENCE_REFERENCE
→ INCREMENTAL_N3W_REINTRODUCTION
→ REEVALUATE_KF089_PRODUCT_REPAIR
→ RETURN_TO_REAL_WORLD_PATH_FAILOVER_VALIDATION
```

最终阶段目标：

```text
PROVISIONED_NODE_BEHAVIOR:
- Wi-Fi available → Direct preferred
- Wi-Fi unavailable → discover nearby trusted N3-W node via ESP-NOW
- Relay telemetry reaches T1/Manager
- later Wi-Fi recovery → Direct recovery
- no factory-known peer MAC
- no factory binding to other nodes
- stable node identity / credential / application-key / peer-trust lifecycles preserved
```

当前不得进入：

```text
KF089_PRODUCT_SOURCE_IMPLEMENTATION
PR361_MERGE
FURTHER_BOARD_B_SPATIAL_SEARCH
LIVE_DIRECT_TO_RELAY_ACCEPTANCE_CLAIM
MANAGER_OR_BROKER_REPAIR
ESPRESSIF_ESP_NOW_SOLUTION_FRAMEWORK_ADOPTION
```

---

## 3. Frozen Authorities

只列下一会话继续所需的 current authorities。

### 3.1 Repository / exact-main

交接生成前 exact repository authority：

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN_AT_HANDOFF_INPUT=bff94bc4922d7a984eb1363cc24a163ad466a166
TREE_AT_HANDOFF_INPUT=4ec885dba21c2b90b7788e3bfbdac69afd461d2e
MAIN_MESSAGE=Merge PR #362: docs: archive Board B real-world failover diagnostics
```

本 handoff/design 为 docs-only 后继提交；因此新会话第一步必须 fresh read-back 当前 `main`，并区分：

```text
REPOSITORY_MAIN_TIP
vs
PRODUCT_SOURCE_AUTHORITY
```

产品源码未因 docs-only archive/handoff 改变：

```text
PRODUCT_SOURCE_AUTHORITY=bff94bc4922d7a984eb1363cc24a163ad466a166
```

Exact handoff standard authority：

```text
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD_PATH=docs/development/NEW_CHAT_HANDOFF_STANDARD.md
HANDOFF_TEMPLATE_PATH=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
```

### 3.2 Candidate / artifact / image

官方 reference candidate 尚未 materialize：

```text
UPSTREAM_REPOSITORY=espressif/esp-idf
UPSTREAM_EXAMPLE_PATH=examples/wifi/espnow
TARGET_SOC=ESP32-C6
TARGET_IDF_REVISION=TO_BE_DERIVED_BY_NEXT_GATE
REFERENCE_SOURCE_ARTIFACT=NOT_YET_MATERIALIZED
REFERENCE_BUILD_ARTIFACT=NOT_YET_CREATED
```

当前工程工具链事实：

```text
ESPHOME_VERSION=2026.4.3
ESPTOOL_VERSION_LAST_BOUND=5.3.1
TARGET_FRAMEWORK=ESP-IDF
```

Exact ESP-IDF revision/version **不得从记忆猜测**；必须由下一 Gate 的 current toolchain/build metadata 建立 authority，再绑定 official example 同 revision。

### 3.3 Successor / deployment material

```text
SUCCESSOR_AUTHORITY=NOT_APPLICABLE:REFERENCE_R0_HAS_NO_DEPLOYMENT_SUCCESSOR_YET
```

### 3.4 Target host / runtime authority

```text
R0_HOST=USER_MAC
R0_HOST_ARCH_LAST_KNOWN=x86_64
R0_PHYSICAL_TARGET_FAMILY=ESP32-C6
T1_REQUIRED_FOR_NEXT_GATE=false
BOARD_REQUIRED_FOR_NEXT_GATE=false
```

Diagnostic branch remains separate:

```text
DIAGNOSTIC_PR=361
DIAGNOSTIC_PR_STATE=DRAFT_OPEN_UNMERGED
DIAGNOSTIC_HEAD=a4a8a8784de5f4b99ffd61a2cdf2f40e01ee0a41
DIAGNOSTIC_BRANCH=diag/n3w-boardb-radio-reset-observability-20260904
```

Public test/debug archive authority:

```text
DEBUG_ARCHIVE=docs/development/N3W_BOARD_B_REAL_WORLD_FAILOVER_DEBUG_ARCHIVE_20260904.md
KF_DISPOSITION=docs/development/N3W_BOARD_B_REAL_WORLD_FAILOVER_KF087_KF089_DISPOSITION_20260904.md
DEFERRED_REPAIR_DESIGN=docs/development/N3W_KF089_MINIMAL_PRODUCT_REPAIR_DESIGN_DEFERRED_20260904.md
```

---

## 4. Current Live Baseline

The next gate does not depend on live T1/product runtime, but the latest physical state must not be silently forgotten.

```text
MANAGER_STATE=LAST_OBSERVED_HEALTHY_FOR_BOARD_A_DIRECT_AND_PRIOR_BOARD_B_TESTS
MANAGER_STATE_REQUIRES_FRESH_READONLY_REBIND=true

BROKER_STATE=LAST_OBSERVED_FUNCTIONAL_FOR_ACCEPTED_DIRECT_TELEMETRY
BROKER_STATE_REQUIRES_FRESH_READONLY_REBIND=true

HOMEASSISTANT_STATE=NOT_REQUIRED_BY_NEXT_GATE

PAIRING_SERVICE_STATE=NOT_REQUIRED_BY_NEXT_GATE
PAIRING_PORT_OWNER_STATE=NOT_REQUIRED_BY_NEXT_GATE
```

Latest board state at physical-test stop point:

```text
BOARD_A_LAST_OBSERVED_MANAGER_ACCEPTED=true
BOARD_A_LAST_OBSERVED_PATH=Direct
BOARD_A_LIVE_STATE_REQUIRES_FRESH_READONLY_REBIND=true

BOARD_B_LAST_CONFIRMED_POWER_SOURCE=BATTERY
BOARD_B_LAST_CONFIRMED_APPLICATION_VISUALLY_ALIVE=true
BOARD_B_LAST_POSITION_CLASS=NO_ACCEPTED_TELEMETRY_ZONE
BOARD_B_LAST_MANAGER_ACCEPTED=false
BOARD_B_CURRENT_LIVE_STATE_REQUIRES_FRESH_REBIND_BEFORE_ANY_PHYSICAL_USE=true

BOARD_C_ACCESS_IN_CURRENT_TEST=false
```

Next-gate hard defaults:

```text
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
T1_MUTATION=false
```

---

## 5. Proven Current Facts

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_REGRESSION=FROZEN_PASS

BOARD_B_DIRECT_RUNTIME_PREVIOUSLY_PROVEN=true
BOARD_B_BATTERY_ONLY_DIRECT_RUNTIME_PREVIOUSLY_PROVEN=true
BOARD_A_DIRECT_RUNTIME_PREVIOUSLY_PROVEN=true

BOARD_B_COLD_BOOT_AT_WIFI_GOOD_LOCATION=Direct
BOARD_B_COLD_BOOT_AT_FARTHER_LOCATIONS=NO_ACCEPTED_TELEMETRY

COLD_BOOT_RELAY_ACQUISITION_SOURCE_DEFECT=PROVEN
ROOT_CAUSE=PRODUCT_RUNTIME_STARTUP_REQUIRES_WIFI_CONNECTED
FAILURE_CLASS=RUNTIME_BOOTSTRAP_ARCHITECTURE

LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED

PR361_DIAGNOSTIC_INSTRUMENTATION_CI=PASS_AT_a4a8a878
PR361_MERGED=false

KF087_SOURCE_ARTIFACT_BOARD_BINDING=RESOLVED
KF088_CONTROLLED_RESET_ROM_DOWNLOAD_MODE=OPEN_ROOT_CAUSE_TBD
KF089_PROVISIONED_COLD_BOOT_RELAY=OPEN_PRODUCT_DEFECT
```

Further source facts retained for later repair design:

```text
CURRENT_WIFI_ESPNOW_RADIO_ARBITRATION=DESIGN_GAP_CONFIRMED
CURRENT_DISCOVERY_FAILED_CHANNEL_SWITCH_BACKOFF=DESIGN_GAP_CONFIRMED
CURRENT_ASYNC_TX_RESULT_HANDLING=DESIGN_GAP_CONFIRMED
```

The first two are directly relevant to safe future Discovery design. The async TX gap is real but is not proven to be the KF-089 cold-boot blocker.

Inference/proposal, not proven product authority:

```text
INFERENCE_OFFICIAL_REFERENCE_WILL_REDUCE_INTEGRATION_UNCERTAINTY=true
PROPOSED_STRATEGY=RUN_UNMODIFIED_OFFICIAL_REFERENCE_BEFORE_PRODUCT_REPAIR
```

---

## 6. Current Root Cause / Blockers

### Blocker A — KF-089 provisioned cold-boot startup architecture

```text
ROOT_CAUSE=PRODUCT_RUNTIME_STARTUP_REQUIRES_WIFI_CONNECTED
PROVEN_BY=READ_ONLY_CURRENT_PRODUCT_SOURCE_REVIEW_PLUS_PHYSICAL_COLD_BOOT_OBSERVATIONS
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=COLD_BOOT_RELAY_PATH_ONLY
```

Current `SimpleProductComponent::start_runtime_if_ready_()` requires current Wi-Fi association before ESP-NOW initialization and runtime start. This deterministically prevents a provisioned node from acquiring Relay on cold boot when Direct Wi-Fi cannot associate.

### Blocker B — no official same-IDF ESP-NOW physical reference baseline yet

```text
OFFICIAL_REFERENCE_BASELINE_PROVEN=false
EXACT_TARGET_IDF_REVISION_BOUND=false
UNMODIFIED_OFFICIAL_EXAMPLE_HOST_COMPILE_PROVEN=false
UNMODIFIED_OFFICIAL_EXAMPLE_PHYSICAL_PASS=false
```

This blocker is methodological: before modifying the product, the project now requires a minimal official reference baseline to separate hardware/IDF semantics from N3-W integration semantics.

---

## 7. Closed / Forbidden Routes

除非出现新的 direct counter-evidence，下一会话不得重新进入：

```text
BOARD_B_GPIO9_DEEP_FORENSICS=CLOSED:normal_power_cycle_restored_product_and_mainline_no_longer_depends_on_exact_transient_source

FURTHER_ZONE_C_SPATIAL_BRACKETING_BEFORE_SOURCE_OR_REFERENCE_WORK=CLOSED:KF089_source_blocker_proven

PR361_AS_PRODUCT_REPAIR_BASE=FORBIDDEN:diagnostic_only_branch_must_remain_separate
PR361_MERGE=FORBIDDEN_UNLESS_SEPARATELY_AUTHORIZED

DELETE_WIFI_CONNECTED_GUARD_ONLY=FORBIDDEN:existing_runtime_start_contract_still_requires_valid_direct_channel_and_initial_DIRECT_state

MANAGER_BROKER_DYNSEC_REPAIR=FORBIDDEN:no_current_evidence_they_cause_KF089

ESPRESSIF_ESP_NOW_SOLUTION_FRAMEWORK=DEFERRED_TOO_BROAD:use_minimal_esp-idf_examples/wifi/espnow_reference_first

COLD_BOOT_TEST_RESULT_AS_LIVE_FAILOVER_RESULT=FORBIDDEN:live_Direct_to_Relay_remains_unadjudicated
```

---

## 8. Authorization Ledger

No live/physical authorization is active at handoff.

```text
AUTHORIZATION=PR361_MERGE
CLAIMED=false
CONSUMED=false
RESULT=NOT_AUTHORIZED
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
```

```text
AUTHORIZATION=KF089_PRODUCT_SOURCE_REPAIR_IMPLEMENTATION
CLAIMED=false
CONSUMED=false
RESULT=DEFERRED_BEFORE_IMPLEMENTATION
REPLAY_PERMITTED=false
SUPERSEDED_BY=OFFICIAL_ESPNOW_REFERENCE_ROUTE_FOR_NOW
```

```text
PROPOSED_AUTHORIZATION=N3W_OFFICIAL_ESPNOW_REFERENCE_R0_TWO_BOARD_PHYSICAL_FLASH
GRANTED=false
```

The next one gate is host-only/read-only with bounded temporary build writes and does not claim the above physical authorization.

---

## 9. Rollback Authority

The next gate does not mutate live product/runtime/boards or repository persistent state.

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:HOST_ONLY_REFERENCE_SOURCE_AND_COMPILE_PRECLAIM
LIVE_RUNTIME_MUTATION=false
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
SECOND_ATTEMPT_ALLOWED=false
```

Bounded temporary files created for source materialization/compile must be disposable and must not be promoted into repository authority by the next gate.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_OFFICIAL_ESPNOW_REFERENCE_R0_SOURCE_AUTHORITY_AND_HOST_COMPILE_PRECLAIM
```

### 10.1 Purpose

Establish the exact ESP-IDF revision actually used by the current ESPHome 2026.4.3 ESP32-C6 build environment, bind Espressif's unmodified `examples/wifi/espnow` at the same revision, and prove that the unmodified official example can be configured/compiled for ESP32-C6 in a disposable host workspace. Do not flash or access any board.

### 10.2 Frozen inputs

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRODUCT_SOURCE_AUTHORITY=bff94bc4922d7a984eb1363cc24a163ad466a166
ESPHOME_VERSION_EXPECTED=2026.4.3
TARGET_SOC=ESP32-C6
UPSTREAM_REPOSITORY=https://github.com/espressif/esp-idf.git
UPSTREAM_EXAMPLE_PATH=examples/wifi/espnow
UPSTREAM_REVISION_POLICY=MUST_MATCH_DERIVED_CURRENT_TARGET_IDF_AUTHORITY
```

### 10.3 Required proof / operations

```text
1. Fresh read-back repository main and handoff/archive files.
2. Prove local ESPHome version is exactly 2026.4.3; otherwise STOP.
3. Derive exact ESP-IDF version/revision used by the current ESP32-C6 toolchain from authoritative installed package/build metadata; do not guess.
4. Corroborate that revision against the available framework/package metadata. Ambiguity => STOP.
5. In a disposable temporary workspace only, materialize official Espressif esp-idf at that exact revision using existing Git/network tooling. No package/tool installation.
6. Bind exact upstream commit and exact `examples/wifi/espnow` file/tree hashes.
7. Verify the official example declares/supports ESP32-C6 at that revision. If not, STOP.
8. Configure/build the official example for ESP32-C6 using the exact bound IDF toolchain/revision, without product/N3-W source edits.
9. Record build artifact identity/hash and relevant compile metadata.
10. Prove repository worktree/product source unchanged, no board access, no T1/runtime mutation.
11. STOP and return closure. Do not flash.
```

### 10.4 PASS

```text
OFFICIAL_ESPNOW_R0_SOURCE_AUTHORITY=PASS
EXACT_TARGET_IDF_REVISION_BOUND=true
UNMODIFIED_OFFICIAL_EXAMPLE_BOUND=true
ESP32C6_SUPPORT_PROVEN=true
UNMODIFIED_OFFICIAL_EXAMPLE_HOST_COMPILE=PASS
READY_FOR_R0_TWO_BOARD_PHYSICAL_AUTHORIZATION=true
```

### 10.5 FAIL

Examples:

```text
GATE_RESULT=FAIL_ESPHOME_VERSION_DRIFT
GATE_RESULT=FAIL_IDF_AUTHORITY_AMBIGUOUS
GATE_RESULT=FAIL_UPSTREAM_REVISION_UNAVAILABLE
GATE_RESULT=FAIL_ESP32C6_UNSUPPORTED_AT_BOUND_REVISION
GATE_RESULT=FAIL_OFFICIAL_EXAMPLE_COMPILE
GATE_RESULT=FAIL_TOOLCHAIN_UNAVAILABLE
```

Any FAIL:

```text
READY_FOR_R0_TWO_BOARD_PHYSICAL_AUTHORIZATION=false
AUTO_REPAIR=false
STOP=true
```

Codex 不得自动进入物理 flash gate。

---

## 11. Hard Allowed / Forbidden Scope

Default：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- read current Git repository metadata/files
- inspect already-installed ESPHome / PlatformIO / ESP-IDF package and build metadata
- run version/configuration/read-only tool queries
- use Git/network to fetch exact public Espressif upstream source into a disposable temp workspace
- create bounded disposable local workspace for official reference source and compile outputs
- run host configuration/compile for the official example
- calculate SHA/hash/size/provenance metadata
- remove or leave clearly disposable temp workspace after evidence capture
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=DISPOSABLE_LOCAL_TEMP_WORKSPACE_ONLY
```

### FORBIDDEN

```text
- modify HomeAssistant product source
- commit/push repository changes
- modify PR #361
- access Board A/B/C
- USB/serial open
- flash/erase/reset/BOOT operation
- NVS read/write
- RF execution
- T1 SSH or mutation unless strictly needed to read a repository fact; default is no T1 access
- Manager/Broker/HA/DynSec mutation
- install or upgrade ESPHome/PlatformIO/ESP-IDF/toolchain packages
- silently substitute a different ESP-IDF revision because compile is easier
- edit the official ESP-NOW example to make it compile
- adopt the larger `espressif/esp-now` solution framework
- auto-enter physical R0 after compile PASS
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required unless
this protocol explicitly says so.

Mechanically compile this DSL into the minimum necessary commands
using already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not install tooling.
Do not retry with a different IDF revision.
Do not access or flash boards.
Do not enter the next gate.

============================================================
0. EXECUTION STATUS
============================================================

EXECUTION_ID=N3W-OFFICIAL-ESPNOW-R0-SOURCE-AUTHORITY-HOST-COMPILE-PRECLAIM-20260904-01
AUTHORIZATION=NOT_REQUIRED_HOST_ONLY_PRECLAIM
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
RF_EXECUTION=false

============================================================
1. FROZEN INPUTS
============================================================

REPOSITORY=chrenguo-stack/HomeAssistant
PRODUCT_SOURCE_AUTHORITY=bff94bc4922d7a984eb1363cc24a163ad466a166
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
ESPHOME_VERSION_EXPECTED=2026.4.3
TARGET_SOC=ESP32-C6
UPSTREAM_REPOSITORY=https://github.com/espressif/esp-idf.git
UPSTREAM_EXAMPLE_PATH=examples/wifi/espnow

============================================================
2. HARD SCOPE
============================================================

ALLOWED:
- local repository read-only rebind
- installed toolchain/package metadata inspection
- public upstream fetch into disposable local temp workspace
- official unmodified example configure/compile
- local temp evidence/hash generation

FORBIDDEN:
- HomeAssistant repository writes
- product source edits
- PR #361 writes
- tool installation/upgrade
- board/USB/serial/flash/NVS/RF
- T1/runtime mutation
- official example modification
- alternative-IDF fallback

============================================================
3. REPOSITORY / STANDARD REBIND
============================================================

Read current remote/local main.
Record:
CURRENT_MAIN=
CURRENT_TREE=

Read/verify:
- this handoff
- exact standard/template at HANDOFF_STANDARD_AUTHORITY
- current KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- N3W_BOARD_B_REAL_WORLD_FAILOVER_KF087_KF089_DISPOSITION_20260904.md
- N3W_KF089_MINIMAL_PRODUCT_REPAIR_DESIGN_DEFERRED_20260904.md

If any required authority cannot be uniquely rebound:
STOP=FAIL_REPOSITORY_OR_HANDOFF_AUTHORITY

Documentation-only main advancement is allowed, but PRODUCT_SOURCE_AUTHORITY
must remain separately recorded. Do not silently redefine product source.

============================================================
4. LOCAL TOOLCHAIN AUTHORITY
============================================================

Prove exact ESPHome version.

If ESPHOME_VERSION != 2026.4.3:
STOP=FAIL_ESPHOME_VERSION_DRIFT

Derive the exact ESP-IDF version/revision used for the current ESP32-C6
ESPHome toolchain using authoritative installed package/build metadata.
Use more than a display string if necessary; bind package/version/revision
or equivalent exact provenance.

Record:
IDF_VERSION=
IDF_REVISION=
IDF_AUTHORITY_SOURCE=
IDF_AUTHORITY_UNIQUE=true|false

If exact revision cannot be uniquely established:
STOP=FAIL_IDF_AUTHORITY_AMBIGUOUS

Do not install or change tooling.

============================================================
5. UPSTREAM EXACT REFERENCE BINDING
============================================================

Create a new disposable temp root outside the authoritative product source worktree.

Using existing Git/network tooling only, materialize:
UPSTREAM_REPOSITORY
at exact IDF_REVISION.

Verify repository HEAD exactly equals IDF_REVISION or an exact canonical commit
proven equivalent to the derived framework authority.

Bind:
UPSTREAM_HEAD=
UPSTREAM_TREE=
OFFICIAL_EXAMPLE_TREE_OR_FILE_HASHES=

Verify UPSTREAM_EXAMPLE_PATH exists at that exact revision.
Do not edit any upstream file.

If exact revision/source cannot be fetched:
STOP=FAIL_UPSTREAM_REVISION_UNAVAILABLE

============================================================
6. ESP32-C6 SUPPORT PRECLAIM
============================================================

Read the official example metadata/readme/CMake/Kconfig needed to establish
that the bound example supports ESP32-C6.

ESP32C6_SUPPORT_PROVEN=true|false

If false or ambiguous:
STOP=FAIL_ESP32C6_UNSUPPORTED_AT_BOUND_REVISION

============================================================
7. UNMODIFIED HOST COMPILE
============================================================

Configure exact official example for target esp32c6 using the exact bound IDF.
Use only existing tooling.

Do not modify example source to resolve errors.
Do not substitute another chip/revision.

Run compile.

Record:
REFERENCE_CONFIGURE=PASS|FAIL
REFERENCE_COMPILE=PASS|FAIL
REFERENCE_BUILD_TARGET=esp32c6
REFERENCE_APP_ELF=
REFERENCE_APP_BIN=
REFERENCE_APP_ELF_SHA256=
REFERENCE_APP_BIN_SHA256=

If configure/compile fails:
classify the first real failure and STOP.
No repair.

============================================================
8. POSTCHECK
============================================================

Prove:
HOMEASSISTANT_PRODUCT_SOURCE_CHANGED=false
HOMEASSISTANT_REPOSITORY_WRITE=false
PR361_CHANGED=false
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
RF_EXECUTION=false
T1_MUTATION=false

Temp/build artifacts are reference evidence only and are not yet repository/product authority.

============================================================
9. HARD STOP
============================================================

Do not flash Board A/B/C.
Do not create the physical R0 authorization yourself.
Do not implement KF-089 product repair.
Return only the structured closure below.
```

---

## 13. Expected Closure

```text
=== N3W OFFICIAL ESPNOW R0 SOURCE AUTHORITY + HOST COMPILE PRECLAIM CLOSURE ===

EXECUTION_ID=N3W-OFFICIAL-ESPNOW-R0-SOURCE-AUTHORITY-HOST-COMPILE-PRECLAIM-20260904-01
AUTHORIZATION=NOT_REQUIRED_HOST_ONLY_PRECLAIM
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

CURRENT_MAIN=
CURRENT_TREE=
PRODUCT_SOURCE_AUTHORITY=bff94bc4922d7a984eb1363cc24a163ad466a166

ESPHOME_VERSION=
IDF_VERSION=
IDF_REVISION=
IDF_AUTHORITY_SOURCE=
IDF_AUTHORITY_UNIQUE=

UPSTREAM_REPOSITORY=espressif/esp-idf
UPSTREAM_HEAD=
UPSTREAM_TREE=
UPSTREAM_EXAMPLE_PATH=examples/wifi/espnow
UNMODIFIED_OFFICIAL_EXAMPLE_BOUND=
ESP32C6_SUPPORT_PROVEN=

REFERENCE_CONFIGURE=
REFERENCE_COMPILE=
REFERENCE_BUILD_TARGET=
REFERENCE_APP_ELF_SHA256=
REFERENCE_APP_BIN_SHA256=

HOMEASSISTANT_PRODUCT_SOURCE_CHANGED=false
HOMEASSISTANT_REPOSITORY_WRITE=false
PR361_CHANGED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
RF_EXECUTION=false
T1_MUTATION=false

OFFICIAL_ESPNOW_R0_SOURCE_AUTHORITY=
READY_FOR_R0_TWO_BOARD_PHYSICAL_AUTHORIZATION=

GATE_RESULT=
NEXT_ROUTE=

=== END ===
```

Closure 必须足以让高阶模型直接分类，不依赖 Codex 再次解释 raw log。

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=N3W_OFFICIAL_ESPNOW_REFERENCE_R0_TWO_BOARD_PHYSICAL_BASELINE
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true
```

Physical R0 目标应是：两块 ESP32-C6 使用同一 exact official unmodified reference，先证明 broadcast/discovery/unicast/send-callback/receive-callback 基础链路。物理 flash gate 必须遵守 KF-087 source→fresh-artifact→board binding。

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

失败只允许分类为 toolchain/upstream/reference-compile authority问题；不得为使 Gate PASS 自动修改官方 example 或产品代码。

---

## 15. KNOWN_FAILURES Updates

本轮已产生并公开归档：

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
```

```text
KF_ID=KF-087
DOMAIN=INFRASTRUCTURE
SYMPTOM=upload_PASS_but_runtime_semantics_stale
ROOT_CAUSE=missing_exact_source_to_fresh_artifact_to_board_binding
FIX_OR_GUARD=fresh_disposable_build_plus_artifact_hash_plus_postflash_runtime_marker
STATUS=RESOLVED
```

```text
KF_ID=KF-088
DOMAIN=PHYSICAL_HARNESS
SYMPTOM=controlled_RESET_entered_ROM_Download_Mode
ROOT_CAUSE=TBD
FIX_OR_GUARD=separate_ROM_strap_vs_application_failure_oracle;normal_power_cycle_recovery
STATUS=OPEN
```

```text
KF_ID=KF-089
DOMAIN=PRODUCT
SYMPTOM=provisioned_node_cold_boot_without_Direct_cannot_acquire_Relay
ROOT_CAUSE=PRODUCT_RUNTIME_STARTUP_REQUIRES_WIFI_CONNECTED
FIX_OR_GUARD=PRODUCT_REPAIR_PENDING_OFFICIAL_REFERENCE_BASELINE
STATUS=OPEN
```

Exact semantics are already reserved in:

`docs/development/N3W_BOARD_B_REAL_WORLD_FAILOVER_KF087_KF089_DISPOSITION_20260904.md`

Central `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` fold-in is still required before or with the eventual product repair merge. Do not prematurely mark KF-089 GUARDED merely because the official reference passes.

---

## 16. New Chat Start Prompt

```text
阅读《N3W_OFFICIAL_ESPNOW_REFERENCE_R0_PREEXECUTION_NEW_CHAT_HANDOFF_V1.0_20260904.md》。

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并读取 current repository：
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_BOARD_B_REAL_WORLD_FAILOVER_DEBUG_ARCHIVE_20260904.md
- docs/development/N3W_BOARD_B_REAL_WORLD_FAILOVER_KF087_KF089_DISPOSITION_20260904.md
- docs/development/N3W_KF089_MINIMAL_PRODUCT_REPAIR_DESIGN_DEFERRED_20260904.md

继续“温室环境监测系统（ESP32-C6）”。

本轮继续采用“高阶模型思考 + Codex 低阶模型执行”。
Codex 的职责包括将 exact DSL execution contract 机械编译为最低必要命令；
PREWRITTEN_EXECUTOR_REQUIRED=false。

当前路线不是立即修 KF-089 产品源码，而是先建立 Espressif 官方 ESP-NOW reference baseline。

当前只进入：
NEXT_ONE_GATE=N3W_OFFICIAL_ESPNOW_REFERENCE_R0_SOURCE_AUTHORITY_AND_HOST_COMPILE_PRECLAIM

目标：
1. fresh rebind current main；
2. 从当前 ESPHome 2026.4.3 / ESP32-C6 toolchain 建立 exact ESP-IDF revision authority；
3. 绑定同 revision 的 Espressif `examples/wifi/espnow`；
4. 在 disposable host workspace 中原样 configure/compile ESP32-C6；
5. STOP，不刷板。

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

不得：
- 修改产品源码；
- 修改/合并 PR #361；
- 安装或升级 toolchain；
- 为编译通过修改官方 example；
- USB/serial/flash/NVS/RF；
- 自动进入两板物理 R0。

先 rebind 当前 authority，再执行该唯一 Gate；任何 substantive mismatch fail-closed STOP 并返回高阶模型。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=N3W_OFFICIAL_ESPNOW_REFERENCE_BASELINE_PREPARATION
CURRENT_STOP_POINT=BEFORE_R0_EXACT_IDF_SOURCE_AUTHORITY_AND_HOST_COMPILE_PRECLAIM

SOURCE_DEFECT_PROVEN=true
CURRENT_BLOCKER=KF089_PRODUCT_RUNTIME_STARTUP_REQUIRES_WIFI_CONNECTED

OFFICIAL_REFERENCE_BASELINE_PROVEN=false
DEFERRED_PRODUCT_REPAIR_DESIGN_PRESERVED=true
PRODUCT_REPAIR_IMPLEMENTATION_DEFERRED=true

PRODUCT_SOURCE_AUTHORITY=bff94bc4922d7a984eb1363cc24a163ad466a166
DIAGNOSTIC_PR361_STATE=DRAFT_OPEN_UNMERGED

LIVE_SYSTEM_STATE=NOT_REQUIRED_BY_NEXT_GATE_AND_REQUIRES_FRESH_REBIND_BEFORE_PHYSICAL_USE

NEXT_ONE_GATE=N3W_OFFICIAL_ESPNOW_REFERENCE_R0_SOURCE_AUTHORITY_AND_HOST_COMPILE_PRECLAIM

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
