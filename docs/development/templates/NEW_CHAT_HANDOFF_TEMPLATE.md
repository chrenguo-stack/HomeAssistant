# <PROJECT NAME>
# <STAGE / SUBJECT>
# 新会话交接文档 V<version> — <YYYY-MM-DD>

```text
HANDOFF_TEMPLATE_VERSION=1.1
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
COMMUNICATION_STYLE=PLAIN_DIRECT_CONCRETE
ABSTRACT_TERM_DENSITY=LOW
NEXT_ONE_GATE_ONLY=true
```

> 如果当前项目指定了 exact handoff standard authority，应按指定 commit 读取并遵守对应标准；不要假定 current `main` 一定包含历史标准文件。  
> 如本文与 fresh repository/runtime/live evidence 冲突，以最新直接证据为准，并先停止执行、重新确认当前状态。

---

## 0. 会话切换结论

说明为什么现在切换会话，以及下一会话从哪里继续。

```text
CURRENT_STAGE=
CURRENT_STOP_POINT=
NEXT_ONE_GATE=
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=<true|false>
```

下一会话不重新复盘全部历史，先确认当前状态，然后从 `NEXT_ONE_GATE` 继续。

---

## 1. 工作原则与表达方式

### 1.1 首要原则

所有流程和工具都只服务于一个目标：**准确、安全、高效、可验证地完成当前任务**。

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
WORKFLOW_CONVENTIONS_ARE_MEANS_NOT_GOALS=true
```

必须遵守：

- 不为了流程形式增加没有实际价值的步骤；
- 不把推测写成事实；
- 不在没有授权时扩大修改范围；
- 第一处实质性异常出现后先停止，说明发生了什么，再决定是否继续；
- 能用更简单的方法得到同样可靠的结果时，优先选简单方法。

### 1.2 对话表达规则

面向用户的回复优先使用直白、具体、容易形成画面的说法。

```text
COMMUNICATION_STYLE=PLAIN_DIRECT_CONCRETE
ABSTRACT_TERM_DENSITY=LOW
EXPLAIN_CAUSE_EFFECT=true
EXPLAIN_NEXT_ACTION=true
```

具体要求：

- 先说“现在发生了什么、为什么、下一步做什么”，再给技术细节；
- 能用普通中文说明时，不连续堆叠 `authority / gate / rebind / contract / closure` 等抽象词；
- 必须使用专业术语时，第一次出现就紧跟一句白话解释；
- 不为了显得严谨而重复罗列同一组状态字段；
- 命令、SHA、路径、错误码等需要精确保留的内容放在代码块里；
- 解释故障时优先使用具体对象和因果关系，例如“Board B 发 Challenge 时 Wi-Fi 已切到别的信道，所以发送被驱动拒绝”，而不是只给抽象分类名；
- 除非用户要求详细清单，否则避免把一段解释拆成大量标签和术语列表；
- 用户需要执行命令前，先用一句话说明是否需要动哪块板、是否会写入或重启。

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

只列下一会话继续所需的当前权威信息，不把历史资料全部搬进来。

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

```text
TARGET_HOST=
TARGET_ARCH=
<OTHER REQUIRED EXACT AUTHORITIES>
```

---

## 4. Current Live Baseline

记录交接时真正还在运行的状态，而不是只引用旧记录。

```text
MANAGER_STATE=
MANAGER_IMAGE_ID=
MANAGER_RESTART_STATE=

BROKER_STATE=
BROKER_IMAGE_ID=
BROKER_RESTART_STATE=

HOMEASSISTANT_STATE=
HOMEASSISTANT_IMAGE_ID=

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

需要下一会话重新读取的项目明确写：

```text
<LIVE_FACT>_REQUIRES_FRESH_READONLY_RECHECK=true
```

---

## 5. Proven Current Facts

这里只写已经有直接证据支持的事实。

```text
<FACT_1>=
<FACT_2>=
...
```

重要的路径、SHA、错误码可以保留，但不要输出 secret。

推断必须单独标记：

```text
INFERENCE_<NAME>=
```

不得把推断混进已证明事实。

---

## 6. Current Root Cause / Blockers

只写仍然挡住当前产品路线的问题。

### Blocker A — <name>

用一两句话先讲白话原因，再保留需要的精确字段：

```text
ROOT_CAUSE=
PROVEN_BY=
SOURCE_DEFECT_PROVEN=
RUNTIME_DEFECT_PROVEN=
```

如果没有 blocker：

```text
CURRENT_BLOCKER_COUNT=0
```

---

## 7. Closed / Forbidden Routes

已经证明不需要再走的路线，除非出现新的直接反证，否则不要重新进入。

```text
<CLOSED_ROUTE_1>
<CLOSED_ROUTE_2>
...
```

推荐附简短原因：

```text
<ROUTE>=CLOSED:<proof/reason>
```

---

## 8. Authorization Ledger

只记录还会影响后续执行的授权。

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

先用一段白话说明：这一步到底要确认什么，为什么现在要做它。

### 10.2 Frozen inputs

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
```

### 10.5 FAIL

```text
<GATE_RESULT>=FAIL_<EXACT_CLASS>
READY_FOR_<NEXT_STAGE>=false
STOP=true
```

执行者不得自动跨到下一个 gate。

---

## 11. Hard Allowed / Forbidden Scope

默认：

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

本节写清楚“谁执行、执行什么、什么情况下必须停”。不要依赖固定的模型层级或角色分工。

```text
EXECUTOR=
EXECUTION_METHOD=<chat-tool|mac-terminal|script|manual-physical|other>
DIRECT_CODE_SUPPLIED=true|false
DSL_COMPILATION_USED=true|false
```

如果采用 DSL，可以写：

```text
ROLE:
Task-appropriate executor under the bounded contract below.

This document is an executable DSL protocol.
Use the minimum necessary commands with already-installed tools.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair automatically.
Do not retry unless explicitly permitted.
Do not enter the next gate.
```

然后写完整编号步骤：

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================
...

============================================================
1. FROZEN INPUTS
============================================================
...

============================================================
2. HARD SCOPE
============================================================
...

============================================================
3. PRECHECK / EXECUTION
============================================================
...

============================================================
N. HARD STOP
============================================================
...
```

如果直接给一段完整命令或完整代码更清楚、更安全，就直接给，不需要为了流程形式把它拆成很多层。

---

## 13. Expected Closure

预先定义最终需要返回的结构化字段。

```text
=== <GATE NAME> CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

<EXACT BINDING FIELDS>

LIVE_RUNTIME_MUTATION=
BOARD_ACCESS=

<GATE_RESULT>=
NEXT_ROUTE=

=== END ===
```

结构化 closure 用来保留精确证据；面向用户的说明仍应先用白话总结结果。

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

---

## 16. New Chat Start Prompt

提供一段可以直接粘贴到新会话的启动文本，至少要求新会话：

- 阅读本 handoff；
- 如果项目指定 exact handoff standard authority，按指定 commit 读取；
- 阅读当前状态文档和 `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`；
- 准确、安全、高效、可验证优先；
- 回复少堆抽象术语，优先用直白具体的中文解释；
- 先说发生了什么、为什么、下一步做什么；
- 只进入 `NEXT_ONE_GATE`；
- 默认不 mutation、不访问板卡；
- 不重放 consumed authorization；
- 不重新进入 closed routes。

建议正文：

```text
阅读《<handoff file>》，并读取：
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

如果 handoff 指定了 exact handoff standard authority，再按指定 commit 读取对应标准。

继续“<project>”。

准确、安全、高效、可验证优先。
回复时少罗列抽象术语，尽量用直白、具体、容易理解的中文；
先说明“现在发生了什么、为什么、下一步做什么”，必要时再给精确字段、SHA、错误码和命令。

当前只进入：
NEXT_ONE_GATE=<...>

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

先确认当前状态，再执行该步骤；不要自动跨越下一阶段。
```

---

## 17. Final Frozen State

以紧凑机器可读形式冻结交接点：

```text
CURRENT_STAGE=
CURRENT_STOP_POINT=

SOURCE_DEFECT_PROVEN=
CURRENT_BLOCKER=

LIVE_SYSTEM_STATE=
NEXT_ONE_GATE=

PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
COMMUNICATION_STYLE=PLAIN_DIRECT_CONCRETE
ABSTRACT_TERM_DENSITY=LOW

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

HANDOFF_TEMPLATE_VERSION=1.1
```

---

## 18. Handoff Compliance Audit

正式交接文档结束前逐项检查：

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.1

PRIMARY_EXECUTION_PRINCIPLE_EXPLICIT=PASS
COMMUNICATION_STYLE_EXPLICIT=PASS
PLAIN_LANGUAGE_RULE_PRESENT=PASS
MODEL_HIERARCHY_REQUIREMENT_ABSENT=PASS

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
