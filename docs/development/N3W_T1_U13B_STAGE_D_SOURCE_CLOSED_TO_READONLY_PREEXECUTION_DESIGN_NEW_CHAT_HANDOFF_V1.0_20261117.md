# N3-W U13B Stage D Source CLOSED_PASS → Read-only Preexecution Design 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：完成 U13B Stage D D4 automatic reconciliation orchestration 的 exact-head CI 与独立源码复核，正式关闭 Stage D 源码层；用户要求本轮停止后续开发并切换到新对话。
- 已完成到：Stage A/B/C 均 CLOSED_PASS；Stage D D1/D2/D3/D4 均 CLOSED_PASS；最终 Stage D 产品源码 head 为 `a47fc818eaea84a7357d158e2c4f92b2367d8d44`，16/16 CI SUCCESS，最终独立源码复核 PASS。
- 当前状态：可继续，但本轮按用户要求停止。新对话先 fresh rebind，再进入 read-only preexecution design；不得把本交接视为 T1/live 授权。

## 2. 代码与证据

- 仓库／分支／PR：
  - Repository: https://github.com/chrenguo-stack/HomeAssistant
  - Branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR #807: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR 状态：OPEN / DRAFT / UNMERGED / MERGEABLE
- 核对时 main／本任务源码：
  - `MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - `PR_BASE_HEAD=ab277001dc9b31dcccb4d36b1507cec5f26d5a1d`
  - `STAGE_D_SOURCE_HEAD=a47fc818eaea84a7357d158e2c4f92b2367d8d44`
- 证据入口：
  - Stage D final closure: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6941289833
  - D3 final closure: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6941109932
  - D4 pre-final checkpoint: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6941152138
  - D3 design: `docs/development/N3W_T1_U13B_STAGE_D_D3_HOST_ONLY_RECONCILIATION_WRITER_SOURCE_DESIGN_20261117.md`
  - D4 design: `docs/development/N3W_T1_U13B_STAGE_D_D4_AUTOMATIC_RECONCILIATION_ORCHESTRATION_20261117.md`
  - Overall U13B design: `docs/development/N3W_T1_U13B_AUTOMATIC_ROLLBACK_SOURCE_DESIGN_V1_20261117.md`
  - Core Stack current authority CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44035165912
  - Manager A-to-B CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44035165928
  - HA target-binding CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44035165909
  - Exact-head CI total: `16_OF_16_SUCCESS`

## 3. 必须继承的结论

- 已证实：
  - `STAGE_A_CLOSED_PASS=true / STAGE_B_CLOSED_PASS=true / STAGE_C_CLOSED_PASS=true`。
  - `STAGE_D_D1_CLOSED_PASS=true / D2=true / D3=true / D4=true / STAGE_D_SOURCE_CLOSED=true`。
  - D1 保证 USB phase commit marker 前已有 exact public-safe `host-transaction.json`。
  - D2 对每条合法 USB-one-phase-ahead rollback edge 使用真实后置条件只读验证；observer 结果必须字面量为 `True`。
  - D3 使用共享 transaction lock，在锁内重新读取 Host/USB、重新分类、重新观察；只将 USB exact mirror 写回 Host，写后 readback 并要求 `HOST_USB_EXACT`。reconciliation 期间不写 USB metadata、不重放 rollback operation。
  - D3 专用 USB resolver 对未挂载 ext4 使用 `ro,noload,nodev,nosuid,noexec`；已有 RW mount fail-closed；临时 RO reconciliation mount 在退出时释放。
  - 正常 U13B rollback controller 已与 D3 共用 transaction lock。
  - D4 顺序固定为 `D3 reconcile -> 释放 D3 RO mount/lock -> normal rollback controller 重新加锁并重新验证`，不增加外层 nested lock。
  - D4 writer/controller 必须共享同一个 transaction-store 实例和同一个 backend 实例；装配不一致直接 STOP。
  - 最终 source head `a47fc818...` 的 16 条 CI 全部 SUCCESS，最终独立源码复核无新 runtime blocker。
- 待确认：
  - Stage D 尚未做新的 real-T1 U13B read-only preexecution 或 live rollback 验收。
  - `NEXT_CHAT_LIVE_RUNTIME=UNKNOWN_FRESH`；最后有证据支持的 live transaction 是历史 `U13A_COMMITTED`，不能把历史健康状态当作新对话的 fresh runtime。
  - 下一阶段具体 read-only preexecution package / executor / physical acceptance contract 尚未设计。
- 已排除：
  - USB ahead 时直接 blind replay rollback operation。
  - 仅凭 USB phase 重建 successor。
  - D3 使用普通 RW ext4 mount 作为“只读”证据。
  - D3 写 Host 后不读回验证。
  - D3 与 normal rollback 并发使用不同锁。
  - D4 使用不同 store/backend 的错误装配。
  - D4 在 reconciliation 与 normal rollback 外再套不可重入的 transaction lock。

## 4. 执行范围与授权

- 可继续：
  - fresh repository/main/PR/source rebind；
  - 读取本交接、current-state、known failures 和 Stage D 设计；
  - 在现有源码范围内进行 read-only preexecution 的设计、源码复核、模拟测试与 GitHub 归档；
  - 若同一 source-only gate 内发现局部、明确、无设计歧义的小问题，可按项目规则直接修复并验证。
- 暂停边界：
  - `T1_ACCESS=false`
  - `T1_MUTATION=false`
  - `U13B_LIVE_EXECUTION_AUTHORIZED=false`
  - `BOARD_ACCESS=false`
  - `MERGE=false`
  - 不得执行 real-T1 U13B rollback、服务/镜像/USB 内容变更、生产事务迁移或 PR #807 merge，除非后续有新的明确授权／阶段合同。
- 授权状态：当前 U13B live 授权为“无”。历史 U13A 一次性授权已经 claim/consume，且不可复用；本交接不授予任何新权限。

## 5. 下一步

- 行动：
  1. fresh rebind `main`、PR #807、branch head 和 `STAGE_D_SOURCE_HEAD=a47fc818...`；
  2. 确认本 handoff docs-only advance 没有产生产品源码漂移；
  3. 读取 Stage D final closure 与 D3/D4 design；
  4. 继续 `NEXT_ONE_GATE=U13B_STAGE_D_SOURCE_CLOSURE_AND_READONLY_PREEXECUTION_DESIGN` 的剩余部分——Stage D source closure 已满足，只进行 read-only preexecution design，不直接进入 T1/live execution；
  5. 将后续设计、测试和 review 证据继续归档到 PR #807 / current-state。
- 完成条件：形成明确的 U13B read-only preexecution contract，覆盖 fresh state binding、Host/USB split 分类、恢复资产和真实后置条件观察、零生产 mutation 证明、结构化 PASS/STOP 输出，以及进入 future live gate 所需的独立授权边界；源码/测试/CI/复核结果均固定到 GitHub exact head。
- 失败／停点：fresh rebind 出现源码 drift、设计发现 false-PASS/权限扩大、或需要 T1/live/merge 时停止受影响动作；局部明确 source-only 缺陷可在同一 gate 修复。不要使用本交接跨越 live authorization。

## 6. 必读定位与归档

- 仓库规则：
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`
  - 最小新会话读取规则：`docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
  - Handoff 模板 authority：`docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`，版本 1.4
- 任务资料：
  - 本交接：`docs/development/N3W_T1_U13B_STAGE_D_SOURCE_CLOSED_TO_READONLY_PREEXECUTION_DESIGN_NEW_CHAT_HANDOFF_V1.0_20261117.md`
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
  - `docs/development/N3W_T1_U13B_AUTOMATIC_ROLLBACK_SOURCE_DESIGN_V1_20261117.md`
  - `docs/development/N3W_T1_U13B_STAGE_D_D3_HOST_ONLY_RECONCILIATION_WRITER_SOURCE_DESIGN_20261117.md`
  - `docs/development/N3W_T1_U13B_STAGE_D_D4_AUTOMATIC_RECONCILIATION_ORCHESTRATION_20261117.md`
- 已归档：
  - Stage D final closure PR comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6941289833
  - D3 final closure PR comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6941109932
  - D4 checkpoint PR comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6941152138
  - Stage D source commits、tests、design docs 均已在 PR #807 branch。
- 未归档重要资料：无。本轮没有产生新的 private T1/board runtime evidence。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复 U13B。先 fresh rebind main、PR #807、branch head 与 Stage D source authority，确认 docs-only handoff advance 未造成产品源码漂移；Stage D source closure 已完成，从 read-only preexecution design 开始继续。不得执行 T1/live rollback、board 操作或 merge，除非后续获得新的明确授权。
