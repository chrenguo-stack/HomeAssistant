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

---

# 当前活动计划实例：T1 Core Stack OTA V1.3 / R8 备用 T1 代表性验收

> 本节是当前活动阶段的 master task-chain authority。上面的 V1.0 通用模板骨架继续保留；本节按
> `docs/development/STAGE_EXECUTION_PLAN_STANDARD.md` 建立具体任务链。
> 产品行为、容量算法、事务状态机和安全边界继续以 V1.3 architecture / source authority 为准。

## A. 计划身份

```text
PLAN_ID=N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE
PLAN_VERSION=1.0
PLAN_STATUS=ACTIVE

LONG_TERM_GOAL=完成 Home Assistant OTA V1.3 的代表性实机成功、故障恢复、完整回滚和中断续办验收
STAGE_GOAL=在备用 T1 上先建立 exact 2026.10.0 前驱基线，再完成 fresh R8 2026.10.0->2026.10.4 全路径验收

TASK_CHAIN_MUTATION_ALLOWED=false
```

- 上位路线／产品 authority：`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`
- 当前状态 authority：`docs/development/N3W_CURRENT_STATE.md`
- R8 predecessor preparation source alignment：`docs/development/N3W_T1_OTA_V1_2_R8_EXISTING_TRANSACTION_PREDECESSOR_PREPARATION_SOURCE_ALIGNMENT_20261123.md`
- 创建原因：原路线中的“fresh R8 / V1.3 transaction”需要拆成两个独立事务，避免把“建立 10.0 测试起点”和“正式 R8 10.0→10.4 代表性升级”混为同一事务。
- 适用范围：备用 T1、Home Assistant 单组件 OTA V1.3、R8 代表性实机验收。
- Broker OTA：`DEFERRED_UNTIL_HA_OTA_ACCEPTANCE_CLOSED`。

## B. 范围

### IN_SCOPE

- V1.3 exact source / CI / package 闭环及其已取得证据；
- V1.3 updater 在备用 T1 的部署与旧事务兼容接管；
- 旧维护事务安全终结及进入 fresh transaction 前的运行环境收敛；
- 事务 A：`2026.10.4 -> 2026.10.0` 前驱基线准备与完整 U0-U13 终态；
- exact、健康 `2026.10.0` 基线确认；
- 事务 B：真正的 fresh R8 `2026.10.0 -> 2026.10.4` 正常成功路径；
- target / predecessor / protected-data backup 三类动态容量不足验收；
- 真实安装、启动、业务验收和恢复类 fault injection；
- 完整 U13B rollback；
- 关键持久化边界的中断 / 断电续办；
- R8 V1.3 最终验收结论和证据归档。

### OUT_OF_SCOPE

- Broker OTA 的首次开发与验收；
- 多组件 Core Stack 整套提交验收；
- PR merge、release、生产发布；
- 与 R8 当前验收无关的功能扩展。

## C. 完整任务链

```text
TASK_CHAIN=
R8V13-01 V1.3 exact CI/package closure
→ R8V13-02 V1.3 updater 部署到备用 T1
→ R8V13-03 现有旧 U1 只读 rebind
→ R8V13-04 旧 U1 -> V1.3 动态容量 U4 兼容性验证
→ R8V13-05 结束旧维护事务并收敛 fresh transaction 前运行环境
→ R8V13-06 事务 A fresh PREPARE：2026.10.4 -> 2026.10.0 到 U4
→ R8V13-07 事务 A INSTALL/cutover：U5 -> U13A 或自动 U13B
→ R8V13-08 exact 2026.10.0 健康前驱基线确认
→ R8V13-09 事务 B fresh R8：2026.10.0 -> 2026.10.4 正常成功路径
→ R8V13-10 动态容量不足 fault injection
→ R8V13-11 恢复 / 真实故障 fault injection
→ R8V13-12 完整 U13B rollback 验收
→ R8V13-13 关键中断 / 断电续办验收
→ R8V13-14 R8 V1.3 最终验收结论

INITIAL_TASK=R8V13-01
CURRENT_TASK=R8V13-07
NEXT_TASK=R8V13-08
```

> 事务 A 和事务 B 是两个独立、fresh 的产品事务。任何 terminal transaction 都不得被复活以替代后续 fresh transaction。

## D. 任务节点

### R8V13-01 — V1.3 exact CI/package closure

```text
TASK_ID=R8V13-01
GOAL=冻结用于 R8 实机验收的 exact V1.3 source、CI 与 package authority
PRECONDITIONS=V1.3 architecture 已冻结，源码实现完成
ACTIONS=exact source review；适用测试；CI；artifact/package checksum binding
EXIT_CRITERIA=源码、CI、package 同一 authority 闭环且无未解释失败
EVIDENCE=PR #824；N3W_CURRENT_STATE.md；V1.3 source/package closure records
NEXT_TASK=R8V13-02
STOP_BOUNDARY=无 exact package 或 CI 未闭环时不得实机部署
STATUS=PASS
```

### R8V13-02 — V1.3 updater 部署到备用 T1

```text
TASK_ID=R8V13-02
GOAL=只替换/收敛 V1.3 updater 控制面，不越过当时 HA transaction 边界
PRECONDITIONS=R8V13-01 PASS；备用 T1 fresh read-only rebind；exact artifact 绑定
ACTIONS=部署 exact updater；验证 systemd/socket/timer 和运行时非漂移
EXIT_CRITERIA=updater exact；HA/Manager/Broker 保持健康；HA transaction 未被越界推进
EVIDENCE=V1.3 updater live deployment / KF-144 repair evidence
NEXT_TASK=R8V13-03
STOP_BOUNDARY=运行时或事务身份漂移立即停止
STATUS=PASS
```

### R8V13-03 — 现有旧 U1 只读 rebind

```text
TASK_ID=R8V13-03
GOAL=重新确认旧事务、USB、运行时、目标材料和授权状态
PRECONDITIONS=R8V13-02 PASS
ACTIONS=只读核对 transaction / USB UUID / image refs / service health / authority residues
EXIT_CRITERIA=旧事务真实 durable state 与 exact evidence 一致
EVIDENCE=R8 live rebind records / Current State
NEXT_TASK=R8V13-04
STOP_BOUNDARY=不得因 rebind 结果自行重建或重放事务
STATUS=PASS
```

### R8V13-04 — 旧 U1 → V1.3 动态容量 U4 兼容性验证

```text
TASK_ID=R8V13-04
GOAL=证明 pre-V1.3 / existing transaction 可被 V1.3 动态容量实现安全接管并到达 U4
PRECONDITIONS=R8V13-03 PASS；exact transaction materials 可验证
ACTIONS=兼容接管；per-operation capacity checks；U3/U4 identity/material verification
EXIT_CRITERIA=到达兼容 U4；材料 exact；未伪造历史容量事实；运行时健康
EVIDENCE=V1.3 dynamic USB capacity / schema-v2 U3->U4 live acceptance records
NEXT_TASK=R8V13-05
STOP_BOUNDARY=兼容合同不满足时不得进入 install
STATUS=PASS
```

### R8V13-05 — 结束旧维护事务并收敛 fresh transaction 前运行环境

```text
TASK_ID=R8V13-05
GOAL=终结旧维护事务，并建立后续 fresh HA transaction 所需的 monitoring / Manager self-test 健康运行环境
PRECONDITIONS=旧事务已证明无法作为正式 R8 fresh transaction 继续复用
ACTIONS=安全退休旧事务；Manager successor；candidate monitoring activation；Manager->Broker->HA self-test
EXIT_CRITERIA=旧事务 terminal；不得复用；HA 仍 exact 10.4；Manager successor healthy；monitoring self-test PASS
EVIDENCE=KF-144 through KF-147 closure；monitoring self-test SHA256；Current State
NEXT_TASK=R8V13-06
STOP_BOUNDARY=不得从 terminal 旧事务直接进入正式 R8
STATUS=PASS
```

### R8V13-06 — 事务 A fresh PREPARE：2026.10.4 → 2026.10.0 到 U4

```text
TASK_ID=R8V13-06
GOAL=创建新的普通 HA U0-U13 predecessor-preparation transaction，并只推进到 fresh U4 READY_TO_INSTALL
PRECONDITIONS=R8V13-05 PASS；当前 HA exact 10.4 healthy；candidate monitoring 已激活；exact 10.0 target authority 可用
ACTIONS=post-activation readonly proof；candidate materialization；fresh U1；fresh prepare authority；U2；U3；U4
EXIT_CRITERIA=新的 ACTIVE U4_READY_TO_INSTALL；target/predecessor exact verified+fsynced；无 install authority；10.0 image 未加载；10.4 runtime 保持健康
EVIDENCE=KF-148 through KF-151；N3W_T1_V1_3_FRESH_HA_PREPARE_RESUME_20261123_05.sh；transaction 463c8065eea5ada915074194058ee45880ddab2c94d06715c82f09fb84481969；fresh U4 receipt
NEXT_TASK=R8V13-07
STOP_BOUNDARY=STOP_BEFORE_INSTALL；本任务不授权 INSTALL/cutover
STATUS=PASS
```

### R8V13-07 — 事务 A INSTALL/cutover：U5 → U13A 或自动 U13B

```text
TASK_ID=R8V13-07
GOAL=用既有 U0-U13 状态机把备用 T1 从 10.4 安全准备为 R8 所需的 exact 10.0
PRECONDITIONS=R8V13-06 PASS；fresh install/cutover authorization 单独取得；U4 rebind exact
ACTIONS=INSTALL intent / authority；U5-U12；成功 commit U13A；失败按既有恢复链自动 U13B
EXIT_CRITERIA=成功则 U13A + healthy 10.0；失败则 U13B + healthy exact 10.4，且不得留下停机系统
EVIDENCE=transaction ledger；USB recovery materials；runtime / protected-data / monitoring evidence；PR #824 comments 7124599609 / 7125179778 / 7125215220；tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_U5_AUTHORITY_CONTINUE_AND_INSTALL_20261124_03.sh
NEXT_TASK=R8V13-08
STOP_BOUNDARY=若 U13B，则先处理事务 A 失败原因；不得把已恢复的 10.4 当作正式 R8 起点
STATUS=IN_PROGRESS
CURRENT_SUBSTATE=NEW_FRESH_TRANSACTION_A_PREPARE_PACKAGE_CI_PENDING
LAST_TRANSACTION_ID=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
LAST_TRANSACTION_STATUS=ROLLED_BACK
LAST_TRANSACTION_PHASE=U8_RECOVERY_ADMISSION_COMPLETE
LAST_TRANSACTION_FAILURE_CODE=ha_usb_release_predecessor_container_drift
LAST_TRANSACTION_REPLAY=false
RECOVERY_REQUIRED=false
PRE_CUTOVER_PREDECESSOR_RESTORED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
DESTRUCTIVE_BOUNDARY_CROSSED=false
KF153_STATUS=GUARDED
KF154_STATUS=GUARDED
LIVE_RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
NEW_FRESH_TRANSACTION_A_CREATED=false
NEW_FRESH_TRANSACTION_A_PREPARE_GATE=N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_TO_U4_20261124_01
NEW_FRESH_TRANSACTION_A_PREPARE_AUTHORIZATION=PENDING
NEW_FRESH_TRANSACTION_A_INSTALL_AUTHORIZATION=false
NEXT_ACTION=WAIT_FRESH_TRANSACTION_A_PREPARE_FOCUSED_CI_THEN_REQUEST_EXPLICIT_GATE_APPROVAL
R8V13_08_BLOCKED=true
```

### R8V13-08 — exact 2026.10.0 健康前驱基线确认

```text
TASK_ID=R8V13-08
GOAL=证明事务 A 成功后得到的 10.0 是合法、健康、可作为正式 R8 起点的前驱基线
PRECONDITIONS=R8V13-07 reached U13A
ACTIONS=只读核对 HA exact ref/portable identity；Manager/Broker peer health；HA data / monitoring / protected state；transaction terminal
EXIT_CRITERIA=healthy exact 10.0 baseline=true；事务 A terminal 且不再复用
EVIDENCE=post-U13A read-only acceptance record
NEXT_TASK=R8V13-09
STOP_BOUNDARY=10.0 基线不健康不得开始正式 R8
STATUS=NOT_STARTED
```

### R8V13-09 — 事务 B fresh R8：2026.10.0 → 2026.10.4 正常成功路径

```text
TASK_ID=R8V13-09
GOAL=从产品入口完整证明 V1.3 正常 OTA 成功路径
PRECONDITIONS=R8V13-08 PASS；fresh transaction；exact 10.4 release authority；独立实机授权
ACTIONS=PREPARE；动态容量准入；INSTALL；cutover；业务验收；durable commit
EXIT_CRITERIA=U13A_COMMITTED；HA exact 10.4 healthy；受影响功能正常；受保护数据正确；用户终态为升级成功
EVIDENCE=fresh R8 transaction ledger；runtime / HA / USB / monitoring evidence
NEXT_TASK=R8V13-10
STOP_BOUNDARY=不得用事务 A 或其他 terminal transaction 替代
STATUS=NOT_STARTED
```

### R8V13-10 — 动态容量不足 fault injection

```text
TASK_ID=R8V13-10
GOAL=证明 V1.3 不依赖固定 reserve，并在每个大文件动作前按真实 payload 与最新 free bytes fail-closed
PRECONDITIONS=R8V13-09 正常成功路径已建立基线；fault injection 方案和授权明确
ACTIONS=分别覆盖 target、predecessor export、protected-data backup；覆盖停服后内部空间不足；验证允许的同事务继续/必须 fresh PREPARE 的边界
EXIT_CRITERIA=不足空间不会越过对应写入/加载边界；已停服务自动恢复健康前代；无伪成功
EVIDENCE=capacity measurement records；transaction / runtime / USB evidence
NEXT_TASK=R8V13-11
STOP_BOUNDARY=不得通过删除用户 USB 历史数据或复活 terminal transaction 制造空间
STATUS=NOT_STARTED
```

### R8V13-11 — 恢复 / 真实故障 fault injection

```text
TASK_ID=R8V13-11
GOAL=证明真实安装、启动、业务验收与恢复故障由产品状态机处理，而非 checker 假失败主导
PRECONDITIONS=正常路径和动态容量基线已成立；每个 fault 有预定义预期结果
ACTIONS=覆盖 archive/identity drift、target load/start failure、业务验收失败、protected-data rollback、recovery-health failure
EXIT_CRITERIA=每类故障都得到预期 fail-closed 或自动恢复；恢复责任不因 status/checker 辅助异常中断
EVIDENCE=fault matrix；transaction ledger；runtime / business / data evidence
NEXT_TASK=R8V13-12
STOP_BOUNDARY=未知故障不得直接标记产品失败，先区分 product failure 与 executor/checker regression
STATUS=NOT_STARTED
```

### R8V13-12 — 完整 U13B rollback 验收

```text
TASK_ID=R8V13-12
GOAL=从已进入破坏性边界的代表性失败证明完整旧版恢复
PRECONDITIONS=R8V13-11 已选定可触发真实 rollback 的代表性故障
ACTIONS=执行失败路径；恢复 exact predecessor image；必要时恢复 protected HA data；重建业务健康；durable U13B
EXIT_CRITERIA=U13B_ROLLED_BACK；旧版 exact + healthy；数据恢复正确；用户终态为升级失败，系统已自动恢复原版本
EVIDENCE=U13B ledger；rollback image/data/runtime/business evidence
NEXT_TASK=R8V13-13
STOP_BOUNDARY=业务尚未恢复时不得把 rollback 标记完成
STATUS=NOT_STARTED
```

### R8V13-13 — 关键中断 / 断电续办验收

```text
TASK_ID=R8V13-13
GOAL=证明在关键持久化边界前后中断后可自动识别真实状态、续办或恢复且不重复破坏性动作
PRECONDITIONS=正常成功与完整 rollback 路径均已成立
ACTIONS=覆盖首次停服、旧镜像释放、恢复数据写入、服务启动、最终提交等关键边界前后中断
EXIT_CRITERIA=重启后不重放已消费授权、不重复删除/恢复；提交前可恢复，提交后尊重已持久终态
EVIDENCE=power/interruption matrix；transaction durability；post-reboot runtime evidence
NEXT_TASK=R8V13-14
STOP_BOUNDARY=任何无法唯一归类的 durable state 先只读取证，不盲目重试
STATUS=NOT_STARTED
```

### R8V13-14 — R8 V1.3 最终验收结论

```text
TASK_ID=R8V13-14
GOAL=汇总同一 V1.3 candidate 的正常成功、容量失败、真实恢复、U13B 和中断续办证据
PRECONDITIONS=R8V13-09 through R8V13-13 均满足各自 exit criteria
ACTIONS=独立复核证据；核对源码/包/live transaction binding；归档遗留项；形成发布前 R8 结论
EXIT_CRITERIA=能够明确给出 PASS 或 BLOCKED；所有关键证据可追溯；无未归档关键结果
EVIDENCE=R8 V1.3 final acceptance closure
NEXT_TASK=STAGE_CLOSED_OR_R9_PRODUCT_ACCEPTANCE
STOP_BOUNDARY=Broker OTA、merge、release、生产发布不由本计划自动授权
STATUS=NOT_STARTED
```

## E. 阶段完成条件

```text
STAGE_EXIT_CRITERIA=
- 事务 A 已建立并验证 exact healthy 2026.10.0 前驱基线
- 事务 B fresh R8 2026.10.0->2026.10.4 正常成功路径 U13A 验收通过
- target / predecessor / protected-data backup 动态容量不足均有 fail-closed 实机证据
- 代表性真实故障进入并完成 U13B 自动恢复，旧版和受保护数据健康
- 关键持久化边界中断/断电后续办与恢复验收通过
- 产品最终用户终态只有“升级成功”或“升级失败，系统已自动恢复原版本”
- 源码、CI、artifact、实机事务与归档证据相互对应
- UNARCHIVED_CRITICAL_RESULT_COUNT=0
```

只有满足上述条件后，才能把本活动计划标记为 `CLOSED` 并进入后续产品级验收。Broker OTA 仍是后续独立工作。

## F. 任务链变更记录

| Revision | Commit | Change | Reason | Current State synchronized |
|---|---|---|---|---|
| 1.0 | b7f9b90b4f2aed5d76f07a699c4416cd70c05603 | 建立 R8/V1.3 master task chain；把原单一 “fresh R8 transaction” 明确拆为事务 A 基线准备与事务 B 正式 R8 | 当前 live HA 已是 10.4，而正式 R8 起点必须是健康 exact 10.0；两个目的不能共用同一 transaction 语义 | yes |

## G. Current State / Handoff 绑定

当前坐标冻结为：

```text
MASTER_TASK_DOCUMENT=docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md
ACTIVE_STAGE_ID=N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE
CURRENT_TASK_ID=R8V13-07
NEXT_TASK_ID=R8V13-08
TASK_CHAIN_STATUS=ALIGNED
TASK_CHAIN_MUTATION_ALLOWED=false
```

当前任务 R8V13-07 正在执行 fresh physical reacceptance。fresh transaction `afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3` 已完成 fresh PREPARE 并已提交一次 INSTALL intent，当前 durable state 为 `ACTIVE / U5_INSTALL_REQUESTED_REVALIDATING`。fresh install authority 尚未签发，authorization 尚未 claim/consume，HA/Manager 尚未停服，predecessor 尚未释放，target 10.0 尚未加载。下一动作只能从现有 U5 签发新的合法 authority 并进入 product worker；不得重放 PREPARE 或 INSTALL intent。R8V13-08 继续 BLOCKED，直到 R8V13-07 达到 healthy `U13A_COMMITTED`。

