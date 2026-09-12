# <PROJECT NAME>
# <STAGE / SUBJECT>
# 新会话交接文档 V<version> — <YYYY-MM-DD>

```text
HANDOFF_STANDARD_VERSION=1.1
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODEX_ROLE=EXACT_EXECUTOR
EXECUTION_PACKAGE_MODEL=true
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文必须符合：  
> `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`  
> `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`  
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

## 1. 执行模式与首要原则

### 1.0 首要执行原则

所有流程、角色分工、Execution Package、授权与证据设计都服务于同一个目标：**准确、安全、高效、可验证地完成当前任务**。

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
WORKFLOW_CONVENTIONS_ARE_MEANS_NOT_GOALS=true
TEAM_SHARED_WORKSPACE=GITHUB
CHAT_AND_EXECUTOR_SESSIONS=EPHEMERAL_WORKSPACES
```

### 1.1 默认执行模型

正式执行 gate 默认采用：

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODEX_ROLE=EXACT_EXECUTOR
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
```

解释：

- 高阶模型负责目标、架构、gate、scope、authorization、rollback、evidence contract 和最终判定；
- 具体命令、顺序、checkpoint、证据写入方式放进经过测试并提交 GitHub 的 exact executor；
- Codex 在正式执行 gate 中只运行绑定到 exact commit/hash 的 executor，不再把长篇 DSL 临时翻译成 shell/Python 命令；
- DSL/自然语言仍可描述目标、允许/禁止范围、PASS/FAIL/STOP 条件，但不再是命令生成权威；
- 任何需要后续判断的 argv/stdout/stderr/return code/traceback 必须由 executor 自动保存，不能只靠 Codex 摘要；
- executor 若缺失、漂移或失败，默认 STOP；修 executor 是新的 host-only gate，不在一次性物理授权中边修边继续。

### 1.2 高阶模型默认职责

- 维护产品路线与架构边界；
- 维护 exact-main/image/runtime/artifact authority；
- 设计 gate、scope、authorization、rollback；
- 设计或审查 Execution Package；
- 明确 raw evidence 在操作前后必须保存什么；
- 对结果做 `OBSERVED / DERIVED / HYPOTHESIS` 分类；
- 根据源码 + raw evidence 做 PASS / FAIL / STOP；
- 防止把 host/executor/tooling defect 误判成产品 defect；
- 不得声称知道未被 raw evidence 或 exact source 证明的命令/代码细节。

### 1.3 Codex 默认职责

正式执行 gate 中 Codex 必须：

- rebind exact package commit；
- 验证 manifest / executor / evidence schema / tests 绑定；
- 精确运行 executor；
- 不修改 executor；
- 不临时拼接 substitute command；
- 第一处 substantive failure 后按 contract STOP；
- 返回 closure + evidence manifest。

Codex 不得自行扩大 scope、修复、重放 consumed authorization、跨越下一 gate。

### 1.4 标准交互循环

```text
高阶模型：设计 gate + Execution Package/evidence contract
        ↓
Host-only：实现/测试/审查 package，提交 GitHub，绑定 commit/hash
        ↓
用户：批准需要的 exact live/physical authorization
        ↓
Codex：运行 exact executor，自动保存 raw evidence
        ↓
高阶模型：读取 source + raw evidence + closure，完成判定
```

若 package 尚未 READY，则下一 gate 必须先是 host-only package materialization/repair，而不是直接进入实板或 live mutation。

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

### 3.5 Execution Package authority

```text
EXECUTION_PACKAGE_REQUIRED=true|false
EXECUTION_PACKAGE_STATUS=READY|MATERIALIZATION_REQUIRED|NOT_APPLICABLE
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
```

若 `EXECUTION_PACKAGE_REQUIRED=true` 且 `EXECUTION_PACKAGE_STATUS!=READY`，不得直接进入 physical/live gate。

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

## 5. Proven Current Facts / Evidence Classes

只列已有 direct evidence 支持的当前事实。

必须使用以下分类：

```text
OBSERVED_<NAME>=<direct raw/source/live evidence>
DERIVED_<NAME>=<strictly derived from OBSERVED facts>
HYPOTHESIS_<NAME>=<plausible but not proven>
```

规则：

- `OBSERVED`：直接来自 raw evidence、exact source、GitHub commit、live readback；
- `DERIVED`：无需新增假设即可严格推出；
- `HYPOTHESIS`：合理猜测，不能写入 proven facts；
- Codex 的一句摘要若没有 raw evidence 支持，只能证明摘要本身被返回，不能反推出 argv/source line/root cause。

保留重要 evidence/path/hash，但不输出 secret。

---

## 6. Current Root Cause / Blockers

只写仍然阻塞当前 product route 的事项。

### Blocker A — <name>

```text
ROOT_CAUSE=
ROOT_CAUSE_CLASS=OBSERVED|DERIVED|HYPOTHESIS|TBD
PROVEN_BY=
SOURCE_DEFECT_PROVEN=
RUNTIME_DEFECT_PROVEN=
EXECUTOR_DEFECT_PROVEN=
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
BOUND_EXECUTION_PACKAGE_COMMIT=
BOUND_EXECUTOR_BLOB=
CLAIMED=
CONSUMED=
RESULT=
REPLAY_PERMITTED=
SUPERSEDED_BY=
```

必须显式列出 consumed/superseded 的 replay guard。

优化规则：host-only package 构造/测试应尽量在 claim 前完成；一次性 physical authorization 应尽量在第一处真正 target/device action 前才 claim。

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
<GATE_RESULT>=FAIL_<EXACT_CLASS>|STOP_<EXACT_CLASS>
READY_FOR_<NEXT_STAGE>=false
STOP=true
```

执行者不得自动进入下一个 gate。

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

本节取代旧版 `Codex DSL Execution Contract`。

### 12.1 Package readiness

```text
EXECUTION_PACKAGE_REQUIRED=true|false
EXECUTION_PACKAGE_MATERIALIZED=true|false
EXECUTION_PACKAGE_GITHUB_SHARED=true|false
EXECUTION_PACKAGE_TESTS_PASS=true|false
EXECUTION_PACKAGE_EXACT_BINDING=PASS|FAIL|NOT_APPLICABLE
CODEX_MAY_MODIFY_EXECUTOR_DURING_EXECUTION=false
AD_HOC_COMMAND_SYNTHESIS_ALLOWED=false
```

若 required package 未 READY：

```text
NEXT_ONE_GATE=<HOST_ONLY_EXECUTION_PACKAGE_MATERIALIZATION_OR_REPAIR>
PHYSICAL_EXECUTION_ALLOWED=false
LIVE_MUTATION_ALLOWED=false
```

### 12.2 Canonical package contents

典型内容：

```text
TASK.md                    # goal/scope/PASS/STOP，人类可读
executor.py                # exact command/order/checkpoint/evidence behavior
evidence_schema.json       # required evidence files/fields
manifest.json              # source/tool/input/hash/auth bindings
tests/...                  # host regression tests
```

实际路径：

```text
TASK_SPEC_PATH=
EXECUTOR_PATH=
EVIDENCE_SCHEMA_PATH=
MANIFEST_PATH=
TEST_PATH=
```

### 12.3 Exact execution invocation

Codex 正式执行时只应收到简短、可验证的 invocation，例如：

```text
Checkout/rebind EXECUTION_PACKAGE_COMMIT=<sha>.
Verify manifest and package hashes.
Run exactly:
<EXACT_EXECUTOR_INVOCATION>
Do not modify executor.
Do not synthesize substitute commands.
Return closure + evidence manifest.
```

如果 executor 无法启动、工具绑定不一致、hash 漂移或 manifest 不满足：STOP。不要现场修复并继续。

### 12.4 DSL role

```text
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
```

交接文档中的编号步骤只定义意图和约束；真正会运行的 argv、工具路径、顺序、重试、证据写入必须存在于 exact executor/manifest/tests 中。

---

## 13. Expected Closure + Raw Evidence Contract

### 13.1 Raw evidence first

Closure 是摘要，不是 raw evidence 替代品。

对每个重要 external command/device operation，executor 至少应按顺序保存：

```text
persist command.json
→ execute
→ persist stdout/stderr/result
→ validate
→ persist validation/adjudication
```

推荐：

```text
op_NN/
  command.json
  stdout.txt|stdout.bin
  stderr.txt|stderr.bin
  result.json
```

`command.json` 应在命令启动前存在，使“命令根本没启动”也仍然能够恢复实际 argv/executable/tool hash。

必须明确：

```text
RAW_EVIDENCE_REQUIRED=true|false
RAW_EVIDENCE_PRIVATE_ROOT=
PUBLIC_SAFE_EVIDENCE_MANIFEST=
RAW_EVIDENCE_HASH_ALGORITHM=SHA256
```

raw private evidence 可留在 Git 外，但 GitHub 必须保留 public-safe locator/hash/status，不得提交 secret/private identity。

### 13.2 Expected closure

```text
=== <GATE NAME> CLOSURE ===

EXECUTION_ID=
EXECUTION_PACKAGE_COMMIT=
EXECUTOR_GIT_BLOB=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

RAW_EVIDENCE_COMPLETE=
EVIDENCE_MANIFEST_PATH_OR_HASH=
FIRST_FAILED_OPERATION=
TARGET_ACCESS_OCCURRED=

<EXACT BINDING FIELDS>

LIVE_RUNTIME_MUTATION=
BOARD_ACCESS=

<GATE_RESULT>=
NEXT_ROUTE=
STOP_REASON=

=== END ===
```

不得用 closure 声称 executor 未保存/未证明的 argv、源码位置、root cause 或 target state。

---

## 14. After PASS / FAIL

### PASS 后

只说明下一阶段名称：

```text
AFTER_PASS_NEXT_STAGE=
AUTO_EXECUTE_AFTER_PASS=false
```

需要新 authorization 时：

```text
NEW_AUTHORIZATION_REQUIRED=true
```

### FAIL / STOP 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

若失败发生在 executor/host 层，先做 host-only 取证或 package repair；不得仅凭摘要猜测具体 root cause。

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
ROOT_CAUSE_CLASS=OBSERVED|DERIVED|HYPOTHESIS|TBD
FIX_OR_GUARD=
STATUS=
```

根因未证明写 `TBD`。

---

## 16. New Chat Start Prompt

提供一段可以直接粘贴到新会话的启动文本，至少要求新会话：

- 阅读本 handoff；
- 阅读 `NEW_CHAT_HANDOFF_STANDARD.md`；
- 阅读 `TEAM_COLLABORATION_WORKSPACE_STANDARD.md`；
- 阅读 `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`；
- 承认准确、安全、高效、可验证优先；
- 使用 GitHub versioned Execution Package，而不是把 DSL 临时编译成命令；
- Codex 正式执行时只运行 exact executor；
- raw evidence 优先于 closure 摘要；
- 只进入 `NEXT_ONE_GATE`；
- 默认不 mutation、不访问板卡；
- 不重放 consumed authorization；
- 不重新进入 closed routes。

建议正文：

```text
阅读《<handoff file>》以及：
- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“<project>”。

首要执行原则：准确、安全、高效、可验证。
执行模式：高阶模型设计并审查 GitHub versioned Execution Package；Codex 是 exact executor。
DSL/自然语言只描述目标和边界，不作为临时命令编译权威。
任何重要执行必须 raw-evidence-first；不要根据简短 STOP_REASON 猜 argv、源码或 root cause。

当前只进入：
NEXT_ONE_GATE=<...>

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

先 rebind 当前 authority 和 exact execution package；不要自动跨越下一阶段。
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
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODEX_ROLE=EXACT_EXECUTOR
EXECUTION_PACKAGE_STATUS=
EXECUTION_PACKAGE_COMMIT=
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=
TEAM_SHARE_COMPLETENESS=PASS|FAIL

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_STANDARD_VERSION=1.1
```

---

## 18. Handoff Compliance Audit

正式交接文档结束前必须全部检查。

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.1

PRIMARY_EXECUTION_PRINCIPLE_EXPLICIT=PASS
EXECUTION_MODEL_EXPLICIT=PASS
EXECUTION_PACKAGE_MODEL_EXPLICIT=PASS
CODEX_EXACT_EXECUTOR_ROLE_EXPLICIT=PASS
DSL_NOT_COMMAND_AUTHORITY=PASS
RAW_EVIDENCE_FIRST_EXPLICIT=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS

OBSERVED_DERIVED_HYPOTHESIS_SEPARATED=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
AUTHORIZATION_PACKAGE_BINDING_EXPLICIT=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS
EXECUTION_PACKAGE_READY_OR_MATERIALIZATION_GATE=PASS

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

如果任一适用项无法 PASS：

```text
HANDOFF_READY_FOR_NEW_CHAT=false
```

不得把该文档称为正式交接 authority。
