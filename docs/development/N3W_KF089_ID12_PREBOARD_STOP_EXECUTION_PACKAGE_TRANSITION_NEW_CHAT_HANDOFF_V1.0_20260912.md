# 温室环境监测系统（ESP32-C6）
# N3-W / KF-089 — ID12 pre-board STOP + Execution Package transition
# 新会话交接文档 V1.0 — 2026-09-12

```text
HANDOFF_PROCESS_MODEL=USER_APPROVED_EXECUTION_PACKAGE_TRANSITION
HANDOFF_STANDARD_CANDIDATE_VERSION=1.1
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
CODEX_CODE_AUTHORING=false
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> Process note: PR #388 contains the candidate `NEW_CHAT_HANDOFF_STANDARD.md` v1.1 and the updated handoff template. It is open and unmerged. This handoff records the user's explicit transition away from DSL command compilation. The next chat must align PR #388 with the stricter user direction that the high-level model authors all project/execution code and Codex only executes exact committed code and reports results.

---

## 0. 会话切换结论

This conversation is ending after:

- one consumed ID11 RF capture;
- two incomplete post-RF evidence-recovery attempts;
- proof that the old DSL/summary workflow can lose execution detail;
- creation of PR #388 to replace DSL command synthesis with versioned Execution Packages;
- user direction to make the high-level model the sole code author and GitHub committer, with Codex acting only as exact executor/result reporter.

```text
CURRENT_STAGE=N3W_KF089_RELAY_END_TO_END_EVIDENCE_RECOVERY
CURRENT_STOP_POINT=ID12_STOPPED_BEFORE_BOARD_ACCESS
NEXT_ONE_GATE=N3W_KF089_EXECUTION_PACKAGE_ROLE_AND_STORAGE_FREEZE
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

The next chat must not reconstruct or repeat the ID11 RF experiment. It starts from the process/storage freeze, then authors the successor read-only recovery package.

---

## 1. 执行模式与首要原则

### 1.0 首要原则

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
WORKFLOW_CONVENTIONS_ARE_MEANS_NOT_GOALS=true
TEAM_SHARED_WORKSPACE=GITHUB
CHAT_AND_EXECUTOR_SESSIONS=EPHEMERAL_WORKSPACES
```

### 1.1 User-approved future role split

The user explicitly moved the project away from the old DSL execution style.

Freeze for the next chat:

```text
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
HIGH_LEVEL_MODEL_WRITES_EXECUTION_CODE=true
HIGH_LEVEL_MODEL_COMMITS_CODE_TO_GITHUB=true
CODEX_CODE_AUTHORING=false
CODEX_AD_HOC_COMMAND_SYNTHESIS=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
```

Meaning:

- the high-level model designs and writes product code, tooling code, execution executors, manifests, evidence schemas, and tests;
- useful code must be committed to GitHub before Codex is asked to use it;
- Codex may execute exact committed code, run tests/commands explicitly defined by that code, and return raw evidence/results;
- Codex does not improvise implementation, patch executor code, or translate long-form DSL into substitute commands during an execution gate;
- if the exact executor is wrong or incomplete, execution stops and returns to the high-level model for a new GitHub code revision.

### 1.2 Execution-package storage decision to freeze next

Recommended repository layout:

```text
EXECUTION_PACKAGE_STORAGE_MODEL=STAGE_AND_GATE_SCOPED
EXECUTION_PACKAGE_ROOT=tools/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_TEST_ROOT=tests/execution_packages/<project>/<stage>/<gate_id>/
CODEX_ONLY_FOLDER=false
```

Typical package:

```text
tools/execution_packages/n3w/kf089/<gate_id>/
  TASK.md
  executor.py
  manifest.json
  evidence_schema.json
  README.md                 # optional if TASK.md is sufficient

tests/execution_packages/n3w/kf089/<gate_id>/
  test_executor.py
```

Rationale to preserve into the next chat:

- do **not** create one opaque folder whose meaning is merely “files for Codex”;
- execution code is project engineering code and should be discoverable by product stage/gate;
- exact historical gate packages remain reproducible and reviewable;
- genuinely reusable helpers may later move to a small shared module only after real reuse is demonstrated;
- avoid premature generic framework construction.

The next chat must formalize this in PR #388 before using it as the project-wide process authority.

### 1.3 Evidence semantics

Every later conclusion must distinguish:

```text
OBSERVED=directly present in raw evidence, exact source, or live readback
DERIVED=strictly derivable from OBSERVED facts
HYPOTHESIS=plausible but unproven
```

Do not promote a hypothesis to root cause.

---

## 2. Product North Star

```text
NORTH_STAR=N3W_RELAY_END_TO_END_RELIABLE_TELEMETRY
CURRENT_PRODUCT_ROUTE=PROVE_BOARD_B_TO_BOARD_A_TO_T1_RELAY_DATA_PATH
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

Already proven:

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
```

Deferred/forbidden without new direct evidence:

```text
FULL_CUSTOM_WIFI_ESPNOW_RADIO_OWNERSHIP_ARCHITECTURE=DEFERRED
ASSOCIATED_OFFCHANNEL_LIFECYCLE_REOPEN=FORBIDDEN_WITHOUT_NEW_COUNTER_EVIDENCE
NEW_RELAY_PROTOCOL_DESIGN=OUT_OF_SCOPE
PAIRING_OR_KEY_REDESIGN=OUT_OF_SCOPE
RETRY_POLICY_CHANGE=OUT_OF_SCOPE
```

---

## 3. Frozen Authorities

### 3.1 Repository / source

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
ACTIVE_N3W_PROGRESS_PR=387
ACTIVE_N3W_PROGRESS_BRANCH=docs/n3w-kf089-board-b-physical-successor-preclaim-20260911
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
```

### 3.2 Process candidate

```text
PROCESS_PR=388
PROCESS_BRANCH=docs/handoff-execution-package-v1-1-20260912
PROCESS_HEAD=81c89fd4765081603fabbbeaaf99692623ef63f3
PROCESS_PR_STATE=OPEN_UNMERGED
PROCESS_STANDARD_CANDIDATE_VERSION=1.1
```

PR #388 currently establishes:

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODEX_ROLE=EXACT_EXECUTOR
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
```

But its wording still allows Codex to implement/repair a package during a host-only development gate. The user's later direction is stricter and must supersede that wording before merge:

```text
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_CODE_AUTHORING=false
```

### 3.3 Board identity mapping

```text
BOARD_A_BASE_MAC_SUFFIX=F3:50
BOARD_B_BASE_MAC_SUFFIX=F4:5C
USB_PORT_IS_LOCATOR_ONLY=true
FULL_PRIVATE_MAC_MUST_NOT_BE_COMMITTED=true
```

### 3.4 NVS diagnostic geometry

```text
NVS_OFFSET=0x790000
NVS_SIZE=0x70000
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
DIAGNOSTIC_KEY=snapshot
EXPECTED_SCHEMA_VERSION=5
```

---

## 4. Current Live Baseline

```text
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
AUTHORITATIVE_MANAGER_COUNT=1
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_MANAGER_COUNT=0
LEGACY_BROKER_COUNT=0

BOARD_B_BOOT_RECOVERY=CLOSED_ENOUGH_FOR_RELAY_TESTING
PRODUCT_RUNTIME_AFTER_POWER_CYCLE=PASS
N3W_RUNTIME=PASS
SCHEMA_V5_RUNTIME_STATE=PASS

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_WRITE=false
RF_EXECUTION=false
```

Post-ID11 snapshot preservation is not proven:

```text
POST_RF_APPLICATION_BOOT_OBSERVED=false
ID11_SCHEMA_V5_SNAPSHOT_PRESERVATION=UNKNOWN
```

ID12 did not access Board B, so it did not itself alter the board or its NVS evidence.

---

## 5. Proven Current Facts

### 5.1 ID11 RF capture

```text
AUTHORIZATION_ID=N3W_KF089_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL_20260912_11
ID11_CLAIMED=true
ID11_CONSUMED=true
REPLAY_PERMITTED=false
RF_WINDOW_COMPLETED=true
RF_WINDOW_SECONDS=90
RF_WINDOW_START=2026-09-12T01:11:08.309724329Z
RF_WINDOW_END=2026-09-12T01:12:38.355480750Z
BOARD_A_DIRECT_BASELINE=true
BOARD_A_DIRECT_DURING_WINDOW=true
BOARD_B_COLD_BOOT_EXECUTED=true
SELECTIVE_RF_ZONE_USED=true
BOARD_B_DIRECT_INGRESS_COUNT=0
BOARD_B_RELAY_INGRESS_COUNT=0
BOARD_B_ACCEPTED_RELAY_COUNT=0
SECOND_RF_CAPTURE=false
```

This does **not** prove relay product failure because A/B Schema-v5 counters remain unread.

### 5.2 ID11 historical evidence gap

```text
ID11_IDENTITY_COMMAND_RECOVERED=false
ID11_IDENTITY_STDOUT_RECOVERED=false
ID11_IDENTITY_STDERR_RECOVERED=false
ID11_VALIDATION_SOURCE_RECOVERED=false
IDENTITY_FAILURE_CLASS=EVIDENCE_INCOMPLETE
```

Therefore the earlier identity-normalization root cause cannot be factually replayed.

### 5.3 ID12 STOP

```text
AUTHORIZATION_ID=N3W_KF089_ID11_AB_SCHEMA_V5_READONLY_RECOVERY_20260912_12
ID12_CLAIMED=true
ID12_CONSUMED=true
REPLAY_PERMITTED=false

BOARD_B_IDENTITY_PASS=NOT_EXECUTED
BOARD_B_NVS_READ_PASS=NOT_EXECUTED
BOARD_A_IDENTITY_PASS=NOT_EXECUTED
BOARD_A_NVS_READ_PASS=NOT_EXECUTED
FIRST_UNPROVEN_OR_FAILED_STAGE=BOARD_B_IDENTITY_COMMAND_START
RAW_EVIDENCE_PERSISTED=false
SECOND_RF_CAPTURE=false
APPLICATION_BOOT=false
FLASH_WRITE=false
NVS_WRITE=false
AUTO_RETRY=false
RESULT=STOP
```

Observed STOP statement:

```text
esptool wrapper had no executable permission;
command failed before read-mac;
Board B was not accessed.
```

Facts that are **not proven**:

```text
WRAPPER_IS_PYTHON_SCRIPT=NOT_PROVEN
DIRECT_WRAPPER_EXECUTION_USED=NOT_PROVEN
MISSING_EXECUTABLE_BIT_IS_ROOT_CAUSE=NOT_PROVEN
CORRECT_FIX_IS_PYTHON_PLUS_WRAPPER=NOT_PROVEN
```

Do not resume from the previous assistant hypothesis that these were proven.

---

## 6. Current Root Cause / Blockers

### Blocker A — ID11 decisive counters unread

```text
BLOCKER=BOARD_B_AND_BOARD_A_SCHEMA_V5_COUNTERS_NOT_RECOVERED
PRODUCT_DEFECT_PROVEN=false
```

Needed fields remain:

Board B:

```text
schema_version
boot_session
snapshot_uptime_ms
path_state
relay_active_count
relay_telemetry_attempts
relay_telemetry_success
unicast_completion_count
unicast_completion_success
unicast_completion_failure
```

Board A:

```text
schema_version
boot_session
snapshot_uptime_ms
path_state
compact_rx_count
compact_state_reject_count
compact_child_binding_failure
compact_decode_success
compact_decode_failure
compact_wrap_failure
compact_forward_attempts
compact_forward_submit_success
compact_forward_submit_failure
```

### Blocker B — execution evidence quality

```text
BLOCKER=AD_HOC_DSL_EXECUTION_AND_SUMMARY_DID_NOT_PRESERVE_REQUIRED_RAW_EVIDENCE
PROCESS_REPAIR_DIRECTION=VERSIONED_EXECUTION_PACKAGE
```

### Blocker C — exact ID12 host failure mechanism unknown

```text
HOST_FAILURE_OBSERVED=true
HOST_FAILURE_ROOT_CAUSE_PROVEN=false
```

Do not guess the invocation model. The successor executor must record exact argv/tool/hash before launch so a future failure remains adjudicable.

---

## 7. Closed / Forbidden Routes

```text
REPEAT_ID11_RF_CAPTURE=FORBIDDEN
REPLAY_ID11_AUTHORIZATION=FORBIDDEN
REPLAY_ID12_AUTHORIZATION=FORBIDDEN
AUTO_RETRY=FORBIDDEN
APP0_REFLASH_FOR_THIS_GATE=FORBIDDEN
OTADATA_REWRITE_FOR_THIS_GATE=FORBIDDEN
NVS_WRITE_FOR_THIS_GATE=FORBIDDEN
PAIRING_CHANGE_FOR_THIS_GATE=FORBIDDEN
T1_MUTATION_FOR_THIS_GATE=FORBIDDEN
```

`esp_now_send(...) == ESP_OK` remains submit evidence only, never delivery proof.

---

## 8. Authorization Ledger

```text
AUTHORIZATION=N3W_KF089_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL_20260912_11
CLAIMED=true
CONSUMED=true
RESULT=RF_CAPTURE_COMPLETE_READBACK_INCOMPLETE
REPLAY_PERMITTED=false

AUTHORIZATION=N3W_KF089_ID11_AB_SCHEMA_V5_READONLY_RECOVERY_20260912_12
CLAIMED=true
CONSUMED=true
RESULT=STOP_BEFORE_BOARD_ACCESS
REPLAY_PERMITTED=false

PROPOSED_NEXT_PHYSICAL_AUTHORIZATION=NONE
GRANTED=false
```

No new physical authorization should be requested until the exact successor Execution Package exists in GitHub and passes host review/tests.

---

## 9. Rollback Authority

Next gate is host-only process/package work:

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:HOST_ONLY_NO_TARGET_MUTATION
```

For the later A/B read-only recovery package:

```text
TARGET_FLASH_WRITE=false
TARGET_NVS_WRITE=false
TARGET_OTADATA_WRITE=false
APPLICATION_BOOT=false
AUTO_RETRY=false
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_KF089_EXECUTION_PACKAGE_ROLE_AND_STORAGE_FREEZE
```

### 10.1 Purpose

Freeze the stricter collaboration model and repository layout before authoring the successor read-only recovery executor.

### 10.2 Required operations

Host/GitHub only:

1. Re-read PR #388 exact head and candidate standard/template.
2. Amend PR #388 so code authoring is high-level-model-only and Codex is execution/result-only.
3. Freeze the repository layout as stage/gate-scoped Execution Packages rather than a generic Codex-only folder.
4. Record canonical roots, recommended naming, evidence layout, and shared-helper rule.
5. Review the resulting process files for contradictions with the user direction.
6. Do not merge PR #388 without separate user authorization.

### 10.3 Recommended storage to freeze

```text
EXECUTION_PACKAGE_ROOT=tools/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_TEST_ROOT=tests/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_STORAGE_MODEL=STAGE_AND_GATE_SCOPED
CODEX_ONLY_FOLDER=false
```

### 10.4 PASS

```text
ROLE_SPLIT_FROZEN=true
STORAGE_LAYOUT_FROZEN=true
PR388_ALIGNED_WITH_USER_DIRECTION=true
READY_FOR_ID13_EXECUTION_PACKAGE_AUTHORING=true
```

### 10.5 STOP

```text
ROLE_OR_STORAGE_CONFLICT=true
STOP=true
BOARD_ACCESS=false
```

Do not automatically proceed to physical readback.

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

ALLOWED:

```text
- GitHub source/process reads
- GitHub branch/PR documentation updates
- process-standard/template edits
- execution-package architecture design
- host-only static review
```

FORBIDDEN:

```text
- Board A/B access
- USB/serial open
- RF execution
- T1 mutation
- Flash/NVS/otadata writes
- consumed authorization replay
- PR #385/#387/#388 merge without separate user authorization
```

---

## 12. Execution Contract

This gate is process/code-authoring work, so it is performed by the high-level model through GitHub, not by Codex-generated implementation.

```text
EXECUTION_ROLE_ALLOCATION=HIGH_LEVEL_MODEL_AUTHORS_AND_COMMITS;CODEX_EXECUTES_ONLY_AFTER_PACKAGE_EXISTS
HIGH_LEVEL_MODEL_RESPONSIBILITY=WRITE_REVIEW_COMMIT_PROCESS_AND_EXECUTION_CODE
CODEX_RESPONSIBILITY=RUN_EXACT_COMMITTED_EXECUTOR_AND_REPORT_RESULTS_ONLY
CODEX_CODE_AUTHORING=false
DSL_COMPILATION_USED=false
RAW_EVIDENCE_FIRST=true
```

After the storage/process freeze, the subsequent host-only stage will be:

```text
N3W_KF089_ID13_READONLY_RECOVERY_EXECUTION_PACKAGE_MATERIALIZATION
```

The high-level model must author the package in the frozen repository path, including at minimum:

```text
TASK.md
executor.py
manifest.json
evidence_schema.json
host tests
```

Only after the exact package commit/hash and tests are frozen may a new one-time physical read-only authorization be requested.

---

## 13. Expected Closure

For the next gate:

```text
=== N3W KF089 EXECUTION PACKAGE ROLE/STORAGE FREEZE CLOSURE ===

PR388_EXACT_HEAD=
CODE_AUTHORING_MODEL=
CODEX_ROLE=
CODEX_CODE_AUTHORING=

EXECUTION_PACKAGE_STORAGE_MODEL=
EXECUTION_PACKAGE_ROOT=
EXECUTION_PACKAGE_TEST_ROOT=
CODEX_ONLY_FOLDER=

PR388_STANDARD_UPDATED=
PR388_TEMPLATE_UPDATED=
CONTRADICTION_REVIEW=

BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false

GATE_RESULT=
READY_FOR_ID13_EXECUTION_PACKAGE_AUTHORING=

=== END ===
```

---

## 14. After PASS / FAIL

PASS:

```text
AFTER_PASS_NEXT_STAGE=N3W_KF089_ID13_READONLY_RECOVERY_EXECUTION_PACKAGE_MATERIALIZATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_PHYSICAL_AUTHORIZATION_REQUIRED_LATER=true
```

FAIL/STOP:

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

---

## 15. KNOWN_FAILURES Updates

This conversation exposed a process-level regression class:

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
DOMAIN=EXECUTION_EVIDENCE_AND_AI_COORDINATION
SYMPTOM=DSL_SUMMARY_RETURNS_WITHOUT_EXACT_ARGV_STDOUT_STDERR_TRACEBACK
ROOT_CAUSE=AD_HOC_COMMAND_SYNTHESIS_PLUS_RAW_EVIDENCE_NOT_GUARANTEED
FIX_OR_GUARD=VERSIONED_EXECUTION_PACKAGE_PLUS_RAW_EVIDENCE_FIRST
STATUS=PROCESS_REPAIR_CANDIDATE_PR388
```

The exact ID12 esptool invocation root cause itself remains `TBD` because raw evidence was not preserved.

---

## 16. New Chat Start Prompt

```text
阅读：
1. docs/development/N3W_KF089_ID12_PREBOARD_STOP_EXECUTION_PACKAGE_TRANSITION_NEW_CHAT_HANDOFF_V1.0_20260912.md
2. docs/development/N3W_CURRENT_STATE.md
3. docs/development/N3W_CURRENT_STATE_INDEX.md
4. PR #388 exact current head, including:
   - docs/development/NEW_CHAT_HANDOFF_STANDARD.md
   - docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
5. docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md
6. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目。

本轮起采用用户确认的新协作方向：

CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_AND_COMMITS_CODE=true
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
CODEX_CODE_AUTHORING=false
DSL_EXECUTION_MODEL=false
DSL_TO_COMMAND_COMPILATION=false
RAW_EVIDENCE_FIRST=true

第一步只进入：
NEXT_ONE_GATE=N3W_KF089_EXECUTION_PACKAGE_ROLE_AND_STORAGE_FREEZE

先完成：
- 将 PR #388 的角色分工收紧到“高阶模型写代码，Codex只执行反馈”；
- 冻结 Execution Package 的 GitHub 存储结构；
- 推荐采用按 project/stage/gate_id 分层的目录，而不是仅供 Codex 读取的杂项目录；
- 不合并 PR #388，除非用户另行授权。

当前不得：
- 访问 Board A/B；
- 打开 USB/serial；
- 重跑 ID11 RF；
- 重放 ID11/ID12 authorization；
- 修改 T1/Broker/Manager；
- 写 Flash/NVS/otadata。

特别注意：ID12 只证明“esptool wrapper 无执行权限，命令在 read-mac 前失败且未访问 Board B”。
以下均未证明，不得当作事实：
WRAPPER_IS_PYTHON_SCRIPT
DIRECT_WRAPPER_EXECUTION_USED
MISSING_EXECUTABLE_BIT_IS_ROOT_CAUSE
CORRECT_FIX_IS_PYTHON_PLUS_WRAPPER

完成角色/目录冻结后再由高阶模型编写并提交 ID13 read-only recovery Execution Package；Codex 只执行 exact committed package。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=N3W_KF089_RELAY_END_TO_END_EVIDENCE_RECOVERY
CURRENT_STOP_POINT=ID12_STOP_BEFORE_BOARD_ACCESS

KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX

ID11_RF_CAPTURE_CONSUMED=true
SECOND_RF_CAPTURE=false
ID12_CONSUMED=true
ID12_BOARD_ACCESS=false
ID11_SCHEMA_V5_SNAPSHOT_PRESERVATION=UNKNOWN

PR385_STATE=OPEN_UNMERGED
PR387_STATE=OPEN_UNMERGED
PR388_STATE=OPEN_UNMERGED_PROCESS_CANDIDATE

NEXT_ONE_GATE=N3W_KF089_EXECUTION_PACKAGE_ROLE_AND_STORAGE_FREEZE

CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
CODEX_CODE_AUTHORING=false
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_TO_COMMAND_COMPILATION=false

EXECUTION_PACKAGE_STORAGE_RECOMMENDATION=STAGE_AND_GATE_SCOPED
EXECUTION_PACKAGE_ROOT_RECOMMENDATION=tools/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_TEST_ROOT_RECOMMENDATION=tests/execution_packages/<project>/<stage>/<gate_id>/

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
TEAM_SHARED_WORKSPACE=GITHUB
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_PROCESS_MODEL_EXPLICIT=PASS
PRIMARY_EXECUTION_PRINCIPLE_EXPLICIT=PASS
CODE_AUTHORING_ROLE_EXPLICIT=PASS
CODEX_EXECUTION_ONLY_ROLE_EXPLICIT=PASS
DSL_COMMAND_COMPILATION_DISABLED=PASS
RAW_EVIDENCE_FIRST_EXPLICIT=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS

PROVEN_FACTS_SEPARATED_FROM_HYPOTHESIS=PASS
ID12_OVERINFERENCE_CORRECTED=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_HOST_ONLY=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS

EXECUTION_PACKAGE_STORAGE_RECOMMENDATION_PRESENT=PASS
PR388_UNMERGED_STATUS_EXPLICIT=PASS
NO_PR_MERGE_AUTHORITY=PASS

EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
