# N3-W 普通切换对话 mini handoff 模板 V1.1

`MINI_HANDOFF_TEMPLATE_VERSION=1.1`

本模板用于**普通切换对话**。目标是让新会话快速恢复当前任务，不重复生成完整阶段交接。

## 适用条件

只有同时满足以下条件时才使用本模板：

```text
GITHUB_STATE_ALIGNED=true
UNARCHIVED_CRITICAL_RESULT_COUNT=0
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0

LIVE_OR_PHYSICAL_MUTATION_PENDING=false
PRODUCTION_RECOVERY_IN_PROGRESS=false
UNCONSUMED_ONE_SHOT_AUTHORIZATION=false
ROLLBACK_STATE_AMBIGUOUS=false
CURRENT_STATE_AMBIGUOUS=false
```

以下任一情况出现时，**不要使用 mini handoff**，改用
[`NEW_CHAT_HANDOFF_TEMPLATE.md`](NEW_CHAT_HANDOFF_TEMPLATE.md) V1.5：

- 即将跨对话执行 T1、板卡、生产服务写入、回滚、断电或恢复；
- 存在尚未认领/消费、且下一会话需要继续执行的一次性授权；
- 当前存在失败恢复、部分写入、回滚中、UNKNOWN/UNPROVEN 关键状态；
- 需要冻结多个 SHA / artifact / transaction / runtime authority 才能安全继续；
- 刚发生新的重要故障、误判、源码修复，且状态尚未稳定收口；
- 后续由不同执行者接手，必须携带完整 rollback / authorization / execution contract；
- 用户明确要求正式交接或模板 1.5。

mini handoff 不能授予权限，也不能替代 GitHub current state、KF、closure 或正式授权记录。

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

如果下一动作涉及新的实机、生产、不可逆写入或新的授权边界，先切换为正式模板 1.5，而不是在 mini handoff 中补成长篇执行合同。

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
MINI_HANDOFF_TEMPLATE_VERSION=1.1
MINI_HANDOFF_ELIGIBLE=true

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
UNARCHIVED_CRITICAL_RESULT_COUNT=0

LIVE_OR_PHYSICAL_MUTATION_PENDING=false
PRODUCTION_RECOVERY_IN_PROGRESS=false
UNCONSUMED_ONE_SHOT_AUTHORIZATION=false
ROLLBACK_STATE_AMBIGUOUS=false
CURRENT_STATE_AMBIGUOUS=false

FRESH_REBIND_REQUIRED=true
MASTER_TASK_DOCUMENT_BOUND=<true|false>
TASK_ALIGNMENT=<PASS|UNBOUND>
NEXT_ACTION_EXPLICIT=true
NEXT_TASK_CHAIN_EXPLICIT=true
STOP_BOUNDARY_EXPLICIT=true
```

任一适用字段无法满足时：

```text
MINI_HANDOFF_ELIGIBLE=false
USE_FULL_HANDOFF_TEMPLATE_V1_5=true
```

不要为了满足 mini 条件而删除、隐藏或弱化真实的 live / authorization / rollback 状态。
