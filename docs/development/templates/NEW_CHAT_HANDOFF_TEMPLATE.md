# <PROJECT NAME>
# <STAGE / SUBJECT>
# 新会话交接文档 V<version> — <YYYY-MM-DD>

```text
HANDOFF_TEMPLATE_VERSION=1.2
PROJECT_WORKING_CONTEXT_VERSION=1.0
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本 handoff 是“当前阶段增量”，不是完整项目百科。  
> 稳定的工作原则、GitHub 操作习惯、开发环境约定、证据规则、授权规则和公开/私有边界统一继承自 `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`，除非本 handoff 明确写出更严格的阶段性例外。  
> 如果当前项目指定了 exact handoff standard authority，应按指定 commit 读取并遵守对应标准；不要假定 current `main` 一定包含历史标准文件。  
> 如本文与 fresh repository/runtime/live evidence 冲突，以最新直接证据为准，并先停止执行、重新确认当前状态。

---

## 0. 会话切换结论

只说明为什么现在切换会话，以及下一会话从哪里继续。

```text
CURRENT_STAGE=
CURRENT_STOP_POINT=
NEXT_ONE_GATE=
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=<true|false>
```

下一会话不重新复盘全部历史，先读取长期工作上下文和当前状态，再从 `NEXT_ONE_GATE` 继续。

---

## 1. 长期上下文引用与本阶段例外

不要重复抄写长期固定规则。

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.0
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false
STAGE_SPECIFIC_OVERRIDE_COUNT=<n>
```

如本阶段需要比长期规则更严格的临时要求，只在这里列出：

```text
STAGE_OVERRIDE_1=
STAGE_OVERRIDE_2=
```

没有例外时：

```text
STAGE_SPECIFIC_OVERRIDE_COUNT=0
STAGE_OVERRIDES=NONE
```

---

## 2. Product North Star

当前产品路线：

```text
<CURRENT PRODUCT ROUTE>
```

最终阶段目标：

```text
<FINAL ACCEPTANCE / PRODUCT TARGET>
```

当前不得进入：

```text
<DEFERRED / OUT-OF-SCOPE ROUTES>
```

---

## 3. Frozen Authorities

只列下一会话继续所需的**当前**精确信息。不要搬运全部历史 SHA。

### 3.1 Repository / exact-main

```text
REPOSITORY=
MAIN=
TREE=
```

### 3.2 Candidate / artifact / image

```text
CANDIDATE_REF=
CANDIDATE_ID=
VERSION=
REVISION=
ARCH=
```

不适用时：

```text
CANDIDATE_AUTHORITY=NOT_APPLICABLE:<reason>
```

### 3.3 Successor / deployment material

```text
SUCCESSOR_PATH=
SUCCESSOR_SHA256=
```

不适用时：

```text
SUCCESSOR_AUTHORITY=NOT_APPLICABLE:<reason>
```

### 3.4 Target host / runtime authority

只保存公开、安全、后续真正需要的 binding。

```text
TARGET_ROLE=
TARGET_ARCH=
<OTHER REQUIRED EXACT AUTHORITIES>
```

不要在公开 handoff 中写私有 SSH 地址、密码、私网地址、原始设备身份或其他敏感 locator。

---

## 4. Current Live Baseline

只记录交接时真正 live 的状态，或明确写 `UNKNOWN_FRESH`。

```text
MANAGER_STATE=
MANAGER_RESTART_STATE=

BROKER_STATE=
BROKER_RESTART_STATE=

HOMEASSISTANT_STATE=

BOARD_A_POWER_STATE=
BOARD_A_LOCATION_ROLE=
BOARD_B_POWER_STATE=
BOARD_B_LOCATION_ROLE=

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

如果某项只是历史已知、下一会话必须重新确认：

```text
<LIVE_FACT>=UNKNOWN_FRESH
<LIVE_FACT>_REQUIRES_FRESH_READONLY_RECHECK=true
```

不要把历史状态冒充为当前状态。

---

## 5. Proven Current Facts

这里只写已有直接证据支持、且对下一步仍有用的事实。

```text
<FACT_1>=
<FACT_2>=
...
```

重要路径、SHA、错误码可以保留，但不得输出 secret。

推断必须单独标记：

```text
INFERENCE_<NAME>=
```

不要把 inference 混进 proven facts。

---

## 6. Current Root Cause / Blockers

只写**仍然挡住当前产品路线**的问题。

### Blocker A — <name>

先用一两句话讲清楚实际发生了什么，再保留需要的精确字段：

```text
ROOT_CAUSE=
PROVEN_BY=
SOURCE_DEFECT_PROVEN=
RUNTIME_DEFECT_PROVEN=
```

没有 blocker 时：

```text
CURRENT_BLOCKER_COUNT=0
```

不要为了“完整”把已经关闭的问题重新列成当前 blocker。

---

## 7. Closed / Forbidden Routes

只保留下一个会话真的需要知道的关闭路线和禁区。

```text
<CLOSED_ROUTE_1>=CLOSED:<short reason>
<CLOSED_ROUTE_2>=CLOSED:<short reason>
```

完整历史放在 current state / known failures，不在 handoff 里重复。

---

## 8. Authorization Ledger

只记录仍会影响下一步执行的授权状态。

```text
AUTHORIZATION=<name>
CLAIMED=
CONSUMED=
RESULT=
REPLAY_PERMITTED=
SUPERSEDED_BY=
```

已消费或已被替代的授权必须明确禁止重放。

下一授权如果只是建议：

```text
PROPOSED_AUTHORIZATION=<name>
GRANTED=false
```

`READY_FOR_NEW_AUTHORIZATION=true` 不等于用户已经授权。

---

## 9. Rollback Authority

下一步如果可能修改系统，写清楚如何退回原状态。

```text
ROLLBACK_BASELINE=
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true|false
ROLLBACK_AUTHORITY_PATH_OR_ID=
NORMAL_PATH_RESTART_ALLOWED=
ROLLBACK_ONLY_RESTART_LIMIT=
SECOND_ATTEMPT_ALLOWED=
```

Rollback 顺序：

```text
<STEP 1>
→ <STEP 2>
→ ...
→ verify exact prechange state
→ STOP
```

Rollback 失败：

```text
ROLLBACK_INCOMPLETE=true
MANUAL_RECOVERY_REQUIRED=true
```

完全只读时：

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=<exact logical gate name>
```

### 10.1 Purpose

用一小段白话说明：

- 这一步到底要确认什么；
- 为什么现在做；
- 这一步**不能**证明什么。

### 10.2 Frozen inputs

只列本 gate 真正使用的输入：

```text
<INPUT_1>=
<INPUT_2>=
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
STOP=true
```

### 10.5 FAIL

```text
<GATE_RESULT>=FAIL_<EXACT_CLASS>
READY_FOR_<NEXT_STAGE>=false
STOP=true
```

不得自动跨到下一个 gate。

---

## 11. Hard Allowed / Forbidden Scope

长期默认规则来自 `N3W_PROJECT_WORKING_CONTEXT.md`；这里只写本 gate 的具体边界。

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

如果允许有限范围的 evidence/snapshot 写入：

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=<exact path/scope>
```

---

## 12. Execution Contract

写清楚**这一步由谁执行、在哪里执行、执行到哪里必须停**。

```text
EXECUTOR=
EXECUTION_METHOD=<chat-tool|mac-terminal|script|manual-physical|other>
DIRECT_CODE_SUPPLIED=true|false
DSL_COMPILATION_USED=true|false
```

如果由 Mac Terminal / 用户现场执行，直接给完整、可复制、可停止的命令或步骤，不要为了形式再包一层无必要 executor。

如果采用 DSL：

```text
ROLE:
Task-appropriate executor under the bounded contract below.

Use the minimum necessary commands with already-installed tools.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair automatically.
Do not retry unless explicitly permitted.
Do not enter the next gate.
```

然后只写当前 gate 必需的编号步骤。

如果前一步结果决定后一步是否安全，可以分阶段；否则尽量一次交付完整机械操作包，避免无意义的“一条命令一次对话”。

---

## 13. Expected Closure

预先定义最终需要返回的结构化字段。

```text
=== <GATE NAME> CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

<EXACT BINDING / EVIDENCE FIELDS>

LIVE_RUNTIME_MUTATION=
BOARD_ACCESS=

<GATE_RESULT>=
NEXT_ROUTE=
STOP=true

=== END ===
```

结构化 closure 用来保留精确证据；面向用户的说明仍先讲白话结论。

---

## 14. After PASS / FAIL

### PASS 后

只说明下一阶段名称，不自动执行：

```text
AFTER_PASS_NEXT_STAGE=
AUTO_EXECUTE_AFTER_PASS=false
```

需要新 mutation authorization 时：

```text
NEW_AUTHORIZATION_REQUIRED=true
```

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
STOP_AND_REVIEW=true
```

---

## 15. KNOWN_FAILURES Updates

本轮如果发现了新的真实问题：

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true|false
```

如 true：

```text
KF_ID=
DOMAIN=
SYMPTOM=
ROOT_CAUSE=
FIX_OR_GUARD=
STATUS=
```

根因没证明就写 `TBD`，不要补猜测。

如果只是触发已有 guard：

```text
EXISTING_KF_GUARD_USED=<KF-ID>
NEW_KF_REQUIRED=false
```

---

## 16. New Chat Start Prompt

启动提示词只负责把新会话带到正确起点，不再重复整份 handoff。

最低读取集：

```text
1. 本 handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. exact handoff standard authority（仅当本 handoff 明确指定）
```

如用户另有私有工作上下文，可在新会话中单独读取；不得把其中敏感值复制到公开 GitHub。

建议正文：

```text
阅读《<handoff file>》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

如果 handoff 指定了 exact handoff standard authority，再按指定 commit 读取对应标准。

继续“<project>”。

不要重新复盘全部历史。
先进行当前 gate 所需的最小只读确认，然后只进入：

NEXT_ONE_GATE=<...>

默认：
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

不要重放 consumed authorization，不要重新进入 closed routes，不要自动跨越下一阶段。
```

---

## 17. Final Frozen State

只冻结下一会话真正需要的状态。

```text
CURRENT_STAGE=
CURRENT_STOP_POINT=

CURRENT_BLOCKER=
LIVE_SYSTEM_STATE=
NEXT_ONE_GATE=

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=
TEAM_SHARE_COMPLETENESS=PASS|FAIL

PROJECT_WORKING_CONTEXT_VERSION=1.0
HANDOFF_TEMPLATE_VERSION=1.2

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

如果存在重要但尚未进入 GitHub 的工程产物，必须在本节列出公开安全的 locator/hash 和原因；不要假装 `TEAM_SHARE_COMPLETENESS=PASS`。

---

## 18. Handoff Compliance Audit

正式交接文档结束前逐项检查：

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.2
PROJECT_WORKING_CONTEXT_VERSION=1.0

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

如果任一适用项无法 PASS：

```text
HANDOFF_READY_FOR_NEW_CHAT=false
```

不得把该文档称为正式交接 authority。
