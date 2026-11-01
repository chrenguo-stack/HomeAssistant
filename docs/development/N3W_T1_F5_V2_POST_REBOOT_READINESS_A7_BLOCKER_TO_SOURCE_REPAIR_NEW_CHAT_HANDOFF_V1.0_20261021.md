# 温室环境监测系统（ESP32-C6）
# N3-W / T1 F5 V2 post-reboot readiness A7 blocker → source repair
# 新会话交接文档 V1.0 — 2026-10-21

```text
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD_PATH=docs/development/NEW_CHAT_HANDOFF_STANDARD.md
FORMAL_TEMPLATE_PATH=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
FORMAL_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前阶段增量。长期工作规则统一引用
> `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`。
> exact handoff standard 使用历史 authority
> `4300890dff0ce63d5a547df21426e287d084d9ee`；
> 当前正式模板使用 candidate branch 的 V1.3。
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=N3W_T1_F5_V2_POST_REBOOT_READINESS_RACE_SOURCE_REPAIR
CURRENT_STOP_POINT=PR637_INDEPENDENT_REVIEW_BLOCKED_BY_A7_ERROR_CODE_SANITIZATION
NEXT_ONE_GATE=N3W_T1_F5_V2_POST_REBOOT_READINESS_ERROR_CODE_SANITIZER_SOURCE_REPAIR_20261021_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本会话已经完成 readiness race 的设计、源码实现、CI 和一轮独立源码复核。
readiness 屏障本身通过复核；唯一剩余 blocker 是 A7 错误代码脱敏边界。
后续 A7 修复、修后 CI/复核以及再往后的 merge/release/live 路线转入新会话继续。

新会话不是重新复盘 F5 V2 全部历史，而是先 fresh rebind PR #637，
确认本文所列 A7 blocker 仍存在，然后只进入 `NEXT_ONE_GATE`。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=5
STAGE_OVERRIDES=
1. PR637_MERGE=false
2. T1_ACCESS=false
3. T1_MUTATION=false
4. REFLASH=false
5. PRODUCTION_EXECUTION=false
```

本阶段允许 repository source/test/docs mutation，仅限 A7 sanitizer 修复及其测试/状态对齐。
不允许把“源码修复”扩张成 live/T1/board/merge gate。

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=
F5_V2_EXACT_SOURCE
-> POST_REBOOT_READINESS
-> STRICT_POST_REBOOT_ACCEPTANCE
-> FIVE_EXTERNAL_PROBES
-> EXISTING_90_SECOND_STABILITY_OBSERVATION
-> MARKER_ACCEPTED
-> T1_PRODUCTION_READY

FINAL_ACCEPTANCE_TARGET=
FRESH_ARMBIAN_T1
-> ONE_PRODUCTION_APPROVAL
-> HOST_BASELINE/F3/PROVISION/F4
-> CONTROLLED_REBOOT
-> READINESS_BARRIER_PASS
-> STRICT_ACCEPTANCE_PASS
-> 90S_STABILITY_PASS
-> ACCEPTED

DEFERRED_OR_OUT_OF_SCOPE=
BOARD_FIRMWARE
RADIO_STATE_MACHINE
PR474
KF094/KF095/KF096
MULTI_RELAY_SELECTION
B2_HOSTNAME_MDNS_TLS_IDENTITY
TARGET_REFLASH_UNTIL_SOURCE_REPAIR_MERGED_AND_NEW_RELEASE_LOCALLY_VALIDATED
```

A7 只解决失败证据中的错误代码安全边界，不改变 300 秒 readiness、
2 秒 poll、现有严格 verifier、5 个外部探测或原有 90 秒观察。

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN=0654ab3f5b914acd278ffb7333344d86cf5878d2
TREE=a4b31277c53e8497e78bce9ae352f940de1dd553
MAIN_DRIFT_AT_HANDOFF=false
```

### 3.2 Candidate / PR

```text
PR=637
PR_STATE_AT_REVIEW=OPEN_DRAFT
PR_BASE=0654ab3f5b914acd278ffb7333344d86cf5878d2

PRODUCT_SOURCE_HEAD=6b521d0294917a693d436a718e855d6191ab7451
PRODUCT_SOURCE_TREE=a86bc011e5e4436c6d54d7f2875062dbb55a2db1

INDEPENDENT_REVIEW_HEAD=338068e099735e4d251262f68fba09fcfc5826dc
INDEPENDENT_REVIEW_TREE=b9dae44006df761430b819ef275749fd04ea87bc
INDEPENDENT_REVIEW_COMMENT_ID=6311930353

DESIGN_PR=636
DESIGN_HEAD=2f937db0be898736bba434c0d80a45bdae5abb0c
DESIGN_TREE=a2c6b89e34cdd5e2bc155349de9e91eff718ce1c

NEW_CHAT_MUST_FRESH_REBIND_PR637_HEAD=true
```

本文提交到 PR #637 branch 后，PR latest head 会产生 docs-only advance。
因此新会话不得把新的 PR head 当成“已重新完成独立 source review”；
必须保留 `INDEPENDENT_REVIEW_HEAD=338068e...` 作为 A7 blocker 的 exact review authority，
再检查 handoff 之后是否只有 docs-only drift。

### 3.3 Current source CI evidence

```text
REVIEW_HEAD_CI_TOTAL=14
REVIEW_HEAD_CI_PASS=14
REVIEW_HEAD_CI_FAIL=0
REVIEW_HEAD_CI_PENDING=0

F4_FOCUSED_TESTS=153_PASS
F5_R3_FOCUSED_TESTS=172_PASS
PUBLIC_REPOSITORY_SAFETY=PASS
```

这些结果证明 review head 的现有实现通过自动测试；
它们不能覆盖 A7 独立复核发现的 sanitizer 逻辑缺陷。

### 3.4 Artifact / release authority

```text
ARTIFACT_ID=NOT_APPLICABLE:SOURCE_REPAIR_NOT_MERGED
ARTIFACT_SHA256=NOT_APPLICABLE:SOURCE_REPAIR_NOT_MERGED
DEPLOYED_SOURCE_HEAD=HISTORICAL_FAILED_RUN_ONLY
DEPLOYED_SOURCE_TREE=HISTORICAL_FAILED_RUN_ONLY
CURRENT_PRODUCTION_RELEASE_AUTHORITY=NONE_FOR_NEXT_RUN
```

任何旧 exact release 都不能用于下一次 real-T1 production。
A7/KF-125 repair merge 后必须重新构建整条 exact artifact/release chain。

---

## 4. Current Live Baseline

下一 gate 是 repository source-only，不需要访问 T1。

```text
T1_PRODUCTION_READY=false
FAILED_RUN_DISPOSITION=TERMINAL_FAIL_REFLASH_REQUIRED
T1_RUNTIME_STATE=UNKNOWN_FRESH
T1_RUNTIME_STATE_REQUIRES_FRESH_READONLY_RECHECK=false:NEXT_GATE_SOURCE_ONLY

LAST_PROVEN_POSTFAIL_TARGET_STATE=
SYSTEMD_RUNNING_NO_FAILED_UNITS_NO_PENDING_JOBS_PRODUCT_CONTAINERS_RUNNING_ZERO_RESTARTS

LAST_PROVEN_STATE_IS_HISTORICAL=true

MANAGER_STATE=UNKNOWN_FRESH
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH
HOMEASSISTANT_STATE=UNKNOWN_FRESH

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=OUT_OF_SCOPE
BOARD_B_POWER_STATE=UNKNOWN_FRESH
BOARD_B_LOCATION_ROLE=OUT_OF_SCOPE

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

不要为了 A7 source gate 去“顺手”探测 T1。

---

## 5. Proven Current Facts

```text
KF_125_ROOT_CAUSE_CLASS=POST_REBOOT_PRODUCT_READINESS_RACE
KF_125_ROOT_CAUSE_CONFIDENCE=HIGH

POST_REBOOT_READINESS_TIMEOUT_SECONDS=300
POST_REBOOT_READINESS_POLL_SECONDS=2
POST_REBOOT_READINESS_TARGET_MUTATION=false

READINESS_BEFORE_STRICT_ACCEPTANCE=true
STRICT_TARGET_VERIFIER_PRESERVED=true
FIVE_EXTERNAL_PROBES_PRESERVED=true
RUNTIME_STABILITY_OBSERVATION_SECONDS=90
RUNTIME_STABILITY_OBSERVATION_UNCHANGED=true

NEW_SSH_EPOCH_FOR_READINESS=false
NEW_PASSWORD_PROMPT_FOR_READINESS=false
NEW_PRODUCTION_APPROVAL_FOR_READINESS=false

FAILED_RUN_REPLAY=false
TARGET_LOCAL_FIX_FORWARD=false
PR637_MERGE_READY=false

INDEPENDENT_REVIEW_A1_TO_A6=PASS
INDEPENDENT_REVIEW_A7=BLOCKED
INDEPENDENT_REVIEW_A8_TO_A10=PASS
NEW_BLOCKER_COUNT=1
```

A7 的 direct source evidence：

1. `tools/n3w_t1_f4_reboot_verify.py::_safe_error_code()` 当前先执行：

```text
if SAFE_ERROR_CODE_RE.fullmatch(value) is not None:
    return value
```

2. 后面才尝试专门处理：

```text
command_failed:<command>:<exit>:<stderr>
```

因此例如：

```text
command_failed:systemctl:1:secrettoken
```

本身符合当前通用 regex，会提前原样返回，专门的 command-failure 脱敏不会执行。

3. `main()` 捕获的不只 `VerifyError`，还包括：

```text
ImportError
KeyError
OSError
RuntimeError
subprocess.SubprocessError
TypeError
ValueError
```

普通异常如果 message 恰好是简单 token，也可能被当前 generic regex 原样作为
`error_code` 发出。

4. Mac executor 当前也使用宽泛的字符格式校验接收 target `error_code`，
因此 target 侧未正确脱敏的 token 可能进入 private frozen failure evidence。

这是 source observability/sanitization blocker，不是 readiness state-machine blocker。

---

## 6. Current Root Cause / Blockers

### Blocker A7 — structured verifier error-code sanitization

```text
CURRENT_BLOCKER_COUNT=1
CURRENT_BLOCKER=A7_ERROR_CODE_SANITIZATION

ROOT_CAUSE=
GENERIC_SAFE_CHARACTER_REGEX_IS_USED_AS_TRUST_AUTHORITY_BEFORE_COMMAND_FAILURE_SANITIZATION

PROVEN_BY=
PR637_EXACT_SOURCE_REVIEW_HEAD_338068e099735e4d251262f68fba09fcfc5826dc
REVIEW_COMMENT_6311930353

SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=false
```

必须修复的安全合同：

```text
COMMAND_FAILURE_SANITIZE_BEFORE_GENERIC_ACCEPTANCE=true
ARBITRARY_STDERR_PERSISTENCE=false
ARBITRARY_BROAD_EXCEPTION_MESSAGE_PERSISTENCE=false
REPOSITORY_DEFINED_CODES_ONLY=true
UNKNOWN_EXCEPTION_FIXED_FALLBACK=verification_error
EVIDENCE_INSUFFICIENT_CLASS_DISTINCT=true
```

“字符看起来安全”不等于“内容来自仓库定义的错误码”。

---

## 7. Closed / Forbidden Routes

```text
FAILED_RUN_15212AA9_REPLAY=CLOSED:TERMINAL_STARTED_RUN
OLD_FAILED_RUN_C715FDEE_REPLAY=CLOSED:TERMINAL_STARTED_RUN
OLD_PREMUTATION_RUN_84E1A8ED_REPLAY=CLOSED:HISTORICAL

TARGET_LOCAL_FIX_FORWARD=CLOSED:FAILED_STARTED_RUN_REQUIRES_REFLASH
IMMEDIATE_REFLASH_NOW=CLOSED_UNTIL_SOURCE_REPAIR_MERGED_AND_NEW_EXACT_RELEASE_VALIDATED

REMOVE_90_SECOND_OBSERVATION=CLOSED:NOT_THE_DEFECT
REPLACE_READINESS_WITH_FIXED_SLEEP=CLOSED:BOUNDED_STATE_POLLING_IS_FROZEN
ADD_THIRD_SSH_EPOCH=CLOSED:NOT_REQUIRED
ADD_SECOND_PRODUCTION_APPROVAL=CLOSED:NOT_REQUIRED

MERGE_PR637_WHILE_A7_OPEN=CLOSED
T1_OR_BOARD_ACCESS_DURING_A7_GATE=CLOSED
```

除非出现新的 direct counter-evidence，不重新进入这些路线。

---

## 8. Authorization Ledger

### 8.1 Failed real-T1 production run

```text
AUTHORIZATION=N3W_T1_F5_V2_REAL_T1_PRODUCTION_RUN_15212AA9
CLAIMED=true
CONSUMED=true
RESULT=TERMINAL_FAIL_POST_REBOOT_ACCEPTANCE
REPLAY_PERMITTED=false
SUPERSEDED_BY=NEW_RELEASE_NEW_RUN_ID_NEW_PRODUCTION_APPROVAL_REQUIRED
```

### 8.2 A7 source repair

用户已明确要求把 A7 blocker 及后续任务转入新会话修复。

```text
AUTHORIZATION=N3W_T1_F5_V2_POST_REBOOT_READINESS_ERROR_CODE_SANITIZER_SOURCE_REPAIR_20261021_01
GRANTED=true
CLAIMED=false
CONSUMED=false
SCOPE=PR637_REPOSITORY_SOURCE_TEST_DOCS_ONLY
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false
```

新会话在 fresh rebind 后可直接执行这个 source-only gate，不需要再为同一 A7
小范围源码/测试修复反复申请批准。

### 8.3 Merge

```text
PROPOSED_AUTHORIZATION=PR637_MERGE
GRANTED=false
```

### 8.4 Future real-T1 production

```text
PROPOSED_AUTHORIZATION=NEW_REAL_T1_PRODUCTION_AFTER_NEW_RELEASE_AND_FRESH_QUALIFICATION
GRANTED=false
NEW_RUN_ID_REQUIRED=true
NEW_PRODUCTION_APPROVAL_REQUIRED=true
```

---

## 9. Rollback Authority

A7 gate 只修改 Git repository，不修改 live T1。

```text
ROLLBACK_BASELINE=INDEPENDENT_REVIEW_HEAD_338068e099735e4d251262f68fba09fcfc5826dc
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false:GIT_HISTORY_IS_IMMUTABLE
ROLLBACK_AUTHORITY_PATH_OR_ID=PR637_GIT_HISTORY
RESTART_SCOPE_ALLOWED=NONE
SECOND_ATTEMPT_ALLOWED=true:SOURCE_ONLY_NO_LIVE_AUTH_CONSUMPTION
ROLLBACK_FAILURE_CLASS=REPOSITORY_REPAIR_INCOMPLETE
```

若 source repair 出现问题，保留失败 commit/evidence，使用新的 repair commit 修复；
禁止为了“干净历史”强推覆盖已公开的 evidence。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_F5_V2_POST_REBOOT_READINESS_ERROR_CODE_SANITIZER_SOURCE_REPAIR_20261021_01
```

### Purpose

只修 A7：确保 target verifier 和 Mac executor 只能传播仓库定义且已脱敏的错误代码，
任何 command stderr、普通异常 message 或仅仅“字符格式合法”的未知 token 都不能进入
structured/frozen evidence。

本 gate 不改变 readiness 行为，不访问 T1，不重刷，不 merge。

### Inputs

```text
MAIN=0654ab3f5b914acd278ffb7333344d86cf5878d2
PR637=OPEN_DRAFT
INDEPENDENT_REVIEW_HEAD=338068e099735e4d251262f68fba09fcfc5826dc
PRODUCT_SOURCE_HEAD=6b521d0294917a693d436a718e855d6191ab7451
A7_REVIEW_COMMENT_ID=6311930353
DESIGN_HEAD=2f937db0be898736bba434c0d80a45bdae5abb0c
```

### Operations

```text
1. fresh rebind main + PR637 latest head + changed files + CI state.
2. prove any handoff-era drift after 338068e... is docs-only before editing source.
3. independently re-read:
   - tools/n3w_t1_f4_reboot_verify.py
   - tools/n3w_t1_production_v2_executor.py
   - tools/n3w_t1_production_v2.py
   - focused tests
4. repair _safe_error_code so command_failed sanitization occurs before any code preservation.
5. replace "generic safe characters == trusted code" with repository-defined code/family authority.
6. broad caught exceptions that are not known verifier codes must emit fixed verification_error.
7. Mac executor must reject unknown syntactically-safe tokens rather than freezing them.
8. preserve EVIDENCE_INSUFFICIENT vs VERIFY_FAILED distinction.
9. add regression tests at minimum:
   - command_failed:systemctl:1:secrettoken -> command_failed:systemctl:1
   - RuntimeError("secrettoken") -> verification_error
   - known repository VerifyError code remains preserved
   - unknown syntactically-valid target code is rejected by executor
   - frozen failure summary never receives arbitrary token/stderr
10. run focused tests and relevant CI.
11. if CI fails, inspect exact failed job/log; same-gate bounded source/test/style repairs may continue.
12. after CI green, independently re-review A7 plus A1-A10 at exact repaired head.
13. do not merge.
```

Implementation guidance:

- do not solve this by simply making the current regex slightly narrower;
- distinguish provenance/known-code family from character safety;
- keep dynamic repository-defined suffixes only where the code family itself is explicit and sanitized;
- never persist raw stderr as a structured code;
- no new framework, executor, or error-reporting architecture is required.

### PASS / FAIL / STOP

```text
PASS_IF=
A7_CLOSED
AND_NO_NEW_FALSE_PASS_PATH
AND_FOCUSED_TESTS_PASS
AND_REQUIRED_CI_PASS
AND_A1_TO_A10_REVIEW_PASS

FAIL_IF=
ARBITRARY_MESSAGE_CAN_REACH_ERROR_CODE
OR_COMMAND_STDERR_CAN_SURVIVE_UNSANITIZED
OR_EVIDENCE_CLASS_COLLAPSES
OR_READINESS_90S_OR_NO_REPLAY_CONTRACT_REGRESSES
OR_NEW_BLOCKER_FOUND

STOP_BOUNDARY=
SOURCE_REPAIR_AND_INDEPENDENT_REVIEW_CLOSURE_ONLY

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- fresh read-only GitHub main/PR/branch/CI inspection
- modify PR637 branch source/tests/docs only for A7
- add focused unit/regression tests
- run/observe repository CI
- add PR Conversation evidence/comments
- docs-only current-state alignment
- same-gate bounded low-risk repair after a proven CI/review defect
```

### FORBIDDEN

```text
- T1 SSH
- T1 mutation
- target-local fix-forward
- reflash
- production execution
- reuse any failed RUN_ID
- create/consume a new production approval
- board/USB/serial/flash/NVS/RF access
- firmware/wireless/relay changes
- change 300s readiness policy
- change 2s poll policy
- remove/change existing 90s stability observation
- add fixed blind sleep as readiness
- merge PR637
- automatically start exact release rebuild
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
REPOSITORY_MUTATION=true:A7_SOURCE_TEST_DOCS_ONLY
```

---

## 12. Execution Contract

```text
EXECUTOR=HIGH_LEVEL_MODEL_WITH_GITHUB_CONNECTOR
EXECUTION_METHOD=chat-tool
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false

GITHUB_OPERATION_MODE=PHASED_SHORT_CALLS
VERIFY_AFTER_REPOSITORY_WRITE=true
BLIND_REPLAY_AFTER_TOOL_FAILURE=false

CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
CROSS_GATE_AUTO_EXECUTE=false
```

执行顺序：

```text
A. fresh rebind main / PR637 / latest head
B. compare latest head against 338068e... and classify docs-only/source drift
C. inspect exact A7 source and existing tests
D. make the smallest sanitizer repair
E. add regression tests
F. commit to existing PR637 repair branch
G. re-fetch/compare exact repaired head
H. inspect CI
I. if green, immediately perform required independent source review
J. publish structured closure
K. STOP before merge
```

如 GitHub mutation 调用结果不确定，先读取 remote state，禁止盲目重放。

---

## 13. Expected Closure

```text
=== N3W_T1_F5_V2_POST_REBOOT_READINESS_ERROR_CODE_SANITIZER_SOURCE_REPAIR CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=N3W_T1_F5_V2_POST_REBOOT_READINESS_ERROR_CODE_SANITIZER_SOURCE_REPAIR_20261021_01
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

REVIEW_BASE=
REPAIR_HEAD=
REPAIR_TREE=
PR637_STATE=

COMMAND_FAILURE_SANITIZE_FIRST=
ARBITRARY_STDERR_PERSISTENCE=
ARBITRARY_BROAD_EXCEPTION_MESSAGE_PERSISTENCE=
REPOSITORY_DEFINED_ERROR_CODE_AUTHORITY=
EXECUTOR_UNKNOWN_CODE_REJECTION=
EVIDENCE_INSUFFICIENT_DISTINCT=

READINESS_300S_UNCHANGED=
READINESS_2S_POLL_UNCHANGED=
STRICT_VERIFIER_UNCHANGED=
EXTERNAL_PROBES_UNCHANGED=
OBSERVATION_90S_UNCHANGED=
FAILED_RUN_REPLAY_GUARD_UNCHANGED=

FOCUSED_TESTS=
CI_TOTAL=
CI_PASS=
CI_FAIL=
CI_PENDING=

A1=
A2=
A3=
A4=
A5=
A6=
A7=
A8=
A9=
A10=

NEW_BLOCKER_COUNT=
SOURCE_REPAIR_REQUIRED=
PR637_MERGE_READY=

LIVE_RUNTIME_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false

GATE_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_F5_V2_POST_REBOOT_READINESS_SOURCE_REPAIR_MERGE_DECISION_20261021_01
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true:MERGE
```

merge 若另行批准并完成，后续完整路线仍必须是：

```text
MERGE
-> F3/F4 EXACT ARTIFACT REBUILD
-> RELEASE_INPUTS REBUILD
-> FINAL EXACT RELEASE REBUILD
-> MAC LOCAL EXACT_RELEASE VALIDATION
-> REFLASH FAILED T1
-> STANDARD FRESH ARMBIAN QUALIFICATION
-> NEW RUN_ID
-> NEW PRODUCTION APPROVAL
-> REAL T1 PRODUCTION
-> POST_REBOOT_READINESS
-> STRICT POST_REBOOT_ACCEPTANCE
-> EXISTING 90S STABILITY OBSERVATION
-> MARKER_ACCEPTED
```

每个跨 gate / live / merge 边界仍按项目规则单独决定，不在 A7 gate 自动执行。

### FAIL 后

```text
AUTO_REPAIR_AFTER_FAIL=false:UNLESS_BOUNDED_LOW_RISK_SAME_GATE_DEFECT_IS_PROVEN
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

若发现新的架构/安全 blocker，而不是小型同 gate 修补，立即 STOP 返回高阶模型。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
EXISTING_KF_GUARD_USED=KF_125
NEW_KF_REQUIRED=false:A7_IS_KF125_SOURCE_REPAIR_BLOCKER
```

当前分类：

```text
KF_122=OPEN
KF_124=SOURCE_REPAIR_MERGED_LIVE_PATH_REVALIDATED_FULL_RUN_PENDING
KF_125=SOURCE_CI_PASS_INDEPENDENT_REVIEW_BLOCKED_A7
```

A7 修复通过后，应更新 KF-125 source 状态，但不得提前宣称 live closed。

---

## 16. New Chat Start Prompt

把下面整段粘贴到新会话：

```text
阅读：

docs/development/N3W_T1_F5_V2_POST_REBOOT_READINESS_A7_BLOCKER_TO_SOURCE_REPAIR_NEW_CHAT_HANDOFF_V1.0_20261021.md

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_F5_V2_POST_REBOOT_READINESS_RACE_SOURCE_REPAIR_DESIGN_20261021.md

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md

使用当前 formal template V1.3：
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
- blob=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0

继续“温室环境监测系统（ESP32-C6）”项目 N3-W / T1 F5 V2。

先 fresh rebind：
- repository main
- PR #637
- PR #637 latest head
- INDEPENDENT_REVIEW_HEAD=338068e099735e4d251262f68fba09fcfc5826dc
- PRODUCT_SOURCE_HEAD=6b521d0294917a693d436a718e855d6191ab7451
- review comment 6311930353

先确认 handoff 之后如果 PR head 有漂移，是否仅为 docs-only；不能默认接受。

当前只进入：

NEXT_ONE_GATE=
N3W_T1_F5_V2_POST_REBOOT_READINESS_ERROR_CODE_SANITIZER_SOURCE_REPAIR_20261021_01

用户已授权该 source/test/docs-only A7 repair gate。
同一 gate 内已证明的小型低风险源码/测试/CI 修补可直接继续，不需反复申请。

必须独立检查源码，不能只接受 handoff 或 PR comment 的结论。

A7 blocker：
- _safe_error_code() 当前把 generic safe-character regex 当成 trust authority；
- command_failed sanitizer 排在 generic acceptance 后面；
- token-only stderr 可能原样进入 error_code；
- main() 还捕获 RuntimeError/ValueError/OSError/TypeError 等 broad exceptions；
- Mac executor 同样不能只因为 token 字符格式合法就把未知 code 冻结进 evidence。

必须保持：
- POST_REBOOT_READINESS_TIMEOUT_SECONDS=300
- POST_REBOOT_READINESS_POLL_SECONDS=2
- readiness target mutation=false
- no third SSH epoch
- no new password prompt
- no second production approval
- strict target verifier remains
- five external probes remain
- existing 90-second stability observation remains unchanged
- failed RUN_ID never replayed

本轮：
LIVE_MUTATION_DEFAULT=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
REFLASH=false
PRODUCTION_EXECUTION=false
MERGE=false

修复后运行 focused tests / relevant CI。
CI 全绿后在同一 gate 继续独立源码复核 A1-A10。
不要自动 merge；最终输出 handoff 定义的 structured closure 并 STOP。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=KF125_A7_SOURCE_REPAIR_HANDOFF
CURRENT_STOP_POINT=PR637_REVIEW_BLOCKED_A7

CURRENT_BLOCKER=A7_ERROR_CODE_SANITIZATION
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=false

MAIN=0654ab3f5b914acd278ffb7333344d86cf5878d2
PRODUCT_SOURCE_HEAD=6b521d0294917a693d436a718e855d6191ab7451
INDEPENDENT_REVIEW_HEAD=338068e099735e4d251262f68fba09fcfc5826dc

LATEST_REVIEW_CI=14_14_PASS
PR637_MERGE_READY=false
T1_PRODUCTION_READY=false

NEXT_ONE_GATE=N3W_T1_F5_V2_POST_REBOOT_READINESS_ERROR_CODE_SANITIZER_SOURCE_REPAIR_20261021_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.3
HANDOFF_STANDARD_VERSION=1.0

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
