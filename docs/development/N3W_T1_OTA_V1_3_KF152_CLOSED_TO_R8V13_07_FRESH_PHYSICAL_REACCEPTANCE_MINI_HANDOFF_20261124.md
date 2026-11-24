# N3-W KF-152 closed → R8V13-07 fresh physical reacceptance mini handoff

`MINI_HANDOFF_TEMPLATE_VERSION=1.1`

> 模板 authority：`docs/development/templates/mini-handoff-template.md` historical blob `14c7ee3c6c89f4e72dad0c35e3a466835138b9ea`.
> 用户明确要求本轮使用 mini-handoff-template。
> 下一轮包含新的 T1 updater patch / fresh transaction / INSTALL/cutover 写入边界，因此按模板原始 eligibility 规则，本 handoff **不满足自动执行型 mini eligibility**。它只用于恢复现场、fresh rebind 和进入新的实机授权前置；不授予任何 T1 写入权限。

## 1. 当前任务与停点

- 当前任务：`R8V13-07` — 事务 A 的 fresh physical reacceptance；目标仍是安全把备用 T1 从 healthy exact HA 2026.10.4 准备为 healthy exact HA 2026.10.0。
- 已完成到：历史 Attempt A 在 U8 前切换恢复，终态 `ROLLED_BACK / U8_RECOVERY_ADMISSION_COMPLETE`；KF-152 source/test/real-Docker/package/CI 已闭环并标记 `GUARDED`。
- 当前状态：源码闭环完成；下一轮实机重验尚未开始。
- 当前停点：保持历史终态事务不重放；新会话先做 repository + T1 read-only fresh rebind，确认 live predecessor/control plane/USB/authority 状态，再制定并申请新的实机重验授权。

历史事务：

```text
TRANSACTION_ID_SHA256=463c8065eea5ada915074194058ee45880ddab2c94d06715c82f09fb84481969
STATUS=ROLLED_BACK
PHASE=U8_RECOVERY_ADMISSION_COMPLETE
FAILURE_CODE=ha_usb_pre_cutover_interrupted
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
RECOVERY_REQUIRED=false
PRE_CUTOVER_PREDECESSOR_RESTORED=true
PREDECESSOR_RELEASE_INTENT=false
PREDECESSOR_RELEASE_OBSERVED=false
TARGET_LOAD_IDENTITY=false
HA_DATA_RESTORE=false
OLD_TRANSACTION_REPLAY=false
U13B_FULL_ROLLBACK=NOT_REACHED
```

最后有实机证据支持的 runtime：

```text
HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
MANAGER=local/greenhouse-manager:fresh-1cae18039eee
MANAGER_IMAGE_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
BROKER=local/n3w-mosquitto:2.1.2-3184566d
BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
LIVE_RECOVERY_PYZ_LAST_VERIFIED_SHA256=eee49d52ae4ea7f9ecb20a27d1fc467e66708d4fc7df28493acf7bb7f8a049cf
KF152_REPAIRED_PYZ_DEPLOYED=false
```

USB / storage last observed：

```text
USB_MOUNT=/mnt/n3w-ha-r8-predecessor
USB_DEVICE=/dev/sda1
USB_FILESYSTEM=ext4
USB_UUID=b72ac2fc-79a0-4fb8-888e-f35b0114f959
ROOT_FILESYSTEM=/dev/mmcblk2p2
ROOT_AVAILABLE_BYTES_LAST_OBSERVED=4689645568
```

The historical install-authority file was still present at the last forensic read and was bound to the terminal historical transaction. Its historical expiry was 2026-11-24 11:07:26 +08:00. It is never reusable regardless of current file presence or expiry state. New conversation must fresh-read its state before creating any fresh transaction/authority.

## 2. GitHub 续接入口

- 仓库：`chrenguo-stack/HomeAssistant`
- PR：`#824` — OPEN / DRAFT
- 分支：`review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
- repository main at handoff preparation：`bf78ed80ac9586c702c045d953205c1a7082f627`
- docs-aligned head before this handoff：`1267c2669941b244d1dcf1d42dc45796a52dd9db`
- KF-152 product repair head：`6b6c735ae12a253a62dd64b0adedb90b6c5ad03f`
- KF-152 Docker integration head：`71260221ebcbc1e4f461dc7f3cea842e0406616a`
- KF-152 exact CI closure head：`9339ab22fc29ddd14d2e147d13e616ccebed945b`
- exact CI：22/22 SUCCESS
- Master Task Document：`docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md`
- Master Task Document SHA：`acc4e2c2fce5b68b24cc2b993662a72faffc25ee`
- Current Stage：`N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE`
- Current Task：`R8V13-07`
- Next Task：`R8V13-08`，仍 BLOCKED
- Current State：`docs/development/N3W_CURRENT_STATE.md`
- State Index：`docs/development/N3W_CURRENT_STATE_INDEX.md`
- KF closure：`docs/development/N3W_T1_OTA_V1_3_KF152_SOURCE_CI_DOCKER_PACKAGE_CLOSURE_20261124.md`
- Regression authority：`docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`，重点 KF-143～KF-152
- Architecture：`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`

Exact recovery candidate：

```text
RUN_ID=45317562079
ARTIFACT_ID=14885876408
ARTIFACT_NAME=n3w-t1-ha-recovery-install-9339ab22fc29ddd14d2e147d13e616ccebed945b
ARTIFACT_DIGEST_SHA256=23289a67fd60051ac60d4392f690917134c3076d3d8aeb9226eae9a37d52407c
INSTALL_MANIFEST_SHA256=6792c681b61404d7a6a31e1bd78f25e6332d89a147d2639f2c4b6a1b705bdd89
HA_RECOVERY_PYZ_SHA256=d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
REAL_DOCKER_IMAGE_ID_RELEASE=PASS
```

Fresh exact ARM64 closure：

```text
RUN_ID=45317562014
ARTIFACT_ID=14886237329
ARTIFACT_DIGEST_SHA256=ed70e7e2fc9a010cca20ae128c2f4afc030f3bc3a60716aee683a69860574287
POST_UPLOAD_EXACT_BINDING=PASS
```

Next Task Chain：

```text
R8V13-07 fresh physical reacceptance: 10.4 -> 10.0
→ R8V13-08 exact 2026.10.0 healthy predecessor baseline
→ R8V13-09 fresh transaction B: 2026.10.0 -> 2026.10.4 normal success path
→ R8V13-10 dynamic capacity-insufficient injection
→ R8V13-11 recovery / real-fault injection
→ R8V13-12 full U13B rollback acceptance
→ R8V13-13 interruption / power-loss continuation acceptance
→ R8V13-14 R8 V1.3 final acceptance
```

新会话不得仅凭本 handoff 假定 live 状态仍然成立；必须先 fresh rebind。

## 3. 下一步

- 下一动作：进入新会话后，先做 read-only fresh rebind：
  1. repository main / PR #824 / branch / current PR head；
  2. Current State / Index / KF-152 closure / master task coordinate；
  3. T1 exact HA/Manager/Broker runtime 与 active Compose；
  4. live recovery pyz SHA，确认 KF-152 repaired pyz 尚未部署或识别任何 drift；
  5. historical transaction 仍 terminal/non-replayable；
  6. historical install-authority file 当前存在/过期/清理状态，仅作取证，绝不复用；
  7. USB filesystem UUID、历史 archive bytes、root/USB available space；
  8. recovery retry timer/socket 与 fresh KF-144 Manager→Broker→HA business-health path。
- 允许范围：仓库/GitHub/源码/CI/artifact 只读核对；T1 只读 preflight；生成新的 R8V13-07 physical reacceptance execution contract。
- 暂停边界：**STOP_BEFORE_NEW_LIVE_AUTHORIZATION**。没有新的明确授权时，不得替换 live recovery pyz、不得退休/删除任何 authority 文件、不得创建 fresh transaction、不得提交 INSTALL intent、不得签发 authority、不得停 HA/Manager、不得释放/加载镜像、不得恢复/重启、不得执行 Broker OTA、不得 merge/release。
- 需要用户操作：只读 rebind 通过后，由用户明确批准新的 R8V13-07 fresh physical reacceptance 范围。新的授权必须绑定 exact recovery artifact/head、fresh transaction 和允许的失败自动恢复范围；不得继承历史 Attempt A 授权。

成功合同保持：

```text
SUCCESS => fresh transaction U13A_COMMITTED + healthy exact Home Assistant 2026.10.0
FAILURE => automatic safe recovery + healthy exact Home Assistant 2026.10.4
```

如果 fresh attempt 出现与 KF-152 不同的新故障，应新建 KF；不要重新打开已经 guarded 的 KF-152，除非证据明确证明 KF-152 guard 本身失效。

Broker OTA 继续 `DEFERRED_UNTIL_HA_OTA_ACCEPTANCE_CLOSED`。

## 4. 新会话启动语

```text
继续 N3-W 当前任务，进入 R8V13-07 fresh physical reacceptance。

先读取：
- docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_T1_OTA_V1_3_KF152_CLOSED_TO_R8V13_07_FRESH_PHYSICAL_REACCEPTANCE_MINI_HANDOFF_20261124.md
- docs/development/N3W_T1_OTA_V1_3_KF152_SOURCE_CI_DOCKER_PACKAGE_CLOSURE_20261124.md
- docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

fresh rebind：
- repository main
- PR #824
- branch review/t1-ota-r8-existing-tx-predecessor-prep-20261123
- current PR head
- master task coordinate R8V13-07 -> R8V13-08
- KF-152 status must remain GUARDED
- exact recovery candidate run 45317562079 / artifact 14885876408 / pyz d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
- live T1 HA/Manager/Broker / active Compose / recovery pyz / timer/socket
- historical transaction 463c8065eea5ada915074194058ee45880ddab2c94d06715c82f09fb84481969 must remain terminal and replay-forbidden
- historical install authority current file state, but never reuse
- USB identity/materials/storage capacity

当前停点：
KF-152 source/test/real-Docker/package/CI 已闭环为 GUARDED；历史 R8V13-07 Attempt A 已安全恢复到 10.4，但没有达到 U13A，也没有完成 full U13B。修复版 recovery pyz 尚未在 T1 上获得新的部署授权。

当前任务：
R8V13-07 fresh physical reacceptance

下一任务链：
R8V13-07 -> R8V13-08 -> R8V13-09 -> R8V13-10 -> R8V13-11 -> R8V13-12 -> R8V13-13 -> R8V13-14

先完成 read-only fresh rebind 和新的 execution-contract 复核。没有新的明确 live authorization 时必须 STOP_BEFORE_NEW_LIVE_AUTHORIZATION。旧 transaction、旧 install authority、旧 Attempt A authorization 均不可重用。

按现有授权边界继续；如发现 source、runtime、authorization 或 evidence drift，停止受影响操作并重新判定。
```

## 5. mini handoff 完整性检查

```text
MINI_HANDOFF_TEMPLATE_VERSION=1.1
MINI_HANDOFF_ELIGIBLE=false
USER_EXPLICIT_TEMPLATE_REQUEST=MINI_HANDOFF
HANDOFF_ROLE=NAVIGATION_FRESH_REBIND_AND_PREAUTH_ONLY

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

OLD_TRANSACTION_REPLAY=false
NEW_LIVE_AUTHORIZATION_GRANTED=false
BROKER_OTA=DEFERRED
```

本文件不授予权限，也不能替代 Current State、master Stage Execution Plan、KF-152 closure 或下一轮单独的 R8V13-07 fresh physical reacceptance 授权。
