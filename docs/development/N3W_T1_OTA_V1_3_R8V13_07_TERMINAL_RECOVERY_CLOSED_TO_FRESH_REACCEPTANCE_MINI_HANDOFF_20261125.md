# N3-W R8V13-07 terminal recovery closed → fresh reacceptance mini handoff

`MINI_HANDOFF_TEMPLATE_VERSION=1.2`

Template authority used for this handoff:
`bf78ed80ac9586c702c045d953205c1a7082f627:docs/development/templates/mini-handoff-template.md`
(blob `3d57e9a2283acda660357d89c82de623cee4d972`).

## 1. 当前任务与停点

- 当前任务：继续 `R8V13-07`，在已失败的 transaction 完成 terminal rollback 后，为**新的 fresh R8V13-07 reacceptance**准备经过完整 CI 验证的 recovery artifact；尚未进入 `R8V13-08`。
- 已完成到：
  - transaction `d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4` 已终态 `ROLLED_BACK / U13B_ROLLED_BACK`；
  - exact 2026.10.4 predecessor 已恢复并通过最终 resident runtime health；
  - retry timer 已恢复 active；
  - `ha_usb_rollback_protected_data_evidence_pending` 假失败分类已修复为 non-error pending；
  - full HA target-binding CI `45522904136` SUCCESS；
  - 新 recovery artifact `14980338287` 已完成 source / ZIP / manifest / pyz exact binding。
- 当前状态：**可继续，但下一步仅允许 fresh rebind + exact read-only deployment preflight；新 artifact 尚未部署，fresh transaction 尚未创建。**
- 当前停点：从“新 recovery artifact 已 CI/artifact 闭环、备用 T1 仍运行旧 live repaired pyz”继续。

## 2. GitHub 续接入口

- 仓库／PR／分支：`chrenguo-stack/HomeAssistant` / PR #824 / `review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
- 当前 head：`7f8cf62cec89438f3e62f5a887ec00e506ba8d3f`（本 handoff 创建前的 docs-aligned head；handoff 写入会产生新的 docs-only head，新会话必须 fresh rebind PR #824 latest）
- Master Task Document：`docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md`
- Master Task Document SHA：blob `06c2f60b69874789a16fe7f14abf576b6832f356`
- Current Stage / Task：`N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE / R8V13-07`
- Next Task Chain：`R8V13-07 fresh reacceptance -> R8V13-08 -> R8V13-09 -> R8V13-10 -> R8V13-11 -> R8V13-12 -> R8V13-13 -> R8V13-14`
- Current State：`docs/development/N3W_CURRENT_STATE.md`，blob `21d4937bae8c47a5a0e6f898b3b418086fc91d5f`
- State Index：`docs/development/N3W_CURRENT_STATE_INDEX.md`，blob `7ad2562696df19744565a59ee201a23d8a92e00b`
- 相关 closure／设计文档：
  - `docs/development/N3W_T1_OTA_V1_3_R8V13_07_U10_TERMINAL_RECOVERY_HEALTH_CLOSURE_20261125.md`，blob `3a86e1bea19a35f2de93823223832e280e0ac2e0`
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`
- CI／artifact：
  - full HA target-binding CI run `45522904136 = SUCCESS`
  - HA source suite：`330 passed, 1 skipped`
  - Docker release integration：`1 passed`
  - artifact source head：`07eefc1e6d87eff464133771191d155fa9ee9d3d`
  - recovery artifact ID：`14980338287`
  - artifact ZIP digest SHA256：`d47d3fc4183805e63431c105682fbd93ed1cdc56b5fdc8681f41277afcd14ed1`
  - manifest SHA256：`c3071a9dcc2a5e54ca6017cfb58d1afad8d715cc47ca0640ae22493472430838`
  - new `ha-recovery.pyz` SHA256：`9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa`
  - manifest `source_head`：`07eefc1e6d87eff464133771191d155fa9ee9d3d`
  - artifact source binding：`PASS`

新会话不得仅凭本 handoff 假定上述状态仍然成立；执行前必须 fresh rebind。Master Task Document 的任务链未改变，`R8V13-08` 仍被 `R8V13-07` 阻塞。

## 3. 下一步

- 下一动作：fresh rebind 后，**准备并执行 recovery artifact `14980338287` 的 exact read-only deployment preflight**，核对 artifact/source/manifest/pyz、当前 live pyz、terminal transaction、10.4 runtime、systemd timer/socket 和 USB/runtime 基线；只读证据归档后再决定是否受控替换。
- 允许范围：repository/source review、CI/artifact exact binding、只读 T1 preflight、必要的只读 executor/preflight 源码与测试开发、CI、GitHub 归档。
- 暂停边界：
  - preflight 出现任何 source/artifact/runtime/transaction drift 时停止受影响操作；
  - **不得在 preflight 之前替换 live pyz**；
  - **不得创建新的 fresh transaction / PREPARE / INSTALL authority**；
  - **不得进入 R8V13-08**；
  - Broker OTA、host reboot、USB format/delete、merge、release 均不在当前授权范围。
- 需要用户操作：如果新会话进入备用 T1 只读检查，由 assistant 给出 Mac Terminal 可直接复制命令，用户执行并回传输出；当前 handoff 本身不要求用户操作 T1。

## 3A. 条件补充信息

```text
TARGET=spare T1 R8 validation host
MUTATION_OR_RECOVERY_ACTION=N/A_NEXT_ACTION_IS_READONLY_DEPLOYMENT_PREFLIGHT
PRE_ACTION_BASELINE=HA exact 2026.10.4 healthy; transaction d866... terminal U13B; live recovery pyz d7915bc3...; retry timer active; target 2026.10.0 absent

AUTHORIZATION_SOURCE=NONE_FOR_NEXT_READONLY_ACTION
AUTHORIZATION_SCOPE=NONE_FOR_NEXT_READONLY_ACTION
AUTHORIZATION_STATE=N/A
AUTHORIZATION_REPLAY_ALLOWED=false

EXACT_SOURCE_HEAD=07eefc1e6d87eff464133771191d155fa9ee9d3d
EXACT_ARTIFACT=ID 14980338287; ZIP d47d3fc4183805e63431c105682fbd93ed1cdc56b5fdc8681f41277afcd14ed1; manifest c3071a9dcc2a5e54ca6017cfb58d1afad8d715cc47ca0640ae22493472430838; pyz 9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa
EXACT_TRANSACTION=d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4 / ROLLED_BACK / U13B_ROLLED_BACK / consumed authorization / replay forbidden
EXACT_RUNTIME_AUTHORITY=HA local/n3w-homeassistant:2026.10.4-5881590f / sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365; live recovery pyz d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e; retry timer active

LAST_SUCCESSFUL_STEP=R8V13_07_U10_TERMINAL_RECOVERY_HEALTH_PASS + full HA target-binding CI/artifact binding PASS
ACTUAL_CHANGES_ALREADY_MADE=live repaired pyz d7915bc3... is installed; failed transaction recovered to exact 10.4 U13B; target 10.0 removed; retry timer restored active; new pyz 9d69992a... is NOT deployed
ROLLBACK_OR_RECOVERY_ENTRY=terminal recovery already complete; on any new live drift use read-only forensic first and never replay the terminal transaction

FRESH_REBIND_REQUIRED=true
STOP_CONDITION=any exact binding mismatch; live baseline drift; attempt to mutate/deploy before read-only preflight closure; attempt to reuse d866... authorization/transaction; attempt to create fresh transaction without a separately reviewed gate; any auto-advance to R8V13-08
```

## 4. 新会话启动语

```text
继续 N3-W 当前任务。

先读取：
- docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_T1_OTA_V1_3_R8V13_07_U10_TERMINAL_RECOVERY_HEALTH_CLOSURE_20261125.md
- docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md

fresh rebind：
- repository main
- PR #824
- branch review/t1-ota-r8-existing-tx-predecessor-prep-20261123 latest head
- master task document blob/current task chain
- full HA target-binding CI run 45522904136
- recovery artifact 14980338287 and exact ZIP/manifest/pyz hashes
- spare-T1 live baseline: terminal d866... U13B, exact 10.4 runtime, live pyz d7915bc3..., retry timer active

当前停点：
失败 transaction 已安全 U13B 回滚并完成健康闭环；protected-data pending 假失败修复及新 recovery artifact 已完成 CI/artifact exact binding，但新 artifact 尚未部署。下一步只做 exact read-only deployment preflight。

当前任务：
R8V13-07

下一任务链：
R8V13-07 fresh reacceptance
-> R8V13-08 exact 2026.10.0 healthy predecessor baseline
-> R8V13-09 fresh R8 success path
-> R8V13-10
-> R8V13-11
-> R8V13-12
-> R8V13-13
-> R8V13-14

按现有授权边界继续；如发现 source、runtime、authorization 或 evidence drift，停止受影响操作并重新判定。
不得复活/重放 transaction d866...；不得在只读 preflight 闭环前部署新 pyz；不得自动进入 R8V13-08。
```

## 5. mini handoff 完整性检查

```text
MINI_HANDOFF_TEMPLATE_VERSION=1.2
MINI_HANDOFF_COMPLETE=PASS

TEAM_SHARED_WORKSPACE=GITHUB
GITHUB_STATE_ALIGNED=true
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
UNARCHIVED_CRITICAL_RESULT_COUNT=0

LIVE_OR_PHYSICAL_MUTATION_PENDING=false
PRODUCTION_RECOVERY_IN_PROGRESS=false
UNCONSUMED_ONE_SHOT_AUTHORIZATION=false
ROLLBACK_STATE_AMBIGUOUS=false
CURRENT_STATE_AMBIGUOUS=false

SUPPLEMENT_REQUIRED=true
SUPPLEMENT_COMPLETE=true
FORMAL_HANDOFF_RECOMMENDED=false

FRESH_REBIND_REQUIRED=true
MASTER_TASK_DOCUMENT_BOUND=true
TASK_ALIGNMENT=PASS
NEXT_ACTION_EXPLICIT=true
NEXT_TASK_CHAIN_EXPLICIT=true
STOP_BOUNDARY_EXPLICIT=true
```
