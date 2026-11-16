# N3-W T1 U11 R40 post-claim recovery successor design / read-only preflight — 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：R40 real-T1 U11 one-shot 在 claim 后因 services-owner supervision contract false drift 停止。根因已经通过只读 forensic 证明，U11 supervision parser/adapter 源码修复已完成并通过 16/16 CI。本轮停止继续开发；新会话进入**新的 successor recovery gate 设计与只读预检**，不重放 R40。
- 已完成到：
  - R40 Attempt 01 本地 SAFE STOP：evidence root 非空，T1 未访问、授权未 claim；
  - R40 Attempt 02：`u11-r40-live02-20261116T063426Z`，RC=2 / `STOP_POSTCLAIM`；
  - R40 authorization 已 claimed + consumed + no-replay；
  - exact target image 已加载，HA production binding 已切到 `local/n3w-homeassistant:2026.10.4-5881590f`；
  - host transaction 与 USB phase 仍精确停在 `U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED`；
  - services owner failed/quiesced，Manager 与 Home Assistant stopped，Broker running；
  - 根因证明完成：旧 `LocalHost._service_unit()` 未按 systemd reset/replace 语义解释正式 `95-n3w-ha-ota.conf`；
  - U11 supervision source repair head `155f9a7b62d6b758fb87c109b3ffbf54aa5614c7`，16/16 CI SUCCESS；
  - GitHub 现场对齐完成于 `ee59308270bd6658f6ae48f495a9cd56053201e9`。
- 当前状态：**可继续 repository/source design 与 real-T1 read-only preflight；live recovery mutation 未授权。** R40 不可重放。U11 尚未 durable commit，U12/U13 尚未进入。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state at handoff: OPEN / DRAFT / UNMERGED / MERGEABLE
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - U11 supervision source-repair authority: `155f9a7b62d6b758fb87c109b3ffbf54aa5614c7`
  - state-alignment authority: `ee59308270bd6658f6ae48f495a9cd56053201e9`
  - historical R40 grant/execution head: `7649743b27f125c37ce360dafe5a3455ef10bbdc`
- 证据入口：
  - closure: https://github.com/chrenguo-stack/HomeAssistant/blob/ee59308270bd6658f6ae48f495a9cd56053201e9/docs/development/N3W_T1_U11_R40_POSTCLAIM_SUPERVISION_FALSE_STOP_SOURCE_REPAIR_CLOSURE_20261116.md
  - aligned current state: https://github.com/chrenguo-stack/HomeAssistant/blob/ee59308270bd6658f6ae48f495a9cd56053201e9/docs/development/N3W_CURRENT_STATE.md
  - aligned current-state index: https://github.com/chrenguo-stack/HomeAssistant/blob/ee59308270bd6658f6ae48f495a9cd56053201e9/docs/development/N3W_CURRENT_STATE_INDEX.md
  - KF-162: https://github.com/chrenguo-stack/HomeAssistant/blob/ee59308270bd6658f6ae48f495a9cd56053201e9/docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
  - source repair commit: https://github.com/chrenguo-stack/HomeAssistant/commit/155f9a7b62d6b758fb87c109b3ffbf54aa5614c7
  - HA target-binding CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43825253517
  - Manager A-to-B CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43825253528

生产/运行状态必须与仓库源码区分：
- repository/source repair 已闭环；
- real T1 仍是 R40 partial state，不得将 16/16 CI 解释为 U11 physical completion；
- 新修复源码尚未因此自动成为 T1 installed-source authority。

## 3. 必须继承的结论

- 已证实：
  - R40 authorization 已 consumed/no-replay；同一 R40 executor/authorization 永久禁止重放。
  - real T1 durable host transaction SHA-256 仍为 `c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3`，phase=`U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED`。
  - USB phase 同样仍为 U10；R40 没有写 USB U11 metadata，也没有写 host U11 transition。
  - target image 已存在：`local/n3w-homeassistant:2026.10.4-5881590f`；observed runtime image ID=`sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365`。
  - production HA binding 已指向 target。
  - Broker running；Manager stopped；Home Assistant stopped；services owner failed/quiesced。
  - R40 在新的 `systemctl start` 之前停止：failure window 无新的 services-owner journal、无 Docker container event、无 target HA container creation。
  - production `95-n3w-ha-ota.conf` 是 repository-owned 正式配置，不是 T1 漂移。
  - root cause 是旧 `LocalHost._service_unit()` 将 base + reset + replacement 的 systemd directive 误判为 drift。
  - source repair `155f9a7b...` 正确按 reset 语义解析 effective directive，并由 U11 要求 exact HA-OTA overlay；16/16 CI SUCCESS。
  - R39 false-PASS coverage gap 已证明：历史 R39 preclaim 没有验证 future U11 effective supervision contract。
- 待确认：
  - successor recovery 之前必须 fresh rebind 当前 PR/head，确认无新的 source drift；
  - fresh real-T1 read-only preflight 必须重新验证 R40 consumed failure ledger、exact U10 host/USB durable state、target image identity、target binding、Broker continuity、Manager/HA quiescence、services owner state、exact effective HA-OTA `ExecStart/ExecStop`；
  - successor 应如何使用 `155f9a7b...` repaired host helper：优先设计为 exact temporary/source-bound execution package，禁止假设 T1 已安装该修复；
  - successor 是否可直接复用现有 U11 controller 的部分逻辑，必须在 source design 中证明；原 `install()` 的初始前提与当前 partial state 不同，禁止直接调用后“试试看”。
- 已排除：
  - 不是 HA target image 已证明启动失败；R40 从未真正发起本轮服务启动；
  - 不是 OOM：历史 Manager exit 137 的 `OOMKilled=false`，且时间早于 R40；
  - 不是磁盘不足：R40 已成功完成 target load；
  - 不能通过手工 `systemctl start`、手工 Compose up 或重跑 R40 作为恢复方案；
  - 不能把旧 R39 PASS 当成 successor preclaim authority。

## 4. 执行范围与授权

- 可继续：
  - repository/source-only successor recovery gate 设计；
  - focused source review、simulation/unit/contract tests；
  - GitHub 归档与 CI；
  - 根据用户本轮明确要求，在新会话进入 **real-T1 read-only preflight**；只读访问不得改变服务、Compose、image、transaction、USB metadata 或 recovery ledger。
- 暂停边界：
  - successor live claim；
  - `systemctl start/restart/reset-failed`；
  - Docker/Compose create/start/up/remove；
  - Compose/env binding rewrite；
  - target/predecessor image delete/load/reload；
  - USB U11 metadata write；
  - host U11 transaction write；
  - U10→U11 mutation；
  - U12 acceptance；
  - U13A commit / U13B rollback；
  - board access；
  - PR merge。
  上述任何写操作均需新设计闭环、fresh exact binding 和单独明确授权。
- 授权状态：
  - R40 authorization: **CLAIMED=true / CONSUMED=true / REPLAY=false / RETIRED**。
  - successor source design: **AUTHORIZED by current user instruction**。
  - successor real-T1 read-only preflight: **AUTHORIZED by current user instruction**, subject to fresh target/host binding and strictly read-only execution.
  - successor live recovery mutation: **NOT_AUTHORIZED**。
  - U12/U13/board/merge: **NOT_AUTHORIZED**。

交接本身不授予任何额外权限。

## 5. 下一步

- 行动：
  1. fresh rebind main、PR #807、branch head、`155f9a7b...` source repair 与本 handoff；
  2. 读取 closure、Current State、KF-162；
  3. 设计新的 successor recovery gate，不复用 R40 authorization；
  4. successor preclaim 必须位于任何新 claim 之前，并至少验证：
     - exact R40 `authorization_claim.json` + `failure.json`，consumed/no-replay；
     - exact host U10 transaction SHA/phase；
     - exact USB U10 phase/mirror/recovery authority；
     - exact target image ref + runtime/portable identity；
     - production HA binding=target；
     - Broker exact continuity；
     - Manager/HA stopped；
     - services owner quiesced；
     - **effective systemd ExecStart/ExecStop 精确等于正式 HA-OTA overlay**；
     - no unexpected target HA container residue；
     - recovery assets/capacity remain valid；
  5. source-only design完成后实现只读 successor preflight package + focused tests；
  6. CI 通过后执行授权范围内的 real-T1 read-only preflight并归档；
  7. 到达“是否授权 successor live recovery”时停止，等待单独明确授权。
- 完成条件：
  - successor design 明确 partial-state input、preclaim、new authorization boundary、post-claim execution order、failure/reconciliation、no-replay；
  - read-only package 可证明当前 partial U10 state 与 repaired supervision contract；
  - focused tests/适用 CI PASS；
  - real-T1 read-only结果结构化归档；
  - 不发生任何 live mutation。
- 失败／停点：
  - 任一 durable state、image identity、binding、R40 ledger、USB mirror、Broker/Manager/HA state 或 effective systemd contract 不匹配 → fail-closed；
  - read-only transport ambiguity → 只做 read-back/reconciliation，不触发写操作；
  - source drift → 重新绑定并重新审查受影响 source；
  - 不得通过手工启动服务验证猜测；
  - 到达 live recovery claim 边界必须停止。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
- 任务资料：
  - `docs/development/N3W_T1_U11_R40_POSTCLAIM_SUPERVISION_FALSE_STOP_SOURCE_REPAIR_CLOSURE_20261116.md`：R40 failure、实机 forensic、root cause、source repair；
  - `docs/development/N3W_CURRENT_STATE.md`：最新 live/durable state；
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：阶段索引；
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：KF-162 与 no-replay/preclaim guards；
  - `tools/n3w_t1_core_updater_host.py` @ `155f9a7b...`：effective systemd directive 修复；
  - `tools/n3w_t1_core_updater_ha_u11_host.py` @ `155f9a7b...`：exact HA-OTA overlay contract；
  - `tests/tools/test_n3w_t1_core_updater_ha_u11_host.py` @ `155f9a7b...`：drop-in regression；
  - historical `tools/execution_packages/n3w/r7a/u11_target_install_readonly_preflight_r39/`：用于证明旧 preclaim coverage gap，只作历史参考，不作为 successor authority；
  - historical `tools/execution_packages/n3w/r7a/u11_target_install_r40/`：用于 consumed failure/ledger reconciliation，不得执行。
- 已归档：
  - state-alignment commit `ee59308270bd6658f6ae48f495a9cd56053201e9`；
  - source-repair commit `155f9a7b62d6b758fb87c109b3ffbf54aa5614c7`；
  - closure / Current State / Index / KF-162 均已进入 GitHub；
  - 临时 raw output 文件已从当前分支删除；其关键事实已提炼进 closure/current state/KF。
- 未归档重要资料：
  - 公开仓库：无；
  - 私有 raw T1/SSH evidence 仍保存在操作者私有证据区，按安全边界不上传 GitHub；公开交接所需的全部 continuation-critical 结论已经脱敏归档。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind main、PR #807、当前 branch head、source-repair authority `155f9a7b62d6b758fb87c109b3ffbf54aa5614c7` 与 state-alignment authority `ee59308270bd6658f6ae48f495a9cd56053201e9`。进入新的 U11 post-R40 successor recovery gate **设计与只读 preflight**；先证明 exact partial U10 state 与 repaired effective HA-OTA supervision contract，再实现/执行只读 preflight。不得重放 R40，不得进行 live recovery mutation，不得进入 U12/U13，不得访问板卡，不得合并 PR。
