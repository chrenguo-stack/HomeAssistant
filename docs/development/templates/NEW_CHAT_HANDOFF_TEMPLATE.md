# <PROJECT NAME>
# <STAGE / SUBJECT>
# 新会话交接文档 V<version> — <YYYY-MM-DD>

```text
HANDOFF_STANDARD_VERSION=1.1
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
HIGH_LEVEL_MODEL_WRITES_EXECUTION_CODE=true
HIGH_LEVEL_MODEL_COMMITS_CODE_TO_GITHUB=true
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
EXECUTION_PACKAGE_MODEL=true
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
EXECUTION_PACKAGE_STORAGE_MODEL=STAGE_AND_GATE_SCOPED
EXECUTION_PACKAGE_ROOT=tools/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_TEST_ROOT=tests/execution_packages/<project>/<stage>/<gate_id>/
CODEX_ONLY_FOLDER=false
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文必须符合：  
> `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`  
> `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`  
> `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`  
> 如本文与 exact repository/runtime/live evidence 冲突，以更高 authority 为准，并先 STOP/rebind。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=
CURRENT_STOP_POINT=
NEXT_ONE_GATE=
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=<true|false>
```

下一会话从 `NEXT_ONE_GATE` 开始，不重新打开已经关闭的路线，不重放 consumed authorization。

---

## 1. 执行模式与首要原则

### 1.0 首要原则

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
WORKFLOW_CONVENTIONS_ARE_MEANS_NOT_GOALS=true
TEAM_SHARED_WORKSPACE=GITHUB
CHAT_AND_EXECUTOR_SESSIONS=EPHEMERAL_WORKSPACES
```

### 1.1 冻结的代码作者 / 执行者分工

```text
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
HIGH_LEVEL_MODEL_WRITES_EXECUTION_CODE=true
HIGH_LEVEL_MODEL_COMMITS_CODE_TO_GITHUB=true
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
```

高阶模型负责：

- 产品/架构与 route；
- gate / scope / authorization / rollback；
- project source code；
- Execution Package 中的 `executor`、helper、manifest、evidence schema、tests；
- GitHub commit/hash binding；
- raw evidence contract；
- `OBSERVED / DERIVED / HYPOTHESIS` 分类与最终 PASS/FAIL/STOP。

Codex 只负责：

- checkout/rebind 指定 exact commit；
- 验证 package/manifest/hash；
- 运行 exact committed tests / executor；
- 保存并返回 raw evidence、closure、result；
- substantive mismatch 时按 contract STOP。

Codex 不得：

```text
AUTHOR_PROJECT_CODE=false
AUTHOR_EXECUTOR=false
AUTHOR_HELPER=false
AUTHOR_MANIFEST=false
AUTHOR_EVIDENCE_SCHEMA=false
AUTHOR_TEST=false
PATCH_EXECUTOR_LOCALLY=false
SYNTHESIZE_SUBSTITUTE_COMMAND=false
COMPILE_DSL_TO_COMMANDS=false
AUTO_REPAIR=false
```

若执行代码有问题：

```text
STOP
-> RETURN_TO_HIGH_LEVEL_MODEL
-> HIGH_LEVEL_MODEL_EDITS_AND_COMMITS_GITHUB_CODE
-> NEW_COMMIT
-> HOST_TESTS
-> EXACT_REBIND
-> THEN_ONLY_CONSIDER_REEXECUTION
```

不得让 Codex 在执行现场修代码后继续。

### 1.2 DSL / Natural Language role

```text
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
AD_HOC_COMMAND_SYNTHESIS_ALLOWED=false
```

DSL/自然语言只定义目的、边界、frozen inputs、PASS/FAIL/STOP、authorization、expected closure。真正执行的 argv、顺序、工具路径、重试和证据写入必须存在于 exact committed code/manifest/tests 中。

### 1.3 标准交互循环

```text
高阶模型：设计 gate + 编写 Execution Package/tests
        ↓
高阶模型：提交 GitHub + 绑定 exact commit/blob/hash
        ↓
Host-only：运行已提交 tests / review package
        ↓
用户：仅在 package READY 后批准所需 live/physical authorization
        ↓
Codex：exact rebind + exact execution + raw result reporting
        ↓
高阶模型：读取 source + raw evidence + closure 并判定
```

---

## 2. Product North Star

```text
NORTH_STAR=
CURRENT_PRODUCT_ROUTE=
FINAL_ACCEPTANCE_TARGET=
```

当前不得进入：

```text
<DEFERRED_OR_FORBIDDEN_ROUTE_1>
<DEFERRED_OR_FORBIDDEN_ROUTE_2>
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=
MAIN=
TREE=
```

### 3.2 Candidate / source / artifact authority

```text
PRODUCT_SOURCE_AUTHORITY=
DIAGNOSTIC_SOURCE_AUTHORITY=
CANDIDATE_REF=
CANDIDATE_SHA=
```

不适用时明确写 `NOT_APPLICABLE:<reason>`。

### 3.3 Target host / runtime authority

```text
TARGET_HOST=
TARGET_ARCH=
<OTHER_REQUIRED_EXACT_AUTHORITIES>
```

### 3.4 Execution Package authority

```text
EXECUTION_PACKAGE_REQUIRED=true|false
EXECUTION_PACKAGE_STATUS=READY|AUTHORING_REQUIRED|REPAIR_REQUIRED|NOT_APPLICABLE
EXECUTION_PACKAGE_STORAGE_MODEL=STAGE_AND_GATE_SCOPED
EXECUTION_PACKAGE_ROOT=tools/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_TEST_ROOT=tests/execution_packages/<project>/<stage>/<gate_id>/
CODEX_ONLY_FOLDER=false

EXECUTION_PACKAGE_COMMIT=
TASK_SPEC_PATH=
EXECUTOR_PATH=
EXECUTOR_GIT_BLOB=
EXECUTOR_SHA256=
EVIDENCE_SCHEMA_PATH=
EVIDENCE_SCHEMA_GIT_BLOB=
MANIFEST_PATH=
MANIFEST_GIT_BLOB=
TEST_PATH=
TEST_RESULT=
RAW_EVIDENCE_CONTRACT_PASS=
```

若 required package 不是 `READY`：

```text
PHYSICAL_EXECUTION_ALLOWED=false
LIVE_MUTATION_ALLOWED=false
RETURN_TO_HIGH_LEVEL_MODEL_AUTHORING=true
```

---

## 4. Current Live Baseline

只记录交接时真正 live 的状态。

```text
MANAGER_STATE=
BROKER_STATE=
HOMEASSISTANT_STATE=

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_WRITE=false
OTADATA_WRITE=false
RF_EXECUTION=false
T1_MUTATION=false
```

需要 fresh read-only rebind 的项：

```text
<LIVE_FACT>_REQUIRES_FRESH_READONLY_REBIND=true
```

---

## 5. Proven Current Facts / Evidence Classes

必须分开写：

```text
OBSERVED_<NAME>=<direct raw/source/live evidence>
DERIVED_<NAME>=<strictly derived without added assumption>
HYPOTHESIS_<NAME>=<plausible but not proven>
```

不得把摘要、猜测、建议性修复写成已证实 root cause。

---

## 6. Current Root Cause / Blockers

### Blocker A — <name>

```text
ROOT_CAUSE=
ROOT_CAUSE_CLASS=OBSERVED|DERIVED|HYPOTHESIS|TBD
PROVEN_BY=
PRODUCT_DEFECT_PROVEN=
HOST_DEFECT_PROVEN=
EXECUTOR_DEFECT_PROVEN=
```

若无 blocker：

```text
CURRENT_BLOCKER_COUNT=0
```

---

## 7. Closed / Forbidden Routes

```text
<CLOSED_ROUTE_1>=CLOSED:<proof/reason>
<CLOSED_ROUTE_2>=CLOSED:<proof/reason>
```

必须保留 authorization replay guards。

---

## 8. Authorization Ledger

```text
AUTHORIZATION=<name>
BOUND_EXECUTION_PACKAGE_COMMIT=
BOUND_EXECUTOR_BLOB=
CLAIMED=
CONSUMED=
RESULT=
REPLAY_PERMITTED=
SUPERSEDED_BY=
```

建议但尚未批准的 authorization：

```text
PROPOSED_AUTHORIZATION=<name>
GRANTED=false
```

`READY_FOR_NEW_AUTHORIZATION=true` 不等于 granted。

---

## 9. Rollback Authority

如果下一 gate 有 mutation：

```text
ROLLBACK_BASELINE=
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true|false
ROLLBACK_AUTHORITY_PATH_OR_ID=
NORMAL_PATH_RESTART_ALLOWED=
ROLLBACK_ONLY_RESTART_LIMIT=
SECOND_ATTEMPT_ALLOWED=
```

若下一 gate 完全 host-only/read-only：

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_OR_HOST_ONLY_GATE
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=<exact logical gate name>
```

### 10.1 Purpose

<one concise paragraph>

### 10.2 Frozen inputs

```text
<INPUT_1>=
<INPUT_2>=
EXECUTION_PACKAGE_COMMIT=
EXECUTOR_GIT_BLOB=
```

### 10.3 Required proof / operations

```text
1. ...
2. ...
3. ...
```

### 10.4 PASS

```text
<GATE_RESULT>=PASS
READY_FOR_<NEXT_STAGE>=true
```

### 10.5 FAIL / STOP

```text
<GATE_RESULT>=FAIL_<CLASS>|STOP_<CLASS>
READY_FOR_<NEXT_STAGE>=false
STOP=true
```

不得自动进入下一个 gate。

---

## 11. Hard Allowed / Forbidden Scope

Default：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTO_REPAIR=false
AUTO_RETRY=false
```

### ALLOWED

```text
- ...
```

### FORBIDDEN

```text
- ...
```

如允许 bounded evidence filesystem write：

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=<exact path/scope>
```

---

## 12. Versioned Execution Package Contract

### 12.1 Frozen storage model

```text
EXECUTION_PACKAGE_STORAGE_MODEL=STAGE_AND_GATE_SCOPED
EXECUTION_PACKAGE_ROOT=tools/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_TEST_ROOT=tests/execution_packages/<project>/<stage>/<gate_id>/
CODEX_ONLY_FOLDER=false
```

Canonical example:

```text
tools/execution_packages/n3w/kf089/id13_readonly_recovery/
  TASK.md
  executor.py
  manifest.json
  evidence_schema.json

tests/execution_packages/n3w/kf089/id13_readonly_recovery/
  test_executor.py
```

Do not build a generic framework or shared helper in advance. Keep helper code package-local until at least two concrete packages require the same stable behavior; shared extraction is then a separate high-level-model-authored GitHub change with tests.

### 12.2 Package readiness

```text
EXECUTION_PACKAGE_REQUIRED=true|false
EXECUTION_PACKAGE_MATERIALIZED=true|false
EXECUTION_PACKAGE_GITHUB_SHARED=true|false
EXECUTION_PACKAGE_TESTS_PASS=true|false
EXECUTION_PACKAGE_EXACT_BINDING=PASS|FAIL|NOT_APPLICABLE
RAW_EVIDENCE_CONTRACT_PASS=true|false|NOT_APPLICABLE
CODEX_MAY_MODIFY_EXECUTOR=false
CODEX_MAY_AUTHOR_MISSING_PACKAGE_FILES=false
AD_HOC_COMMAND_SYNTHESIS_ALLOWED=false
```

若 package 缺失、漂移或测试失败：

```text
STOP=true
RETURN_TO_HIGH_LEVEL_MODEL_AUTHORING=true
PHYSICAL_EXECUTION_ALLOWED=false
LIVE_MUTATION_ALLOWED=false
```

### 12.3 Exact execution invocation

Codex 正式执行时只应收到简短、可验证的 invocation：

```text
Checkout/rebind EXECUTION_PACKAGE_COMMIT=<sha>.
Verify manifest and package hashes.
Run the exact committed host tests if required.
Run exactly the committed executor invocation specified by TASK.md/manifest.
Do not modify or author package code.
Do not synthesize substitute commands.
Return raw evidence manifest + closure/result.
```

如果 executor 无法启动、工具绑定不一致、hash 漂移、manifest 不满足或 committed tests 失败：STOP，返回结果。不得现场修复并继续。

---

## 13. Expected Closure + Raw Evidence Contract

### 13.1 Raw evidence first

对每个重要 external command/device operation，executor 至少保存：

```text
persist command.json
-> execute
-> persist stdout/stderr/result
-> validate
-> persist validation/adjudication
```

推荐：

```text
op_NN/
  command.json
  stdout.txt|stdout.bin
  stderr.txt|stderr.bin
  result.json
```

必须明确：

```text
RAW_EVIDENCE_REQUIRED=true|false
RAW_EVIDENCE_PRIVATE_ROOT=
PUBLIC_SAFE_EVIDENCE_MANIFEST=
RAW_EVIDENCE_HASH_ALGORITHM=SHA256
```

### 13.2 Expected closure

```text
EXECUTION_ID=
EXECUTION_PACKAGE_COMMIT=
EXECUTOR_BLOB=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=
RAW_EVIDENCE_COMPLETE=
EVIDENCE_MANIFEST_PATH_OR_HASH=
FIRST_FAILED_OPERATION=
TARGET_ACCESS_OCCURRED=
<GATE_RESULT>=
NEXT_ROUTE=
STOP_REASON=
```

Closure 不能替代 raw evidence，也不能补写 executor 未记录的事实。

---

## 14. After PASS / FAIL

### PASS

```text
<WHAT BECOMES PROVEN>
READY_FOR_<NEXT_GATE>=true
```

只报告 readiness，不自动执行下一 gate。

### FAIL / STOP

```text
<WHAT REMAINS PROVEN>
PRODUCT_FAILURE_PROVEN=<true|false>
EXECUTOR_OR_HOST_FAILURE=<true|false>
RETURN_TO_HIGH_LEVEL_MODEL_AUTHORING=<true|false>
```

若 package code 有问题：高阶模型修改并提交新 commit；Codex 不得现场修复。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true|false
NEW_KF_ID=
DOMAIN=PRODUCT|SECURITY|PHYSICAL_HARNESS|INFRASTRUCTURE|CI|NOT_APPLICABLE
STATUS=OPEN|GUARDED|RESOLVED|NOT_APPLICABLE
```

尚未确认 root cause 时必须写 `TBD` / `HYPOTHESIS`。

---

## 16. New Chat Start Prompt

必须自包含，至少包含：

```text
- handoff path
- exact standard/template authority
- current state authority
- exact next gate
- frozen role split
- package storage model
- consumed authorization replay guards
- hard forbidden scope
- instruction to rebind current GitHub authority before execution
```

---

## 17. Final Frozen State

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
HIGH_LEVEL_MODEL_WRITES_EXECUTION_CODE=true
HIGH_LEVEL_MODEL_COMMITS_CODE_TO_GITHUB=true
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER

REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_TO_COMMAND_COMPILATION=false

EXECUTION_PACKAGE_STORAGE_MODEL=STAGE_AND_GATE_SCOPED
EXECUTION_PACKAGE_ROOT=tools/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_TEST_ROOT=tests/execution_packages/<project>/<stage>/<gate_id>/
CODEX_ONLY_FOLDER=false
PREMATURE_GENERIC_EXECUTION_FRAMEWORK=false

NEXT_ONE_GATE=
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=
TEAM_SHARE_COMPLETENESS=PASS|FAIL
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.1

PRIMARY_EXECUTION_PRINCIPLE_EXPLICIT=PASS
CODE_AUTHORING_MODEL_HIGH_LEVEL_ONLY=PASS
HIGH_LEVEL_MODEL_EXECUTION_CODE_AUTHORING_EXPLICIT=PASS
HIGH_LEVEL_MODEL_GITHUB_COMMIT_ROLE_EXPLICIT=PASS
CODEX_CODE_AUTHORING_DISABLED=PASS
CODEX_EXACT_EXECUTOR_AND_RESULT_REPORTER_ROLE=PASS

EXECUTION_PACKAGE_MODEL_EXPLICIT=PASS
EXECUTION_PACKAGE_STORAGE_MODEL_EXPLICIT=PASS
EXECUTION_PACKAGE_ROOT_EXPLICIT=PASS
EXECUTION_PACKAGE_TEST_ROOT_EXPLICIT=PASS
CODEX_ONLY_FOLDER_DISABLED=PASS
PREMATURE_GENERIC_FRAMEWORK_PROHIBITED=PASS

DSL_NOT_COMMAND_AUTHORITY=PASS
RAW_EVIDENCE_FIRST_EXPLICIT=PASS
OBSERVED_DERIVED_HYPOTHESIS_SEPARATED=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
AUTHORIZATION_PACKAGE_BINDING_EXPLICIT=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS
EXECUTION_PACKAGE_READY_OR_EXECUTION_BLOCKED=PASS
ALLOWED_FORBIDDEN_SCOPE_EXPLICIT=PASS
RAW_EVIDENCE_CONTRACT_PRESENT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

TEAM_SHARED_WORKSPACE_EXPLICIT=PASS
TEAM_SHARE_COMPLETENESS_CLASSIFIED=PASS
KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS
HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```

如果任何适用项不能 PASS，则该 handoff 仍是 draft/incomplete，不得称为正式交接 authority。
