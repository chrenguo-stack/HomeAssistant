# N3-W 新会话交接模板 V1.5

`HANDOFF_TEMPLATE_VERSION=1.5`

本模板用于**正式／复杂／高风险新会话交接**。V1.4 及更早版本和已生成的旧交接保留作历史记录。历史提交可继续提供其适用的流程或执行依据。

V1.5 新增“任务权威与任务链”绑定：交接文档只负责恢复现场，不再承担长期任务规划。活动阶段已有 master Stage Execution Plan 时，必须引用它并记录当前 Task ID、下一 Task ID 和后续任务链。任务链如需改变，应先修改 master plan，再同步 Current State 和 handoff。

跨对话续接默认优先选择能清晰承载当前信息量的模板。[`mini-handoff-template.md`](mini-handoff-template.md) V1.2 可以用于普通任务，也可以用于实机、生产、回滚、断电、复杂一次性授权或关键状态不确定等场景，但这些场景必须按 mini 模板补齐对应的授权、基线、回滚/恢复和 exact authority 信息。只有当用户明确要求正式交接，或补充信息已经使 mini handoff 明显失去简洁性时，再使用本 V1.5 模板。

填写下方七部分。只保留本次增量，省略不适用的字段；涉及实机、生产或发布时补齐文末相应信息。

## 1. 任务权威与任务链

先读取 [`STAGE_EXECUTION_PLAN_STANDARD.md`](../STAGE_EXECUTION_PLAN_STANDARD.md)。

```text
MASTER_TASK_DOCUMENT=<阶段 master plan 路径；尚未建立写 UNBOUND>
MASTER_TASK_DOCUMENT_SHA=<blob/full commit SHA；未绑定写 UNBOUND>

LONG_TERM_GOAL=<长期目标>
CURRENT_STAGE=<阶段 ID/名称>
CURRENT_TASK=<稳定 Task ID；未绑定写 UNBOUND>
NEXT_TASK=<稳定 Task ID；未绑定写 UNBOUND>
NEXT_TASK_CHAIN=<从 NEXT_TASK 开始的后续任务链；必须保留链条，不只写一步>

STAGE_EXIT_CRITERIA=<阶段完成条件摘要或 master plan 对应章节>
OUT_OF_SCOPE=<当前阶段明确不做的事项>

TASK_CHAIN_MUTATION_ALLOWED=false
TASK_ALIGNMENT=<PASS|FAIL|UNBOUND>
```

规则：

- master Stage Execution Plan 是阶段任务链的唯一权威；
- `N3W_CURRENT_STATE.md` 只记录当前位置，不得自行改写任务链；
- 本 handoff 只记录上一轮增量、停点和恢复入口，不得自行创造新的阶段任务；
- 局部修复可以在同一 Task ID 内推进；若需要新增/删除/重排独立任务节点或扩大阶段范围，先修改 master plan 并形成 Git 记录；
- 如果 master plan、Current State 和 handoff 不一致，标记 `TASK_ALIGNMENT=FAIL`，先重新定位，不沿着 handoff 临时描述继续扩展任务；
- `UNBOUND` 只允许用于“框架已建立但具体阶段任务链尚未填写”的过渡状态。

## 2. 目标与停点

- 任务／交接原因：<当前 Task 的目标、完成条件和本次切换原因>
- 已完成到：<最后有证据支持的步骤>
- 当前状态：<可继续／等 CI／等用户／阻塞／已完成；说明原因>
- 当前停点：<从 master task chain 的哪个位置继续>

## 3. 代码与证据

- 仓库／分支／PR：<适用链接>
- 核对时 main／本任务源码：<适用的完整 SHA；相同时只写一次>
- 证据入口：<固定提交的文件、CI run 或证据链接>

按需要区分仓库主线、候选源码、产物来源和实际部署版本。

## 4. 必须继承的结论

- 已证实：<结论＋证据；区分源码、本地测试、CI 和实机结果>
- 待确认：<未知状态或推断＋最小核对方法>
- 已排除：<会影响下一步的失败路线及原因，适用时填写>

## 5. 执行范围与授权

- 可继续：<已授权操作与范围>
- 暂停边界：<需要用户操作或决定的位置，明确禁止项和本任务的临时例外>
- 授权状态：<来源、目标、候选、有效条件和当前状态；无则写“无”>

交接本身不授予新权限。适用的一次性授权须标明是否已认领、消费或被替代。

## 6. 下一步

- 行动：<先完成任务对齐检查，再执行 master plan 中的 NEXT_TASK；必要时给执行入口>
- 完成条件：<当前 Task / NEXT_TASK 的适用检查、验收结果和证据保存位置>
- 失败／停点：<失败后的处理、暂停条件和恢复入口>

新会话开始执行前至少核对：

```text
MASTER_PLAN_FOUND=<true|false|UNBOUND>
CURRENT_TASK_EXISTS_IN_PLAN=<true|false|UNBOUND>
NEXT_TASK_MATCHES_PLAN=<true|false|UNBOUND>
HANDOFF_MATCHES_CURRENT_STATE=<true|false|UNBOUND>
TASK_ALIGNMENT=<PASS|FAIL|UNBOUND>
```

授权范围内的开发、测试、复核和归档可连续推进。已固定的阶段边界及其执行合同继续适用。

## 7. 必读定位与归档

- 仓库规则：<适用 AGENTS.md，以及[工作上下文的读取规则](../N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)>
- 阶段任务权威：<MASTER_TASK_DOCUMENT；UNBOUND 时说明何时建立>
- Current State：<通常为 docs/development/N3W_CURRENT_STATE.md>
- State Index：<通常为 docs/development/N3W_CURRENT_STATE_INDEX.md>
- 任务资料：<路径＋章节／KF 条目＋用途，注明按需补读条件>
- 已归档：<GitHub 固定链接>
- 未归档重要资料：<无，或原因及可恢复位置／摘要>

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=<n>
TEAM_SHARE_COMPLETENESS=<PASS|FAIL>
```

归档审计按[归档规则](../development-artifact-archive-rules.md)执行，交接只引用结果和未解决项。

新会话启动顺序：

1. 阅读本交接和适用仓库指令；
2. 若 `MASTER_TASK_DOCUMENT != UNBOUND`，读取 master Stage Execution Plan；
3. 读取 Current State / State Index；
4. 完成任务链对齐检查；
5. 按当前 Task 真正依赖的 source / CI / runtime / physical evidence 做 fresh rebind；
6. 仅在 `TASK_ALIGNMENT=PASS` 或明确的 `UNBOUND` 框架搭建任务内继续。

### 按需补充到对应部分

| 涉及事项 | 应补信息 |
|---|---|
| CI 等待／复核 | PR、完整 head SHA、run 直链、适用检查状态、剩余复核、已查询次数 |
| 构建或发布 | 产物 ID、摘要、源码／配置／工具链绑定、必要清单；发布与运行证据分列 |
| T1／板卡只读 | 目标脱敏身份、访问范围、证据时间、需要复查的基线；未核对标 `UNKNOWN_FRESH` |
| T1／板卡／服务写入或恢复 | 目标与候选精确绑定、授权状态、写前基线、回滚入口与摘要、可否重启或重试、写后验证。失败时记录最后成功步骤、实际变更和恢复状态 |
| 同一 boot 的实机试验 | boot 绑定、供电及位置、操作对象和禁止改变的试验条件 |
| 生产版本判断 | 分开列实际接受的生产组成、组件回滚基线和不可变 Stack release，按任务取用 |

执行前实际核对所引用执行包。目标、授权、来源或证据漂移时暂停受影响操作。已消费、过期或被替代的一次性授权不可重用。公开交接只使用脱敏证据，私有地址、凭据和原始设备身份保存在私有上下文。
