# N3-W 阶段执行计划模板 V1.0

`STAGE_EXECUTION_PLAN_TEMPLATE_VERSION=1.0`

> 使用前先阅读 `docs/development/STAGE_EXECUTION_PLAN_STANDARD.md`。
> 本模板只定义任务链；产品技术设计应引用对应 architecture / ADR / source authority，不在这里重复创造。

## 1. 计划身份

```text
PLAN_ID=<stable id>
PLAN_VERSION=<version>
PLAN_STATUS=<DRAFT|ACTIVE|PAUSED|CLOSED>

LONG_TERM_GOAL=<长期目标>
STAGE_GOAL=<本阶段目标>

TASK_CHAIN_MUTATION_ALLOWED=false
```

- 上位路线／产品 authority：<路径或固定链接>
- 创建原因：<为什么需要这个阶段计划>
- 适用范围：<系统/组件/版本>

## 2. 范围

### IN_SCOPE

- <...>

### OUT_OF_SCOPE

- <...>

## 3. 完整任务链

```text
TASK_CHAIN=
<TASK-01>
→ <TASK-02>
→ <TASK-03>
→ <TASK-N>

INITIAL_TASK=<TASK-01>
```

> 这里必须展示整个阶段的后续任务链，不能只写“下一步”。

## 4. 任务节点

### <TASK-01> — <标题>

```text
TASK_ID=<TASK-01>
GOAL=<...>
PRECONDITIONS=<...>
ACTIONS=<...>
EXIT_CRITERIA=<...>
EVIDENCE=<...>
NEXT_TASK=<TASK-02>
STOP_BOUNDARY=<...>
```

### <TASK-02> — <标题>

```text
TASK_ID=<TASK-02>
GOAL=<...>
PRECONDITIONS=<...>
ACTIONS=<...>
EXIT_CRITERIA=<...>
EVIDENCE=<...>
NEXT_TASK=<TASK-03>
STOP_BOUNDARY=<...>
```

<!-- 按实际任务数量继续增加。 -->

## 5. 阶段完成条件

```text
STAGE_EXIT_CRITERIA=
- <...>
- <...>
```

只有满足这些条件后，才能把本计划标记为 `CLOSED` 并进入下一阶段。

## 6. 任务链变更记录

| Revision | Commit | Change | Reason | Current State synchronized |
|---|---|---|---|---|
| <v1> | <sha> | initial chain | <reason> | <yes/no> |

任何增加、删除、重排任务节点或范围变化都必须先修改本文件并留下 Git 记录。

## 7. Current State / Handoff 绑定

计划激活后，在 `N3W_CURRENT_STATE.md` 和新生成 handoff 中维护：

```text
MASTER_TASK_DOCUMENT=<this file>
MASTER_TASK_DOCUMENT_SHA=<current blob or fixed commit>
ACTIVE_STAGE_ID=<...>
CURRENT_TASK_ID=<...>
NEXT_TASK_ID=<...>
TASK_ALIGNMENT=PASS
```
