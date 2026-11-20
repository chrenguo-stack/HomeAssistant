# N3-W T1 U11 R40 preauthorization source CLOSED_PASS → live authorization boundary new-chat handoff V1.0 — 2026-11-16

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：完成 R39 真实 T1 只读预检后的 U11 production controller、production host adapter 与 R40 one-shot target-install execution package；完成 exact-head CI 和独立源码复核；将状态归档后停在真实 U11 授权边界，供新会话继续。
- 已完成到：R40 preauthorization source exact head `a187e70f4c3aef4657be3d47983a404d61ea07e3` 已完成 16/16 CI SUCCESS；HA target-binding source job 实际执行 R40 测试并报告 `777 passed in 8.22s`；独立源码复核 PASS、`NEW_BLOCKER_COUNT=0`；closure、current state 和 index 已同步到 GitHub。
- 当前状态：**等用户明确授权**。R40 source/preauthorization 已 CLOSED_PASS，但 real T1 U11 未授权。当前必须停在 target image load、HA binding mutation、production services owner start、USB/host U11 persistence 之前。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: `#807`，OPEN / DRAFT / unmerged；最后核对时 mergeable=true
- 核对时 main／本任务源码：
  - repository main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - R40 exact source authority: `a187e70f4c3aef4657be3d47983a404d61ea07e3`
  - GitHub state-alignment parent head: `f4a1e6eb00d387a60f9dfe356bf0a23cb3731b4a`
  - PR base branch at handoff: `fix/kf147-post-destructive-stop-readonly-forensic-20261110`
  - PR base SHA: `ab277001dc9b31dcccb4d36b1507cec5f26d5a1d`
- Exact R40 blobs：
  - executor: `f3b42958bbffeeb1b49afc2ad6be9ad8e59c4425`
  - manifest: `53348743072e6a868b98fa6abd85cf5870e464b0`
  - focused test: `3c72c533b1715aa50a2c0f2035614c6ca66a5e01`
  - U11 controller: `33bd5e486db17b2476674009a6c23eecf750c12a`
  - U11 host adapter: `1ec5adaf63fe9ae5024be05922536cfe4f2168ba`
  - R39 executor dependency: `273ccfc6c7ba3d12da9f47af507e13543f29716a`
- 证据入口：
  - source-review closure: `docs/development/N3W_T1_U11_R40_PREAUTHORIZATION_SOURCE_REVIEW_CLOSURE_20261116.md`
  - R39 physical closure: `docs/development/N3W_T1_U11_R39_READONLY_PREFLIGHT_CLOSURE_20261116.md`
  - current state: `docs/development/N3W_CURRENT_STATE.md`
  - state index: `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - R40 package: `tools/execution_packages/n3w/r7a/u11_target_install_r40/`
  - HA target-binding CI run: `43812175507` / SUCCESS
  - Manager A-to-B CI run: `43812175493` / SUCCESS
  - storage lifecycle CI run: `43812175466` / SUCCESS
  - Core Stack authority CI run: `43812175342` / SUCCESS

## 3. 必须继承的结论

- 已证实：
  - R39 real-T1 read-only preflight 已 CLOSED_PASS：`U11_R39_READONLY_PREFLIGHT_PASS`, RC=0。
  - durable host transaction 仍为 `U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED`，SHA-256 `c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3`。
  - R38 authorization 已 claimed + consumed + permanently no-replay，不得重复 R38。
  - R39 证明 target internal image absent、predecessor internal image absent、Home Assistant predecessor container absent、Broker running、Manager quiesced、production HA binding 仍指向 predecessor。
  - R39 内部 Docker free bytes = `10887344128`，冻结的 U11 import requirement = `4950401057`，capacity PASS。
  - R40 package source authority 在 exact head 逐项复核，全部 blob match；不存在 source drift。
  - R40 manifest 当前为 preauthorization：`live_execution_authorized=false`, `granted=false`, claimed=false, consumed=false, replay=false。
  - local executor 在创建 T1 transport **之前**检查 live authorization；当前 preauthorization head 不能进入真实 T1 execution。
  - future R40 execution 必须先执行 embedded R39 read-only preclaim；preclaim PASS 后才可建立 R40 one-shot claim。
  - U11 controller 顺序已冻结为：exact target reverify → image load → runtime identity verify → HA binding publish → official production services owner start → exact Manager/Broker/HA runtime + production `/config` evidence → USB U11 metadata → host U11 transaction。
  - USB U11 metadata 必须先于 host U11 transaction。
  - R40 source 不执行 `wait_services()` / full listener、MQTT、HTTP acceptance，也不调用 U12 transition；U12 health acceptance 保持为后续独立 gate。
  - post-claim failure = fail-closed / recovery required / no replay；transport ambiguity 必须从 durable remote status reconciliation，禁止盲目重跑。
  - exact R40 source head CI = 16/16 SUCCESS；HA source job = 777 passed。
- 待确认：
  - 新会话开始时 fresh rebind PR #807、main、current state/index；确认 handoff 之后没有新的 source drift。
  - 真实 R40 执行前的实时 T1/USB/runtime 状态由 future grant-head executor 的 embedded R39 preclaim fresh 验证；本交接不把 R39 之后的运行状态推测为 fresh evidence。
  - 本次 source review 没有重新访问 T1。
- 已排除：
  - 直接从 preauthorization head 执行 R40：禁止，manifest fail-closed。
  - 重放 R38：禁止，已 consumed/no-replay。
  - 用 unmanaged `docker compose up homeassistant` 绕开 production owner：不采用。
  - 在 U11 内完成 HTTP/MQTT/listener 健康验收：不采用，属于 U12。
  - post-claim 自动 retry / partial compensation：不采用。
  - PR #807 merge：未授权。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind repository / PR / current state / handoff；
  - repository-only read/review；
  - **仅在用户明确授权 R40 live U11 后**，创建 grant-only successor manifest，将授权状态改为 granted/live=true，并保持已复核 controller/adapter/executor source 不变，除非发现明确 blocker；
  - grant-only successor 完成 fresh exact-head CI 和 final exact-source review。
- 暂停边界：
  - 当前禁止任何 real T1 target image load；
  - 禁止 HA Compose/env binding mutation；
  - 禁止 production services owner start；
  - 禁止 USB U11 metadata 或 host U11 transaction mutation；
  - 禁止 U10→U11 transition；
  - 禁止 U12+；
  - 禁止 Board access；
  - 禁止 merge PR #807。
- 授权状态：
  - R38 destructive authorization：claimed=true / consumed=true / replay=false。
  - R39 real-T1 read-only preflight：已执行 PASS，不授予 U11 mutation。
  - R40 live authorization：**无**。
  - R40 preauthorization manifest：`live_execution_authorized=false`, `authorization_state.granted=false`。
  - future explicit authorization target: `N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U11_R40_20261116_01`
  - future execution confirmation: `EXECUTE U11 R40 TARGET INSTALL: YES`
  - 交接本身不授予该 authorization。

## 5. 下一步

- 行动：
  1. fresh rebind repository main、PR #807、current state/index、本交接和 R40 exact source authority；
  2. 若用户尚未明确授权 R40 live U11：停止，不创建 grant state；
  3. 若用户明确授权：只创建 R40 grant-only successor，设置 live/granted=true；不得顺带扩大到 U12；
  4. 对 grant successor 跑 fresh exact-head CI；要求适用 workflow 全 SUCCESS；
  5. 再做一次 final exact-source review，确认授权状态、source blobs、R39 preclaim order、no-replay、U11/U12 boundary 未漂移；
  6. 只有以上全部 PASS 后，才能使用 exact grant head 运行一次 real T1 R40。executor 必须先 fresh embedded R39 preclaim；preclaim 未 PASS 时不得 claim；
  7. R40 real execution 成功后归档 U11 physical closure，再单独设计/复核 U12 target acceptance。
- 完成条件：
  - grant predecessor checks PASS；
  - exact target image loaded and portable/runtime identity verified；
  - Home Assistant binding exact target；
  - official production services owner active；
  - exact Manager/Broker peer identities preserved；
  - Home Assistant exact target runtime + production `/config` bind proven；
  - USB transaction phase and host transaction both durably reach `U11_TARGET_INSTALLED_STARTED`；
  - R40 success ledger durable；
  - no U12 acceptance claim；
  - private raw evidence retained locally; GitHub receives de-identified closure/status evidence。
- 失败／停点：
  - embedded R39 preclaim failure before claim：SAFE STOP，可在修复真实前置条件后重新做 read-only preclaim；不得创建 R40 claim。
  - R40 claim 之后任何失败或 transport ambiguity：authorization considered claimed/consumed/no-replay；禁止直接重跑 R40，必须先 status reconciliation / recovery planning。
  - actual durable U11 与 executor client result 冲突时，以 durable remote state + exact transaction/USB evidence为准，先 reconciliation，禁止基于 client timeout replay。
  - 任何 source/blob/target/authorization drift：停止受影响操作，重新 review。

## 6. 必读定位与归档

- 仓库规则：
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`，按 §12 minimum new-chat read set；
  - 当前 formal handoff template：`docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4 / blob `885fd63131e80936e5e1fe907378be08a0060f12`。
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md`：当前 R40 source closure / authorization boundary；
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：快速定位 R40/R39/R38；
  - `docs/development/N3W_T1_U11_R40_PREAUTHORIZATION_SOURCE_REVIEW_CLOSURE_20261116.md`：本轮 source review authority；
  - `docs/development/N3W_T1_U11_R39_READONLY_PREFLIGHT_CLOSURE_20261116.md`：最后一次 real-T1 physical authority；
  - `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_AND_DATA_ROLLBACK_ARCHITECTURE_V1.1_20261106.md`：U11/U12 lifecycle architecture；
  - `tools/n3w_t1_core_updater_ha_u11.py`：U10→U11 controller；
  - `tools/n3w_t1_core_updater_ha_u11_host.py`：production owner adapter；
  - `tools/execution_packages/n3w/r7a/u11_target_install_r40/`：R40 executor + preauthorization manifest；
  - `tests/tools/test_n3w_t1_u11_target_install_r40.py`：R40 security/order regression tests；
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：如 execution/recovery 出现已知失败模式时按需补读。
- 已归档：
  - R39 physical closure、R40 source-review closure、current state、state index、R40 source/tests/workflow 均已在 PR #807 分支；
  - PR #807 progress comments 已记录 R39 closure、U11 controller/adapter 和 R40 preauthorization CI/review 进展。
- 未归档重要资料：
  - R39 raw execution evidence 按项目规则仅保存在操作者私有本地 evidence root，不进入公开 GitHub；共享 closure 已包含恢复任务所需的非敏感结论。
  - 无必须依赖聊天文本才能恢复的工程事实。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind PR #807、main、current state/index 和 R40 exact source authority；若没有用户新的明确 R40 live U11 authorization，停在授权边界；若已明确授权，只创建 grant-only successor，完成 fresh CI 和 final exact-source review 后再进入一次性 real T1 R40，任何 post-claim 不确定状态都禁止 replay。
