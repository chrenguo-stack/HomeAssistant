# 温室环境监测系统（ESP32-C6）
# N3-W / T1 Golden Master R2C Read-only Probe Source Continuation
# 新会话交接文档 V1.0 — 2026-10-13

```text
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
HANDOFF_TEMPLATE_SOURCE=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
HANDOFF_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
EXACT_HANDOFF_STANDARD_AUTHORITY=NOT_SPECIFIED
```

> 本文严格使用 candidate branch 当前的 `NEW_CHAT_HANDOFF_TEMPLATE.md` V1.3。  
> 不使用 historical `4300890dff0ce63d5a547df21426e287d084d9ee` 中的旧模板，也不把 `N3W_PROJECT_WORKING_CONTEXT.md` 当作 handoff 模板。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=R2C_READONLY_PROBE_SOURCE_IMPLEMENTATION
CURRENT_STOP_POINT=E1-E4 initial collectors + E2/E3 bounded armbian-firstrun static analysis implemented at source head a626eb88; exact-head CI incomplete
NEXT_ONE_GATE=N3W_T1_GOLDEN_MASTER_R2C_READONLY_PROBE_E5_E9_SOURCE_CONTINUATION_20261013_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本地对话最后明确可见的 source head 是 `b2b0a63292096fb624e733891466663d19abd86a`。
fresh GitHub rebind 发现 PR #541 已前进 9 个 source/test commits 到
`a626eb8827a584b7a84f3838beaf08f86766cd73`。这 9 个提交只改 R2C 的
`n3w_t1_r2c_firstrun.py`、`n3w_t1_r2c_collectors.py` 及两个 focused tests，
补入 E2/E3 的 bounded `armbian-firstrun` 静态分析和 fail-closed 回归。

本会话已经按 fresh GitHub authority 完成本地对话 ↔ GitHub 对齐，并将结果写入
`N3W_CURRENT_STATE.md` 和 `N3W_CURRENT_STATE_INDEX.md`。新会话不要回退这 9 个 source/test commits，
也不要把它们误认为已经完成 CI/source closure。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=2
STAGE_OVERRIDES=1) current exact source head CI must be freshly rebound before further source continuation; 2) actual R2C T1 evidence execution remains separately authorized and is not part of the next gate
```

继续遵守 working context 的 GitHub/CI 规则：短调用、写后复核、同一 HEAD 单次回复最多轮询 3 次；
若仍 pending，给直接链接并停止轮询；已明确定位的同一 Gate 低风险源码/测试问题直接修复，不再逐项申请授权。

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=GOLDEN_MASTER_BUILD→MASTER_VALIDATED→FINAL_SEAL→DISK_IMAGE_CAPTURED→CLONE_WRITE_VERIFIED→CLONE_BOOTED_UNPROVISIONED→EXPLICIT_PROVISION_COMMAND→DEVICE_READY→FACTORY_ACCEPTED→ACTIVE
FINAL_ACCEPTANCE_TARGET=同一 Golden Master 克隆到不同 T1 后 OS/host identity 与产品 identity 均唯一且稳定；产品秘密不进入公共母盘；普通 boot 不创建新的产品实例
DEFERRED_OR_OUT_OF_SCOPE=本 next gate 不访问 T1、不执行实际 R2C evidence、不实现真实 Seal mutation、不做 disk capture、不做 clone A/B acceptance、不 merge PR #541
```

---

## 3. Frozen Authorities

### 3.1 Repository / source

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
MAIN_TREE=ee977996a4c962097684519841dce2e3bcba23f2

CANDIDATE_REF=plan/n3w-t1-full-fresh-install-from-zero-20261010
R2C_SOURCE_HEAD=a626eb8827a584b7a84f3838beaf08f86766cd73
R2C_SOURCE_TREE=4e13eea60bf175e1e00a5aecc6c17e7ee65f902b

ALIGNMENT_DOCS_HEAD=0866a6cb7e7750c088bdd2e0d2cd00ff0217d01c
ALIGNMENT_DOCS_TREE=c4b7bd88ded1e1082ebe2c100535c4262f70d262

PR=541
PR_STATE=OPEN_DRAFT
PR_MERGED=false
```

本 handoff 提交后 candidate branch 会再次发生 docs-only advance。新会话开头必须 fresh rebind，
并继续把 `a626eb88...` 视为当前已实现 R2C source 的精确基线，除非 fresh compare 证明又有新的 source/test/workflow drift。

### 3.2 Current template authority

```text
HANDOFF_TEMPLATE_VERSION=1.3
HANDOFF_TEMPLATE_PATH=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
HANDOFF_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
HISTORICAL_430089_TEMPLATE_IS_CURRENT=false
```

### 3.3 Design / evidence authorities

```text
R2C_PREPARATION_CONTRACT=docs/development/N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_READONLY_EVIDENCE_PREPARATION_20261013.md
R2_SOURCE_DESIGN=docs/development/N3W_T1_GOLDEN_MASTER_R2_BUILD_AND_FINAL_SEAL_SOURCE_DESIGN_20261013.md
P2B_TARGET_EVIDENCE=docs/development/N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION_CLOSURE_20261013.md
LIFECYCLE_ADR=docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md
KNOWN_FAILURE_GUARD=KF-113
```

### 3.4 Target identity

```text
TARGET_OS=Armbian 26.05.0
TARGET_ARCH=arm64
TARGET_KERNEL_ARCH=aarch64
TARGET_BOARD=S912-Phicomm-T1
```

公开 handoff 不包含私有 SSH locator、私网地址、原始 machine-id、SSH fingerprint 或 credential。

---

## 4. Current Live Baseline

当前 source-only 工作不需要 fresh live baseline，因此本会话没有访问 T1/board/runtime。

```text
MANAGER_STATE=UNKNOWN_FRESH
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH
HOMEASSISTANT_STATE=UNKNOWN_FRESH

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=UNKNOWN_FRESH
BOARD_B_POWER_STATE=UNKNOWN_FRESH
BOARD_B_LOCATION_ROLE=UNKNOWN_FRESH

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
```

actual R2C evidence execution 以后若获新授权，必须在执行前重新绑定目标机和 SSH host-key authority；
当前 handoff 不携带这些私有 locator。

---

## 5. Proven Current Facts

```text
PR541_OPEN_DRAFT=true
MAIN_UNCHANGED=true
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee

LOCAL_DIALOGUE_LAST_EXPLICIT_SOURCE_HEAD=b2b0a63292096fb624e733891466663d19abd86a
FRESH_R2C_SOURCE_HEAD=a626eb8827a584b7a84f3838beaf08f86766cd73
SOURCE_ADVANCE_FROM_LOCAL_DIALOGUE=9_COMMITS
SOURCE_ADVANCE_FILE_COUNT=4

R2C_BOUNDED_FILE_PRIMITIVES=IMPLEMENTED
R2C_COMMAND_ALLOWLIST_BOUNDARY=IMPLEMENTED
R2C_EVIDENCE_SCHEMA=IMPLEMENTED
R2C_PUBLIC_BASE_PROJECTION=IMPLEMENTED

R2C_E1_COLLECTION=IMPLEMENTED_INITIAL
R2C_E2_COLLECTION=IMPLEMENTED_INITIAL
R2C_E3_COLLECTION=IMPLEMENTED_INITIAL
R2C_E4_COLLECTION=IMPLEMENTED_INITIAL
R2C_E5_E9=NOT_COMPLETE
R2C_REMOTE_EXECUTOR=NOT_IMPLEMENTED
EXECUTION_READY=false

R2A_SOURCE_REPAIR=CLOSED_SOURCE
R2B_HOST_INDEPENDENT_SOURCE_REPAIR=CLOSED_SOURCE
A1_A10=CLOSED_SOURCE

R2C_TARGET_ARMBIAN_SEAL_ADAPTER=NOT_ENTERED
OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_EVIDENCE_REQUIRED=true
DISK_CAPTURE_READY=false
```

E2/E3 当前 source 会：

- bounded 读取 `/usr/lib/armbian/armbian-firstrun`；
- 只在批准的 `/usr/lib/armbian/` helper root 内递归；
- helper count ≤ 16、depth ≤ 4；
- 动态 source、eval/command substitution、外部 download、越界 source fail closed；
- E3 只输出引用配置键名和 BOOLEAN/DEFAULT/CUSTOM/ABSENT/UNKNOWN 分类，不输出配置原值；
- source closure 未完成时 E3 保持 UNKNOWN，不会误报 complete。

```text
SOURCE_HEAD_CI_SNAPSHOT_AFTER_THIRD_POLL=10/27_SUCCESS_0_FAILURE_17_PENDING
PUBLIC_REPOSITORY_SAFETY_CI=PASS
GOLDEN_MASTER_SOURCE_CI=PENDING
CI_FAILURE_AT_HANDOFF_SNAPSHOT=false
```

第三次轮询后仍 pending，因此本会话按 working context 停止继续轮询：

- Golden Master source CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/38413146226
- PR #541 checks: https://github.com/chrenguo-stack/HomeAssistant/pull/541/checks

```text
INFERENCE_NONE=NONE
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=2

CURRENT_BLOCKER_1=R2C_PROBE_SOURCE_INCOMPLETE_E5_E9
ROOT_CAUSE_1=E5 SSH / E6 NetworkManager+netplan / E7 journald / E8 random-seed / E9 boot-order and reachability evidence collectors are not yet implemented
PROVEN_BY_1=fresh source inspection at a626eb8827a584b7a84f3838beaf08f86766cd73

CURRENT_BLOCKER_2=R2C_SOURCE_HEAD_CI_NOT_CLOSED
ROOT_CAUSE_2=exact source head a626eb88 still had pending workflows after third poll
PROVEN_BY_2=GitHub Actions exact-head snapshot

SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
LIVE_PRODUCT_FAILURE_PROVEN=false
```

当前不把“CI 尚未跑完”或“E5-E9 尚未实现”误报成 target runtime failure。

---

## 7. Closed / Forbidden Routes

```text
R2A_R2B_SOURCE_REOPEN=CLOSED:closed exact source review; only new direct counter-evidence may reopen
A1_A10_REENTRY=CLOSED:do not replay resolved R2A/R2B blockers
GENERIC_LINUX_ASSUMPTION_AS_CLONE_AUTHORITY=CLOSED:target-specific evidence required
P2B_AUTHORIZATION_REPLAY=FORBIDDEN
ACTUAL_R2C_T1_EXECUTION_WITHOUT_NEW_AUTH=FORBIDDEN
FINAL_GOLDEN_CAPTURE_WITH_POPULATED_MACHINE_ID=FORBIDDEN
FINAL_GOLDEN_CAPTURE_WITH_POPULATED_SSH_HOST_KEYS=FORBIDDEN
ARMBIAN_FIRSTRUN_AS_UNIQUENESS_AUTHORITY=FORBIDDEN_UNTIL_PROVEN
NETWORKMANAGER_AUTO_UNIQUENESS_ASSUMPTION=FORBIDDEN_UNTIL_PROVEN
REAL_SEAL_OS_IDENTITY_MUTATION_BEFORE_R2C=FORBIDDEN
DISK_IMAGE_CAPTURE_BEFORE_SEAL_ACCEPTANCE=FORBIDDEN
PR541_AUTO_MERGE=FORBIDDEN
```

---

## 8. Authorization Ledger

历史 P2B 授权只保留 replay guard：

```text
AUTHORIZATION=N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION
CLAIMED=true
CONSUMED=false
RESULT=CLOSED_PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NEW_R2C_TARGET_ARMBIAN_READONLY_EVIDENCE_AUTHORIZATION_REQUIRED_FOR_ACTUAL_EXECUTION
```

当前 source continuation 不需要 live authorization：

```text
SOURCE_CONTINUATION_AUTHORIZATION=NOT_REQUIRED:REPOSITORY_ONLY
PROPOSED_AUTHORIZATION=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE
GRANTED=false
ACTUAL_T1_EXECUTION_AUTHORIZATION_GRANTED=false
```

---

## 9. Rollback Authority

next gate 只修改 GitHub source/tests，不修改 live system。

```text
ROLLBACK_BASELINE=a626eb8827a584b7a84f3838beaf08f86766cd73
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
ROLLBACK_AUTHORITY_PATH_OR_ID=GIT_HISTORY_EXACT_COMMIT
RESTART_SCOPE_ALLOWED=NONE
SECOND_ATTEMPT_ALLOWED=true:SAME_GATE_SOURCE_TEST_REPAIR_ONLY
LIVE_ROLLBACK_AUTHORITY=NOT_APPLICABLE:NO_LIVE_MUTATION
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_GOLDEN_MASTER_R2C_READONLY_PROBE_E5_E9_SOURCE_CONTINUATION_20261013_01
```

### Purpose

先 fresh rebind 当前 branch/PR/source CI。若 `a626eb88...` CI 已失败，只做同一 source gate 的最小修复；
若 CI 已绿，先做 focused source review，再继续实现 R2C remaining E5-E9 collectors 和本地隔离测试。

本 gate 只完成 repository-side probe source；不能证明 target OS identity semantics，不能访问 T1，
不能实现 remote SSH executor，也不能自动进入 actual evidence execution。

### Inputs

```text
INPUT_1=R2C_SOURCE_HEAD:a626eb8827a584b7a84f3838beaf08f86766cd73
INPUT_2=R2C_PREPARATION_CONTRACT:docs/development/N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_READONLY_EVIDENCE_PREPARATION_20261013.md
INPUT_3=R2_SOURCE_DESIGN:docs/development/N3W_T1_GOLDEN_MASTER_R2_BUILD_AND_FINAL_SEAL_SOURCE_DESIGN_20261013.md
INPUT_4=P2B_TARGET_EVIDENCE:docs/development/N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION_CLOSURE_20261013.md
INPUT_5=ADR:docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md
INPUT_6=KF-113
```

### Operations

```text
1. fresh rebind main / PR #541 / candidate / source head / current state / current template
2. fresh read exact a626 source-head CI; if failed, inspect job/log and repair only the proven same-gate source/test issue
3. if exact source head is green, focused-review E1-E4/E2-E3 boundaries before extending source
4. implement E5: SSH key metadata, key-generation conditions, approved HostKey path classes, socket/keygen relation; never read private key body
5. implement E6: bounded NM/netplan identity inventory and identity-field classification; no SSID/IP/MAC/UUID raw public values
6. implement E7: bounded journald identity directory/storage-policy classification; no journal body
7. implement E8: random-seed metadata/owner/order only; never read/hash seed body
8. implement E9: bounded unit dependency/condition/activation-order evidence; After/Requires semantics remain distinct and unresolved edges remain UNKNOWN
9. add isolated fixtures/regressions for every fail-closed boundary and privacy rule
10. run/observe exact-head CI according to CI_POLL_MAX=3
11. STOP before remote executor or T1 access
```

### PASS / FAIL / STOP

```text
PASS_IF=E5-E9 source collectors and focused isolation tests satisfy the frozen read-only/privacy/UNKNOWN-vs-ABSENT semantics, exact-head required CI is green, and focused source review finds no blocker
FAIL_IF=collector requires target mutation/generic Linux assumption/unsafe raw identity retention, or exact-head CI/source review finds a blocker that cannot be closed inside this bounded source gate
STOP_BOUNDARY=repository-side E1-E9 probe source complete and reviewed; remote executor and actual T1 execution remain not entered

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
MERGE=false
```

### ALLOWED

```text
- fresh GitHub read-only rebind
- repository source/test inspection
- bounded changes under tools/n3w_t1_r2c_*.py and tests/tools/test_n3w_t1_r2c_*.py required by E5-E9
- same-gate low-risk source/test/CI repairs after proven failure
- current-state/index/handoff documentation alignment
- GitHub CI inspection with max-three-poll rule
```

### FORBIDDEN

```text
- SSH/T1 access
- Mac-side private target locator retrieval for live execution
- machine-id / D-Bus machine-id mutation
- SSH host-key delete/generate/change
- NetworkManager/netplan mutation
- journald/random-seed mutation or content reads outside frozen metadata rules
- systemd service start/stop/restart/reload/enable/disable/daemon-reload
- Docker/Broker/Manager/Home Assistant runtime mutation/start
- remote R2C executor execution
- Golden Master live build/final Seal
- disk capture/write
- board/USB/serial/Flash/NVS/RF access
- P2B authorization replay
- PR #541 merge
```

---

## 12. Execution Contract

```text
EXECUTOR=HIGH_LEVEL_MODEL_WITH_GITHUB_CONNECTOR
EXECUTION_METHOD=chat-tool
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false

CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

Source/test changes are authored directly in the repository and reviewed against the frozen R2C evidence contract.
No Mac Terminal/T1 executor is needed for the next gate.

如果 exact-head CI 失败：

```text
READ_FAILED_JOB_AND_LOG=true
CLASSIFY_BEFORE_REPAIR=true
SAME_GATE_MINIMAL_REPAIR=true
ASK_USER_FOR_ROUTINE_REPAIR=false
CROSS_GATE_AUTO_EXECUTE=false
```

如果 CI 全绿：直接完成本 Gate 已要求的 focused review，不等待用户再次说“开始复核”。

---

## 13. Expected Closure

```text
=== N3W_T1_GOLDEN_MASTER_R2C_READONLY_PROBE_E5_E9_SOURCE_CONTINUATION_20261013_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=NOT_REQUIRED:REPOSITORY_SOURCE_ONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

SOURCE_BASE=
SOURCE_HEAD=
SOURCE_TREE=
EXACT_HEAD_CI=

E1_COLLECTION=
E2_COLLECTION=
E3_COLLECTION=
E4_COLLECTION=
E5_COLLECTION=
E6_COLLECTION=
E7_COLLECTION=
E8_COLLECTION=
E9_COLLECTION=

PRIVATE_PUBLIC_BOUNDARY=
UNKNOWN_ABSENT_SEMANTICS=
SOURCE_REVIEW=

R2C_REMOTE_EXECUTOR=NOT_ENTERED
ACTUAL_T1_EXECUTION_AUTHORIZATION_GRANTED=false

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false

R2C_E5_E9_SOURCE_GATE_RESULT=
NEXT_ROUTE=N3W_T1_GOLDEN_MASTER_R2C_READONLY_REMOTE_EXECUTOR_SOURCE_PREPARATION
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_GOLDEN_MASTER_R2C_READONLY_REMOTE_EXECUTOR_SOURCE_PREPARATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=false:next stage remains repository-only source preparation

AUTO_REPAIR_AFTER_FAIL=false:except proven low-risk repair inside the same current gate
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

actual T1 execution remains later and requires a new explicit R2C authorization.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF-113
NEW_KF_REQUIRED=false
```

本阶段出现过的 Ruff、public-safety fixture、evidence-classification 等 CI failure 都已按同一 source gate 修正；
当前没有证据支持新增一个 product/runtime KF。若 E5-E9 后续发现新的真实 failure class，再更新 KF。

---

## 16. New Chat Start Prompt

默认读取集：

```text
1. 本 handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. docs/development/N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_READONLY_EVIDENCE_PREPARATION_20261013.md
7. docs/development/N3W_T1_GOLDEN_MASTER_R2_BUILD_AND_FINAL_SEAL_SOURCE_DESIGN_20261013.md
8. docs/development/N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION_CLOSURE_20261013.md
9. docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md
10. candidate branch current docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md V1.3
```

建议启动文本：

```text
阅读《N3W_T1_GOLDEN_MASTER_R2C_READONLY_PROBE_SOURCE_CONTINUATION_NEW_CHAT_HANDOFF_V1.0_20261013.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_READONLY_EVIDENCE_PREPARATION_20261013.md
- docs/development/N3W_T1_GOLDEN_MASTER_R2_BUILD_AND_FINAL_SEAL_SOURCE_DESIGN_20261013.md
- docs/development/N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION_CLOSURE_20261013.md
- docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md
- candidate branch 当前 docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

先 fresh rebind repository main、PR #541、candidate branch、current state/index 和当前模板。
特别确认 handoff 提交后的 docs-only advance 是否引入新的 source/test/workflow drift。

当前 source authority：
R2C_SOURCE_HEAD=a626eb8827a584b7a84f3838beaf08f86766cd73

当前只进入：
NEXT_ONE_GATE=N3W_T1_GOLDEN_MASTER_R2C_READONLY_PROBE_E5_E9_SOURCE_CONTINUATION_20261013_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
T1_ACCESS=false

承认：
- R2A_SOURCE_REPAIR=CLOSED_SOURCE
- R2B_HOST_INDEPENDENT_SOURCE_REPAIR=CLOSED_SOURCE
- A1-A10=CLOSED_SOURCE
- E1/E2/E3/E4 initial source 已实现
- E5-E9 尚未完成
- R2C_REMOTE_EXECUTOR=NOT_IMPLEMENTED
- EXECUTION_READY=false
- OS_IDENTITY_SEMANTICS_PROVEN=false
- CONTROLLED_CLONE_BOOT_EVIDENCE_REQUIRED=true

先检查 a626 exact-head CI。若失败，读 job/log 后在同一 source gate 做最小修复；
若全绿，直接 focused review 后继续 E5-E9。不要重新等待 routine repair 授权。

不要访问 T1/SSH，不要重放 P2B authorization，不要进入 real Seal/disk capture/clone acceptance，
不要自动跨越到 remote executor 或 actual R2C evidence execution，不要 merge PR #541。
```

本 handoff 使用 current template V1.3 + working context V1.1；没有指定 historical exact handoff standard authority。

---

## 17. Final Frozen State

```text
CURRENT_STAGE=R2C_READONLY_PROBE_SOURCE_IMPLEMENTATION
CURRENT_STOP_POINT=a626eb88 source contains E1-E4 initial collectors plus E2/E3 bounded firstrun analysis; exact-head CI still pending at third poll
CURRENT_BLOCKER=E5_E9_NOT_IMPLEMENTED + EXACT_SOURCE_HEAD_CI_NOT_CLOSED
LIVE_SYSTEM_STATE=UNKNOWN_FRESH_NOT_REQUIRED_FOR_SOURCE_GATE
NEXT_ONE_GATE=N3W_T1_GOLDEN_MASTER_R2C_READONLY_PROBE_E5_E9_SOURCE_CONTINUATION_20261013_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1

PROJECT_WORKING_CONTEXT_REFERENCED=PASS
LONG_TERM_RULE_DUPLICATION_MINIMIZED=PASS
STAGE_SPECIFIC_OVERRIDES_EXPLICIT=PASS
PRIVATE_CONTEXT_EXCLUDED_FROM_PUBLIC_HANDOFF=PASS

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
EXECUTION_CONTRACT_SELF_CONTAINED=PASS
CI_CONTINUATION_HARD_RULES_PRESENT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
TEAM_WORKSPACE_STATUS_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
