# <PROJECT NAME>
# <STAGE / SUBJECT>
# 新会话交接文档 V<version> — <YYYY-MM-DD>

```text
HANDOFF_TEMPLATE_VERSION=1.2
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存“当前阶段增量”。长期工作规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`，不要重复抄写。  
> 如 handoff 指定 exact handoff standard authority，按指定 commit 读取。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。

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

一句话说明为什么切换会话，以及新会话从哪里继续。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=
STAGE_OVERRIDES=
```

没有临时例外时写：

```text
STAGE_SPECIFIC_OVERRIDE_COUNT=0
STAGE_OVERRIDES=NONE
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=
FINAL_ACCEPTANCE_TARGET=
DEFERRED_OR_OUT_OF_SCOPE=
```

---

## 3. Frozen Authorities

只列下一 gate 真正需要的当前精确信息。

```text
REPOSITORY=
MAIN=
TREE=

CANDIDATE_REF=
CANDIDATE_HEAD=
CANDIDATE_TREE=

ARTIFACT_ID=
ARTIFACT_SHA256=

DEPLOYED_SOURCE_HEAD=
DEPLOYED_SOURCE_TREE=

OTHER_REQUIRED_AUTHORITY=
```

不适用的字段写 `NOT_APPLICABLE:<reason>`。

公开 handoff 不写私有 SSH 地址、私网地址、密码、凭据、原始设备身份等私有 locator。

---

## 4. Current Live Baseline

只写交接时刚确认的状态；没 fresh 确认就写 `UNKNOWN_FRESH`。

```text
MANAGER_STATE=
MANAGER_RESTART_STATE=
BROKER_STATE=
HOMEASSISTANT_STATE=

BOARD_A_POWER_STATE=
BOARD_A_LOCATION_ROLE=
BOARD_B_POWER_STATE=
BOARD_B_LOCATION_ROLE=

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

需要新会话重新确认的项目：

```text
<FIELD>=UNKNOWN_FRESH
<FIELD>_REQUIRES_FRESH_READONLY_RECHECK=true
```

---

## 5. Proven Current Facts

只写对下一步仍有用、已有直接证据支持的事实。

```text
<FACT_1>=
<FACT_2>=
```

推断必须单独写：

```text
INFERENCE_<NAME>=
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=
CURRENT_BLOCKER=
ROOT_CAUSE=
PROVEN_BY=
SOURCE_DEFECT_PROVEN=
RUNTIME_DEFECT_PROVEN=
```

没有 blocker 时写 `CURRENT_BLOCKER_COUNT=0`。

---

## 7. Closed / Forbidden Routes

只保留下一个会话真正需要知道的关闭路线：

```text
<CLOSED_ROUTE_1>=CLOSED:<reason>
<CLOSED_ROUTE_2>=CLOSED:<reason>
```

完整历史留在 current state / known failures。

---

## 8. Authorization Ledger

只列仍会影响下一步执行的授权。

```text
AUTHORIZATION=
CLAIMED=
CONSUMED=
RESULT=
REPLAY_PERMITTED=
SUPERSEDED_BY=
```

如下一授权尚未获得：

```text
PROPOSED_AUTHORIZATION=
GRANTED=false
```

---

## 9. Rollback Authority

有 mutation 风险时：

```text
ROLLBACK_BASELINE=
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=
ROLLBACK_AUTHORITY_PATH_OR_ID=
RESTART_SCOPE_ALLOWED=
SECOND_ATTEMPT_ALLOWED=
ROLLBACK_FAILURE_CLASS=ROLLBACK_INCOMPLETE
```

完全只读时：

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=<exact gate name>
```

### Purpose

用几句话说明：

- 这一步要证明什么；
- 为什么现在做；
- 这一步不能证明什么。

### Inputs

```text
<INPUT_1>=
<INPUT_2>=
```

### Operations

```text
1. ...
2. ...
3. ...
```

### PASS / FAIL / STOP

```text
PASS_IF=
FAIL_IF=
STOP_BOUNDARY=

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
- ...
```

### FORBIDDEN

```text
- ...
```

如允许有限证据写入：

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=
```

---

## 12. Execution Contract

```text
EXECUTOR=
EXECUTION_METHOD=<chat-tool|mac-terminal|script|manual-physical|other>
DIRECT_CODE_SUPPLIED=true|false
DSL_COMPILATION_USED=true|false
```

只写当前 gate 的实际执行方法和停止条件。

原则：

- 能直接给完整 Mac Terminal 命令时，不额外制造 executor；
- 只有前一步会决定后一步是否安全时才拆成多段；
- GitHub 操作按长期工作上下文要求分阶段、短调用执行；
- macOS ESP32-C6 板卡操作如使用 esptool，应记录实际 Python/module 调用环境；USB path 只作为 locator，不能当作板卡身份；
- fresh-silicon / replacement-board 首次写入前，必须在当前 gate 中明确 exact artifact 的 bootloader / partition table / OTA-data / application / factory-image 或等价 flash layout authority；不得继承 existing-board partial-write 假设；
- 不自动修复、不自动重试、不自动进入下一 gate。

---

## 13. Expected Closure

```text
=== <GATE NAME> CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

<EXACT EVIDENCE FIELDS>

LIVE_RUNTIME_MUTATION=
BOARD_ACCESS=

<GATE_RESULT>=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true|false
EXISTING_KF_GUARD_USED=
NEW_KF_REQUIRED=
```

新 KF 需要时再填写：

```text
KF_ID=
SYMPTOM=
ROOT_CAUSE=
FIX_OR_GUARD=
STATUS=
```

根因未证明写 `TBD`。

---

## 16. New Chat Start Prompt

默认读取集：

```text
1. 本 handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. exact handoff standard authority（仅当本 handoff 指定）
```

建议启动文本：

```text
阅读《<handoff file>》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

如果 handoff 指定 exact handoff standard authority，再按指定 commit 读取。

继续“<project>”。

先做当前 gate 所需的最小 fresh 只读确认，然后只进入：

NEXT_ONE_GATE=<...>

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

不要重放 consumed authorization，不要重新进入 closed routes，不要自动跨越下一阶段。
```

如存在用户私有工作上下文，可在新会话单独读取；不要把私有值复制到公开 GitHub。

---

## 17. Final Frozen State

```text
CURRENT_STAGE=
CURRENT_STOP_POINT=
CURRENT_BLOCKER=
LIVE_SYSTEM_STATE=
NEXT_ONE_GATE=

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=
TEAM_SHARE_COMPLETENESS=PASS|FAIL

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.2

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

如有重要工程产物尚未进入 GitHub，列出公开安全的 locator/hash 和原因。

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.2
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

任一适用项不能 PASS 时：

```text
HANDOFF_READY_FOR_NEW_CHAT=false
```
