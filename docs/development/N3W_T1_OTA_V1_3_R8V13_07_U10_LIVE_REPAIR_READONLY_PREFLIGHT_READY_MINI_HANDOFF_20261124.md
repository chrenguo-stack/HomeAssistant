# N3-W R8V13-07 U10 recovery repair read-only preflight ready mini handoff

`MINI_HANDOFF_TEMPLATE_VERSION=1.2`

## 1. 当前任务与停点

- 当前任务：处理 R8V13-07 实机 INSTALL/cutover 在 `U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED` 暴露的 `ha_usb_predecessor_launch_binding_drift`，恢复现有已消费授权的 transaction，禁止重放 INSTALL。
- 已完成到：
  - 实机故障已定位：target 绑定把 HA image 与 `GH_N3W_T1_OTA_INSTALLED_VERSION` 一起切到 2026.10.0，而旧 rollback normalization 只归一化 image，导致 target-start 与 rollback 都出现 false drift；
  - 产品源码修复与回归测试已完成并通过完整相关 CI；
  - exact successor recovery artifact 已生成并绑定；
  - 专门针对当前 U10 现场的只读 live-repair preflight 已实现、审查并通过 focused CI。
- 当前状态：**现有 transaction 仍 ACTIVE/U10，recovery_required=true；INSTALL destructive authorization 已 claimed/consumed，绝不可重放。T1 尚未部署 repaired pyz。**
- 当前停点：**新对话先 fresh rebind，然后运行 exact U10 read-only preflight；取得 TX/env/image/media/recovery-owner 的最新现场证据后，再绑定并推进 live repair。**

## 2. GitHub 续接入口

- 仓库／PR／分支：`chrenguo-stack/HomeAssistant` / PR #824 / `review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
- 当前 head：`1623b2b3aaff8bbbd4d4cabc3217e78d63f7a3ac`（handoff 创建前 Current State + State Index docs-aligned head；新会话必须 fresh rebind）
- Master Task Document：UNBOUND
- Master Task Document SHA：UNBOUND
- Current Stage / Task：`N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE / R8V13-07`
- Next Task Chain：`RUN_U10_READONLY_PREFLIGHT -> ARCHIVE_PREFLIGHT_EVIDENCE -> BIND_AND_REVIEW_EXACT_U10_LIVE_REPAIR -> OBTAIN/CONFIRM_LIVE_REPAIR_MUTATION_AUTHORIZATION_IF_REQUIRED -> EXECUTE_EXISTING_TRANSACTION_RECOVERY -> VERIFY_TERMINAL_RECOVERY_AND_HEALTH -> ARCHIVE_R8V13_07_RESULT -> DECIDE_FRESH_R8V13_07_RETRY -> STOP_BEFORE_R8V13_08`
- Current State：`docs/development/N3W_CURRENT_STATE.md`
- State Index：`docs/development/N3W_CURRENT_STATE_INDEX.md`
- 相关 KF／closure／设计文档：
  - `docs/development/N3W_T1_OTA_V1_3_R8V13_07_SOURCE_LEVEL_END_TO_END_AUDIT_20261124.md`
  - `docs/development/N3W_T1_OTA_V1_3_R8V13_07_THIN_REENTRY_EXECUTOR_CONVERGENCE_20261124.md`
  - prior thin-executor handoff：`docs/development/N3W_T1_OTA_V1_3_R8V13_07_THIN_EXECUTOR_CI_SEALED_TO_INDEPENDENT_REVIEW_MINI_HANDOFF_20261124.md`
  - current read-only preflight：`tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT_20261124_01.sh`
  - preflight test：`tests/tools/test_n3w_t1_ota_r8v13_07_u10_live_repair_preflight.py`
- CI／artifact：
  - repaired product recovery source head：`a9b76d77c2a930a21089af7fe0cc814f4db60a9a`
  - HA target-binding CI run：`45429049845 = SUCCESS`
  - HA source suite：`329 passed, 1 skipped`
  - Docker release integration：`1 passed`
  - prior R8 focused CI run：`45429049683 = SUCCESS`，`56 passed` + product recovery `25 passed, 73 deselected`
  - exact recovery artifact ID：`14939405227`
  - artifact zip SHA256：`9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5`
  - manifest SHA256：`489aa375fda2b0fba76ee4e9bd30ab168ce9ee00feff05ee074af5b656d1eca8`
  - repaired successor `ha-recovery.pyz` SHA256：`d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e`
  - execution/preflight source head：`f13dc97dfaec03e0aa27447115357a7da90baf00`
  - `a9b76d77... -> f13dc97...` diff：仅新增/调整 U10 read-only preflight、对应 test、focused workflow；product recovery source 无 drift；
  - U10 read-only preflight Git blob：`87a564592f0204199be061d6c823b45e0936b889`
  - U10 read-only preflight SHA256：`c1a117208aad4ccc613885f233cc32efb4b609b86f1f2cf7530fc3d36a297886`
  - U10 preflight focused CI run：`45431604551 = SUCCESS`
  - focused suite：`59 passed`
  - product recovery subset：`25 passed, 73 deselected`
  - Public repository safety CI：SUCCESS。

新会话不得仅凭本 mini handoff 假定上述 live 状态仍成立；任何实机动作前必须 fresh rebind。

## 3. 下一步

- 下一动作：**新对话运行 exact U10 read-only preflight**。先 fresh rebind PR #824 / branch / current head，再确认 preflight blob/SHA256 与 focused CI；随后由用户在 Mac Terminal 对 spare T1 执行该 preflight，并回传完整输出。
- 允许范围：
  1. fresh rebind GitHub/source/CI；
  2. 运行上述只读 preflight；
  3. 归档 preflight 返回的 exact transaction-file SHA256、compose-env SHA256、predecessor image presence、target image ID、USB mount、retry owner 和 live binding；
  4. 基于该证据继续设计、实现、测试、CI 和独立复核 exact U10 live-repair executor。
- 暂停边界：
  1. **不得重新执行 thin INSTALL executor，不得再次提交 INSTALL，不得重新签发当前 transaction INSTALL authority；**
  2. preflight 任一 exact gate 漂移即停止 live repair 设计的实机部分并重新判定；
  3. repaired pyz 的实机替换属于新的 live physical mutation；在 exact live-repair gate 封存后，若现有授权不能明确覆盖该恢复写操作，必须先取得明确 mutation authorization；
  4. 无论 recovery 最终成功还是失败，都必须先归档 R8V13-07 结果，禁止自动进入 R8V13-08。
- 需要用户操作：新对话由 ChatGPT 给出 exact Mac Terminal 命令；用户执行 read-only preflight 并反馈完整输出。

## 3A. 条件补充信息（按需填写）

```text
TARGET=root@<spare-t1-private-ip> / spare T1 / transaction d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4
MUTATION_OR_RECOVERY_ACTION=下一步仅运行 exact U10 read-only preflight；preflight PASS 后绑定 live repair。当前不执行 repaired pyz replacement
PRE_ACTION_BASELINE=ACTIVE/U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED; recovery_required=true; authorization_claimed=true; authorization_consumed=true; predecessor_release_observed=true; target_activation=BINDING; target_loaded_image_id=sha256:c261fa53...5306; failure_code=null

AUTHORIZATION_SOURCE=原 R8V13-07 INSTALL/cutover 用户授权已被 transaction claim/consume；本轮用户明确要求新对话运行只读 preflight 并继续后续任务
AUTHORIZATION_SCOPE=READONLY_PREFLIGHT=AUTHORIZED; source/test/CI/archive continuation=AUTHORIZED; original INSTALL replay=FORBIDDEN; repaired-pyz live mutation must be covered by an exact recovery mutation gate and explicit authority if existing scope is insufficient
AUTHORIZATION_STATE=CONSUMED
AUTHORIZATION_REPLAY_ALLOWED=false

EXACT_SOURCE_HEAD=product recovery fix a9b76d77c2a930a21089af7fe0cc814f4db60a9a; preflight/execution source f13dc97dfaec03e0aa27447115357a7da90baf00
EXACT_ARTIFACT=artifact 14939405227 / zip SHA256 9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5 / manifest 489aa375fda2b0fba76ee4e9bd30ab168ce9ee00feff05ee074af5b656d1eca8 / repaired pyz d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e
EXACT_TRANSACTION=d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4 / ACTIVE / U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED / recovery_required=true
EXACT_RUNTIME_AUTHORITY=live recovery pyz 5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a; live HA target local/n3w-homeassistant:2026.10.0-0c73235a / sha256:c261fa53...5306; frozen predecessor local/n3w-homeassistant:2026.10.4-5881590f / sha256:31bc185b...7365; manager local/greenhouse-manager:fresh-1cae18039eee exact; broker local/n3w-mosquitto:2.1.2-3184566d exact

LAST_SUCCESSFUL_STEP=U10 read-only preflight source/test/workflow sealed by focused CI run 45431604551 SUCCESS: 59 passed + product recovery 25 passed/73 deselected; Public Safety SUCCESS
ACTUAL_CHANGES_ALREADY_MADE=physical INSTALL transaction crossed live authorization boundary; predecessor capacity was released; target 2026.10.0 image was loaded; HA env/binding was persisted to target; product recovery then stopped at U10 because old pyz raised ha_usb_predecessor_launch_binding_drift. No later manual T1 mutation has been performed. GitHub product source was repaired and exact successor artifact built, but repaired pyz is not yet deployed on T1
ROLLBACK_OR_RECOVERY_ENTRY=n3w-t1-ha-recovery-retry.service + n3w-t1-ha-recovery-retry.timer; durable product resume_host_recovery() owns the existing transaction. Do not create a second transaction or replay INSTALL

FRESH_REBIND_REQUIRED=true
STOP_CONDITION=preflight drift/FAIL; source/artifact/runtime/transaction mismatch; any attempt to replay INSTALL; live-repair mutation without exact gate/authority; any attempt to auto-enter R8V13-08
```

## 4. 新会话启动语

```text
继续 N3-W 当前任务。

先读取：
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_T1_OTA_V1_3_R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT_READY_MINI_HANDOFF_20261124.md
- docs/development/N3W_T1_OTA_V1_3_R8V13_07_SOURCE_LEVEL_END_TO_END_AUDIT_20261124.md
- docs/development/N3W_T1_OTA_V1_3_R8V13_07_THIN_REENTRY_EXECUTOR_CONVERGENCE_20261124.md

fresh rebind：
- repository main
- PR #824
- branch review/t1-ota-r8-existing-tx-predecessor-prep-20261123
- current PR head
- product recovery fix source head a9b76d77c2a930a21089af7fe0cc814f4db60a9a
- U10 preflight source head f13dc97dfaec03e0aa27447115357a7da90baf00
- preflight blob 87a564592f0204199be061d6c823b45e0936b889
- preflight SHA256 c1a117208aad4ccc613885f233cc32efb4b609b86f1f2cf7530fc3d36a297886
- focused CI run 45431604551 = SUCCESS
- recovery artifact 14939405227 / artifact digest 9843b554...42e5 / repaired pyz d7915bc3...185e
- live transaction durable state before any action

当前停点：
R8V13-07 physical transaction 已进入 ACTIVE/U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED，authorization 已 claimed/consumed，target_activation=BINDING，recovery_required=true。旧 recovery pyz 因 target-binding normalization 漏掉 GH_N3W_T1_OTA_INSTALLED_VERSION 而 false-stop。修复源码与 exact successor artifact 已完成，但 repaired pyz 尚未部署。

当前任务：
R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT

下一任务链：
RUN_U10_READONLY_PREFLIGHT -> ARCHIVE_PREFLIGHT_EVIDENCE -> BIND_AND_REVIEW_EXACT_U10_LIVE_REPAIR -> OBTAIN/CONFIRM_LIVE_REPAIR_MUTATION_AUTHORIZATION_IF_REQUIRED -> EXECUTE_EXISTING_TRANSACTION_RECOVERY -> VERIFY_TERMINAL_RECOVERY_AND_HEALTH -> ARCHIVE_R8V13_07_RESULT -> DECIDE_FRESH_R8V13_07_RETRY -> STOP_BEFORE_R8V13_08

先运行：
tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT_20261124_01.sh

要求：
- 先验证当前 preflight blob/SHA256 和 CI sealing；
- 给出 exact Mac Terminal 命令，由用户执行；
- preflight 只读，不启动/停止服务，不调用 --resume-pending，不提交 INSTALL；
- 收到完整输出后，绑定 TX_FILE_SHA256 / COMPOSE_ENV_SHA256 / image/media/recovery-owner 现场；
- 不得重新执行旧 INSTALL executor；
- 不得创建第二 transaction；
- 不得自动进入 R8V13-08。

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
UNCONSUMED_ONE_SHOT_AUTHORIZATION=false
ROLLBACK_STATE_AMBIGUOUS=false
CURRENT_STATE_AMBIGUOUS=false

SUPPLEMENT_REQUIRED=true
SUPPLEMENT_COMPLETE=true
FORMAL_HANDOFF_RECOMMENDED=false

FRESH_REBIND_REQUIRED=true
MASTER_TASK_DOCUMENT_BOUND=false
TASK_ALIGNMENT=UNBOUND
NEXT_ACTION_EXPLICIT=true
NEXT_TASK_CHAIN_EXPLICIT=true
STOP_BOUNDARY_EXPLICIT=true
```
