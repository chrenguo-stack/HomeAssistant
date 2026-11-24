# N3-W 普通切换对话 mini handoff 模板 V1.2

`MINI_HANDOFF_TEMPLATE_VERSION=1.2`

本模板用于**跨对话快速续接**。目标是让新会话准确恢复当前任务，不重复生成完整阶段交接。

mini handoff 是否可用，不再由“任务是否高风险”单独决定，而由**下一会话能否从交接中获得安全继续所需的完整信息**决定。实机、生产、回滚、一次性授权、失败恢复等情形仍可使用 mini handoff，但必须补充相应信息；当信息量已经不适合简洁表达，或用户明确要求正式交接时，可改用 [`NEW_CHAT_HANDOFF_TEMPLATE.md`](NEW_CHAT_HANDOFF_TEMPLATE.md) V1.5。

## 适用原则

以下状态用于判断交接需要补充哪些信息，不再作为“禁止使用 mini handoff”的资格门：

```text
GITHUB_STATE_ALIGNED=<true|false>
UNARCHIVED_CRITICAL_RESULT_COUNT=<n>
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=<n>

LIVE_OR_PHYSICAL_MUTATION_PENDING=<true|false>
PRODUCTION_RECOVERY_IN_PROGRESS=<true|false>
UNCONSUMED_ONE_SHOT_AUTHORIZATION=<true|false>
ROLLBACK_STATE_AMBIGUOUS=<true|false>
CURRENT_STATE_AMBIGUOUS=<true|false>

SUPPLEMENT_REQUIRED=<true|false>
```

任何非理想状态都必须如实记录，不能为了继续使用 mini handoff 而改写成安全状态。

以下任一情况出现时，**需要补充完善具体信息**：

| 情形 | mini handoff 必须补充的信息 |
|---|---|
| 即将跨对话执行 T1、板卡、生产服务写入、回滚、断电或恢复 | 精确目标、当前基线、下一操作、授权边界、回滚/恢复入口、禁止项 |
| 存在尚未认领/消费且下一会话需要继续执行的一次性授权 | 授权来源、目标、候选、适用条件、是否已认领/消费、是否允许重放 |
| 当前存在失败恢复、部分写入、回滚中、UNKNOWN/UNPROVEN 关键状态 | 最后成功步骤、实际发生的变更、当前恢复状态、最小 fresh 核对方法 |
| 需要冻结多个 SHA / artifact / transaction / runtime authority 才能安全继续 | 所有 exact 标识及其相互关系，不使用“最新”“当前那个”等模糊指代 |
| 刚发生新的重要故障、误判、源码修复且状态尚未稳定收口 | 根因/证据、修复 head、已完成验证、未完成验证、不可复用失败路径 |
| 后续由不同执行者接手 | 可执行入口、必要命令/执行包、授权状态、停止条件、恢复方式 |
| 用户明确要求正式交接或模板 V1.5 | 按用户要求使用正式模板 V1.5 |

正式模板 V1.5 是更完整的表达形式，不再因为任务属于上述风险类别而自动成为强制要求。除用户明确要求正式模板外，只要 mini handoff 已完整包含下一会话安全续接所需信息，就可以继续使用 mini handoff。

mini handoff 不能授予权限，也不能替代 GitHub current state、KF、closure、Stage Execution Plan 或正式授权记录。

---

## 1. 当前任务与停点

- 当前任务：<正在做什么>
- 已完成到：<最后一个有证据支持的步骤>
- 当前状态：<可继续／等 CI／等用户／阻塞／已完成>
- 当前停点：<一句话说明从哪里继续>

## 2. GitHub 续接入口

- 仓库／PR／分支：<必要时填写>
- 当前 head：<完整 SHA；不适用写 N/A>
- Master Task Document：<活动阶段 master plan；尚未建立写 UNBOUND>
- Master Task Document SHA：<blob/full commit SHA；未绑定写 UNBOUND>
- Current Stage / Task：<稳定 Stage ID / Task ID；未绑定写 UNBOUND>
- Next Task Chain：<至少保留 NEXT_TASK 及后续链；未绑定写 UNBOUND>
- Current State：<通常为 docs/development/N3W_CURRENT_STATE.md>
- State Index：<通常为 docs/development/N3W_CURRENT_STATE_INDEX.md>
- 相关 KF／closure／设计文档：<只列下一步需要的路径或编号>
- CI／artifact：<仅当下一步依赖它时填写>

新会话不得仅凭本 mini handoff 假定上述状态仍然成立；执行前按下一步需要做 fresh rebind。

如果 `Master Task Document != UNBOUND`，新会话还必须确认 Current Task / Next Task 与 master plan 一致；不一致时先恢复任务坐标，不沿 handoff 临时描述继续扩展任务。

## 3. 下一步

- 下一动作：<一项完整、明确的动作>
- 允许范围：<只写当前已经允许继续的范围>
- 暂停边界：<到哪里必须停>
- 需要用户操作：<无／具体操作>

如果下一动作涉及实机、生产、不可逆写入、新的一次性授权、回滚或恢复，不需要仅因风险类别而强制切换模板；必须先把第 3A 节中与本任务有关的信息补齐。若补充后 mini handoff 已明显失去简洁性，或用户明确要求完整正式交接，再使用正式模板 V1.5。

## 3A. 条件补充信息（按需填写）

没有对应情形时可省略。存在对应情形时不得省略关键字段。

```text
TARGET=<精确目标；不适用写 N/A>
MUTATION_OR_RECOVERY_ACTION=<下一项写入/恢复/回滚动作；不适用写 N/A>
PRE_ACTION_BASELINE=<写前或恢复前基线；不适用写 N/A>

AUTHORIZATION_SOURCE=<来源；无写 NONE>
AUTHORIZATION_SCOPE=<范围；无写 NONE>
AUTHORIZATION_STATE=<UNCLAIMED|CLAIMED|CONSUMED|SUPERSEDED|N/A>
AUTHORIZATION_REPLAY_ALLOWED=<true|false|N/A>

EXACT_SOURCE_HEAD=<sha/N/A>
EXACT_ARTIFACT=<id+hash/N/A>
EXACT_TRANSACTION=<id+phase/N/A>
EXACT_RUNTIME_AUTHORITY=<version/hash/N/A>

LAST_SUCCESSFUL_STEP=<失败/恢复现场最后成功步骤；不适用写 N/A>
ACTUAL_CHANGES_ALREADY_MADE=<实际已发生变更；无写 NONE>
ROLLBACK_OR_RECOVERY_ENTRY=<入口；不适用写 N/A>

FRESH_REBIND_REQUIRED=<true|false>
STOP_CONDITION=<明确停止条件>
```

只填写下一会话真正依赖的字段，不为了“完整”复制无关历史。

## 4. 新会话启动语

```text
继续 N3-W 当前任务。

先读取：
- <MASTER_TASK_DOCUMENT；UNBOUND 时跳过>
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- <本任务相关 KF / closure / design 文档>

fresh rebind：
- repository main
- <PR / branch / head，如适用>
- <下一动作真正依赖的 live / CI / artifact 状态>

当前停点：
<CURRENT_STOP_POINT>

当前任务：
<CURRENT_TASK_ID>

下一任务链：
<NEXT_TASK_CHAIN>

按现有授权边界继续；如发现 source、runtime、authorization 或 evidence drift，停止受影响操作并重新判定。
```

## 5. mini handoff 完整性检查

```text
MINI_HANDOFF_TEMPLATE_VERSION=1.2
MINI_HANDOFF_COMPLETE=<PASS|FAIL>

TEAM_SHARED_WORKSPACE=GITHUB
GITHUB_STATE_ALIGNED=<true|false>
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=<n>
UNARCHIVED_CRITICAL_RESULT_COUNT=<n>

LIVE_OR_PHYSICAL_MUTATION_PENDING=<true|false>
PRODUCTION_RECOVERY_IN_PROGRESS=<true|false>
UNCONSUMED_ONE_SHOT_AUTHORIZATION=<true|false>
ROLLBACK_STATE_AMBIGUOUS=<true|false>
CURRENT_STATE_AMBIGUOUS=<true|false>

SUPPLEMENT_REQUIRED=<true|false>
SUPPLEMENT_COMPLETE=<true|false|N/A>
FORMAL_HANDOFF_RECOMMENDED=<true|false>

FRESH_REBIND_REQUIRED=true
MASTER_TASK_DOCUMENT_BOUND=<true|false>
TASK_ALIGNMENT=<PASS|UNBOUND>
NEXT_ACTION_EXPLICIT=true
NEXT_TASK_CHAIN_EXPLICIT=true
STOP_BOUNDARY_EXPLICIT=true
```

任一下一会话安全续接所需的信息缺失时：

```text
MINI_HANDOFF_COMPLETE=FAIL
RESUME_EXECUTION_ALLOWED=false
MISSING_INFORMATION=<需要补齐的具体内容>
```

此时应先补齐缺失信息。是否转用正式模板 V1.5 取决于哪种形式更清晰；**模板更长本身不是安全条件，信息完整才是安全条件。**

不要为了保持 mini 简短而删除、隐藏或弱化真实的 live / authorization / rollback / recovery 状态。
