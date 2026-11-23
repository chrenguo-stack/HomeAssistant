# development 目录说明

`docs/development/` 同时承担“当前研发入口”和“历史研发档案”两种职责，因此文件很多。不要把目录中所有文件都视为当前有效状态。

## 当前入口

N3-W 当前工作优先读取：

1. `N3W_CURRENT_STATE.md`
2. `N3W_CURRENT_STATE_INDEX.md`
3. `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`

仓库整理状态读取：

- `GITHUB_REPOSITORY_HYGIENE_AUDIT_20260921.md`

这些入口负责把大量日期化文档压缩成可继续工作的当前状态。

## 长任务导航框架

跨多轮对话的长任务使用以下分工：

- `STAGE_EXECUTION_PLAN_STANDARD.md`：定义任务链治理和偏航保护规则；
- `templates/STAGE_EXECUTION_PLAN_TEMPLATE.md`：创建具体阶段 master plan 的空白模板；
- 活动阶段 master plan：定义完整后续任务链，是任务顺序的唯一权威；
- `N3W_CURRENT_STATE.md`：只记录当前位于 master plan 的哪个 Task ID；
- handoff：只记录上一轮增量、停点和恢复入口，不自行改写任务链。

框架刚建立、具体任务尚未绑定时，Current State 使用 `ACTIVE_STAGE_EXECUTION_PLAN=UNBOUND`。具体长任务开始执行前，应先建立 master plan 并完成任务坐标绑定。

## 历史文件如何理解

常见文件名中的日期、PR、KF、阶段号表示某个时间点的开发证据或决策，例如：

- `N3W_KF089_...`
- `N3W_KF096_...`
- `FC4_...`
- `H3N2_Stage2D...`
- `*_NEW_CHAT_HANDOFF_*`

除非 current-state / index 明确引用，或任务明确要求复核该历史阶段，否则这些文件默认按历史证据处理，不应用来覆盖更新的 current-state、源码、CI 或实机结果。

## 新文档放置原则

- 当前状态发生变化：优先更新 current-state 和 index。
- 新的长期架构决定：写入 `docs/adr/`。
- 长期技术路线：写入 `docs/roadmap/`。
- 正式跨组件协议：写入根目录 `protocols/`。
- 验收结果或冻结证据：写入 `docs/acceptance/` 或与现有验收结构保持一致。
- 一次性过程记录确有追溯价值时才新增日期化 development 文档。

目标是让“当前状态”不依赖聊天记录，同时避免每次阶段推进都产生新的并列 authority。
