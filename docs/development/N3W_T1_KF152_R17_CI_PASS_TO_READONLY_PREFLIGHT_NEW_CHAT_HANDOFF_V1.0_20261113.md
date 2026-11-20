# N3-W T1 KF-152 R17 CI PASS 到只读预检
# 新会话交接文档 V1.0 — 2026-11-13

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：完成 R16 terminal STOP 的收尾，把 R17 dependency-safe successor 的源码、实机前态、fresh CI 和授权边界交给新会话；新会话从执行 R17 真实 T1 只读 preflight 开始。
- 已完成到：post-R16 只读取证 PASS；R17 源码与回滚生命周期复核 PASS；exact closure head `c70719af8cb888d574a8cb59cf68510e83cf6211` fresh CI `16/16 SUCCESS`。
- 当前状态：可继续只读预检。R17 live recovery 仍未授权；只读预检 PASS 后必须停在新的 one-shot 实机恢复授权边界。

```text
CURRENT_STAGE=KF152_R17_DEPENDENCY_SAFE_RECOVERY_PREAUTHORIZATION
CURRENT_STOP_POINT=R17_EXACT_HEAD_CI_CLOSED_PASS
NEXT_ONE_GATE=R17_REAL_T1_READONLY_PREFLIGHT
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

## 2. 代码与证据

- 仓库／分支／PR：`chrenguo-stack/HomeAssistant`；`fix/kf147-u3-recovery-and-error-visibility-20261110`；[PR #807](https://github.com/chrenguo-stack/HomeAssistant/pull/807)。
- 核对时 main：`3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`，tree `985af972aee13ee590d757b5d46080caffd925c3`。
- R17 源码候选：`642bb94b621ac5f991f690900602802d08e6bca0`，tree `a210ba3ca38454a9ebbf6a94258248cdb309c798`。
- R17 exact CI closure：`c70719af8cb888d574a8cb59cf68510e83cf6211`，tree `e4c5704dd3c73150f0fcc617da28f6294dc6bfb3`。
- 固定对象：executor blob `8538406a546a1c9dc85e1476c5c5d8feff88fb3b`；manifest blob `f67095c796414077a94b9bbb2ab25fce6f7f661e`；focused test blob `a313645fb3f68bcece93a73ca3e4b1c213053115`。
- 产品修复目标：`tools/n3w_t1_core_updater_ha_prepare_host.py` blob `e25275fbc23a6c04902c5c9e9a7e137926701a06`，SHA-256 `fd2898cf9d63ae143b9620e56a19e9789306c802440bb9424cfc30064bc53005`。
- 证据入口：[post-R16 只读取证归档](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6845682463)、[R17 源码与 CI 待闭合归档](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6845770188)、[Manager A-to-B](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43377682706)、[storage/image lifecycle](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43377682423)、[HA target binding](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43377682585)。

```text
R17_FRESH_CI=16_OF_16_SUCCESS
R17_CI_FAILURE=0
R17_CI_PENDING=0
PR_STATE=OPEN_DRAFT_UNMERGED
```

## 3. 必须继承的结论

- 已证实：R16 one-shot 已 claim/consume，结果为 `STOP:services_owner_not_active`，永久禁止重放。
- 已证实：R16 的单文件源码 rollback 已恢复旧 `prepare_host.py` 字节；运行环境 rollback 不完整。
- 已证实：最后一次实机只读取证中 OTA host daemon 为 `active/running`，services owner 为 `failed/failed`，Manager 与 Home Assistant 容器为 `exited_137`，Broker 仍为 `running`。
- 已证实：transaction 仍为 `U4_READY_TO_INSTALL`，SHA-256 `dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259`；USB 为兼容 ext4 `N3W-UPDATE` 且未挂载；R16 未造成 transaction、USB、U5 或 U6+ mutation。
- 已证实：KF-152 根因是 deployed services owner 对 OTA host daemon 的 reverse `Requires=` 生命周期传播；Stage B R3 已实机证明安全顺序为 stop services → stop host → apply/restore → start host → start services → validate。
- 已证实：R17 execute 与 rollback 都使用上述 dependency-safe 顺序，只激活 `prepare_host.py`，并严格验证 owner、Manager/HA/Broker、IPC 与未变化的 U4。
- 待确认：交接后的真实 T1 是否仍保持 exact post-R16 failed prestate；只能通过 R17 `--preflight-only` fresh 只读复核确认。
- 已排除：直接重放 R16；从 CI PASS 直接进入 R17 execute；在 preflight 前预先启动 services owner；任何 INSTALL/U5/U6+、USB mount/umount 或 transaction 写入。

## 4. 执行范围与授权

- 可继续：fresh rebind PR #807、branch、main 和 `c70719af…` exact package；从该 exact package 执行一次 R17 `--preflight-only`；保存本地私有 evidence；根据 PASS/STOP 做 GitHub 脱敏归档。
- 暂停边界：preflight PASS 后停止，不得同一命令或自动续跑 `--execute`。新的 one-shot 实机恢复必须由用户明确授权并绑定新的 authorized head/manifest，且 fresh CI 通过后方可执行。
- 授权状态：R17 `granted=false`、`claimed=false`、`consumed=false`、`replay_permitted=false`、`live_execution_authorized=false`。交接和 preflight 均不授予 live recovery 权限。

```text
R16_AUTHORIZATION_CLAIMED=true
R16_AUTHORIZATION_CONSUMED=true
R16_REPLAY_PERMITTED=false

R17_AUTHORIZATION_GRANTED=false
R17_AUTHORIZATION_CLAIMED=false
R17_AUTHORIZATION_CONSUMED=false
R17_LIVE_EXECUTION_AUTHORIZED=false

INSTALL_AUTHORIZED=false
U5_AUTHORIZED=false
U6_PLUS_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

## 5. 下一步

- 行动：读取本交接与适用仓库规则；fresh fetch 并核对 main、PR #807 branch head、`c70719af…` exact source/tree/blob 和 16/16 CI；从 detached exact head 运行 R17 executor 的 `--preflight-only`，使用用户本机已有的私有 SSH 参数与独立 evidence 目录。
- 完成条件：返回 `status=PASS`、`read_only=true`、`recovery_activation_eligible=true`、`read_only_preflight=true`、`remote_staging=false`、`authorization_claimed=false`、`authorization_consumed=false`、`transaction_mutation=false`、`usb_mutation=false`、`u5_transition=false`、`u6_plus=false`、`RC=0`；实机前态精确匹配 R17 manifest。
- 失败／停点：任何 `STOP`、状态漂移、源码/hash 漂移、transaction/USB 漂移或 transport 身份异常都立即停止；不做修复性服务启动、不 claim 授权、不自动重试。归档完整脱敏判定后再设计最小恢复入口。

```text
EXECUTOR=tools/execution_packages/n3w/r7a/kf152_r17_dependency_safe_source_activation_successor/executor.py
EXECUTION_METHOD=MAC_TERMINAL_DETACHED_EXACT_HEAD
EXECUTION_MODE=--preflight-only
REMOTE_STAGING=false
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
AUTO_EXECUTE_NEXT_GATE=false
```

R17 preflight PASS 后的新边界：

```text
NEXT_BOUNDARY=NEW_ONE_SHOT_R17_LIVE_RECOVERY_AUTHORIZATION
AUTHORIZATION_MUST_BIND=EXACT_SOURCE_HEAD_PLUS_MANIFEST_PLUS_GATE
FRESH_AUTHORIZED_HEAD_CI_REQUIRED=true
AUTOMATIC_RETRY=false
STOP_BEFORE_INSTALL_INTENT=true
```

## 6. 必读定位与归档

- 仓库规则：`AGENTS.md`；`docs/skills/greenhouse-github-development-efficiency/SKILL.md`；[工作上下文的最小读取集](N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)；`docs/development/development-artifact-archive-rules.md`。
- 任务资料：`docs/development/N3W_PROJECT_WORKING_CONTEXT.md` 顶部 stable authority；`docs/development/N3W_CURRENT_STATE.md` 顶部 authority；`docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 的 KF-152；`tools/execution_packages/n3w/r7a/kf152_r17_dependency_safe_source_activation_successor/{executor.py,manifest.json}`；`tests/tools/test_n3w_t1_kf152_r17_dependency_safe_source_activation_successor.py`。
- 按需补读：只有 preflight 与 frozen prestate 不一致或进入新授权设计时，补读 `docs/development/N3W_T1_KF147_STAGE_B_SYSTEMD_LIFECYCLE_R3_LIVE_VALIDATION_CLOSURE_20261110.md` 和 R16 terminal/forensic PR comments。
- 已归档：R16 terminal、post-R16 forensic、R17 source candidate 和 exact-head CI 均在 PR #807、固定 commits 与 workflow runs 中可恢复。
- 未归档重要资料：无。原始实机 evidence 保留在用户私有 evidence root；GitHub 仅保存脱敏结论与 hash 绑定，未公开私有 SSH locator 或 secret。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=true
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=true
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
REGRESSION_GUARD_ARCHIVED=true
UNTRACKED_CRITICAL_ARTIFACTS=0
UNARCHIVED_CRITICAL_KNOWLEDGE=0
UNARCHIVED_CRITICAL_RESULT_COUNT=0
NEXT_SAFE_ENTRY_POINT=R17_REAL_T1_READONLY_PREFLIGHT
```

新会话启动语：阅读本交接和适用仓库指令，fresh rebind PR #807、branch、main 与 R17 exact package。先执行 R17 真实 T1 只读 preflight；PASS 后停在新的 one-shot 实机恢复授权边界，不自动执行 recovery、INSTALL、U5 或 U6+。
