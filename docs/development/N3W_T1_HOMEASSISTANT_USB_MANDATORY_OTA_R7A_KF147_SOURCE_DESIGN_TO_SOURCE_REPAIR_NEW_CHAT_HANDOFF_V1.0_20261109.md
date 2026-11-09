# 温室环境监测系统（ESP32-C6）N3-W
# T1 Home Assistant mandatory-USB OTA R7A / KF-147 source design → source repair
# 新会话交接文档 V1.0 — 2026-11-09

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文符合 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`。  
> 如本文与 exact repository/runtime/live evidence 冲突，以更高 authority 为准，并先 STOP、fresh rebind。

---

## 0. 会话切换结论

本轮已完成 KF-147 source design，并按用户要求暂停开发。切换前已将对话现场、KF-147 设计和 Current State 对齐到 GitHub；期间发现 Current State / Index 顶部 authority 字段不完整导致两条 docs-only CI 失败，已按 checker 的 exact first-section contract 做局部 docs 修复，未进入 KF-147 source repair。

```text
CURRENT_STAGE=KF147_SOURCE_DESIGN_CLOSED_SOURCE_REPAIR_READY
CURRENT_STOP_POINT=SOURCE_REPAIR_NOT_STARTED
SOURCE_REPAIR_BASE_HEAD=fdb77f29f18158b44102c64b4fcba08f8d066bb8

NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_REPAIR_20261109_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘 USB E1/E2/E3 或 KF-145/KF-146，而是 fresh rebind 后只进入上述 source-repair gate。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护产品路线与架构边界；
- 维护 exact repository / target / runtime authority；
- 守住 KF-147 source design，不随意改公式、发布源和 destructive boundaries；
- 设计 source-repair scope、测试和 closure；
- 根据低阶执行结果做 PASS / FAIL / STOP；
- 区分 source defect、CI/docs authority defect、live infrastructure defect；
- 不把测试框架扩展成第二套产品架构。

### 1.2 Codex 低阶执行职责

- 机械执行本文第 12 节 exact DSL；
- 使用 Git/GitHub、Python/test、Docker/Nginx config test 等最低必要工具；
- 只允许 repository/source/test/CI mutation；
- 第一处 substantive mismatch fail-closed STOP；
- 不访问 T1、不操作当前 USB、不部署线上 `ota.hahub.top`；
- 不重放任何 consumed/superseded authorization；
- 不自动跨入 live publication / T1 repair / destructive confirm。

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
高阶模型：fresh rebind / source-repair contract
        ↓
Codex：DSL compile → source/test mutation → CI evidence → closure
        ↓
高阶模型：独立复核 source + tests + CI
        ↓
决定后续 stage；不自动 live
```

---

## 2. Product North Star

当前产品路线：

```text
普通农户使用
→ Home Assistant 更新由产品自动管理
→ 每次 HA 版本更新要求一个可清空 U 盘
→ PREPARE / 清空确认 / INSTALL 明确分离
→ target 直接下载到 U 盘
→ predecessor recovery + HA_DATA_BACKUP 在内部 destructive install 前完成
→ 更新失败可恢复旧镜像 + 旧数据
→ 用户无需理解 Docker / MQTT / 镜像文件
```

最终阶段目标：

```text
稳定 HTTPS approved artifact
+ 动态 USB 容量 admission
+ exact recovery authority
+ U4 READY_TO_INSTALL
+ U5-U13 安全安装/回滚
+ 上电即用产品体验
```

当前不得进入：

```text
LIVE_OTA_ORIGIN_DEPLOYMENT
LIVE_T1_POLICY_REPAIR
CONFIRM_USB_ERASE
WIPEFS/PARTITION/MKFS/MOUNT
TARGET_DOWNLOAD_ON_LIVE_T1
U2_PLUS_LIVE_ADVANCE
INSTALL/U5_PLUS
BOARD_ACCESS
MERGE
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
HOMEASSISTANT_REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
MAIN_TREE=f15bec7c33c4d44d27c7068e5579b07027dd5ea5

PR=800
PR_BRANCH=feat/n3w-ha-usb-r7a-prepare-pipeline-20261107
PR_BASE_BRANCH=docs/n3w-r5-readonly-preflight-handoff-20261107
PR_BASE_SHA=462018cbf341f1b762a35f82a87a7c98e4a8b615

SOURCE_REPAIR_BASE_HEAD=fdb77f29f18158b44102c64b4fcba08f8d066bb8
SOURCE_REPAIR_BASE_RELATION=KF147_DESIGN_AND_STATE_ALIGNMENT_COMPLETE
```

新会话必须 fresh rebind PR #800 最终 HEAD。若 handoff commit 之后只有 docs-only 交接增量，可继续以 `fdb77f29...` 为 source-repair baseline；若出现 executable drift，STOP。

Handoff process authority：

```text
HANDOFF_STANDARD_AUTHORITY_COMMIT=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD=docs/development/NEW_CHAT_HANDOFF_STANDARD.md
HANDOFF_TEMPLATE=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
```

### 3.2 Candidate / artifact / image

Approved target：

```text
APPROVED_MANIFEST=infra/n3w-t1/upgrades/homeassistant-2026.10.4-approved.json
RELEASE_IDENTITY=homeassistant-2026.10.4
VERSION=2026.10.4
TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
TARGET_PLATFORM=linux/arm64
TARGET_ARCHIVE_SIZE_BYTES=835309535
TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
EXPECTED_PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
```

Repository current-stack compatibility authority：

```text
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
HISTORICAL_CLEAN_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_CLEAN_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
```

### 3.3 Successor / deployment material

KF-147 design authority：

```text
KF147_SOURCE_DESIGN=docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_DESIGN_20261109.md
KF147_DESIGN_RESULT=CLOSED_DESIGN
HOST_RELEASE_POLICY_SCHEMA_NEXT=gh.n3w-t1-ha-ota-host-release-policy/2
```

OTA origin source authority：

```text
OTA_ORIGIN_REPOSITORY=chrenguo-stack/hahub.top
OTA_ORIGIN_BASE_HEAD=140fad2f12e116f25510e968cf87c69409dfc171
OTA_ARTIFACT_ORIGIN=https://ota.hahub.top
OTA_BINARY_IN_GIT=false
OTA_SERVER_STORAGE=/root/myserver/ota
```

### 3.4 Target host / runtime authority

```text
TARGET_HOST=root@192.168.68.194
TARGET_ARCH=aarch64

LIVE_MANAGER=local/greenhouse-manager:fresh-7807271e4c48
LIVE_MANAGER_RUNTIME_IMAGE_ID=sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b

LIVE_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
LIVE_HOMEASSISTANT_RUNTIME_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306

LIVE_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_BROKER_RUNTIME_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
```

这些 live 值来自本轮已完成的 direct live evidence；下一 gate 不允许访问 T1。任何未来 live gate 必须 fresh read-only rebind。

---

## 4. Current Live Baseline

最后 direct evidence：

```text
MANAGER_STATE=RUNNING_LAST_PROVEN
MANAGER_RESTART_COUNT=0_LAST_PROVEN

HOMEASSISTANT_STATE=RUNNING_LAST_PROVEN
HOMEASSISTANT_RESTART_COUNT=0_LAST_PROVEN

BROKER_STATE=RUNNING_LAST_PROVEN
BROKER_RESTART_COUNT=0_LAST_PROVEN

HOST_DAEMON_STATE=ACTIVE_LAST_PROVEN

HA_USB_TRANSACTION_PRESENT=true
HA_USB_PREPARE_STATE_PRESENT=true
TRANSACTION_PHASE=U1_PREPARE_REQUESTED
TRANSACTION_STATUS=ACTIVE
PUBLIC_PHASE=USB_REQUIRED_CONFIRMATION

USB_CONFIRMATION_REQUIRED=true
USB_CONFIRMATION_CONSUMED=false
USB_CANDIDATE_PRESENT=true
USB_CANDIDATE_MODEL=Extreme
USB_CANDIDATE_CAPACITY_BYTES=32017047552
CURRENT_USB_INSERTED=true

CONFIRM_USB_ERASE=false
WIPEFS=false
PARTITION_WRITE=false
MKFS=false
MOUNT=false
TARGET_DOWNLOAD=false
U2_PLUS=false

BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false

LIVE_BASELINE_REQUIRES_FRESH_READONLY_REBIND_BEFORE_ANY_FUTURE_LIVE_MUTATION=true
```

下一 source-repair gate 不使用 live baseline 作为 mutation target，只把它作为必须保护的 frozen现场。

---

## 5. Proven Current Facts

```text
KF145=CLOSED_PASS_LIVE_REVALIDATED
KF146=CLOSED_PASS_LIVE_REVALIDATED

USB_E3=CLOSED_PASS
SECOND_USB_T1_ENUMERATION=PASS
SECOND_USB_R7A_CANDIDATE_DISCOVERY=PASS
T1_USB_PATH_GENERAL_FAILURE=false
ORIGINAL_MXT_DEVICE_SPECIFIC_COMPATIBILITY=PRIMARY_CONFIRMED_DIRECTION

KF147_ROOT_CAUSE=R7A_CONSUMER_IMPLEMENTED_BUT_PRODUCTION_HOST_RELEASE_POLICY_AUTHORITY_NOT_FROZEN_OR_DEPLOYED
PRODUCT_SOURCE_BLOCKER_PROVEN=true

KF147_SOURCE_DESIGN=CLOSED
RELEASE_SOURCE_SELECTED=true
RELEASE_SOURCE=https://ota.hahub.top
CAPACITY_FORMULA=FIXED
CAPACITY_INPUT_MODEL=HYBRID_DYNAMIC

TARGET_ARTIFACT_INPUT=RELEASE_FIXED
PREDECESSOR_RECOVERY_INPUT=RELEASE_TRANSITION_BOUND
HA_DATA_BACKUP_INPUT=RUNTIME_DYNAMIC
TRANSACTION_WORKING_INPUT=FIXED_FORMULA
REMOVABLE_RESERVE_INPUT=FIXED_FORMULA

USB_MEASURED_USABLE_FLOOR_BYTES=15032385536
UI_MIN_RECOMMENDED_NOMINAL_USB_GB=32
```

CI/status-alignment fact：

```text
HEAD_046e8c8a_CORE_STACK_CI=FAIL_state_authority_link_missing
HEAD_046e8c8a_MANAGER_A_TO_B_CI=FAIL_state_authority_link_missing

HEAD_98f01a6a_CORE_STACK_CI=FAIL_state_product_source_missing
HEAD_98f01a6a_MANAGER_A_TO_B_CI=FAIL_state_product_source_missing

ROOT_CAUSE_OF_THESE_FAILURES=LATEST_CURRENT_STATE_AND_INDEX_FIRST_SECTION_MISSING_REQUIRED_CURRENT_STACK_COMPATIBILITY_FIELDS
SOURCE_EXECUTABLE_DEFECT_PROVEN_BY_THESE_CI=false

DOCS_ALIGNMENT_REPAIR_HEAD=fdb77f29f18158b44102c64b4fcba08f8d066bb8
REPAIR=RESTORE_FULL_CURRENT_STACK_AUTHORITY_FIELDS_IN_FIRST_STATE_AND_INDEX_SECTIONS
```

新会话必须检查最终 handoff HEAD CI；不要把上述历史 docs-only CI failure 当作 KF-147 executable source failure。

---

## 6. Current Root Cause / Blockers

### Blocker A — host release policy consumer/deployment gap

```text
ROOT_CAUSE=R7A_CONSUMER_REQUIRES_/etc/n3w-t1-ota/homeassistant-release-source.json_BUT_A1_DOES_NOT_INSTALL_PRODUCTION_POLICY
PROVEN_BY=KF147_PREFLIGHT+SOURCE_REVIEW
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=true
```

### Blocker B — capacity model too static

```text
ROOT_CAUSE=POLICY_V1_TREATS_FOUR_NON_TARGET_CAPACITY_INPUTS_AS_GLOBAL_FIXED_CONSTANTS
PROVEN_BY=SOURCE_SCHEMA_AND_PRODUCT_REQUIREMENT_REVIEW
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=false
```

### Blocker C — predecessor recovery budget exact evidence

```text
ROOT_CAUSE=PREDECESSOR_RECOVERY_BUDGET_MUST_BE_RELEASE_TRANSITION_QUALIFIED_NOT_GUESSED
PROVEN_BY=KF147_SOURCE_DESIGN
SOURCE_REPAIR_MUST_DERIVE_OR_STOP=true
ARBITRARY_NUMERIC_PLACEHOLDER_FORBIDDEN=true
```

---

## 7. Closed / Forbidden Routes

除非出现新的 direct counter-evidence，不得重新进入：

```text
GENERAL_T1_USB_PATH_FAILURE=CLOSED_FOR_TESTED_SECOND_DEVICE
ORIGINAL_MXT_COMPLETELY_DEAD=CLOSED
RETRY_ORIGINAL_MXT_ON_T1=FORBIDDEN

PREPARE_REPLAY=FORBIDDEN
CURRENT_U1_TRANSACTION_RESET=FORBIDDEN
CURRENT_USB_REINSERT_OR_RESELECTION=FORBIDDEN_IN_NEXT_GATE

FIXED_FOUR_GLOBAL_CAPACITY_CONSTANTS=RETIRED_BY_KF147_SOURCE_DESIGN
GITHUB_ACTIONS_ARTIFACT_AS_FINAL_PRODUCT_CDN=CLOSED
STORE_OTA_BINARY_IN_HOMEASSISTANT_GIT=FORBIDDEN
STORE_OTA_BINARY_IN_HAHUB_GIT=FORBIDDEN
STORE_OTA_BINARY_UNDER_WEBSITE_RSYNC_DELETE_TREE=FORBIDDEN

OLD_CONFIRM_USB_ERASE_AUTHORIZATION_REUSE=FORBIDDEN
LIVE_OTA_SERVER_DEPLOYMENT=FORBIDDEN_IN_NEXT_GATE
LIVE_T1_REPAIR=FORBIDDEN_IN_NEXT_GATE
CONFIRM_USB_ERASE=FORBIDDEN_IN_NEXT_GATE
U2_PLUS=FORBIDDEN_IN_NEXT_GATE
MERGE=FORBIDDEN
```

---

## 8. Authorization Ledger

### PREPARE revalidation

```text
AUTHORIZATION=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_BOUNDARY_B_PREPARE_REVALIDATION_20261109_01
CLAIMED=true
CONSUMED=true
RESULT=CLOSED_PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NOT_APPLICABLE
```

### E3 physical substitution

```text
AUTHORIZATION=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_USB_ENUMERATION_DIFFERENTIATION_E3_SECOND_DEVICE_20261109_01
CLAIMED=true
CONSUMED=true
RESULT=CLOSED_PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NOT_APPLICABLE
```

### Old destructive confirmation

```text
AUTHORIZATION=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_BOUNDARY_B_CONFIRM_USB_ERASE_20261109_01
CLAIMED=false
CONSUMED=false
RESULT=SUPERSEDED_UNCLAIMED_BY_KF147_CONTRACT_CHANGE
REPLAY_PERMITTED=false
SUPERSEDED_BY=FRESH_DESTRUCTIVE_AUTHORIZATION_AFTER_KF147_REPAIRED_LIVE_PREFLIGHT
```

### Next source repair

```text
AUTHORIZATION=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_REPAIR_20261109_01
GRANTED=true
GRANT_BASIS=USER_EXPLICITLY_REQUESTED_NEXT_CHAT_ENTER_THIS_GATE
CLAIMED=false
CONSUMED=false
LIVE_MUTATION_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

Repository/source/test/CI work may proceed continuously inside this exact gate. Live deployment remains separately authorized later.

---

## 9. Rollback Authority

下一 gate 不允许 live mutation。Repository source mutation rollback authority：

```text
ROLLBACK_BASELINE=SOURCE_REPAIR_BASE_HEAD_fdb77f29f18158b44102c64b4fcba08f8d066bb8
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
ROLLBACK_AUTHORITY_PATH_OR_ID=GIT_HISTORY
NORMAL_PATH_RESTART_ALLOWED=false
ROLLBACK_ONLY_RESTART_LIMIT=0
SECOND_ATTEMPT_ALLOWED=ONLY_AFTER_HIGH_LEVEL_CLASSIFIES_FAILURE_OR_LOCAL_UNAMBIGUOUS_CI_FIX
```

若 source repair 需要撤回：

```text
restore/revert only source-repair commits
→ preserve KF-147 design + handoff docs
→ verify no live mutation occurred
→ verify PR remains open/draft/unmerged
→ STOP
```

Live rollback：

```text
LIVE_ROLLBACK_AUTHORITY=NOT_APPLICABLE:NO_LIVE_MUTATION_IN_NEXT_GATE
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_REPAIR_20261109_01
```

### 10.1 Purpose

在不触碰真实 T1、当前 SanDisk、线上 OTA 服务器和 U2+ 的前提下，将 KF-147 frozen source design 落到 `HomeAssistant` 与 `hahub.top` 两个源码仓库，补齐 policy V2、hybrid dynamic capacity、A1 deployment authority、用户容量 projection、当前 U1 additive backfill contract，以及 `ota.hahub.top` 的 source-only Nginx route；完成独立可验证测试与 CI。

### 10.2 Frozen inputs

```text
HOMEASSISTANT_SOURCE_REPAIR_BASE=fdb77f29f18158b44102c64b4fcba08f8d066bb8
HAHUB_SOURCE_BASE=140fad2f12e116f25510e968cf87c69409dfc171

DESIGN_AUTHORITY=docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_DESIGN_20261109.md

RELEASE_IDENTITY=homeassistant-2026.10.4
TARGET_ARCHIVE_SIZE_BYTES=835309535
TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
EXPECTED_PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

OTA_ARTIFACT_URL=https://ota.hahub.top/n3w/homeassistant/releases/homeassistant-2026.10.4/homeassistant-arm64.tar.gz

POLICY_SCHEMA=gh.n3w-t1-ha-ota-host-release-policy/2
USB_MEASURED_USABLE_FLOOR_BYTES=15032385536
ROUND_UP_QUANTUM_BYTES=268435456
HA_DATA_BACKUP_MIN_BYTES=1073741824
HA_DATA_GROWTH_RATIO=25_PERCENT
HA_DATA_GROWTH_FLOOR_BYTES=536870912
WORKING_FLOOR_BYTES=536870912
WORKING_TARGET_RATIO=10_PERCENT
RESERVE_FLOOR_BYTES=1073741824
RESERVE_BASE_RATIO=10_PERCENT
UI_TIERS_GB=32,64,128,256,512,1024
NOMINAL_USABLE_GUARD=90_PERCENT
```

### 10.3 Required proof / operations

```text
1. Fresh rebind HomeAssistant main, PR #800 final HEAD, source-repair baseline, current-state docs and final docs-only CI.
2. Prove no executable drift after fdb77f29... before starting source repair.
3. Fresh rebind hahub.top main at/after 140fad2f...; inspect current Nginx/ota_server source before editing.
4. Implement host release policy schema V2 and strict ota.hahub.top URL/origin/redirect contract.
5. Add repository-owned homeassistant-2026.10.4-host-release-policy.json.
6. Derive predecessor_recovery_budget_bytes from exact evidence using the same recovery encoding; if exact evidence is unavailable, STOP rather than guess.
7. Implement hybrid dynamic capacity calculation and integer/rounding guards.
8. Implement runtime HA data read-only measurement contract for /var/lib/n3wfc4-homeassistant, with symlink/external-state fail-closed behavior.
9. Add PREPARE/confirm/INSTALL capacity recomputation boundaries and current U1 additive backfill path.
10. Add public status fields and dynamic standard-market USB size recommendation without exposing raw serial/private host paths.
11. Repair A1 source/deployment authority so exact policy asset is installed root-owned and byte-verified.
12. Add/repair unit/integration tests required by the design.
13. In hahub.top source only, add exact ota.hahub.top HTTPS/static route contract that does not fall through wildcard FRP; do not deploy it.
14. Do not commit OTA binary.
15. Run focused tests, relevant existing regression suites and repository CI.
16. If a CI failure is local/unambiguous and does not expand scope, fix and rerun bounded validation; otherwise STOP and return to high-level model.
17. Archive source-repair closure and exact source heads.
```

### 10.4 PASS

```text
KF147_SOURCE_REPAIR=PASS
POLICY_V2_IMPLEMENTED=true
PRODUCTION_POLICY_ASSET_PRESENT=true
PREDECESSOR_BUDGET_EVIDENCE_BOUND=true
HYBRID_DYNAMIC_CAPACITY_IMPLEMENTED=true
A1_POLICY_DEPLOYMENT_CONTRACT=PASS
U1_ADDITIVE_BACKFILL_CONTRACT=PASS
UI_DYNAMIC_USB_TIER_PROJECTION=PASS
HAHUB_OTA_SOURCE_CONFIG=PASS
REQUIRED_TESTS=PASS
REQUIRED_CI=PASS
LIVE_T1_MUTATION=false
LIVE_OTA_SERVER_MUTATION=false
READY_FOR_KF147_SOURCE_REVIEW=true
```

### 10.5 FAIL

```text
KF147_SOURCE_REPAIR=FAIL_<EXACT_CLASS>
READY_FOR_KF147_SOURCE_REVIEW=false
LIVE_T1_MUTATION=false
LIVE_OTA_SERVER_MUTATION=false
STOP=true
```

特别的合法 STOP：

```text
FAIL_PREDECESSOR_BUDGET_EVIDENCE_MISSING
FAIL_HAHUB_SOURCE_AUTHORITY_DRIFT
FAIL_POLICY_APPROVED_MANIFEST_BINDING
FAIL_DYNAMIC_CAPACITY_CONTRACT
FAIL_A1_DEPLOYMENT_CONTRACT
FAIL_REGRESSION
```

Codex 不得自动进入 live publication、T1 live repair 或 destructive confirmation。

---

## 11. Hard Allowed / Forbidden Scope

Default：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- HomeAssistant PR #800 source/test/docs mutation inside KF-147 design.
- hahub.top repository source/config/test/docs mutation for ota.hahub.top source-only route.
- Create branches/PRs as needed for hahub.top source repair.
- GitHub workflow/CI dispatch caused by source commits.
- Local/simulated Python tests.
- Docker/Nginx config validation in CI or local isolated test environment.
- GitHub archival of source repair, tests, decisions and closure.
- Local unambiguous CI fixes inside the frozen source-repair scope.
```

### FORBIDDEN

```text
- SSH/access/mutation of T1 192.168.68.194.
- Any physical USB action.
- PREPARE replay.
- CONFIRM_USB_ERASE.
- wipefs/partition/mkfs/mount/target download on live T1.
- U2+ or INSTALL.
- Restart of production T1 services.
- Deployment or reload on live hahub.top server.
- Uploading the real OTA binary to live server.
- Board/serial/Flash/NVS/RF access.
- Changing the approved target SHA/size/release identity without a new design decision.
- Guessing predecessor recovery budget.
- Reverting to fixed four-global-capacity constants.
- Broadening Manager privilege or adding Docker socket/block-device access to Manager.
- Merge.
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=REPOSITORY_BRANCHES_AND_CI_ARTIFACTS_ONLY
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

Do not access T1.
Do not deploy hahub.top.
Do not touch physical USB.
Do not repair outside the frozen KF-147 source design.
Do not retry a substantive failure unless the high-level model or
the local-unambiguous-CI-fix rule explicitly permits it.
Do not enter the next gate.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_REPAIR_20261109_01
AUTHORIZATION_GRANTED=true
LIVE_MUTATION_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE_AUTHORIZED=false

============================================================
1. FRESH REBIND
============================================================

READ HomeAssistant:
- repository main
- PR #800
- PR head/base
- SOURCE_REPAIR_BASE_HEAD=fdb77f29f18158b44102c64b4fcba08f8d066bb8
- Current State / Index / Working Context
- KF-147 design authority
- KNOWN_FAILURES
- final docs-only CI at current PR HEAD

PROVE:
- any commits after fdb77f29... before source repair are docs-only handoff/alignment;
- no unexpected executable source drift;
- PR remains open, draft, unmerged.

READ hahub.top:
- main/head
- server-integration Nginx config
- ota_server compose/storage source
- deploy/verify source relevant to Nginx.

If unexpected executable drift or source conflict:
STOP=FAIL_SOURCE_REBIND_DRIFT

============================================================
2. FREEZE TARGET
============================================================

Require exact:
release_identity=homeassistant-2026.10.4
target_size=835309535
target_sha256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
expected_predecessor=local/n3w-homeassistant:2026.10.0-0c73235a
artifact_url=https://ota.hahub.top/n3w/homeassistant/releases/homeassistant-2026.10.4/homeassistant-arm64.tar.gz

Do not alter these values.

============================================================
3. POLICY V2
============================================================

Implement schema:
gh.n3w-t1-ha-ota-host-release-policy/2

Required release fields:
- release_identity
- artifact_url
- target_archive_sha256
- target_archive_size_bytes
- expected_predecessor_image_ref
- predecessor_recovery_budget_bytes
- capacity_policy

Reject:
- scheme != https
- hostname != ota.hahub.top
- userinfo
- query
- fragment
- path outside /n3w/homeassistant/releases/
- filename != homeassistant-arm64.tar.gz
- redirect final URL != exact policy URL
- manifest/release/SHA/size/predecessor drift

============================================================
4. PREDECESSOR RECOVERY BUDGET
============================================================

Use the exact product predecessor-recovery encoding.
Obtain exact measurable export/recovery evidence for the frozen predecessor.

PREDECESSOR_BUDGET =
ROUND_UP_256_MiB(
  max(
    ceil(MEASURED_EXPORT_BYTES * 110%),
    MEASURED_EXPORT_BYTES + 256_MiB
  )
)

If the exact recovery encoding/artifact cannot be exercised or measured
from authoritative source/artifact evidence:
DO_NOT_GUESS
STOP=FAIL_PREDECESSOR_BUDGET_EVIDENCE_MISSING

============================================================
5. HYBRID DYNAMIC CAPACITY
============================================================

HA_DATA_MEASURED_BYTES =
read-only supported backup scope under /var/lib/n3wfc4-homeassistant.

Do not follow symlinks outside the root.
Unsupported external persistent state => fail closed.

HA_DATA_GROWTH_MARGIN =
max(512_MiB, ceil(HA_DATA_MEASURED_BYTES * 25%))

HA_DATA_BACKUP_BUDGET =
ROUND_UP_256_MiB(
  max(1_GiB, HA_DATA_MEASURED_BYTES + HA_DATA_GROWTH_MARGIN)
)

TRANSACTION_WORKING_BUDGET =
ROUND_UP_256_MiB(
  max(512_MiB, ceil(TARGET_ARTIFACT_BYTES * 10%))
)

BASE_REQUIRED =
TARGET_ARTIFACT_BYTES
+ PREDECESSOR_RECOVERY_BUDGET
+ HA_DATA_BACKUP_BUDGET
+ TRANSACTION_WORKING_BUDGET

REMOVABLE_RESERVE =
ROUND_UP_256_MiB(
  max(1_GiB, ceil(BASE_REQUIRED * 10%))
)

USB_REQUIRED_BYTES =
BASE_REQUIRED + REMOVABLE_RESERVE

USB_PASS =
MEASURED_USABLE_BYTES >= 14_GiB
AND
MEASURED_USABLE_BYTES >= USB_REQUIRED_BYTES

All arithmetic is integer-byte, bounded and overflow-checked.

============================================================
6. CAPACITY CHECKPOINTS / CURRENT U1 BACKFILL
============================================================

Implement:
A) PREPARE readonly computation + recommendation.
B) recompute immediately before destructive format; insufficient candidate blocks before wipefs.
C) post-format real ext4 measured usable capacity gate before U2/target download.
D) INSTALL remeasurement/free-space admission; requirement growth blocks before U9.
E) U8 actual verified recovery asset/free-space admission remains authoritative.

For current legacy U1 state:
- additive capacity snapshot backfill only;
- no PREPARE replay;
- no phase reset;
- no candidate reset;
- no confirmation-consumed mutation.

============================================================
7. UI / PUBLIC PROJECTION
============================================================

Add bounded public fields:
- usb_required_bytes_or_null
- usb_recommended_nominal_gb_or_null
- usb_capacity_check_state
- user_message_code_or_null

Allowed nominal tiers:
32,64,128,256,512,1024 GB

Recommendation:
REQUIRED=max(USB_REQUIRED_BYTES,14_GiB)
choose smallest tier where floor(tier*1e9*90%) >= REQUIRED

Primary user copy semantics:
"请插入一个可清空的 {N} GB 或更大容量 U 盘。"
"系统会先检查 U 盘是否合适，在你确认前不会清除任何数据。"

Insertion and erase confirmation remain separate.

Do not expose raw serial/WWN/private host paths.

============================================================
8. A1 DEPLOYMENT CONTRACT
============================================================

Add repository asset:
infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json

Install exactly to:
/etc/n3w-t1-ota/homeassistant-release-source.json

Require:
owner=root
group=root
mode=0644
symlink=false
byte_exact_repository_asset=true

A1 source authority/package must include it.
Post-install validation must byte/hash verify both approved manifest and policy.
A1/destructive path must fail closed when policy missing or cross-binding fails.

============================================================
9. HAHUB.TOP SOURCE-ONLY REPAIR
============================================================

Do not deploy.

Add exact ota.hahub.top source route to the public Nginx integration.

Logical route:
ota.hahub.top:443
-> TLS termination
-> ota_server:80
-> /usr/share/nginx/html
-> host ./ota

Require:
GET/HEAD only
autoindex off
versioned immutable path
application/octet-stream
no upload/delete
no wildcard FRP fallthrough
no OTA binary in Git
no website rsync tree payload

Add source-level config validation/evidence.

============================================================
10. TESTS
============================================================

At minimum prove:
- V1 fixed four-budget production schema rejected.
- V2 exact schema accepted.
- URL/origin/query/fragment/redirect failures.
- manifest/target/predecessor binding drift.
- predecessor budget evidence binding.
- dynamic HA budget boundaries.
- integer/range/rounding failures.
- working/reserve formulas.
- 32/64/128/... recommendation boundaries.
- 14 GiB floor independent of UI recommendation.
- requirement growth before format stops before wipefs.
- requirement growth before INSTALL stops before U9.
- A1 cannot PASS without policy asset.
- deployed policy byte-exact contract.
- legacy U1 additive backfill preserves phase/candidate/confirmation.
- Manager public projection excludes private identity.
- PREPARE and CONFIRM remain separate.
- existing Manager/Broker/HA/DynSec regression suites stay green.
- hahub exact ota host does not fall through wildcard FRP.

============================================================
11. CI
============================================================

Run required focused tests and applicable repository workflows.

Same-run polling rule:
- maximum 3 active checks without terminal state;
- then STOP polling and report links/status.

Local unambiguous CI defect:
- fix inside frozen scope;
- run necessary validation.

Design/scope/live/merge boundary:
- STOP and return to high-level model.

============================================================
12. ARCHIVE
============================================================

Record:
- HomeAssistant exact source repair head/tree
- hahub.top exact source repair head/tree
- changed files
- focused test results
- CI run IDs/conclusions
- source repair closure
- unresolved blockers if any

Do not claim live publication or live repair.

============================================================
13. HARD STOP
============================================================

LIVE_T1_MUTATION=false
LIVE_OTA_SERVER_MUTATION=false
PHYSICAL_USB_MUTATION=false
CONFIRM_USB_ERASE=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false

STOP=true
```

---

## 13. Expected Closure

```text
=== KF147 HOST RELEASE POLICY SOURCE REPAIR CLOSURE ===

GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_REPAIR_20261109_01

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=<true|false>
AUTHORIZATION_CONSUMED=<true|false>

HOMEASSISTANT_REBIND_HEAD=
HOMEASSISTANT_SOURCE_REPAIR_BASE=fdb77f29f18158b44102c64b4fcba08f8d066bb8
HOMEASSISTANT_SOURCE_REPAIR_HEAD=
HOMEASSISTANT_SOURCE_REPAIR_TREE=

HAHUB_BASE_HEAD=140fad2f12e116f25510e968cf87c69409dfc171
HAHUB_SOURCE_REPAIR_HEAD=
HAHUB_SOURCE_REPAIR_TREE=

POLICY_V2_IMPLEMENTED=
PRODUCTION_POLICY_ASSET_PRESENT=
PREDECESSOR_BUDGET_EVIDENCE_BOUND=
HYBRID_DYNAMIC_CAPACITY_IMPLEMENTED=
A1_POLICY_DEPLOYMENT_CONTRACT=
LEGACY_U1_BACKFILL_CONTRACT=
UI_DYNAMIC_USB_TIER_PROJECTION=
HAHUB_OTA_SOURCE_CONFIG=

FOCUSED_TESTS=
HOMEASSISTANT_REQUIRED_CI=
HAHUB_VALIDATION=

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
LIVE_OTA_SERVER_MUTATION=false
PHYSICAL_USB_MUTATION=false
CONFIRM_USB_ERASE=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false

KF147_SOURCE_REPAIR=<PASS|FAIL_EXACT_CLASS>
NEXT_ROUTE=<SOURCE_REVIEW|RETURN_TO_HIGH_LEVEL_MODEL>

STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=KF147_SOURCE_REPAIR_INDEPENDENT_REVIEW
AUTO_EXECUTE_AFTER_PASS=false
NEW_LIVE_AUTHORIZATION_REQUIRED=true
```

PASS 不等于可以部署 `ota.hahub.top`，也不等于可以修改 T1。

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

局部、无歧义、不会扩大范围的 CI 修复例外仍按项目规则允许直接处理。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
KF_ID=KF-147
DOMAIN=T1_HOMEASSISTANT_MANDATORY_USB_OTA
SYMPTOM=HOST_RELEASE_POLICY_MISSING_AND_FIXED_CAPACITY_MODEL_NOT_PRODUCT_SAFE
ROOT_CAUSE=CONSUMER_DEPLOYMENT_AUTHORITY_GAP_PLUS_STATIC_CAPACITY_INPUT_MODEL
FIX_OR_GUARD=POLICY_V2+HYBRID_DYNAMIC_CAPACITY+A1_EXACT_POLICY_DEPLOYMENT+OTA_ORIGIN_CONTRACT
STATUS=SOURCE_DESIGN_CLOSED_SOURCE_REPAIR_READY
```

本轮额外 CI 事件属于 docs authority alignment，不新增 KF：

```text
DOCS_CI_FAILURE=state_authority_link_missing/state_product_source_missing
ROOT_CAUSE=LATEST_STATE_FIRST_SECTION_INCOMPLETE_FOR_EXISTING_CHECKER
NEW_KF_REQUIRED=false
REPAIR_HEAD=fdb77f29f18158b44102c64b4fcba08f8d066bb8
```

---

## 16. New Chat Start Prompt

```text
阅读：
docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_SOURCE_DESIGN_TO_SOURCE_REPAIR_NEW_CHAT_HANDOFF_V1.0_20261109.md

同时读取：
- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_DESIGN_20261109.md

fresh rebind：
- repository main
- PR #800
- SOURCE_REPAIR_BASE_HEAD=fdb77f29f18158b44102c64b4fcba08f8d066bb8
- hahub.top main
- final handoff/docs CI

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

本轮继续采用“高阶模型思考 + Codex 低阶模型执行”。
Codex 必须将 exact DSL execution contract 机械编译为最低必要命令；
PREWRITTEN_EXECUTOR_REQUIRED=false。

当前只进入：
NEXT_ONE_GATE=
N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_REPAIR_20261109_01

本 gate 允许 HomeAssistant 与 hahub.top 的 source/test/CI/GitHub 归档，
但不允许 T1 access/live mutation、真实 USB 操作、线上 ota.hahub.top 部署、
CONFIRM_USB_ERASE、U2+、board access 或 merge。

先完成 fresh rebind，并确认 fdb77f29... 之后到 handoff HEAD 没有意外 executable drift。
如果 predecessor recovery budget 缺少 exact evidence，不得猜值，必须 STOP。

不要重放 consumed/superseded authorization，不要重新进入已关闭 USB 故障路线，
不要自动跨越 source repair 后的独立复核或 live gate。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=KF147_SOURCE_DESIGN_CLOSED_SOURCE_REPAIR_READY
CURRENT_STOP_POINT=SOURCE_REPAIR_NOT_STARTED

SOURCE_REPAIR_BASE_HEAD=fdb77f29f18158b44102c64b4fcba08f8d066bb8
SOURCE_DEFECT_PROVEN=true
CURRENT_BLOCKER=KF147_SOURCE_IMPLEMENTATION_AND_EXACT_PREDECESSOR_BUDGET_EVIDENCE

LIVE_SYSTEM_STATE=U1_ACTIVE_USB_REQUIRED_CONFIRMATION_WITH_SANDISK_EXTREME_INSERTED_LAST_PROVEN
LIVE_MUTATION_IN_THIS_HANDOFF=false

PREPARE_REPLAY=false
OLD_CONFIRM_USB_ERASE_AUTHORIZATION=SUPERSEDED_UNCLAIMED

NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_REPAIR_20261109_01

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
