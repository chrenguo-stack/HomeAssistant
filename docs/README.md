# 文档导航

本目录同时保存长期架构、当前研发状态、验收证据和历史开发记录。它们的“新旧”和“权威级别”不同，不能只按文件日期判断当前状态。

## 当前优先入口

### N3-W / ESP-NOW

当前 N3-W 状态以以下文件为入口：

- `development/N3W_CURRENT_STATE.md`：当前状态权威摘要。
- `development/N3W_CURRENT_STATE_INDEX.md`：当前证据、阶段文档和后续入口索引。
- `development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：已知故障与回归保护。
- `development/GITHUB_REPOSITORY_HYGIENE_AUDIT_20260921.md`：仓库整理记录。

如果这些摘要与更新的 exact repository、CI、runtime 或实机证据冲突，以更新的直接证据为准，并同步修正上述入口文件。

## 目录职责

| 目录 | 主要用途 |
| --- | --- |
| `adr/` | 已接受的长期架构决策。 |
| `roadmap/` | 长期技术路线；当前后继基线见 V0.7。 |
| `architecture/` | 系统和仓库层面的架构说明。 |
| `decisions/` | 阶段进入、实现边界和专项决策记录。 |
| `development/` | 当前研发状态入口及大量阶段性开发档案。 |
| `acceptance/` | 验收结果、manifest、测试证据和归档。 |
| `status/` | 阶段状态和历史状态记录。 |
| `integration/` | 集成阶段记录；其中部分内容属于历史冻结证据。 |
| `handoffs/` | 历史正式交接文档。 |
| `handover/` | 旧的 handover 目录；不作为新文档默认落点。 |
| `process/` | 项目开发流程规范。 |
| `skills/` | 仓库内开发辅助技能。 |

跨固件、主机和网关的正式协议放在仓库根目录的 `protocols/`，不要以 `docs/development/` 中的历史说明替代正式协议。

## 使用原则

1. 查“现在做到哪一步”，先看 current-state / index，而不是遍历所有日期文件。
2. 查“为什么这样设计”，优先看 ADR、roadmap 和正式 protocol。
3. 查“某次测试到底发生了什么”，再进入 acceptance、status、integration 或 development 中的对应历史记录。
4. 历史 handoff、阶段文档和旧 CI 记录保留用于追溯，不自动成为当前执行 authority。
5. 新增长期有效规则时，应进入 ADR、roadmap、protocol 或 process；不要仅埋在一次性开发记录里。
