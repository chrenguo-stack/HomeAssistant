# N3-W 阶段执行计划模板

`STAGE_EXECUTION_PLAN_TEMPLATE_VERSION=1.0`

本模板用于记录跨多轮开发、CI、实机验收和恢复测试的阶段任务路线。它不是一次性执行授权，也不替代具体阶段的 preflight、执行包、授权记录或新会话交接。

适用原则：

- 长期路线只在上位设计发生变化时调整；
- 阶段完成必须有对应源码、CI、实机或归档证据；
- “源码完成”“CI 通过”“实机通过”“事务提交”“回滚完成”必须分开记录；
- 已终结事务不得为了后续测试而复活，后续测试需要 fresh transaction 时必须重新创建；
- 实机写入、安装、切换、断电、恢复、合并和发布继续遵守各自授权边界；
- Broker OTA 在 Home Assistant OTA 完整验收结束前保持独立延期，不插入 HA R8 主链。

---

## 1. 计划标识

```text
PLAN_NAME=<项目 / 子系统 / 阶段>
PLAN_VERSION=<版本>
PLAN_STATUS=<DRAFT|ACTIVE|BLOCKED|CLOSED>
PRODUCT_ARCHITECTURE=<上位设计文档>
CURRENT_STATE=<当前状态文档>
CURRENT_STAGE=<当前阶段>
CURRENT_STOP_POINT=<当前停点>
```

---

## 2. 总体阶段路线

按“每个箭头都必须有明确完成条件”的方式记录。

```text
<阶段 1>
        ↓
<阶段 2>
        ↓
<阶段 3>
        ↓
...
        ↓
<最终验收>
```

如果后续测试需要先制造特定版本基线，必须把“基线准备事务”和“正式产品验收事务”拆开写，禁止用一个模糊的 “fresh transaction” 同时表示两件事。

---

## 3. 当前冻结路线：T1 Core Stack OTA V1.3 / R8

### 3.1 上位目标

```text
PLAN_NAME=N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE
PLAN_VERSION=1.0
PLAN_STATUS=ACTIVE
PRODUCT_ARCHITECTURE=docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md
CURRENT_STATE=docs/development/N3W_CURRENT_STATE.md
BROKER_OTA_DEFERRED=true
```

R8 的正式代表性 OTA 方向保持：

```text
2026.10.0 -> 2026.10.4
```

当前备用 T1 已运行在健康的 2026.10.4，因此在真正重跑 R8 前，必须先通过独立的普通 U0-U13 事务建立健康、精确的 2026.10.0 前驱基线。

### 3.2 调整后的完整路线

```text
V1.3 exact CI/package closure
        ↓
V1.3 updater 部署到备用 T1
        ↓
现有旧 U1 只读 rebind
        ↓
兼容性验证：旧 U1 -> V1.3 动态容量 U4
        ↓
结束旧维护事务
        ↓
事务 A：前驱基线准备
fresh 2026.10.4 -> 2026.10.0
U1 -> ... -> U13A
        ↓
确认健康、精确的 2026.10.0 基线
        ↓
事务 B：真正的 fresh R8 / V1.3 transaction
2026.10.0 -> 2026.10.4
        ↓
正常成功路径
U1 -> ... -> U13A COMMITTED
        ↓
动态容量不足 fault injection
        ↓
恢复 / 真实故障 fault injection
        ↓
完整回滚路径
U1 -> ... -> U13B ROLLED_BACK
        ↓
关键边界中断 / 断电续办验证
        ↓
R8 V1.3 最终验收结论
```

### 3.3 两个 fresh transaction 的职责必须分离

#### 事务 A：前驱基线准备

目的：

- 当前运行版本：`2026.10.4`；
- 目标版本：`2026.10.0`；
- 通过现有 HA U0-U13 状态机建立正式 R8 所需的健康测试起点；
- 不复活旧事务，不创建平行恢复状态机。

成功终态：

```text
U13A_COMMITTED
LIVE_HA=2026.10.0
HEALTHY_BASELINE=true
```

失败终态：

```text
U13B_ROLLED_BACK
LIVE_HA=2026.10.4
HEALTHY_PREDECESSOR_RESTORED=true
```

事务 A 完成之前，不得把后续动作描述为“正式 R8 正常升级”。

#### 事务 B：正式 R8 / V1.3 代表性事务

目的：

- 起点必须是事务 A 已验收的健康 `2026.10.0`；
- 正式验证产品 OTA `2026.10.0 -> 2026.10.4`；
- 覆盖成功、容量不足、恢复、回滚和关键中断续办。

成功终态：

```text
U13A_COMMITTED
LIVE_HA=2026.10.4
PRODUCT_ACCEPTANCE_SUCCESS=true
```

失败恢复终态：

```text
U13B_ROLLED_BACK
LIVE_HA=2026.10.0
PRODUCT_RECOVERY_ACCEPTANCE=true
```

---

## 4. 当前阶段映射

截至 2026-11-23，当前路线状态：

| 阶段 | 状态 | 说明 |
|---|---|---|
| V1.3 exact CI/package closure | PASS | exact source / CI / package 已闭环 |
| V1.3 updater 部署到备用 T1 | PASS | 当前 live recovery/updater 已对齐修复后 exact package |
| 现有旧 U1 只读 rebind | PASS | 旧事务、USB、运行时均完成重新绑定 |
| 旧 U1 -> V1.3 动态容量 U4 兼容性验证 | PASS | schema / identity / dynamic-capacity 路径已闭环 |
| 结束旧维护事务 | PASS | 旧 HA U4 已安全终结为历史 `ROLLED_BACK`，不得复用 |
| Manager successor / candidate monitoring activation | PASS | Manager successor COMMITTED，candidate monitoring 与 Manager->Broker->HA self-test 已通过 |
| 事务 A：10.4 -> 10.0 fresh PREPARE | IN_PROGRESS | 当前处于 post-activation readonly proof 后继续 fresh PREPARE-only |
| 事务 A：U5 -> U13A / U13B | NOT_STARTED | 需独立 install/cutover 授权 |
| 健康 10.0 基线确认 | NOT_STARTED | 事务 A 成功后执行 |
| 事务 B：10.0 -> 10.4 正常成功路径 | NOT_STARTED | 真正的 R8 正式代表性 OTA |
| 动态容量 fault injection | NOT_STARTED | 分别覆盖 target、predecessor、protected-data backup |
| 恢复 / 真实故障 fault injection | NOT_STARTED | 覆盖安装、启动、业务验收等实质故障 |
| 完整 U13B 回滚 | NOT_STARTED | 必须证明旧版健康自动恢复 |
| 关键中断 / 断电续办 | NOT_STARTED | 覆盖持久提交边界及恢复续办 |
| R8 V1.3 最终验收 | NOT_STARTED | 汇总正常成功与失败恢复证据 |

当前精确停点：

```text
CURRENT_STAGE=TRANSACTION_A_FRESH_PREPARE_10_4_TO_10_0
CURRENT_STATE=KF148_EXECUTOR_POST_ACTIVATION_ORACLE_REPAIR_READY_FRESH_PREPARE_PENDING
CURRENT_AUTHORIZATION=N3W_T1_V1_3_FRESH_HA_PREPARE_10_4_TO_10_0_20261123_01
AUTHORIZED_SCOPE=FRESH_PREPARE_ONLY
NEXT_EXPECTED_TERMINAL=U4_READY_TO_INSTALL
STOP_BEFORE_INSTALL=true
```

当前 resume 入口：

```text
RESUME_EXECUTOR=N3W_T1_V1_3_FRESH_HA_PREPARE_RESUME_20261123_02.sh
RESUME_EXECUTOR_SHA256=6626881959796e867f0a0ce38fe0020496fd0728caad5ae66e312268d83884e7
```

---

## 5. R8 V1.3 必须覆盖的验收场景

正常成功路径至少证明：

- fresh transaction 从合法健康前驱启动；
- target / predecessor / protected-data backup 都按各自动作前的实时容量测量准入；
- 安装、启动、业务验证和持久提交顺序正确；
- U13A 之后对外只呈现成功终态。

动态容量不足至少分别覆盖：

1. target 写入前空间不足；
2. predecessor 导出前空间不足；
3. protected-data backup 写入前空间不足；
4. 停服后发现内部空间不足；
5. 原盘释放空间后同事务继续的合法路径；
6. 必须 fresh PREPARE 的场景不得通过复活 terminal transaction 规避。

恢复 / fault injection 至少覆盖：

- target archive / identity 漂移；
- target image load 失败；
- target 启动失败；
- 业务验收失败；
- predecessor 已释放后的恢复；
- protected HA data rollback；
- recovery-health failure；
- 关键持久化点之前和之后的中断 / 断电续办。

最终用户可见结果只允许：

```text
升级成功
或
升级失败，系统已自动恢复原版本
```

不得把 checker 辅助信号缺失、错误阶段复用、执行器 oracle 过强等“假失败”作为产品失败终态。

---

## 6. 动态容量规则

V1.3 不使用固定通用 reserve 代替真实容量判断。

必须分别执行：

```text
target payload exact size
-> write 前重新测 USB free bytes
-> write 后记录实际写入和剩余空间

predecessor export measured size
-> export 前重新测 USB free bytes
-> export 后记录实际写入和剩余空间

protected-data backup measured size
-> writers quiesced
-> 用同一备份管线只读测量
-> backup 前重新测 USB free bytes
-> backup 后记录实际写入和剩余空间
```

内部镜像空间的 install/recovery 判断必须以实际释放动作后的真实可用空间为 authority，不得用 earlier pre-release free bytes 直接代替。

---

## 7. 阶段执行记录格式

每推进一个阶段，至少记录：

```text
STAGE_ID=
STAGE_GOAL=
SOURCE_HEAD=
ARTIFACT_ID=
ARTIFACT_SHA256=
LIVE_AUTHORIZATION=
PRE_STATE=
EXECUTED_ACTION=
RESULT=
POST_STATE=
RECOVERY_STATE=
NEXT_STAGE=
NEXT_AUTHORIZATION_REQUIRED=
UNARCHIVED_CRITICAL_RESULT_COUNT=
```

对已完成阶段必须明确区分：

```text
SOURCE_COMPLETE=
CI_COMPLETE=
PACKAGE_COMPLETE=
LIVE_DEPLOYMENT_COMPLETE=
LIVE_ACCEPTANCE_COMPLETE=
TRANSACTION_TERMINAL=
ARCHIVE_COMPLETE=
```

---

## 8. 失败与恢复规则

- 任一阶段 STOP 后，先判断是否发生 durable mutation；
- 未发生 mutation 时，不得把失败自动升级为产品故障；
- 已发生部分 mutation 时，先只读重建真实状态，再决定 resume / rollback；
- 已消费授权、已提交事务或 terminal transaction 不得重放；
- 执行器自身的路径、阶段、oracle 或 package-entrypoint 错误必须单独归档为 executor regression；
- 如果产品健康状态未被破坏，修复 executor 后从最后已证实 durable state 继续；
- 不通过“重新创建一个看似相同的事务”掩盖未关闭的旧事务；
- 每个 fault injection 必须先定义预期 fail-closed / rollback 结果，再执行实机测试。

---

## 9. 授权边界

本模板本身不授予权限。

默认需要单独授权的边界：

- T1 / USB / Docker / service 实机写入；
- PREPARE 进入新的持久事务；
- INSTALL intent / install authority；
- HA install / cutover；
- 主动 fault injection；
- 断电 / 重启；
- Broker OTA；
- merge / release / production deployment。

授权应绑定 exact source、exact artifact、目标 T1、事务方向、允许阶段和明确 STOP 点。

---

## 10. 当前后续顺序

当前不得跳过事务 A 直接开始正式 R8。

```text
当前
KF-148 post-activation readonly proof
        ↓
事务 A fresh PREPARE
        ↓
U4_READY_TO_INSTALL
        ↓
独立授权
        ↓
事务 A U5 -> U13A / U13B
        ↓
若 U13A：确认健康 exact 10.0 baseline
        ↓
事务 B fresh R8 10.0 -> 10.4 正常成功路径
        ↓
容量不足 fault injection
        ↓
恢复 / 真实故障 fault injection
        ↓
完整 U13B rollback
        ↓
关键中断 / 断电续办
        ↓
R8 V1.3 最终验收
```

如果事务 A 进入 U13B，则系统恢复健康 10.4，但**尚未建立 R8 需要的 10.0 起点**，必须先处理事务 A 失败原因；不得把 U13B 当成“已经可以开始正式 R8”。

---

## 11. 归档与更新规则

- 本文件记录阶段级路线，不记录每次 Terminal 完整输出；
- 每次路线发生实质调整时，更新本文件并在 Current State 中记录变更原因；
- 具体实机证据归档到对应 closure / progress / known-failure 文档；
- 新会话交接使用 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`，并引用本文件作为阶段路线 authority；
- 阶段全部完成后，将 `PLAN_STATUS` 改为 `CLOSED`，保留最终验收结论和证据入口。
