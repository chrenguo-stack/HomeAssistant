# N3-W T1 OTA V1.3 R8V13-07 post-U11 repair + USB cleanup → fresh transaction A U4 mini handoff

`MINI_HANDOFF_TEMPLATE_VERSION=1.2`

## 1. 当前任务与停点

- 当前任务：R8V13-07 事务 A 重验收；U11 durable acceptance repair 已部署并完成 post-replacement readonly rebind，实验 U 盘历史事务已人工清理，fresh-prepare V3 已 CI 封口。
- 已完成到：
  - U11 repair recovery pyz 已在备用 T1 受控替换为 `807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2`；
  - post-replacement readonly rebind V3 = PASS；
  - 旧 terminal transaction `f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a` 保持 `ROLLED_BACK / U13B_ROLLED_BACK`，不得 replay；
  - 用户明确授权并完成实验盘 4 个历史 OTA transaction 目录删除，当前 `f6eb...` 目录完整保留；
  - USB free 从 `3645620224` bytes 提升到 `23234400256` bytes；
  - fresh-prepare V3 focused CI `45603026320` SUCCESS，Public repository safety `45603026025` SUCCESS。
- 当前状态：可继续；但本轮对话按用户要求停止推进，下一会话先做 T1 只读动态容量复核。
- 当前停点：新会话 fresh rebind 后执行 T1 readonly capacity recheck；仅在容量 PASS 时，使用已取得的条件授权创建新的 fresh transaction A，并准备到 `U4_READY_TO_INSTALL` 后停止。

## 2. GitHub 续接入口

- 仓库／PR／分支：`chrenguo-stack/HomeAssistant` / PR #824 / `review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
- 当前 head（handoff 建立前 docs-only alignment head）：`25d10dcf20a08e5c707feb1c5cf664bf9b3faf9d`
- 执行源码 CI authority head：`ac35c93d71b4b2e8221749617c7404582da77df2`
- Master Task Document：`docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md`
- Master Task Document SHA：`434224b8491b7d4521ca7489c1e5a9ffd800af8a`
- Current Stage / Task：`N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE / R8V13-07`
- Next Task Chain：`R8V13-08 → R8V13-09 → R8V13-10 → R8V13-11 → R8V13-12 → R8V13-13 → R8V13-14`
- Current State：`docs/development/N3W_CURRENT_STATE.md`
- State Index：`docs/development/N3W_CURRENT_STATE_INDEX.md`
- 相关设计文档：
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`
  - `docs/development/N3W_T1_OTA_V1_3_R8V13_07_U11_ACCEPTANCE_RETRY_REPAIR_CI_PASS_TO_DEPLOY_PREFLIGHT_MINI_HANDOFF_20261125.md`（历史上游，仅作证据）
- 关键执行包：
  - post-repair readonly rebind：`tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_FRESH_REACCEPTANCE_READONLY_REBIND_20261125_08.sh`
  - fresh transaction A prepare V3：`tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_TO_U4_20261125_03.sh`
- CI／authority：
  - fresh-prepare V3 executor blob：`12ece61775433425a602483f67da460d31e6abf0`
  - fresh-prepare V3 focused CI：`45603026320 = SUCCESS`
  - Public repository safety：`45603026025 = SUCCESS`
  - U11 repair source authority：`29ce1eb341289d0275ab064996a035e5d55ae430`
  - repair artifact ID：`14997816032`

新会话不得只凭本 handoff 假定上述 branch/live/authority 状态仍成立；执行前必须 fresh rebind。R8V13-08 只有在 R8V13-07 真正达到 healthy `U13A_COMMITTED + exact 2026.10.0` 后才可进入。

## 3. 下一步

- 下一动作：
  1. fresh rebind PR #824、branch/head、Master Plan、Current State/Index、fresh-prepare V3 exact executor/CI；
  2. 在备用 T1 执行**只读动态容量复核**，重新测量 USB free、当前 predecessor archive 实际大小、fresh prepare target+predecessor 顺序写入需求，以及 root candidate 空间；
  3. 若 readonly capacity PASS，则按本 handoff 第 3A 节的已存在条件授权，执行 fresh transaction A 的实际创建与 prepare，推进到 `U4_READY_TO_INSTALL`；
  4. 到 U4 后立即停止，不提交 INSTALL，不签发新 install authority，不进入 cutover。
- 允许范围：
  - 新会话可执行 fresh rebind 与 T1 readonly capacity recheck；
  - capacity PASS 且无 source/runtime/authority/evidence drift 时，可执行 fresh transaction A create + prepare to U4；
  - 可刷新 fresh PREPARE 所需 release/prepare authority、写入该 fresh transaction 的 USB 材料，以及产品 prepare 状态推进至 U4。
- 暂停边界：`U4_READY_TO_INSTALL`。不得自动进入 INSTALL/cutover/U5+，不得进入 R8V13-08。
- 需要用户操作：下一会话由用户在 Mac Terminal 执行 T1 命令并回传完整输出；当前已存在 create+prepare-to-U4 条件授权，不需要在容量 PASS 后重复询问同一授权，除非范围发生变化或 fresh rebind 发现 drift。

## 3A. 条件补充信息

```text
TARGET=spare T1 via environment-supplied SSH target; bound USB filesystem UUID b72ac2fc-79a0-4fb8-888e-f35b0114f959
MUTATION_OR_RECOVERY_ACTION=after readonly capacity PASS, create a NEW fresh transaction A and prepare only to U4_READY_TO_INSTALL
PRE_ACTION_BASELINE=healthy exact HA local/n3w-homeassistant:2026.10.4-5881590f (image sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365) + Manager local/greenhouse-manager:fresh-1cae18039eee + Broker local/n3w-mosquitto:2.1.2-3184566d; target 2026.10.0 absent; live recovery pyz 807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2; preserved USB transaction f6eb...; USB available bytes after cleanup 23234400256

AUTHORIZATION_SOURCE=user explicit instruction in current chat: after T1 readonly capacity recheck closes the capacity blocker, enter fresh transaction A actual creation and prepare to U4
AUTHORIZATION_SCOPE=fresh transaction A create + PREPARE only through U4_READY_TO_INSTALL; no INSTALL intent, no new install authority, no cutover, no U5+, no R8V13-08
AUTHORIZATION_STATE=UNCLAIMED
AUTHORIZATION_REPLAY_ALLOWED=false

EXACT_SOURCE_HEAD=ac35c93d71b4b2e8221749617c7404582da77df2
EXACT_ARTIFACT=fresh-prepare V3 executor blob 12ece61775433425a602483f67da460d31e6abf0; U11 repair artifact id 14997816032 / zip sha256 0ed412bfc923755d13b9cbe3ab744f173d4281f9730c4ca1baa490272e96a517
EXACT_TRANSACTION=f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a / ROLLED_BACK / U13B_ROLLED_BACK / transaction file sha256 4b1cc60e5557b9bc338d3d0469d30aa94c7974c34a0c26dffae5caf9fde4b105; this old transaction is terminal and MUST NOT be replayed
EXACT_RUNTIME_AUTHORITY=live repair pyz sha256 807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2; old terminal normalized launch 67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26; current raw healthy baseline launch 987189ccd61c0784db089b08e51a9ad3ff317372ad8a952dcda7a03a6d844c70

LAST_SUCCESSFUL_STEP=authorized lab USB cleanup PASS; preserved f6eb target/predecessor hashes unchanged; fresh-prepare V3 focused CI and public-safety CI both SUCCESS
ACTUAL_CHANGES_ALREADY_MADE=U11 repair pyz replaced on spare T1; four explicitly authorized historical lab OTA transaction directories deleted from bound USB; current f6eb transaction directory retained intact
ROLLBACK_OR_RECOVERY_ENTRY=live system is already healthy exact 2026.10.4 predecessor; old f6eb transaction is terminal U13B and cannot be replayed; fresh prepare is pre-cutover and must stop at U4

FRESH_REBIND_REQUIRED=true
STOP_CONDITION=any source/runtime/USB/authority/evidence drift; readonly capacity FAIL; fresh prepare does not reach exact U4_READY_TO_INSTALL; or U4 is reached (mandatory stop before install authorization)
```

Key latest evidence:

```text
POST_REPAIR_READONLY_REBIND=PASS
CURRENT_RAW_LAUNCH_SHA256=987189ccd61c0784db089b08e51a9ad3ff317372ad8a952dcda7a03a6d844c70
CURRENT_NORMALIZED_LAUNCH_SHA256=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
MANAGER_BROKER_HA_SELF_TEST=PASS
MANAGER_BROKER_HA_SELF_TEST_SHA256=9328f76e172b429c5683c8fc0a67dada601101e9285d0e0aeb8f1f138f2b260f

USB_LAB_CLEANUP=PASS
USB_AVAILABLE_BYTES_AFTER=23234400256
PRESERVED_TARGET_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
PRESERVED_PREDECESSOR_SHA256=6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f
PRESERVED_TRANSACTION_USAGE_BYTES=4897783808

FRESH_PREPARE_V3_CI=SUCCESS
FRESH_PREPARE_V3_FOCUSED_CI_RUN=45603026320
FRESH_PREPARE_V3_PUBLIC_SAFETY=SUCCESS
FRESH_PREPARE_V3_PUBLIC_SAFETY_RUN=45603026025
```

## 4. 新会话启动语

```text
继续 N3-W 当前任务。

先读取：
- docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md
- docs/development/N3W_T1_OTA_V1_3_R8V13_07_POST_U11_REPAIR_USB_CLEANUP_TO_FRESH_TX_A_U4_MINI_HANDOFF_20261125.md

fresh rebind：
- repository main
- PR #824
- branch review/t1-ota-r8-existing-tx-predecessor-prep-20261123
- exact fresh-prepare V3 source authority ac35c93d71b4b2e8221749617c7404582da77df2
- focused CI 45603026320 = SUCCESS
- Public repository safety CI 45603026025 = SUCCESS
- live spare-T1 terminal transaction / recovery pyz / runtime identities / USB UUID and current free space

当前停点：
U11 repair deployed + post-repair readonly rebind PASS + lab USB cleanup PASS + fresh-prepare V3 CI PASS；尚未执行清理后的 T1 readonly capacity recheck；尚未创建新的 fresh transaction A。

当前任务：
R8V13-07

下一任务链：
R8V13-08 → R8V13-09 → R8V13-10 → R8V13-11 → R8V13-12 → R8V13-13 → R8V13-14

先执行 T1 只读动态容量复核。容量阻断关闭且 fresh rebind 无 drift 后，按现有条件授权创建 NEW fresh transaction A 并 prepare 到 U4_READY_TO_INSTALL，然后 STOP。不得提交 INSTALL、不得进入 U5+、不得进入 R8V13-08。

按现有授权边界继续；如发现 source、runtime、authorization 或 evidence drift，停止受影响操作并重新判定。
```

## 5. mini handoff 完整性检查

```text
MINI_HANDOFF_TEMPLATE_VERSION=1.2
MINI_HANDOFF_COMPLETE=PASS

TEAM_SHARED_WORKSPACE=GITHUB
GITHUB_STATE_ALIGNED=true
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
UNARCHIVED_CRITICAL_RESULT_COUNT=0

LIVE_OR_PHYSICAL_MUTATION_PENDING=true
PRODUCTION_RECOVERY_IN_PROGRESS=false
UNCONSUMED_ONE_SHOT_AUTHORIZATION=true
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
