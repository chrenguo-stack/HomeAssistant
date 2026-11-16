# N3-W T1 U11 R41 Attempt 03 repair CI PASS → real-T1 read-only Attempt 04 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：完成 R40 `STOP_POSTCLAIM` 后的 R41 successor read-only gate，证明当前 partial-U10 现场、R40 consumed/no-replay ledger、USB/recovery continuity、target runtime/binding、修复后的 effective supervision contract 和 post-load reserve，之后才允许讨论 successor live recovery。当前对话已完成 R41 Attempt 01–03 的只读执行、三处 bounded source repair 和最终 CI closure；因对话现场较长，切换新会话继续真实 T1。
- 已完成到：R41 最终 source head `d42776f768a0cab1ebf054e393fa64721d155dcb`；16/16 CI SUCCESS。HA target-binding run `43872081096` 的 source + exact-binding 均 SUCCESS，source suite 明确执行 R41 focused test并报告 `790 passed in 8.44s`。Attempt 03 已在真实 T1 只读执行并安全 STOP，根因已修复且 CI 通过。
- 当前状态：**可继续**。下一门且唯一真实 T1 操作为 `R41_REAL_T1_READONLY_ATTEMPT04`。新会话开始时必须 fresh rebind 目标、PR/head、manifest 和 CI；T1 target freshness 当前标记为 `UNKNOWN_FRESH`，不得直接沿用旧会话假定。

## 2. 代码与证据

- 仓库／分支／PR：`chrenguo-stack/HomeAssistant`；`fix/kf147-u3-recovery-and-error-visibility-20261110`；PR #807（OPEN/DRAFT/unmerged）。
- 核对时 main／本任务源码：
  - main = `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - R41 exact source = `d42776f768a0cab1ebf054e393fa64721d155dcb`
  - repository product source authority remains `5b32e1ae82104a42f9e4e6907fe44d9172e87615`；不要把 R41 repository/execution-package head误报为已部署产品 source revision。
- R41 exact blobs：
  - executor = `ec8bafdffd971c1695b0336b89833c86a7879749`
  - manifest = `44c6716b41e06f64214e3231df7f16c11325cf81`
  - focused test = `8cb9c95b2ae9a361910527545a98f967ed463b61`
  - exact in-memory U11 dependency = `33bd5e486db17b2476674009a6c23eecf750c12a`
- CI：
  - all workflows = `16_OF_16_SUCCESS`
  - HA target-binding = https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43872081096
  - Manager A-to-B = https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43872080921
- 固定源码／设计证据：
  - https://github.com/chrenguo-stack/HomeAssistant/blob/d42776f768a0cab1ebf054e393fa64721d155dcb/docs/development/N3W_T1_U11_POST_R40_SUCCESSOR_RECOVERY_GATE_DESIGN_READONLY_PREFLIGHT_SOURCE_20261116.md
  - https://github.com/chrenguo-stack/HomeAssistant/blob/d42776f768a0cab1ebf054e393fa64721d155dcb/tools/execution_packages/n3w/r7a/u11_postclaim_recovery_readonly_preflight/executor.py
  - https://github.com/chrenguo-stack/HomeAssistant/blob/d42776f768a0cab1ebf054e393fa64721d155dcb/tools/execution_packages/n3w/r7a/u11_postclaim_recovery_readonly_preflight/manifest.json
- 真实 T1 证据时间：
  - Attempt 01 = `u11-r41-readonly-20261116T110710Z`
  - Attempt 02 = `u11-r41-readonly02-20261116T114901Z`
  - Attempt 03 = `u11-r41-readonly03-20261116T124701Z`
- 原始 real-T1 evidence 保留在操作者私有 evidence root，不上传共享 GitHub；公开交接只保存 public-safe 结果。生产 T1 的 exact locator、known-host binding 等私有定位 authority 不写入公开交接。

## 3. 必须继承的结论

- 已证实：
  - R40 已 claimed + consumed，`replay_permitted=false`，永久禁止重放。
  - 当前 durable host transaction 和 USB phase 仍为 exact `U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED`；transaction SHA-256 = `c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3`。
  - R40 已加载 exact Home Assistant target 并发布 target Compose binding，但在 service start / host+USB U11 persistence 前 STOP；当前 services owner = failed/quiesced，Broker running，Manager/Home Assistant stopped。
  - Attempt 01 失败属于 transport argv 长度：远端 Python 未启动；修复为通过现有 SSH master stdin 流式传输，T1 不落临时源码。
  - Attempt 02 失败属于 R41 ledger model：R40 durable reason 实际是 `U11PartialMutationError:ha_usb_u11_partial_mutation_requires_recovery:target_owner_start:UpdaterError`；KF-162 的 nested `services_supervision_contract_drift` 由 source-repair authority + repaired supervision probe 证明，不应要求 failure ledger 保存不存在的 nested message。
  - Attempt 03 失败属于 R41 in-memory dependency gap：`n3w_t1_core_updater_ha_u11_host` 依赖 `n3w_t1_core_updater_ha_u11`。最终 repair 将 exact U11 blob 一并随 stdin 传入并按 host → U11 → U11-host 顺序仅在 `sys.modules` 内加载；focused test 已移除 ambient U11 module 以防 CI false-PASS。
  - Attempt 01–03 均为 read-only STOP；没有 transaction、USB、Compose、service、U11、U12/U13、board mutation。
  - 最终 R41 head `d42776f7…` 已 16/16 CI SUCCESS，focused suite 790 passed。
- 待确认：
  - 新会话中 fresh rebind 后，真实 T1 是否仍满足 R41 全部 predicates；当前记为 `UNKNOWN_FRESH`，必须由 Attempt 04 重新证明。
  - 若 Attempt 04 PASS，是否进入 successor live recovery 仍需单独设计/复核并取得明确 live authorization；R41 PASS 本身不授予该权限。
- 已排除：
  - 不再使用旧 SSH argv 方式。
  - 不再要求 R40 durable ledger 直接保存 nested `services_supervision_contract_drift`。
  - 不再依赖 CI/开发机 ambient `n3w_t1_core_updater_ha_u11` import。
  - 不允许通过 R40 replay、手工 `systemctl start`、Compose 手改或直接进入 U12/U13 绕过 recovery gate。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind repository main、PR #807、R41 source head、manifest/blob 和 CI；
  - 使用既有私有 target authority 重新绑定生产 T1；
  - 执行 **R41 Attempt 04 read-only preflight**；
  - 对 Attempt 04 结果做源码复核、模拟测试、GitHub public-safe 归档；这些工作可在既定范围内连续推进。
- 暂停边界：
  - Attempt 04 PASS 后停在 `STOP_AFTER_R41_READONLY_BEFORE_ANY_SUCCESSOR_LIVE_CLAIM`；
  - 禁止 R40 replay、live service start/restart、Compose/transaction/USB mutation、U11 transition、U12/U13、board access、merge；
  - 若 Attempt 04 STOP，先保存/读取其 private evidence 并按根因分类，禁止盲目重试或手工修现场。
- 授权状态：
  - R40 one-shot live authorization：**CLAIMED + CONSUMED + NO_REPLAY**。
  - R41 real-T1 read-only execution：manifest `real_t1_readonly_execution_authorized=true`，可继续 read-only Attempt 04。
  - successor live recovery：`live_recovery_authorized=false`，**无 live mutation 授权**。
  - U12/U13、board、merge：均未授权。
  - 本交接不新增任何权限。

## 5. 下一步

- 行动：
  1. 读取本交接、`N3W_CURRENT_STATE.md`、`N3W_CURRENT_STATE_INDEX.md`、R41 design/source 文档及 exact executor/manifest。
  2. fresh rebind main、PR #807、branch head；确认 R41 source authority仍为 `d42776f768a0cab1ebf054e393fa64721d155dcb` 或仅发生可证明的 docs-only advancement；若 executable/package blob 漂移则 STOP。
  3. 确认 HA target-binding run `43872081096` 和整轮 16/16 CI SUCCESS。
  4. fresh 恢复私有 T1 locator/known-host authority，验证目标唯一且 host-key binding 一致。
  5. 使用 exact R41 package 执行 **Attempt 04 read-only**，生成新的私有 evidence root；不得使用 Attempt 01/02/03 evidence root。
- 完成条件：
  - `status=U11_R41_POST_R40_READONLY_PREFLIGHT_PASS`
  - `successor_live_recovery_eligible=true`
  - `successor_live_recovery_authorized=false`
  - `r40_replay=false`
  - transaction/USB/target-load/Compose/service/U11/U12/U13/board mutation flags全部 false
  - SSH master cleanup PASS，新的 evidence root 保存完成
  - public-safe 结果对齐到 GitHub。
- 失败／停点：
  - 任一 predicate/transport/dependency/target binding 不匹配即 STOP；
  - 不重放 R40，不手工修服务，不直接推进 live recovery；
  - 先读取 Attempt 04 stdout/stderr/local_result，再决定是否为 harness/source/state drift；局部明确 source/harness bug可按项目规则修复并重新 CI，涉及 live mutation/design choice 时停下请求授权。

## 6. 必读定位与归档

- 仓库规则：读取适用 `AGENTS.md`；遵守 [N3W_PROJECT_WORKING_CONTEXT.md §12 minimum new-chat read set](../N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)。
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md`：最新权威现场与边界。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：最近阶段索引。
  - `docs/development/N3W_T1_U11_POST_R40_SUCCESSOR_RECOVERY_GATE_DESIGN_READONLY_PREFLIGHT_SOURCE_20261116.md`：R41 设计、Attempt 01–03 和三次 bounded repair。
  - `tools/execution_packages/n3w/r7a/u11_postclaim_recovery_readonly_preflight/executor.py` + `manifest.json`：Attempt 04 exact execution contract。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：KF-162 及通用 fail-closed/regression rules，按相关条目补读。
- 已归档：
  - source authority：`d42776f768a0cab1ebf054e393fa64721d155dcb`
  - R41 design/source fixed link：https://github.com/chrenguo-stack/HomeAssistant/blob/d42776f768a0cab1ebf054e393fa64721d155dcb/docs/development/N3W_T1_U11_POST_R40_SUCCESSOR_RECOVERY_GATE_DESIGN_READONLY_PREFLIGHT_SOURCE_20261116.md
  - CI fixed run：https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43872081096
- 未归档重要资料：无共享协作阻断。三次 raw T1 evidence 因包含私有 target/transport 信息按规则保留在操作者本地私有 evidence root，不上传 GitHub；其影响下一步的 public-safe 事实已全部归档。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

归档审计按 [development-artifact-archive-rules.md](../development-artifact-archive-rules.md) 执行。

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind main / PR #807 / R41 exact source and CI，再恢复私有 T1 target authority，执行 R41 Attempt 04 read-only preflight。若 PASS，先归档并停在 successor live recovery 独立授权边界；若 STOP，保持现场不变并从新 evidence 定位。
