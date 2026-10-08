# N3-W PR #522 — CI 队列收敛第 1 阶段：只读分类与 PR 旧版本测试替换（2026-10-08）

## 范围与当前结论

```text
TASK=N3W_PR522_GITHUB_ACTIONS_CI_QUEUE_CONVERGENCE_PHASE1_20261008_01
EVIDENCE_MODEL=GITHUB_LIVE_READONLY
IMPLEMENTATION=INDEPENDENT_DRAFT_PR
PR_522_HEAD_AT_START=2b236d2a2e58d907c906abbadbe5910162b251b8
PR_522_BASE_BRANCH=fix/n3w-production-relay-discovery-full-channel-fallback-v1-source-repair-20260924
PR_522_BASE_SHA_AT_START=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
UPSTREAM_BRANCH_PR=474
PR_522_STATE=OPEN_DRAFT_UNMERGED

IN_SCOPE=NON_ARTIFACT_PR_ONLY_SUPERSESSION_FOR_TWO_N3W_CONTRACT_WORKFLOWS
FIRMWARE_OR_MANAGER_SOURCE_MODIFIED=false
T1_ACCESS=false
BOARD_ACCESS=false
SETUP_SECRET_IMPORT=false
RERUN_CI=false
PR_522_MODIFIED=false
AUTOMATIC_MERGE=false
STOP=true
```

## 排队原因取证

独立检查 GitHub Actions 实时 API：曾观察到仓库 `277 queued / 19 in_progress`，后来观察到 `179 queued / 21 in_progress`，说明队列正在推进，并非所有 Runner 停机。最新 PR #522 提交曾同时关联 28 条排队 CI；包括版本不再最新的旧提交，部分很长的 ESP32-C6 CI 正执行代码测试或固件编译。

PR #522 相对其上游分支累计改动 140 个文件（包含固件代码及工作流）。GitHub 对 `pull_request` 的路径过滤基于整条 PR 的变化集合，新提交可反复触发多条与本次增量无关的全量测试。旧版本测试与新版本测试并行积压，工作流未启用 PR-specific `concurrency` 是当前可控制的队列放大因素；账户配额或 GitHub 调度器的具体原因尚未通过管理接口得到验证，不作确定性结论。

部分运行中的 CI 属于固件完整编译，仍需保留最新有效提交、精确固件构建与 P3/P4 物理验收的独立证据。不能按名称或时间无差别批量取消。

## 独立最小变更

本次在 PR #522 **直接上游分支** 的独立新分支提交，仅改变以下两条流程的调度行为：

- `.github/workflows/n3w-production-multi-relay-gateway-selection-v1-ci.yml`
- `.github/workflows/n3w-production-relay-discovery-full-channel-fallback-v1-ci.yml`

插入相同的工作流级控制：

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

逐项含义：
- `pull_request`：同一个工作流、同一个 PR 编号形成同一组，新版本取代旧版本；不跨 PR 取消。
- `push`：没有 PR 编号，使用唯一运行号形成组，`cancel-in-progress=false`；不因本规则取消其他 `push`。
- 只修改 CI 排队策略，不删除测试步骤、不更改编译参数、不更改固件、不删除制品。
- 两个工作流本身不承担本次 P3/P4 首次配对 exact-source 固件发布任务。

## 不能混淆的限制

1. 新规则尚未合入 PR #522 的**上游分支**，不会自动取消已经排队的旧任务，也不应宣称当前队列已清空。
2. 本阶段**只处理两条流程**。PR #522 自身引入或修改的四条工作流仍沿用原来的调度定义；其中 R3 专项 CI 在 PR #522 内引入，必须在后续单独的设计/审批范围中处理。
3. 正在排队的老任务若需立即取消，需要按具体 run ID、PR、head SHA、工作流名称、状态及制品用途做二次检查；当前 GitHub 连接的工具集只提供 GitHub Actions 只读查询与定向重跑，没有取消工作流的动作接口。因此，本轮不声称已经取消任何旧运行。
4. 后续将该独立小 PR 合入其上游分支会改变 PR #522 的基础引用，可能产生新一轮 CI。应选择队列较空时操作，并在合并前复核上游分支仍为正确 HEAD；**不得自动合并**。
5. 如需推广到公共安全、Manager、RC2 固件或 exact artifact 工作流，必须先明确这些证据是否需要保留全部执行，不能复制粘贴取消策略。

## 下一 STOP

```text
PHASE1_SOURCE_PR_STATUS=DRAFT_REVIEW_REQUIRED
OLD_RUNS_CANCELLED_BY_ASSISTANT=false
CI_GATE_RESULT=NOT_YET_VERIFIED
PR_522_UNCHANGED=true

NEXT_ONE_GATE=N3W_PR522_CI_QUEUE_CONVERGENCE_PHASE1_DRAFT_REVIEW_AND_NON_ARTIFACT_STALE_RUN_CLASSIFICATION_20261008_01
STOP=true
```
