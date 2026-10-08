# 温室环境监测系统（ESP32-C6） / N3-W
# Clean Product First-Pair Handoff / Runtime Identity — Clean-Board Eligibility
# 新会话交接文档 V1.0 — 2026-10-07

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文严格按 exact handoff authority `4300890dff0ce63d5a547df21426e287d084d9ee` 中的
> `docs/development/NEW_CHAT_HANDOFF_STANDARD.md` 与
> `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` 生成。
> 如本文与 fresh exact repository/runtime/physical evidence 冲突，以更高 authority 为准，并先 STOP 完成 rebind。

---

## 0. 会话切换结论

本轮已经完成 clean-product first-pair Setup Secret / runtime identity 源码修复、最终源码复核、replacement exact artifact 构建与独立绑定，以及新的 clean-board physical acceptance preexecution 设计。当前对话上下文已很长，因此在任何新的板卡访问之前切换会话。

```text
CURRENT_STAGE=CLEAN_PRODUCT_PHYSICAL_ACCEPTANCE_READY_FOR_P1
CURRENT_STOP_POINT=BEFORE_NEW_CANDIDATE_BOARD_ACCESS
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘全部历史，而是先 fresh rebind 本文列出的 authority，然后只进入 `NEXT_ONE_GATE`。

如果用户尚未明确授权访问一块新的候选板：

```text
BOARD_ACCESS_AUTHORIZATION_REQUIRED=true
STOP_BEFORE_USB_ACCESS=true
```

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 N3-W 产品路线与 clean-product acceptance 边界；
- 维护 exact source / artifact / PR / runtime authority；
- 设计 gate、scope、authorization、rollback；
- 根据低阶执行 closure 做 PASS / FAIL / INVALID / STOP 分类；
- 区分 product defect、acceptance tooling drift、live environment drift 与 physical evidence gap；
- 禁止为了测试方便重新引入 lab-only pairing/recovery 路线。

### 1.2 Codex 低阶执行职责

- 机械执行本文第 12 节 exact DSL；
- 使用 Mac Terminal 已安装的 Git/esptool/Python/zip/hash 工具完成最低必要命令；
- 只有在用户明确授予 board read-only authorization 后才能访问候选板；
- 第一处 substantive mismatch 后 fail-closed STOP；
- 只生成私有原始证据与公开安全 closure；
- 不设计 repair，不跨越下一 gate。

Codex 不得自行扩大 scope、修改产品源码、修复 stale executor、重放已消费授权或进入 P2。

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

现有 `clean_board_eligibility_readonly_preflight/executor.py` 仍绑定旧 artifact，因此下一 gate **不得把它当 exact authority**。这不是 `MISSING_EXECUTOR` blocker；按本标准直接把本文 DSL 机械编译为最小只读命令。

### 1.4 标准交互循环

```text
高阶模型：fresh rebind / gate / 最小授权
        ↓
用户：明确批准新候选板 read-only access
        ↓
Codex：DSL compile → exact read-only execution → closure
        ↓
高阶模型：复核 closure / 决定是否进入 P2
```

---

## 2. Product North Star

当前产品路线：

```text
clean product state
→ normal Wi-Fi provisioning
→ production LCD GHN3W2 optical handoff
→ Manager-owned pairing.sock import
→ KF-050 first-pair interruption acceptance
→ healthy Direct
→ real T1 A->B Broker relocation
→ cold-start revalidation at B
```

最终阶段目标：

```text
CLEAN_PRODUCT_STALE_BROKER_ACCEPTANCE=PASS
AND
FULL_CHANNEL_FALLBACK_PHYSICAL_RF_ACCEPTANCE=PASS
AND
PR522_FINAL_DISPOSITION_REVIEW=PASS
```

当前不得进入：

```text
PR522_MERGE
FULL_CHANNEL_FALLBACK_RF_TEST_INSIDE_CLEAN_BOARD_GATE
LEGACY_RECOVERY_FLOOR
SERIAL_OR_NVS_SETUP_SECRET_EXTRACTION
MANAGER_REPLAY_OR_HIGH_WATER_CLEAR
DIRECT_SQLITE_PAIRING_WRITE
BLOCKED_P4_BOARD_REUSE_AS_CLEAN
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
MAIN_TREE=ee977996a4c962097684519841dce2e3bcba23f2

PR=522
PR_STATE_AT_HANDOFF=OPEN_DRAFT
PR_MERGED=false
PR_BASE=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PR_HEAD_REQUIRES_FRESH_READONLY_REBIND=true
MERGE=false
```

### 3.2 Candidate / artifact / image

```text
CANDIDATE_REF=629f096a32e087087ea32d30707dcc3cd6295e5d
CANDIDATE_ID=SOURCE_HEAD
VERSION=F1.0-RC2_N3W_CLEAN_PRODUCT_FIRST_PAIR_REPAIR
REVISION=629f096a32e087087ea32d30707dcc3cd6295e5d
ARCH=ESP32-C6

SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
SOURCE_REPAIR=CLOSED_PASS

BUILD_RUN_ID=37594598870
ARTIFACT_ID=11469977052
ARTIFACT_NAME=n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source
ARTIFACT_OUTER_SHA256=8587c7bf130f2f17e81b4e4f7652780f372f6a61697cc240e72a6af7392a7dc8
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
FIRMWARE_BIN_SHA256=4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65
FIRMWARE_FACTORY_BIN_SHA256=658645083ed2d83d6951abeb5f894dbde7d7124030c8bc1815683ed2bf24e914
BOOTLOADER_BIN_SHA256=985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTA_DATA_INITIAL_BIN_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
FLASH_ARGS_SHA256=5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713
```

Artifact binding authority:

`docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_REPLACEMENT_EXACT_ARTIFACT_BUILD_AND_BINDING_20261007.md`

### 3.3 Successor / deployment material

```text
SUCCESSOR_AUTHORITY=NOT_APPLICABLE:no new source successor; exact replacement artifact is already frozen
```

Physical acceptance plan authority:

`docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261007.md`

### 3.4 Target host / runtime authority

```text
TARGET_HOST=T1_PRIVATE_LOCATOR_WITHHELD
TARGET_ARCH=REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2
PAIRING_MANAGER_AUTHORITY=Manager-owned pairing.sock
PAIRING_CLI=greenhouse-manager-pairing import-payload --payload-stdin
RUNTIME_IDENTITY_AUTHORITY=OPTICAL_LCD_GHN3W2_EQUALS_UNIQUE_NEW_MANAGER_PENDING
```

Next gate P1 does not require T1 mutation or live pairing access.

Handoff process authority:

```text
HANDOFF_STANDARD_COMMIT=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD_BLOB=0ca966bd3417d8817ca79686b70772c1cb57730b
HANDOFF_TEMPLATE_BLOB=2f48f65c606b6ecc9d0c3aa655bc80ef39400f72
```

---

## 4. Current Live Baseline

Freshly proven at handoff:

```text
PR522_STATE=OPEN_DRAFT
PR522_MERGED=false
PR522_MERGEABLE=true

NEW_CLEAN_CANDIDATE_SELECTED=false
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
FLASH_ERASE=false
FLASH_WRITE=false
NVS_MUTATION=false
RF_EXECUTION=false

REPLACEMENT_ARTIFACT_RUNNING_ON_ANY_BOARD=NOT_CLAIMED
BLOCKED_P4_BOARD_REUSE_AS_CLEAN=false
```

T1/runtime state has not been freshly read in this handoff transaction:

```text
MANAGER_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2
MANAGER_IMAGE_ID=REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2
MANAGER_RESTART_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2

BROKER_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2
BROKER_IMAGE_ID=REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2
BROKER_RESTART_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2

HOMEASSISTANT_STATE=OUT_OF_SCOPE_FOR_P1
HOMEASSISTANT_IMAGE_ID=OUT_OF_SCOPE_FOR_P1

PAIRING_SERVICE_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2
PAIRING_PORT_OWNER_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2
```

Historical P2 healthy-Broker-A evidence must not be treated as fresh current live state.

---

## 5. Proven Current Facts

```text
FIRST_PAIR_HANDOFF_AND_IDENTITY_SOURCE_REPAIR=CLOSED_PASS
SOURCE_REPAIR_CODE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_REPAIR_CI=PASS
EXACT_SOURCE_READBACK=PASS

PRODUCTION_CONVERGENCE_RUN=37590822231
CLEAN_BOARD_PREFLIGHT_RUN=37590822050
GREENHOUSE_MANAGER_RUN=37590822088
F1_RC2_FIRMWARE_RUN=37590822280
PUBLIC_SAFETY_RUN=37590822136

REPLACEMENT_EXACT_ARTIFACT_BUILD_AND_BINDING=CLOSED_PASS
REPLACEMENT_BUILD_RUN_ID=37594598870
REPLACEMENT_ARTIFACT_ID=11469977052
REPLACEMENT_ARTIFACT_INDEPENDENT_HASH_BINDING=PASS
MANIFEST_MEMBER_HASH_BINDING=PASS
BINARY_DEHARNESS_PROOF=PASS
PAIRING_ID_LOG_REDACTION_BINARY_PROOF=PASS
CLEAN_PRODUCT_PAIRING_QR_BINARY_MARKER=PASS

CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION=PASS
CURRENT_BLOCKED_P4_BOARD_REUSE_AS_CLEAN=false
PRODUCT_HARDWARE_ID_PREBOOT_INFERENCE_FORBIDDEN=true
```

The prior P4 blocker was real: old product source reached Wi-Fi, Manager discovery and pending registration but lacked a normal-product Setup Secret handoff. That source defect is now repaired and the replacement artifact is bound.

The existing repository P1 helper is stale:

```text
PREFLIGHT_EXECUTOR_ARTIFACT_BINDING=STALE
STALE_EXECUTOR_SOURCE_HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
STALE_EXECUTOR_ARTIFACT_ID=11320812037
PRODUCT_DEFECT=false
PREWRITTEN_EXECUTOR_REQUIRED=false
```

Inference kept separate:

```text
INFERENCE_NEW_CANDIDATE_WILL_BE_CLEAN=NOT_PROVEN
INFERENCE_T1_CURRENTLY_STILL_HEALTHY_AT_A=NOT_PROVEN_REQUIRES_P2_REBIND
```

---

## 6. Current Root Cause / Blockers

### Blocker A — final clean-product physical evidence not yet rerun

```text
ROOT_CAUSE=NO_GENUINELY_NEW_CANDIDATE_HAS_YET_PASSED_P1_UNDER_REPLACEMENT_ARTIFACT_ROUTE
PROVEN_BY=BOARD_ACCESS_FALSE_AND_NO_NEW_P1_EVIDENCE
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
CLASS=ACCEPTANCE_EVIDENCE_GAP
```

### Tooling drift — not a product blocker

```text
PREFLIGHT_EXECUTOR_ARTIFACT_BINDING=STALE
ROOT_CAUSE=helper constants still point to superseded artifact
PRODUCT_DEFECT=false
PHYSICAL_PRODUCT_BLOCKER=false
EXECUTION_ROUTE=FORMAL_DSL_COMPILATION
```

No source repair is authorized or required merely to run P1.

---

## 7. Closed / Forbidden Routes

Unless new direct counter-evidence appears:

```text
OLD_157448B_ARTIFACT_FOR_NEW_ACCEPTANCE=CLOSED:historical evidence only
BLOCKED_P4_BOARD_AS_NEW_CLEAN_CANDIDATE=CLOSED:identity/pairing history already exists
ROM_BASE_MAC_AS_RUNTIME_PRODUCT_ID=CLOSED:only silicon binding authority
SERIAL_SETUP_SECRET_CAPTURE_FOR_FINAL_ACCEPTANCE=CLOSED:not normal product route
RAW_NVS_SETUP_SECRET_EXTRACTION=CLOSED:not normal product route
DIRECT_SQLITE_PAIRING_WRITE=CLOSED:pairing.sock is authority
LEGACY_RECOVERY_FLOOR_FOR_FINAL_ACCEPTANCE=CLOSED:ADR-0008/KF-050 product route forbids it
MANAGER_REPLAY_CLEAR=CLOSED:must preserve replay/high-water
MANAGER_HIGH_WATER_CLEAR=CLOSED:must preserve replay/high-water
ERASE_TO_MANUFACTURE_CLEAN_EVIDENCE=CLOSED:cleanliness must be proven before erase
STALE_PREFLIGHT_EXECUTOR_AS_EXACT_AUTHORITY=CLOSED:binds superseded artifact
PR522_MERGE=CLOSED_FOR_CURRENT_STAGE:physical acceptance incomplete
FULL_CHANNEL_RF_TEST_MIXED_INTO_CLEAN_STALE_BROKER_GATE=CLOSED:separate acceptance axis
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_SOURCE_REPAIR_20261007_01
CLAIMED=true
CONSUMED=true
RESULT=CLOSED_PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=replacement exact artifact and physical acceptance route

AUTHORIZATION=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_REPLACEMENT_EXACT_ARTIFACT_BUILD_AND_BINDING_20261007_01
CLAIMED=true
CONSUMED=true
RESULT=CLOSED_PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=clean-board physical acceptance route

AUTHORIZATION=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261007_01
CLAIMED=true
CONSUMED=true
RESULT=CLOSED_PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=P1 read-only eligibility

AUTHORIZATION=historical blocked P4 physical authorization
CLAIMED=true
CONSUMED=true
RESULT=STOP_PRODUCT_BLOCKER
REPLAY_PERMITTED=false
SUPERSEDED_BY=repaired-source replacement-artifact clean-board route

PROPOSED_AUTHORIZATION=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01
GRANTED=false
AUTHORIZATION_CLASS=NEW_CANDIDATE_BOARD_READONLY_ACCESS
```

Repository-only fresh rebind may run before this physical authorization. First USB/esptool access requires explicit user approval.

No T1 mutation authorization exists for the next gate.

---

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
NORMAL_PATH_RESTART_ALLOWED=false
ROLLBACK_ONLY_RESTART_LIMIT=0
SECOND_ATTEMPT_ALLOWED=false_without_new_high_level_classification
```

The gate permits bounded private evidence writes only; it performs no board/T1/Manager state mutation.

If any supposedly read-only command is about to erase/write flash/NVS or modify live runtime:

```text
STOP=true
DO_NOT_EXECUTE=true
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01
```

### 10.1 Purpose

Prove that exactly one newly presented ESP32-C6 candidate is genuinely clean **before any write**, is not historical Board A/B or the blocked P4 candidate, has expected chip/flash/security state, and contains no N3-W pairing/Broker/boot residue. The runtime product identity remains deliberately deferred.

### 10.2 Frozen inputs

```text
SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161

ARTIFACT_ID=11469977052
ARTIFACT_OUTER_SHA256=8587c7bf130f2f17e81b4e4f7652780f372f6a61697cc240e72a6af7392a7dc8
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
FIRMWARE_BIN_SHA256=4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTADATA_BIN_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
BOOTLOADER_BIN_SHA256=985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5

HISTORICAL_BOARD_A_SILICON_BINDING_SHA256=054df6316a48b21d216f35424aea38d10a2ca5ab62632b5611ddfe5a295ea4e5
HISTORICAL_BOARD_B_SILICON_BINDING_SHA256=e3a489f954fdcde28e67f166fd01b536d3dd25172aecbfc3b8d056278584f9b1
BLOCKED_P4_SILICON_BINDING_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

PRODUCT_HARDWARE_ID_SHA256=DEFERRED
RUNTIME_IDENTITY_BINDING=NOT_PART_OF_P1
```

Relevant NVS keys:

```text
gh_n3w_v2/peer
gh_n3w_v2/broker
gh_n3w_v2/pair_ack
gh_n3w_v2/pair_intent
gh_n3w_v2/setup
gh_n3w_v2/pair_epoch
gh_n3w/boot_state
```

### 10.3 Required proof / operations

```text
1. Fresh-read repository main, PR #522 and the four current authority documents.
2. Verify PR remains open/draft/unmerged; do not merge.
3. Verify/download artifact 11469977052 and independently bind outer/release/member hashes.
4. Before USB access, require explicit user authorization and confirmation that one genuinely new candidate board is connected.
5. Enumerate USB modem devices; require exactly one candidate locator.
6. Do not open application serial.
7. Require installed esptool major version 5; install/upgrade nothing.
8. Use only read-only esptool operations to prove ESP32-C6, 8MB flash, Secure Boot disabled, Flash Encryption disabled, and obtain ROM MAC privately.
9. Convert ROM MAC privately to silicon binding and publish only SHA-256.
10. Reject if silicon-binding SHA-256 equals historical Board A, Board B or blocked P4 candidate.
11. Read partition table with read-flash only; blank is allowed, valid nonblank table must parse unambiguously.
12. Locate every NVS partition from the observed table and read each NVS partition to private evidence files.
13. Offline inspect all NVS partitions for the frozen N3-W namespaces/keys and conservative distinctive markers.
14. Any target residue -> FAIL and STOP; never erase to make it clean.
15. Any ambiguous table/NVS/security/identity evidence -> INVALID/STOP.
16. Keep PRODUCT_HARDWARE_ID_SHA256 deferred; do not query/guess Manager product identity in P1.
17. Produce only public-safe structured closure, then STOP.
```

### 10.4 PASS

```text
CLEAN_BOARD_ELIGIBILITY=PASS
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
SILICON_BINDING_UNIQUE=true
HISTORICAL_BOARD_MATCH=false
BLOCKED_P4_BOARD_MATCH=false
OLD_N3W_STATE_ABSENT=true
PRODUCT_HARDWARE_ID_SHA256=DEFERRED
FLASH_WRITE=false
FLASH_ERASE=false
T1_MUTATION=false
READY_FOR_P2=true
```

### 10.5 FAIL / INVALID

```text
CLEAN_BOARD_ELIGIBILITY=FAIL_RESIDUE
OR
CLEAN_BOARD_ELIGIBILITY=INVALID_AMBIGUOUS_EVIDENCE

READY_FOR_P2=false
ERASE_TO_MANUFACTURE_CLEAN_STATE=false
AUTO_REPAIR=false
AUTO_RETRY=false
STOP=true
```

Codex 不得自动进入 P2。

---

## 11. Hard Allowed / Forbidden Scope

Default：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- fresh read-only GitHub rebind
- artifact download/hash verification
- after explicit board-read authorization: USB locator enumeration
- esptool version query
- ESP32-C6 get-security-info
- ESP32-C6 flash-id
- read-flash for partition table
- read-flash for every discovered NVS partition
- offline parsing/hashing of read bytes
- bounded private evidence writes
- public-safe JSON/closure writes
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=$HOME/N3W_PRIVATE_EVIDENCE/<this P1 gate>/ and temporary public-safe summary only
```

### FORBIDDEN

```text
- write-flash / erase-flash / erase-region
- any NVS write
- application serial open as passive oracle
- product firmware normal-boot acceptance work
- Wi-Fi provisioning
- optical pairing scan/import
- T1 SSH mutation
- Manager/Broker restart or recreation
- Manager DB write
- replay/high-water clear
- Setup Secret / GHN3W2 capture
- use of stale executor as exact artifact authority
- modification of executor.py inside this gate
- package/tool installation
- PR #522 merge
- P2/P3/P4 execution
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required.
The repository helper executor currently binds the superseded artifact and
MUST NOT be used as exact artifact authority.

Mechanically compile this DSL into the minimum necessary commands using
already-installed tools, then execute exactly the bounded read-only P1 gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not retry unless explicitly permitted.
Do not enter P2.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

EXECUTION_ID=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01
AUTHORIZATION=NEW_CANDIDATE_BOARD_READONLY_ACCESS
AUTHORIZATION_GRANTED=<fresh user decision>
BOARD_ACCESS_BEFORE_GRANT=false

If authorization is not explicitly granted:
  perform repository-only fresh rebind
  emit BOARD_ACCESS_AUTHORIZATION_REQUIRED=true
  STOP

============================================================
1. FROZEN INPUT REBIND
============================================================

Read exact:
  PR #522
  docs/development/N3W_CURRENT_STATE.md
  docs/development/N3W_CURRENT_STATE_INDEX.md
  docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_HANDOFF_AND_IDENTITY_PROGRESS_ALIGNMENT_20261007.md
  docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_REPLACEMENT_EXACT_ARTIFACT_BUILD_AND_BINDING_20261007.md
  docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261007.md

Require:
  source head/tree == frozen values
  artifact ID/name/hashes == frozen values
  PR open
  PR draft
  PR merged == false

Do not require current PR tip to equal product SOURCE_HEAD; later docs-only commits are expected.

============================================================
2. ARTIFACT REBIND
============================================================

If exact artifact bytes are not already locally proven:
  download artifact ID 11469977052
  verify outer SHA256
  open outer ZIP
  require exact release ZIP + .sha256 member
  verify release ZIP SHA256
  verify MANIFEST source/tree/run ID
  verify bootloader/partitions/otadata/firmware hashes

No build.
No source mutation.

============================================================
3. BOARD ACCESS PRECLAIM
============================================================

Require explicit user authorization.
Require operator statement that this is a genuinely new candidate,
not Board A, Board B, or the blocked P4 board.

Enumerate /dev/cu.usbmodem*.
Require exactly one candidate locator.
Do not open application serial.

At first esptool command:
  AUTHORIZATION_CLAIMED=true

============================================================
4. READ-ONLY SILICON / SECURITY PROOF
============================================================

Require esptool major version 5.
Install nothing.

Using --chip esp32c6, candidate port and read-only commands:
  get-security-info
  flash-id

Require:
  CHIP=ESP32-C6
  FLASH_SIZE=8MB
  SECURE_BOOT=false
  FLASH_ENCRYPTION=false

Raw ROM MAC is private.
Derive:
  silicon_binding = rom-c6-<compact lower-case ROM MAC>
  SILICON_BINDING_SHA256=sha256(silicon_binding)

Never print/commit raw MAC or silicon_binding.

Reject if SHA256 equals:
  054df6316a48b21d216f35424aea38d10a2ca5ab62632b5611ddfe5a295ea4e5
  e3a489f954fdcde28e67f166fd01b536d3dd25172aecbfc3b8d056278584f9b1
  3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

============================================================
5. READ-ONLY FLASH / NVS PROOF
============================================================

Use read-flash only.

Read:
  partition table region at 0x8000, size 0x1000

If all 0xFF:
  PARTITION_TABLE_STATE=BLANK
  NVS_PARTITION_COUNT=0
  OLD_N3W_STATE_ABSENT=true

Else:
  parse ESP-IDF partition entries fail-closed
  reject overlaps/out-of-range/invalid records
  locate every data/nvs partition
  read each complete NVS partition to private evidence
  inspect offline for:
    gh_n3w_v2/peer
    gh_n3w_v2/broker
    gh_n3w_v2/pair_ack
    gh_n3w_v2/pair_intent
    gh_n3w_v2/setup
    gh_n3w_v2/pair_epoch
    gh_n3w/boot_state

Also conservatively search distinctive target markers where needed.

Any N3-W residue:
  CLEAN_BOARD_ELIGIBILITY=FAIL_RESIDUE
  ERASE_TO_MANUFACTURE_CLEAN_STATE=false
  STOP

Ambiguous parse/evidence:
  CLEAN_BOARD_ELIGIBILITY=INVALID_AMBIGUOUS_EVIDENCE
  STOP

============================================================
6. IDENTITY BOUNDARY
============================================================

Set:
  PRODUCT_HARDWARE_ID_SHA256=DEFERRED
  PRODUCT_IDENTITY_STATUS=DEFERRED_UNTIL_RUNTIME_QR_MANAGER_BINDING

Do not infer product hardware ID from ROM MAC.
Do not query Manager history for a guessed product identity.
Manager preboot identity-set snapshot belongs to P2.

============================================================
7. EVIDENCE
============================================================

Private evidence may contain:
  raw ROM MAC
  exact USB locator
  raw partition-table bytes
  raw NVS bytes
  local artifact paths

Private evidence dir:
  mode 0700
Private evidence files:
  mode 0600 where applicable

Public-safe closure may contain:
  SHA256
  chip/flash/security classifications
  partition-table classification
  NVS partition count
  residue absent/present
  mutation flags

Never publish:
  raw MAC
  Setup Secret
  pairing payload
  pairing ID
  private T1 address
  raw NVS content

============================================================
8. HARD STOP
============================================================

After closure:
  BOARD_WRITE=false
  FLASH_ERASE=false
  FLASH_WRITE=false
  NVS_WRITE=false
  T1_MUTATION=false
  MANAGER_REPLAY_MUTATION=false
  MANAGER_HIGH_WATER_CLEAR=false
  AUTO_EXECUTE_P2=false
  STOP=true
```

---

## 13. Expected Closure

```text
=== N3W CLEAN PRODUCT P1 READONLY ELIGIBILITY CLOSURE ===

EXECUTION_ID=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01
AUTHORIZATION=NEW_CANDIDATE_BOARD_READONLY_ACCESS
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

REPOSITORY_MAIN=
PR522_HEAD=
PR522_STATE=
PR522_DRAFT=
PR522_MERGED=

SOURCE_HEAD_MATCH=
SOURCE_TREE_MATCH=
ARTIFACT_ID_MATCH=
ARTIFACT_OUTER_SHA256_MATCH=
RELEASE_ZIP_SHA256_MATCH=
MANIFEST_BINDING_MATCH=

USB_MODEM_COUNT=
CHIP=
FLASH_SIZE=
SECURE_BOOT=
FLASH_ENCRYPTION=

SILICON_BINDING_SHA256=
HISTORICAL_BOARD_A_MATCH=
HISTORICAL_BOARD_B_MATCH=
BLOCKED_P4_BOARD_MATCH=

PARTITION_TABLE_STATE=
PARTITION_TABLE_READ_SHA256=
NVS_PARTITION_COUNT=
OLD_N3W_STATE_ABSENT=

PRODUCT_HARDWARE_ID_SHA256=DEFERRED
PRODUCT_IDENTITY_STATUS=DEFERRED_UNTIL_RUNTIME_QR_MANAGER_BINDING

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=
APPLICATION_SERIAL_OPEN=false
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false

CLEAN_BOARD_ELIGIBILITY=
READY_FOR_P2=
NEXT_ROUTE=
STOP=true

=== END ===
```

Closure 必须足以让高阶模型直接分类；不得用 raw log 替代这些字段。

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_T1_HEALTHY_BROKER_A_AND_MANAGER_PREBOOT_IDENTITY_SNAPSHOT_PREPARATION_20261007_01
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true
```

P2 必须 fresh rebind T1/Manager/Broker；不得沿用 2026-10-06 的 live 状态作为当前事实。

### FAIL / INVALID 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
ERASE_TO_MANUFACTURE_CLEAN_STATE=false
RETURN_TO_HIGH_LEVEL_MODEL=true
STOP=true
```

如果候选板有历史 N3-W residue，它永久失去“new clean candidate”资格；不要擦除后继续冒充 clean evidence。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
```

本轮发现的 stale preflight executor 已记录在 current-state / progress-alignment 中，分类为：

```text
CLASS=ACCEPTANCE_TOOLING_DRIFT
PRODUCT_DEFECT=false
PHYSICAL_BLOCKER=false
MITIGATION=FORMAL_DSL_EXECUTION
```

目前不新增 KF，也不在本 handoff 中擅自关闭仍为 OPEN 的历史 KF（包括 KF-046）。

---

## 16. New Chat Start Prompt

```text
阅读《docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261007.md》。

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #522
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_HANDOFF_AND_IDENTITY_PROGRESS_ALIGNMENT_20261007.md
- docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_REPLACEMENT_EXACT_ARTIFACT_BUILD_AND_BINDING_20261007.md
- docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261007.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

必须先承认：
- clean-product first-pair Setup Secret / runtime identity source repair 已 CLOSED_PASS；
- replacement exact artifact 11469977052 已 CLOSED_PASS；
- product source authority 是 629f096a32e087087ea32d30707dcc3cd6295e5d；
- blocked P4 board 不得复用为 clean candidate；
- 现有 clean-board executor.py 仍绑定旧 artifact，不能作为 exact authority；不要因此新造执行框架，按 handoff DSL 直接机械执行；
- PRODUCT_HARDWARE_ID 在 P1 必须 DEFERRED，禁止由 ROM/base MAC 猜测；
- PR #522 保持 OPEN/DRAFT/UNMERGED。

当前只进入：
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

先完成 repository-only fresh rebind。
没有新的候选板 read-only 明确授权时，停在 BOARD_ACCESS_AUTHORIZATION_REQUIRED，不访问 USB。
获得授权后，只执行 handoff 第 12 节 P1 read-only DSL；不要自动进入 P2。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=CLEAN_PRODUCT_PHYSICAL_ACCEPTANCE_READY_FOR_P1
CURRENT_STOP_POINT=BEFORE_NEW_CANDIDATE_BOARD_ACCESS

SOURCE_DEFECT_PROVEN=false
CURRENT_BLOCKER=CLEAN_PRODUCT_PHYSICAL_EVIDENCE_PENDING

SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
ARTIFACT_ID=11469977052
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
FIRMWARE_BIN_SHA256=4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65

LIVE_SYSTEM_STATE=T1_MANAGER_BROKER_REQUIRES_FRESH_READONLY_REBIND_BEFORE_P2
NEW_CLEAN_CANDIDATE_SELECTED=false
PREFLIGHT_EXECUTOR_ARTIFACT_BINDING=STALE
NEXT_GATE_EXECUTION_AUTHORITY=HANDOFF_DSL_PLUS_REPLACEMENT_ARTIFACT_BINDING

NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
MERGE=false

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
