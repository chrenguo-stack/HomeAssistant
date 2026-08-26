# <PROJECT NAME>
# <STAGE / SUBJECT>
# 新会话交接文档 V<version> — <YYYY-MM-DD>

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文必须符合 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`。  
> 如本文与 exact repository/runtime/live evidence 冲突，以更高 authority 为准，并先停止执行、完成 rebind。

---

## 0. 会话切换结论

说明为什么现在切换会话，以及下一会话从哪里开始。

```text
CURRENT_STAGE=
CURRENT_STOP_POINT=
NEXT_ONE_GATE=
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=<true|false>
```

明确：下一会话不是重新复盘全部历史，而是从 `NEXT_ONE_GATE` 开始。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护产品路线与架构边界；
- 维护 exact-main/image/successor/runtime authority；
- 设计 gate、scope、authorization、rollback；
- 根据 Codex closure 做 PASS / FAIL / STOP 分类；
- 区分 product/runtime/infrastructure/CI/physical-harness defect；
- 防止测试框架复杂度超过产品本身。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL contract；
- 运行必要的 Git/Docker/SSH/Compose/shell/test 命令；
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

Codex 必须将 DSL 中的 `inspect / derive / resolve / verify / create bounded snapshot` 等 primitive 机械翻译为最低必要命令执行。除非合同明确要求 exact supplied implementation，否则不得因为缺少预写 Bash/Python executor 而停止。

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

只列下一会话继续所需的 current authorities。

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

如不适用：

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

记录交接时真正 live 的状态，而不是只引用更早历史。

```text
MANAGER_STATE=
MANAGER_IMAGE_ID=
MANAGER_RESTART_STATE=

BROKER_STATE=
BROKER_IMAGE_ID=
BROKER_RESTART_STATE=

HOMEASSISTANT_STATE=
HOMEASSISTANT_IMAGE_ID=

PAIRING_SERVICE_STATE=
PAIRING_PORT_OWNER_STATE=

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

若某项需要新会话开头重新绑定：

```text
<LIVE FACT>_REQUIRES_FRESH_READONLY_REBIND=true
```

---

## 5. Proven Current Facts

只列已有 direct evidence 支持的当前事实。

```text
<FACT_1>=
<FACT_2>=
...
```

保留重要 evidence/path/hash，但不输出 secret。

明确把推断单独标记：

```text
INFERENCE_<NAME>=
```

不得把 inference 写进 proven facts。

---

## 6. Current Root Cause / Blockers

只写仍然阻塞当前 product route 的事项。

### Blocker A — <name>

```text
ROOT_CAUSE=
PROVEN_BY=
SOURCE_DEFECT_PROVEN=
RUNTIME_DEFECT_PROVEN=
```

### Blocker B — <name>

```text
...
```

如果没有 blocker：

```text
CURRENT_BLOCKER_COUNT=0
```

---

## 7. Closed / Forbidden Routes

除非出现新的 direct counter-evidence，下一会话不得重新进入：

```text
<CLOSED_ROUTE_1>
<CLOSED_ROUTE_2>
...
```

推荐保留简短原因：

```text
<ROUTE>=CLOSED:<proof/reason>
```

---

## 8. Authorization Ledger

列出所有仍与当前路线有关的 authorization。

```text
AUTHORIZATION=<name>
CLAIMED=
CONSUMED=
RESULT=
REPLAY_PERMITTED=
SUPERSEDED_BY=
```

必须显式列出 consumed/superseded 的 replay guard。

如果下一 authorization 只是建议：

```text
PROPOSED_AUTHORIZATION=<name>
GRANTED=false
```

`READY_FOR_NEW_AUTHORIZATION=true` 不等于 granted。

---

## 9. Rollback Authority

如下一 gate 可能 mutation，写清：

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

Rollback failure：

```text
ROLLBACK_INCOMPLETE=true
MANUAL_RECOVERY_REQUIRED=true
```

若下一 gate 完全只读且不需要 rollback：

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
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

Codex 不得自动进入下一个 gate。

---

## 11. Hard Allowed / Forbidden Scope

Default：

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

如允许 bounded evidence/snapshot write：

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=<exact path/scope>
```

---

## 12. Codex DSL Execution Contract

本节必须是 self-contained execution protocol，而不是“参考上一条消息”。

起始语义：

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
Do not retry unless explicitly permitted.
Do not enter the next gate.
```

然后写完整编号 DSL：

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
3. PRECLAIM / EXECUTION
============================================================
...

============================================================
N. HARD STOP
============================================================
...
```

不要在本节默认嵌入大型高阶模型生成的 Python executor。

---

## 13. Expected Closure

预先定义 Codex 最终只返回的结构化字段。

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

Closure 必须足以让高阶模型直接分类，不依赖 Codex再次解释 raw log。

---

## 14. After PASS / FAIL

### PASS 后

只说明下一阶段名称：

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
RETURN_TO_HIGH_LEVEL_MODEL=true
```

---

## 15. KNOWN_FAILURES Updates

本轮新发生的问题：

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

根因未证明写 `TBD`。

---

## 16. New Chat Start Prompt

提供一段可以直接粘贴到新会话的启动文本，至少要求新会话：

- 阅读本 handoff；
- 阅读 `NEW_CHAT_HANDOFF_STANDARD.md`；
- 阅读 `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`；
- 使用高阶模型 + Codex low-order execution；
- 承认 DSL compilation authority；
- 只进入 `NEXT_ONE_GATE`；
- 默认不 mutation、不访问板卡；
- 不重放 consumed authorization；
- 不重新进入 closed routes。

建议正文：

```text
阅读《<handoff file>》以及：
- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“<project>”。

本轮继续采用“高阶模型思考 + Codex 低阶模型执行”。
Codex 的职责包括将 exact DSL execution contract 机械编译为最低必要命令；
PREWRITTEN_EXECUTOR_REQUIRED=false。

当前只进入：
NEXT_ONE_GATE=<...>

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

先 rebind 当前 authority，再执行该 gate；不要自动跨越下一阶段。
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

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

HANDOFF_STANDARD_VERSION=1.0
```

---

## 18. Handoff Compliance Audit

正式交接文档结束前必须全部检查。

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

如果任一适用项无法 PASS：

```text
HANDOFF_READY_FOR_NEW_CHAT=false
```

不得把该文档称为正式交接 authority。
