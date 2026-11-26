# N3-W R8V13-06 → R8V13-07 mini handoff

`MINI_HANDOFF_TEMPLATE_VERSION=1.1`

> 模板 authority：`docs/development/templates/mini-handoff-template.md`，参考 blob `14c7ee3c6c89f4e72dad0c35e3a466835138b9ea`。
> 用户明确要求本次使用 mini handoff，不使用 V1.5。
> 按 mini 模板自身 eligibility 规则，下一任务包含新的 T1 INSTALL/cutover 写入边界，因此本 handoff **不满足自动执行型 mini eligibility**；它仅用于恢复现场、fresh rebind 和进入 R8V13-07 的只读前置，不授予任何 INSTALL/cutover 权限。

## 1. 当前任务与停点

- 当前任务：`R8V13-07` — 事务 A INSTALL/cutover：U5 → U13A 或自动 U13B。
- 已完成到：`R8V13-06=PASS`；fresh transaction 已到 `ACTIVE / U4_READY_TO_INSTALL`。
- 当前状态：可继续做只读 U4 fresh rebind；INSTALL/cutover 尚未授权。
- 当前停点：保持 HA 2026.10.4 健康运行，停在 fresh U4，等待新会话 fresh rebind 后单独取得 R8V13-07 INSTALL/cutover 授权。

关键 durable state：

```text
TRANSACTION_ID_SHA256=463c8065eea5ada915074194058ee45880ddab2c94d06715c82f09fb84481969
TRANSACTION_STATUS=ACTIVE
TRANSACTION_PHASE=U4_READY_TO_INSTALL
TRANSACTION_FILE_SHA256=9b7f506869113e0505efbec09e4354ff0670e13126119ab98d90c7d12bdee60d

TARGET_IMAGE_REF=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_ARCHIVE_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
TARGET_VERIFIED=true
TARGET_FSYNCED=true
TARGET_10_0_DOCKER_IMAGE_LOADED=false

PREDECESSOR_IMAGE_REF=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR_ARCHIVE_SHA256=6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f
PREDECESSOR_VERIFIED=true
PREDECESSOR_FSYNCED=true

INSTALL_AUTHORITY_PRESENT=false
INSTALL_INTENT_EXECUTED=false
HA_INSTALL_OR_CUTOVER_EXECUTED=false
BROKER_OTA_EXECUTED=false
REBOOT_EXECUTED=false

REMOTE_STAGING_CLEANUP=PASS
REMOTE_STAGING_PRESENT=false
```

Live runtime at handoff：

```text
HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
MANAGER=local/greenhouse-manager:fresh-1cae18039eee
MANAGER_IMAGE_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
BROKER=local/n3w-mosquitto:2.1.2-3184566d
BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
LIVE_COMPOSE_SHA256=6cd522b55136beceb8661820896351238d2218c23c3b3e71e98a7521ac67f0f4
MONITORING_SELF_TEST_SHA256=3475946a971db38230d0f803ebc0da73c004d12019502a2f348e9b4657e8d5c6
```

## 2. GitHub 续接入口

- 仓库：`chrenguo-stack/HomeAssistant`
- PR：`#824`（OPEN / DRAFT）
- 分支：`review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
- 当前 docs-aligned head（本 handoff 创建前）：`dca66f2418b14618ab818261db234c49591fb80a`
- Executable source authority：`1fbe674e25edb4c6fb1a3740042778adc55def68`
- Master Task Document：`docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md`
- Master Task Document SHA：`acc4e2c2fce5b68b24cc2b993662a72faffc25ee`
- Current Stage：`N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE`
- Current Task：`R8V13-07`
- Current State：`docs/development/N3W_CURRENT_STATE.md`
- State Index：`docs/development/N3W_CURRENT_STATE_INDEX.md`
- Architecture：`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`
- R8 predecessor preparation source alignment：`docs/development/N3W_T1_OTA_V1_2_R8_EXISTING_TRANSACTION_PREDECESSOR_PREPARATION_SOURCE_ALIGNMENT_20261123.md`
- Regression authority：`docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`，重点 KF-144～KF-151。
- R8V13-06 evidence：Resume 05 fresh U4 closure；PR #824 comments `7117413668`、`7117632888`。

Next Task Chain：

```text
R8V13-07 事务 A INSTALL/cutover：U5 -> U13A 或自动 U13B
→ R8V13-08 exact 2026.10.0 健康前驱基线确认
→ R8V13-09 事务 B fresh R8：2026.10.0 -> 2026.10.4 正常成功路径
→ R8V13-10 动态容量不足 fault injection
→ R8V13-11 恢复 / 真实故障 fault injection
→ R8V13-12 完整 U13B rollback 验收
→ R8V13-13 关键中断 / 断电续办验收
→ R8V13-14 R8 V1.3 最终验收结论
```

新会话不得仅凭本 handoff 假定上述状态仍成立；执行前必须对 repository / PR / branch / task coordinate 和 U4 live durable state 做 fresh rebind。

## 3. 下一步

- 下一动作：进入 `R8V13-07`，先做 **read-only U4 fresh rebind**；确认 transaction、USB materials、runtime、install-authority absence 与 GitHub task coordinate 全部一致。
- 允许范围：仓库/GitHub fresh rebind、源码/设计复核、T1 只读 U4 preflight、生成待授权执行方案。
- 暂停边界：**STOP_BEFORE_INSTALL_AUTHORIZATION**。没有新的明确授权时，不得提交 INSTALL intent、不得签发 install authority、不得进入 U5+、不得停 HA/Manager、不得加载 10.0 target、不得回滚/重启、不得执行 Broker OTA、不得 merge/release。
- 需要用户操作：当只读 U4 rebind 通过并给出 exact R8V13-07 execution contract 后，由用户单独明确批准 INSTALL/cutover 授权。

R8V13-07 成功/失败终态合同：

```text
SUCCESS => U13A_COMMITTED + healthy exact Home Assistant 2026.10.0
FAILURE => automatic U13B_ROLLED_BACK + healthy exact Home Assistant 2026.10.4
```

Broker OTA 继续保持 `DEFERRED_UNTIL_HA_OTA_ACCEPTANCE_CLOSED`。

## 4. 新会话启动语

```text
继续 N3-W 当前任务，进入 R8V13-07。

先读取：
- docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_T1_OTA_V1_3_R8V13_06_TO_R8V13_07_MINI_HANDOFF_20261124.md
- docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md
- docs/development/N3W_T1_OTA_V1_2_R8_EXISTING_TRANSACTION_PREDECESSOR_PREPARATION_SOURCE_ALIGNMENT_20261123.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

fresh rebind：
- repository main
- PR #824
- branch review/t1-ota-r8-existing-tx-predecessor-prep-20261123
- current PR head
- executable source authority 1fbe674e25edb4c6fb1a3740042778adc55def68
- master task coordinate R8V13-07 -> R8V13-08
- live transaction 463c8065eea5ada915074194058ee45880ddab2c94d06715c82f09fb84481969
- U4 durable state / transaction SHA / USB exact target+predecessor materials
- HA/Manager/Broker exact runtime
- install authority must remain absent

当前停点：
R8V13-06 已 PASS；fresh transaction ACTIVE / U4_READY_TO_INSTALL；10.0 target 与 10.4 predecessor 已 verified+fsynced；10.0 image 未加载；INSTALL authority/intent/cutover 均未发生；remote staging 已清理。

当前任务：
R8V13-07

下一任务链：
R8V13-07 -> R8V13-08 -> R8V13-09 -> R8V13-10 -> R8V13-11 -> R8V13-12 -> R8V13-13 -> R8V13-14

先完成只读 U4 fresh rebind 和 execution-contract 复核。现有 PREPARE-only authorization 已完成其范围，不能用于 INSTALL/cutover。没有新的明确授权时必须 STOP_BEFORE_INSTALL_AUTHORIZATION。

按现有授权边界继续；如发现 source、runtime、authorization 或 evidence drift，停止受影响操作并重新判定。
```

## 5. mini handoff 完整性检查

```text
MINI_HANDOFF_TEMPLATE_VERSION=1.1
MINI_HANDOFF_ELIGIBLE=false
USER_EXPLICIT_TEMPLATE_REQUEST=MINI_HANDOFF_NO_V1_5
HANDOFF_ROLE=NAVIGATION_AND_FRESH_REBIND_ONLY

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
UNARCHIVED_CRITICAL_RESULT_COUNT=0

GITHUB_STATE_ALIGNED=true
LIVE_OR_PHYSICAL_MUTATION_PENDING=true
PRODUCTION_RECOVERY_IN_PROGRESS=false
UNCONSUMED_ONE_SHOT_AUTHORIZATION=false
ROLLBACK_STATE_AMBIGUOUS=false
CURRENT_STATE_AMBIGUOUS=false

FRESH_REBIND_REQUIRED=true
MASTER_TASK_DOCUMENT_BOUND=true
TASK_ALIGNMENT=PASS
NEXT_ACTION_EXPLICIT=true
NEXT_TASK_CHAIN_EXPLICIT=true
STOP_BOUNDARY_EXPLICIT=true

V1_5_USED=false
NEW_INSTALL_AUTHORIZATION_GRANTED=false
```

本文件不授予权限，也不能替代 GitHub Current State、master Stage Execution Plan、KF/closure 或后续单独的 R8V13-07 INSTALL/cutover 授权。
