# N3W T1 F5 V1 封存与 V2 接替关闭记录 — 2026-10-19

## 0. Conclusion

~~~text
TASK=N3W_T1_F5_V1_ARCHIVE_AND_SUPERSESSION_CLOSURE_20261019_01
RESULT=V1_IMPLEMENTATION_LINE_ARCHIVED_SUPERSEDED

V1_ARCHITECTURE_HISTORY_PRESERVED=true
V1_SOURCE_BRANCH_HISTORY_PRESERVED=true
V1_RELEASE_HISTORY_PRESERVED=true
V1_LIVE_EVIDENCE_PRESERVED=true
V1_NORMAL_DEVELOPMENT_CONTINUES=false

SUPERSEDED_BY=N3W_T1_F5_PRODUCTION_PROCESS_V2_SIMPLIFIED_ARCHITECTURE_CONTRACT_20261019_01

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

## 1. Why V1 is closed

F5 V1 successfully建立了 exact release、Mac durable archive、一次生产批准、SSH 两连接期、目标端 durable authority
以及 fail-closed/UNKNOWN 证据原则，也真实暴露并修复了 KF-122 / KF-123 类跨阶段缺陷。

但 V1 的正常量产入口逐步承担了“识别任意旧主机状态、失败后原地恢复、逐 phase durable claim、复杂 inventory ownership
分类”等职责，偏离了当前产品实际需求。

新的产品决策是：

> 正常量产只接受标准全新 Armbian；不符合就重装；部署失败原则上重装后重新生产；
> 最终真实重启后的独立验收才决定 T1 是否合格。

因此继续扩展 V1 inventory/recovery 不再有产品价值。

## 2. Historical facts retained

以下事实永久保留为历史证据，不因 V2 否认：

- PR #610 / #611 已合并的 F5 V1 架构与对齐记录；
- PR #612 及后续 stacked source/release/recovery 分支历史；
- KF-122 failed-run terminalization 关闭证据；
- KF-123 F3 phase-context source repair；
- source head 4afd89b56e9925d7330b27f3f734ebcefc09182c 的 reviewed CI；
- durable release c8a7e432722121b808a0d31ffbc3d049a64aa5b4f270a7be6f07b90891eecf69；
- artifact 12190255517；
- Mac durable archive acceptance；
- 当前 F5-8 inventory STOP 且 read-only/session-closed/no-mutation。

这些内容用于 regression/reference，不作为 V2 的 current production authority。

## 3. Superseded open PR stack

以下 Draft PR 均属于 V1 implementation line，并应 Close as superseded：

~~~text
#612 F5 V1 production process source
#613 exact production release build
#614 durable production release archive
#615 failed-run controlled terminalization
#616 failed-run terminalization read-only preauth
#617 F5-9 replacement live authorization
#618 KF-123 isolate F3 phase context
#619 KF-123 source review handoff
#620 KF-123 UNKNOWN-run controlled adjudication
#621 F5-7 exact production release rebuild after KF-123
~~~

关闭 PR 不删除 branch、commit、CI、artifact metadata 或 durable Mac archive。

## 4. Current T1-B boundary

最新一次 F5-8 为 read-only STOP：

~~~text
ERROR=production_readonly_preflight_failed:production_preflight_failed:inventory
READ_ONLY=true
MUTATION_PERFORMED=false
SESSION_CLOSED=true
T1_MUTATION=false
LIVE_REBOOT=false
PRODUCT_SERVICE_START=false
BOARD_ACCESS=false
~~~

不再继续 V1 inventory forensic/repair 作为正常生产工作。

T1-B 在 V2 实机阶段前重新安装官方 Armbian。

## 5. V1 artifacts

V1 release/artifacts 只保留历史用途：

~~~text
V1_RELEASE_USE_FOR_NEW_PRODUCTION=false
V1_RELEASE_DELETE=false
V1_DURABLE_ARCHIVE_DELETE=false
V1_BRANCH_DELETE=false
~~~

## 6. Stop

V1 implementation line 到此关闭。后续正常开发只进入 F5 V2。

~~~text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V2_SOURCE_DESIGN_20261019_01
AUTO_EXECUTE_V1_RECOVERY=false
AUTO_EXECUTE_T1=false
MERGE=false
~~~
