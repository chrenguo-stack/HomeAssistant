# N3-W R8V13-07 U11 acceptance retry repair CI PASS → exact artifact deploy preflight mini handoff

`MINI_HANDOFF_TEMPLATE_VERSION=1.2`

Template authority: `main:docs/development/templates/mini-handoff-template.md`, blob `3d57e9a2283acda660357d89c82de623cee4d972`.

## 1. 当前任务与停点

- 当前任务：R8V13-07 事务 A INSTALL/cutover 成功路径重新验收；先部署已修复 U11 durable acceptance / timer-reentry 的 exact recovery artifact。
- 已完成到：
  - 第二笔 fresh transaction A `f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a` 已真实跨过 INSTALL/cutover，并因 `ha_usb_target_acceptance_evidence_unavailable` 自动回滚到 durable `U13B_ROLLED_BACK`。
  - exact 2026.10.4 predecessor、Manager、Broker 已恢复健康；target 2026.10.0 已退休。
  - forensic 已证明旧实现把 3 次 U11 acceptance 在单次 worker 内同步耗尽，间隔仅 2 秒，且 `U11 + recovery_required=false` 没有 timer re-entry。
  - 修复已完成：每次 worker 只消耗 1 次 durable acceptance；持久化 per-check verdict 和 `retry_after_unix`；现有 retry timer 可续办 U11；不得重放 INSTALL/authority。
  - 修复 source head `29ce1eb341289d0275ab064996a035e5d55ae430` 的 focused CI / public-safety / HA target-binding 均 SUCCESS；exact recovery artifact 已产生。
- 当前状态：可继续，但只允许从 fresh GitHub/live rebind 和 exact artifact **只读部署预检**开始；修复尚未部署到备用 T1。
- 当前停点：STOP_BEFORE_U11_REPAIR_ARTIFACT_DEPLOYMENT；不得创建新 transaction，不得进入 R8V13-08。

## 2. GitHub 续接入口

- 仓库／PR／分支：`chrenguo-stack/HomeAssistant` / PR #824 / `review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
- 当前 head：`b6a4c7d61920c67bf5eca538ab2572f3b3ec0071`（handoff 创建前的 GitHub 对齐 head；exact executable/CI authority 仍为 `29ce1eb341289d0275ab064996a035e5d55ae430`）
- Master Task Document：`docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md`
- Master Task Document SHA：`705adbf592fa26b092e71bf3d1e98aebb09e98bf`
- Current Stage / Task：`N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE / R8V13-07`
- Next Task Chain：`R8V13-07 repair artifact deploy + fresh transaction A reacceptance → R8V13-08 exact 2026.10.0 healthy baseline → R8V13-09 fresh R8 10.0→10.4 → R8V13-10 → R8V13-11 → R8V13-12 → R8V13-13 → R8V13-14`
- Current State：`docs/development/N3W_CURRENT_STATE.md`
- State Index：`docs/development/N3W_CURRENT_STATE_INDEX.md`
- 相关 KF／closure／设计文档：
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`（EVIDENCE_UNAVAILABLE / bounded retry 设计依据）
  - PR #824 comments `7154471381`, `7154583509`, `7154686147`, `7154761963`
- CI／artifact：
  - focused CI `45560299329 = SUCCESS`
  - public safety `45560299182 = SUCCESS`
  - HA target-binding `45560299281 = SUCCESS`
  - artifact ID `14997816032`
  - artifact name `n3w-t1-ha-recovery-install-29ce1eb341289d0275ab064996a035e5d55ae430`
  - artifact ZIP SHA256 `0ed412bfc923755d13b9cbe3ab744f173d4281f9730c4ca1baa490272e96a517`
  - `manifest.json` SHA256 `e28e6197c867da322528fbf144a1aa06d56a43b1a9ad91b5ba0ff6af51f96080`
  - `ha-recovery.pyz` SHA256 `807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2`

新会话不得仅凭本 mini handoff 假定上述状态仍然成立；执行前必须 fresh rebind PR head、CI/artifact 和备用 T1 live runtime。

## 3. 下一步

- 下一动作：fresh rebind repository / PR #824 / current state / master task，核对 exact artifact `14997816032`；随后准备并执行**只读** U11 repair artifact deployment preflight，返回 live recovery pyz、terminal transaction、runtime health、USB/root capacity、artifact delta/binding 和 deployment eligibility。
- 允许范围：
  - GitHub 只读 rebind；
  - 必要的源码/测试审查；
  - 只读 T1 deployment preflight 的源码开发、CI 和用户执行；
  - GitHub 状态/证据归档。
- 暂停边界：STOP_BEFORE_ACTUAL_RECOVERY_ARTIFACT_REPLACEMENT。部署 mutation 必须另行取得用户明确执行授权；预检不得创建 fresh transaction、提交 INSTALL、签发 authority、进入 R8V13-08。
- 需要用户操作：下一会话如 preflight CI PASS，需要用户在 Mac Terminal 执行只读 T1 preflight 命令并回传完整输出。

## 3A. 条件补充信息

```text
TARGET=spare T1 root@192.168.68.195; exact recovery control-plane artifact for source 29ce1eb341289d0275ab064996a035e5d55ae430
MUTATION_OR_RECOVERY_ACTION=NONE_YET; immediate next action is readonly deployment preflight
PRE_ACTION_BASELINE=exact HA 2026.10.4 + Manager fresh-1cae18039eee + Broker 2.1.2-3184566d healthy; target 10.0 absent; live recovery pyz 9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa; terminal transaction U13B

AUTHORIZATION_SOURCE=NONE
AUTHORIZATION_SCOPE=NONE
AUTHORIZATION_STATE=N/A
AUTHORIZATION_REPLAY_ALLOWED=false

EXACT_SOURCE_HEAD=29ce1eb341289d0275ab064996a035e5d55ae430
EXACT_ARTIFACT=id=14997816032; zip_sha256=0ed412bfc923755d13b9cbe3ab744f173d4281f9730c4ca1baa490272e96a517; manifest_sha256=e28e6197c867da322528fbf144a1aa06d56a43b1a9ad91b5ba0ff6af51f96080; pyz_sha256=807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2
EXACT_TRANSACTION=f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a / ROLLED_BACK / U13B_ROLLED_BACK / tx_sha256=4b1cc60e5557b9bc338d3d0469d30aa94c7974c34a0c26dffae5caf9fde4b105
EXACT_RUNTIME_AUTHORITY=HA local/n3w-homeassistant:2026.10.4-5881590f id sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365; Manager local/greenhouse-manager:fresh-1cae18039eee; Broker local/n3w-mosquitto:2.1.2-3184566d; live recovery pyz 9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa

LAST_SUCCESSFUL_STEP=automatic rollback reached durable U13B; predecessor runtime health PASS; U11 repair source/package CI all PASS
ACTUAL_CHANGES_ALREADY_MADE=transaction f6eb... consumed INSTALL authorization, loaded/started target 10.0, failed to close mandatory acceptance evidence, then product recovery restored 10.4 and retired target; source repair 29ce... exists only in GitHub artifact and is NOT deployed
ROLLBACK_OR_RECOVERY_ENTRY=n3w-t1-ha-recovery-retry.service + timer; current transaction already terminal, so recovery must NOT be replayed

FRESH_REBIND_REQUIRED=true
STOP_CONDITION=stop on any source/artifact/runtime/transaction drift; stop before actual artifact replacement without new explicit user authorization; never replay f6eb...; never auto-advance R8V13-08
```

禁止项：
- 不得重放 transaction `f6eb...`；
- 不得复用其 INSTALL authorization；
- 不得把当前已恢复的 10.4 当成 R8V13-08 的 10.0 基线；
- 不得在 artifact 未部署/验证前创建下一笔 fresh transaction；
- 不得执行 Broker OTA、host reboot、USB format/delete、PR merge 或 release。

## 4. 新会话启动语

```text
继续 N3-W 当前任务。

先读取：
- docs/development/templates/STAGE_EXECUTION_PLAN_TEMPLATE.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/N3W_T1_OTA_V1_3_R8V13_07_U11_ACCEPTANCE_RETRY_REPAIR_CI_PASS_TO_DEPLOY_PREFLIGHT_MINI_HANDOFF_20261125.md
- docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md

fresh rebind：
- repository main
- PR #824 / review/t1-ota-r8-existing-tx-predecessor-prep-20261123
- exact executable source head 29ce1eb341289d0275ab064996a035e5d55ae430
- focused CI 45560299329 / public safety 45560299182 / HA target-binding 45560299281
- artifact 14997816032 and its exact digest/manifest/pyz hashes
- spare T1 live terminal transaction, runtime images, live recovery pyz and current capacity before any mutation

当前停点：
R8V13-07 second fresh transaction is terminal U13B and healthy 10.4 is restored. U11 durable acceptance/timer-reentry repair is CI/package sealed but not deployed. Start with exact readonly deployment preflight; stop before artifact replacement.

当前任务：
R8V13-07

下一任务链：
R8V13-07 repair artifact deploy + fresh transaction A reacceptance
→ R8V13-08 exact 2026.10.0 healthy predecessor baseline
→ R8V13-09 fresh R8 2026.10.0 -> 2026.10.4
→ R8V13-10
→ R8V13-11
→ R8V13-12
→ R8V13-13
→ R8V13-14

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
MASTER_TASK_DOCUMENT_BOUND=true
TASK_ALIGNMENT=PASS
NEXT_ACTION_EXPLICIT=true
NEXT_TASK_CHAIN_EXPLICIT=true
STOP_BOUNDARY_EXPLICIT=true
```
