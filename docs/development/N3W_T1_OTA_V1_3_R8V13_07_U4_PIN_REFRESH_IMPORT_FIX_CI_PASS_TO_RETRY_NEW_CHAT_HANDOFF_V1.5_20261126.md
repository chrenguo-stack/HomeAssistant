# N3-W T1 Core Stack OTA V1.3 — R8V13-07 U4 Pin Refresh Import Fix CI PASS → Retry Handoff V1.5

`HANDOFF_TEMPLATE_VERSION=1.5`
`HANDOFF_DATE=2026-11-26`

## 1. 任务权威与任务链

先读取 `docs/development/STAGE_EXECUTION_PLAN_STANDARD.md`。

```text
MASTER_TASK_DOCUMENT=docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md
MASTER_TASK_DOCUMENT_SHA=434224b8491b7d4521ca7489c1e5a9ffd800af8a

LONG_TERM_GOAL=完成 Home Assistant OTA V1.3 的代表性实机成功、故障恢复、完整回滚和中断续办验收
CURRENT_STAGE=N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE
CURRENT_TASK=R8V13-07
NEXT_TASK=R8V13-08
NEXT_TASK_CHAIN=R8V13-08 exact 2026.10.0 healthy predecessor baseline
→ R8V13-09 fresh transaction B: 2026.10.0 → 2026.10.4 normal success path
→ R8V13-10 dynamic-capacity insufficiency fault injection
→ R8V13-11 recovery / real-fault fault injection
→ R8V13-12 complete U13B rollback acceptance
→ R8V13-13 critical interruption / power-loss resume acceptance
→ R8V13-14 final R8 V1.3 acceptance conclusion

STAGE_EXIT_CRITERIA=事务A形成健康 exact 2026.10.0 基线；事务B fresh R8 正常路径 U13A；target/predecessor/protected-data 动态容量不足实机证据；真实故障恢复及完整 U13B；关键中断/断电续办；所有源码、CI、产物和实机证据绑定归档
OUT_OF_SCOPE=Broker OTA；多组件 Core Stack 整套验收；PR merge；release；生产发布；与当前 R8 验收无关的功能扩展

TASK_CHAIN_MUTATION_ALLOWED=false
TASK_ALIGNMENT=PASS
```

说明：master plan 的具体活动实例位于上述模板文件的“当前活动计划实例：T1 Core Stack OTA V1.3 / R8 备用 T1 代表性验收”部分；该文件不是空白模板。当前任务和后续链均按该实例继承，handoff 不修改任务顺序。

## 2. 目标与停点

- 任务／交接原因：R8V13-07 事务 A INSTALL/cutover 续办；2026-11-26 U4 Pin Refresh Attempt 01 在 Python 产品模块导入处 STOP，已完成 successor executor 修复及 CI。
- 已完成到：本地曾成功 rebind 到 PR #824 HEAD `03b2808f60b8a4df157128208269af898ce4ac7c`，并核验 Pin Refresh V2 的 Git blob 与 SHA256；随后 PR HEAD 又前进至 `b42fd47125f4641827f3ac9dd90ce6f98b476693`，该最新 HEAD 的相关 CI 已全部 SUCCESS。
- 当前状态：等待下一会话将本地仓库更新到最新 PR HEAD，并 fresh rebind T1 U4 事务状态后，才可执行修复后的 U4→U5 Pin Refresh gate。
- 当前停点：Attempt 01 在 `from n3w_t1_core_updater_ha_ipc import ...` 处抛出 `ModuleNotFoundError`；执行器尚未到 Release Pin 原子写入和 INSTALL intent 提交位置。

## 3. 代码与证据

- 仓库：`chrenguo-stack/HomeAssistant`
- PR：[#824](https://github.com/chrenguo-stack/HomeAssistant/pull/824)，OPEN / DRAFT
- 分支：`review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
- 最新 PR HEAD：`b42fd47125f4641827f3ac9dd90ce6f98b476693`
- 用户本地已核验 HEAD：`03b2808f60b8a4df157128208269af898ce4ac7c`；它早于最新 PR HEAD，下一会话必须 fetch 并 rebind 到 `b42fd47125f4641827f3ac9dd90ce6f98b476693`。
- Pin Refresh V2：
  - `tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_U4_PIN_REFRESH_AND_INSTALL_INTENT_20261126_02.py`
  - Git blob：`06db68329a36baf7f14e470e9e0a44eb62ba72f3`
  - 本地已核验 SHA256：`d432512d34e5efe9d12a7fadde9b09eb5e5ad6865355f48ea87971251d60486b`
  - 修复：先核验 live recovery pyz 的精确 SHA，再把该 pyz 路径加入 `sys.path`，然后才导入产品模块。
- Exact Install Reentry：
  - `tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_EXACT_REENTRY_INSTALL_TO_TERMINAL_20261126_01.py`
  - 最新 PR HEAD 上 Git blob：`4459fb5d67f584dba2e6c87d921ad14cc4ea9d76`
  - 已复核该执行器同样在产品 IPC 模块导入前加入经过校验的 live recovery pyz 路径。
- CI（最新 PR HEAD `b42fd471...`）：
  - T1 R8 spare preflight：[`45740740218`](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45740740218) SUCCESS；focused job SUCCESS，`199 passed`；product recovery execution paths `25 passed, 74 deselected`。
  - Public repository safety：[`45740740228`](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45740740228) SUCCESS。
  - 最新 HEAD 上其余适用 workflow runs 均为 completed / success。
- 前一修复 HEAD `03b2808f...` 的 T1 R8 spare preflight `45736877279` 与 public safety `45736877156` 也均 SUCCESS；该轮 focused tests 为 `172 passed`，product recovery paths 为 `25 passed, 74 deselected`。
- 本次本地终端输出：`LOCAL_SOURCE_REBIND=PASS`、`PIN_REFRESH_EXECUTOR=PASS`、`INSTALL_REENTRY_EXECUTOR=PASS`；只证明当时本地 HEAD `03b2808f...` 的文件身份核验通过，不代表本地已到最新 `b42fd471...`。

## 4. 必须继承的结论

### 已证实

- T1 SSH host key verification：PASS，指纹为用户终端所示 `SHA256:LmyuK0O6XX0IGPpTtBdaa/WEQgd7Msr0Swv4hubkqQE`。
- Attempt 01 错误：`ModuleNotFoundError: No module named 'n3w_t1_core_updater_ha_ipc'`。
- 按执行器源码顺序，产品模块导入发生在 Release Pin 原子更新和 INSTALL intent 子进程调用之前；Attempt 01 在导入处终止。因此本次未刷新 Release Pin、未提交 INSTALL intent、未签发 install authority、未启动 recovery worker。
- 用户输出明确：`STOP_BEFORE_INSTALL_REENTRY=true`。
- 旧执行器 `_20261126_01.py` 保留为历史执行证据；修复使用 successor `_20261126_02.py`，不得覆盖或重新执行旧版本。
- 原事务仍是唯一允许继续的事务：`86b2fb28429672f6bd27269a62549d774e50814e1e428d6a79a8de531eb0cea0`。
- 用户此前明确批准该事务的 INSTALL/cutover continuation；授权绑定该事务且不可重放。Attempt 01 在授权提交前的导入处失败，没有完成 Pin Refresh/INSTALL intent；后续仍必须以 live durable state 重新核对授权和事务状态。
- R8V13-08 只有在 R8V13-07 达到健康 `U13A_COMMITTED` exact 2026.10.0 后才能开始。

### 待确认

- T1 当前 durable transaction phase、Release Pin、INSTALL intent、install authority、worker/recovery 状态及 HA/Manager/Broker 健康状态：`UNKNOWN_FRESH`。Attempt 01 的源码顺序说明没有发生本次写入，但不替代下一轮 live fresh rebind。
- 原 U4 preflight 曾记录 Release Pin expiry `1795632226`（2026-11-26 02:43:46 Asia/Shanghai）；该时间已过，必须从 live T1 重新读取，不得沿用旧 pin 有效性判断。
- 本地 checkout 尚未跟上 PR 最新 HEAD `b42fd471...`。

### 已排除

- 本次不是 SSH host-key 不匹配。
- 本次不是 Release Pin 原子写入失败或 INSTALL intent 被拒绝；执行器尚未运行到这两步。
- 不得把 Attempt 01 标记为 OTA 成功、失败回滚或已消费 INSTALL continuation。

## 5. 执行范围与授权

- 可继续：在 Mac 本地将仓库 fetch/rebind 到精确 PR HEAD `b42fd47125f4641827f3ac9dd90ce6f98b476693`；只读核验两个执行器 blob/SHA；随后按既有事务授权执行 fresh read-only T1 rebind；只有所有 exact binding、U4、Release Pin、原 USB UUID、冻结 launch、健康状态和授权状态全部 PASS，才可运行 Pin Refresh V2 一次。
- 暂停边界：不得重放 PREPARE；不得创建第二事务；不得重新运行 `_20261126_01.py`；不得在 live rebind 前运行 V2；若任何状态不匹配，停止并保存只读证据；Pin Refresh gate 应在成功后停止于 U5，之后使用 exact Install Reentry 执行器继续产品既有恢复/安装状态机，最终只允许停在终态 U13A 或 U13B/待产品恢复。
- 明确禁止：R8V13-08；Broker OTA；host reboot；PR merge；release；生产发布；任何不在事务 A 授权范围内的清理或数据删除。
- 授权状态：用户明确授权 INSTALL/cutover，目标仅为事务 `86b2fb28429672f6bd27269a62549d774e50814e1e428d6a79a8de531eb0cea0`；不可重放。Attempt 01 因导入错误在写入前 STOP；授权是否仍满足当前 live gate，必须由下一轮 fresh rebind 核验。交接不产生新授权。

## 6. 下一步

1. 本地仓库 fresh fetch PR #824，确认 PR HEAD 仍为 `b42fd47125f4641827f3ac9dd90ce6f98b476693`；checkout 到该精确 SHA。
2. 核验 Pin Refresh V2 blob `06db68329a36baf7f14e470e9e0a44eb62ba72f3`、SHA256 `d432512d34e5efe9d12a7fadde9b09eb5e5ad6865355f48ea87971251d60486b`，以及 Install Reentry blob `4459fb5d67f584dba2e6c87d921ad14cc4ea9d76`。
3. 对 T1 执行 fresh read-only rebind：确认 exact transaction ID/file SHA/phase、Release Pin、INSTALL intent、install authority residue、live recovery pyz SHA、USB UUID/mount、冻结 launch SHA、HA/Manager/Broker 及 recovery worker 状态。
4. 若且仅若所有检查 PASS 且原事务授权仍有效，执行 Pin Refresh V2 一次；预期只原子更新 Pin expiry 并提交一次 INSTALL intent，停止在 U5。若 intent 提交失败，遵循执行器对精确旧 Pin bytes 的恢复合同，并重新只读取证，不盲目重试。
5. U5 后用 exact Install Reentry 执行器推进产品状态机；不直接调用 `--resume-pending`，不重复提交 INSTALL intent，不另发 install authority。最终核实并归档 U13A 或 U13B/自动恢复的完整结果。
6. R8V13-07 只有在健康 U13A exact 2026.10.0 后才 CLOSED_PASS；若 U13B，则先分析真实产品失败原因并在 R8V13-07 内完成修复/新鲜验收，不得跳到 R8V13-08。

完成条件：R8V13-07 达到 master plan 的 U13A 或 U13B 终态；若 U13A，exact 2026.10.0 健康并可供 R8V13-08 只读基线确认；若 U13B，系统恢复健康 exact 2026.10.4 且任务仍未通过。

失败／停点：任何 source/head、事务、授权、USB、Pin、launch 或 runtime drift；执行器 STOP；恢复状态不明；CI 非 SUCCESS。先只读取证并更新 Current State，不重放或自动推进。

## 7. 必读定位与归档

- 仓库规则：适用 `AGENTS.md`；`docs/development/N3W_PROJECT_WORKING_CONTEXT.md` 第 1、2、4、12 节。
- Stage Execution Plan 标准：`docs/development/STAGE_EXECUTION_PLAN_STANDARD.md`。
- 阶段任务权威：`docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md` 的活动计划实例（blob `434224b8491b7d4521ca7489c1e5a9ffd800af8a`）。
- Current State：`docs/development/N3W_CURRENT_STATE.md`。
- State Index：`docs/development/N3W_CURRENT_STATE_INDEX.md`。
- 当前 handoff：本文件。
- 任务资料：PR #824 Conversation 中 2026-11-26 INSTALL continuation source closure 与 U4 import failure/source repair 记录；Pin Refresh V2 和 Install Reentry V1 两个 exact executor；对应 R8 CI workflow 和测试。
- 已归档：PR #824 source repair comments；本 handoff 与 Current State/Index 更新提交。
- 未归档重要资料：无；T1 live 当前状态需下一会话 fresh read-only rebind。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动顺序：阅读本 handoff 和适用仓库指令；读取 master plan、Current State / Index；核对 PR HEAD 与本地 checkout；完成任务链对齐和 fresh source/runtime/physical evidence rebind；仅在授权和所有 live gate 均 PASS 后继续。
