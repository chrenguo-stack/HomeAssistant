# N3-W 阶段执行计划标准 V1.0

`STAGE_EXECUTION_PLAN_STANDARD_VERSION=1.0`

本标准用于解决长任务跨多轮对话后逐渐偏离原始目标的问题。它只定义**任务导航与交接治理**，不替代产品架构、ADR、源码、测试、运行时证据或授权边界。

## 1. 四层职责

### 1.1 PROJECT WORKING CONTEXT

回答：**这个项目长期在做什么、哪些稳定规则必须继承。**

不得用它记录频繁变化的当前任务坐标。

### 1.2 STAGE EXECUTION PLAN

回答：**当前阶段最终要走到哪里、完整任务链是什么。**

每个活动阶段必须有且只有一个 master stage execution plan。它是任务链的唯一权威。

### 1.3 CURRENT STATE

回答：**现在位于 master plan 的哪一个任务节点。**

Current State 可以记录事实状态、证据、阻塞和下一任务 ID，但不得自行创造、重排或删除 master plan 中的任务链。

### 1.4 HANDOFF

回答：**上一轮具体完成了什么、停在哪里、下一轮如何恢复现场。**

Handoff 是恢复现场的快照，不是任务规划权威，不得因为对话中的临时修复自行改变长期任务链。

## 2. 权威关系

```text
PROJECT_WORKING_CONTEXT
        │
        ▼
STAGE_EXECUTION_PLAN        ← task-chain authority
        │
        ▼
N3W_CURRENT_STATE           ← current coordinate
        │
        ▼
PR / CI / evidence          ← execution proof
        │
        ▼
NEW_CHAT_HANDOFF            ← resume snapshot
        │
        └──── new chat re-reads master plan
```

产品设计或安全规则发生冲突时，仍以适用的架构 authority、ADR、仓库规则、fresh source/runtime/physical evidence 和授权边界为准。Stage Execution Plan 只对“任务顺序与阶段范围”拥有权威。

## 3. Stage Execution Plan 必填字段

每份活动计划至少包含：

```text
PLAN_ID=
PLAN_VERSION=
PLAN_STATUS=<DRAFT|ACTIVE|PAUSED|CLOSED>

LONG_TERM_GOAL=
STAGE_GOAL=

IN_SCOPE=
OUT_OF_SCOPE=

TASK_CHAIN=
INITIAL_TASK=

STAGE_EXIT_CRITERIA=
TASK_CHAIN_MUTATION_ALLOWED=false
```

任务节点必须具有稳定 ID，例如：

```text
OTA-R8-01
OTA-R8-02
OTA-R8-03
```

或已有稳定阶段编号：

```text
R8.1
R8.2
R8.3
```

自然语言标题可以调整，但在同一计划版本内不应无故复用或改变已归档 Task ID 的含义。

## 4. 每个任务节点的最小定义

```text
TASK_ID=
GOAL=
PRECONDITIONS=
ACTIONS=
EXIT_CRITERIA=
EVIDENCE=
NEXT_TASK=
STOP_BOUNDARY=
```

可以把局部修复、测试补强等作为当前 TASK_ID 的内部子步骤处理，只要没有扩大阶段范围、改变后续顺序或新增独立完成条件。

## 5. Current State 绑定字段

一旦具体阶段计划建立，`N3W_CURRENT_STATE.md` 应维护：

```text
MASTER_TASK_DOCUMENT=
MASTER_TASK_DOCUMENT_SHA=
ACTIVE_STAGE_ID=
CURRENT_TASK_ID=
NEXT_TASK_ID=
TASK_CHAIN_STATUS=<ALIGNED|BLOCKED|PLAN_UPDATE_REQUIRED>
```

Current State 中的 `NEXT_TASK_ID` 必须能在 master plan 中找到对应关系。

## 6. Handoff V1.5 绑定规则

正式 handoff 必须记录：

```text
MASTER_TASK_DOCUMENT=
MASTER_TASK_DOCUMENT_SHA=
LONG_TERM_GOAL=
CURRENT_STAGE=
CURRENT_TASK=
NEXT_TASK=
NEXT_TASK_CHAIN=
STAGE_EXIT_CRITERIA=
OUT_OF_SCOPE=
TASK_CHAIN_MUTATION_ALLOWED=false
TASK_ALIGNMENT=<PASS|FAIL|UNBOUND>
```

当活动阶段尚未正式建立 master plan 时，可临时使用：

```text
MASTER_TASK_DOCUMENT=UNBOUND
TASK_ALIGNMENT=UNBOUND
```

但这只允许用于“框架已建立、具体任务尚待填写”的过渡状态。具体任务链一旦开始执行，应先建立并绑定 master plan。

## 7. 新会话偏航保护

新会话恢复任务时，按顺序读取：

1. 当前 handoff；
2. 适用仓库规则 / AGENTS；
3. handoff 指向的 master stage execution plan；
4. `N3W_CURRENT_STATE.md` 与 `N3W_CURRENT_STATE_INDEX.md`；
5. 当前任务真正需要的架构、KF、closure、CI 或 live evidence。

随后检查：

```text
MASTER_PLAN_FOUND=
CURRENT_TASK_EXISTS_IN_PLAN=
NEXT_TASK_MATCHES_PLAN=
HANDOFF_MATCHES_CURRENT_STATE=
TASK_ALIGNMENT=<PASS|FAIL|UNBOUND>
```

只有 `TASK_ALIGNMENT=PASS` 才能把 handoff 中的“下一步”当作 master task chain 的正常续接。

若为 `FAIL`：

- 不沿着 handoff 临时描述继续扩展任务；
- fresh rebind 当前仓库和事实状态；
- 以 master plan 重新定位 current task；
- 如确需改变路线，先按第 8 节修改 master plan。

## 8. 任务链变更协议

默认：

```text
TASK_CHAIN_MUTATION_ALLOWED=false
```

需要改变阶段目标、任务顺序、增加/删除独立任务节点或扩大范围时，必须：

1. 修改 master Stage Execution Plan；
2. 通过 Git commit 保存变更理由；
3. 同步 `N3W_CURRENT_STATE.md` / index 的任务坐标；
4. 后续 handoff 引用新的 plan blob/SHA；
5. 在继续执行前重新得到 `TASK_ALIGNMENT=PASS`。

不得通过只改 handoff、聊天描述、PR comment 或 Current State 来静默改变任务链。

## 9. 与 GitHub Issue / PR 的关系

- Stage Execution Plan：任务链唯一权威；
- Current State：当前位置；
- Issue：可作为进度看板、讨论与待办入口；
- PR：实现和评审载体；
- CI / evidence：完成条件的证明；
- Handoff：跨会话恢复现场。

Issue、PR 和 handoff 都不得替代 master Stage Execution Plan。

## 10. 当前过渡状态

本标准首次落地时只建立治理框架，不自动推导现有 OTA 或其他长任务的完整任务链。

```text
TASK_NAVIGATION_FRAMEWORK=READY
ACTIVE_STAGE_EXECUTION_PLAN=UNBOUND
TASK_CHAIN_POPULATION=PENDING
```

后续应在用户确认具体长任务后，使用
`docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md`
建立该阶段的 master plan，再把 Current State 与 handoff 绑定到它。
