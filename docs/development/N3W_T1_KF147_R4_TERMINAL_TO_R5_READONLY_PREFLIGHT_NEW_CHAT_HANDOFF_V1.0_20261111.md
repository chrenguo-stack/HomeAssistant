# N3-W T1 KF-147 R4 Terminal → R5 Read-only Preflight
# 新会话交接文档 V1.0 — 2026-11-11

`HANDOFF_TEMPLATE_VERSION=1.4`

> 本交接按 main 上正式 V1.4 模板生成。PR #807 分支内的历史模板副本仍为 V1.3，禁止用于新的 formal handoff。
> V1.4 authority: main commit `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`, template blob `885fd63131e80936e5e1fe907378be08a0060f12`.

## 1. 目标与停点

- 任务／交接原因：继续“温室环境监测系统（ESP32-C6）”N3-W 的 KF-147 Mandatory USB Home Assistant OTA 收口。当前对话已完成 R4 live recovery 的终态分类、无下载根因定位、产品源码永久修复、R5 permission-only successor 设计与 CI 闭环。因上下文较长切换新会话。
- 已完成到：
  - R4 one-shot authorization 已 claim + consume，最终 `STOP / Stop:u3_recovery_timeout`，不可 replay；
  - 实机 IPC 已证明 R4 daemon 的 U3 resume worker 因 `usb_runtime_directory_metadata_invalid` 退出；
  - 实机只读 stat 已证明绑定 USB 上 `n3w-update` 为 `uid=0 gid=999 mode=0770`，`transaction` 为 `0700`，`target` 不存在；
  - 源码根因已证明：旧 `sync_transaction_metadata()` 通过 `parents=True` 隐式创建 `n3w-update`，中间父目录权限不满足后续 private-directory contract；
  - 产品源码已改为先显式创建/校验 `n3w-update`，再创建 `transaction`；
  - R5 fail-closed executor 已实现：只允许精确 `0770→0700` 权限修复 + fsync + service restart + existing U3 resume；
  - R5 source/exact CI 已全部通过。
- 当前状态：可继续。下一步只进入 **R5 只读 preflight**；不得直接执行 R5 live permission repair。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state at handoff: OPEN / DRAFT / mergeable / not merged
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - R5 source + CI authority head: `58b9887e227e6b02b200ee2d996751c231b597ea`
  - PR base: `ab277001dc9b31dcccb4d36b1507cec5f26d5a1d`
- R5 exact source blobs：
  - `tools/n3w_t1_core_updater_ha_prepare_host.py` = `fc5577b9aecc405a24fe1933a3597bc2f80f0e20`
  - `tools/execution_packages/n3w/r7a/kf147_u3_bound_media_recovery/executor.py` = `f4d7adcd3522351244d592f24b7b3f80dab176c6`
  - `tools/execution_packages/n3w/r7a/kf147_u3_bound_media_recovery/manifest.json` = `1bfad10e1269cf5a78ab63ec35e146a1cf2272b0`
  - `tests/tools/test_n3w_t1_kf147_u3_bound_media_recovery.py` = `87f08afdc598538fad56408bbdf54efc75c75bea`
  - retired Host-A1 authority alignment manifest blob = `334d1241c4bb6447dcb3d2ddc02bdaad21fc808b`
- 证据入口：
  - source design / runtime root-cause / R5 contract:
    `docs/development/N3W_T1_KF147_U3_BOUND_MEDIA_RECOVERY_AND_ERROR_VISIBILITY_SOURCE_DESIGN_20261110.md`
  - R4 terminal closure PR comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6773943605
  - R5 exact live metadata proof + fail-closed successor PR comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6773884269
  - R5 authority repair / CI revalidation PR comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6773969324
- CI authority：
  - Target-binding run `42862413016`: SUCCESS
    - `source` = SUCCESS
    - `exact-binding` = SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/42862413016
  - Manager A-to-B run `42862413541`: SUCCESS
    - `source` = SUCCESS
    - `exact-manager-slice` = SUCCESS
    - `pre-u1-v2-simulation` = SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/42862413541
  - same-head public safety / fast closure / applicable CI also SUCCESS.

## 3. 必须继承的结论

- 已证实：
  - durable transaction remains `U3_TARGET_DOWNLOADING_VERIFYING / ACTIVE`, `target_artifact_verified=false`;
  - bound USB filesystem UUID remains `967cf065-abe5-49ee-8499-7c3f50d2c48f`;
  - target archive remains Home Assistant 2026.10.4 ARM64, exact size `835309535`, SHA256 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`;
  - R4 authorization is consumed and non-replayable;
  - R4 final executor result is `STOP / Stop:u3_recovery_timeout / RC=2`;
  - R4 service restart did occur; daemon restarted and reopened the UUID-bound partition;
  - daemon IPC status as admitted UID 999 returned `phase=ERROR / error_code=usb_runtime_directory_metadata_invalid`;
  - R4 target download never started: no target dir, no `.homeassistant-target.*`, no external HTTPS download socket, no meaningful RX growth;
  - exact live permission defect is `n3w-update uid=0 gid=999 mode=0770`; `n3w-update/transaction mode=0700`; target dir absent;
  - permanent product-source fix and R5 successor tests are CI green.
- 待确认：
  - all live T1 facts above must be rechecked fresh in R5 preflight before any live mutation;
  - R5 preflight must confirm the durable R4 `failure.json` exists with `first_failed_operation=Stop:u3_recovery_timeout`;
  - production Manager / Home Assistant / Broker continuity must be freshly revalidated.
- 已排除：
  - slow download / long SHA verification as explanation for the no-traffic period;
  - artifact URL / release / target SHA/size policy mismatch;
  - network download already in progress;
  - USB reformat/repartition as a valid recovery route;
  - any replay of R4 or prior consumed authorizations.

## 4. 执行范围与授权

- 可继续：
  - repository fresh rebind;
  - source/manifest/test read-only review;
  - GitHub CI/status review;
  - R5 **read-only preflight** using the exact R5 package in preflight mode;
  - GitHub evidence archival after the preflight.
- 暂停边界：
  - no R5 live execution;
  - no `chmod/fchmod` on T1 until a future fresh explicit R5 live authorization is granted;
  - no service restart in the read-only preflight;
  - no USB wipe/repartition/format/unmount;
  - no destructive confirmation replay;
  - no U5+;
  - no board access;
  - no merge.
- 授权状态：
  - R4 authorization: CLAIMED=true / CONSUMED=true / REPLAY_PERMITTED=false / terminal STOP;
  - R5 live authorization: NOT GRANTED;
  - R5 manifest at source authority head is fail-closed:
    `live_execution_authorized=false`,
    `authorization_state.granted=false`,
    `claimed=false`,
    `consumed=false`,
    `replay_permitted=false`.
  - 本 handoff 不授予 R5 live mutation 权限。

## 5. 下一步

- 行动：
  1. fresh rebind repository main, PR #807 and R5 source authority head `58b9887e227e6b02b200ee2d996751c231b597ea`;
  2. confirm target-binding run `42862413016` and Manager A-to-B run `42862413541` remain SUCCESS;
  3. independently re-read exact R5 executor/manifest/test and confirm fail-closed contract;
  4. execute **R5 preflight-only** against the real T1 using the existing SSH transport and exact package;
  5. preflight must remain read-only and verify:
     - R4 terminal `failure.json` and consumed/non-replay state;
     - exact U3 transaction binding;
     - exact USB UUID/fingerprint/model/capacity;
     - exact partition already mounted at the expected transaction mountpoint;
     - `n3w-update = root:999 / 0770`;
     - `transaction = root:999 / 0700`;
     - target directory absent;
     - OTA service active;
     - Manager / Home Assistant / Broker exact continuity.
  6. archive preflight result to PR #807.
- 完成条件：
  - `R5_PREFLIGHT=PASS`;
  - `READ_ONLY=true`;
  - no authorization claim/consume;
  - no filesystem mutation;
  - no service restart;
  - no USB mutation;
  - no U5+;
  - no production-container drift.
- 失败／停点：
  - any fresh drift => STOP and classify before changing anything;
  - preflight PASS => STOP before R5 live mutation and request/record a separate fresh explicit R5 authorization;
  - do not auto-execute live permission repair after PASS.

## 6. 必读定位与归档

- 仓库规则：
  - repository applicable instructions;
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`;
  - use the V1.4 template authority from main commit `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`; do not use the stale V1.3 template copy currently present on PR #807 branch.
- 任务资料：
  - this handoff;
  - `docs/development/N3W_T1_KF147_U3_BOUND_MEDIA_RECOVERY_AND_ERROR_VISIBILITY_SOURCE_DESIGN_20261110.md` — sections 5.3 and 7 are the direct R4→R5 authority;
  - `tools/execution_packages/n3w/r7a/kf147_u3_bound_media_recovery/executor.py` — exact R5 preflight/live execution contract;
  - `tools/execution_packages/n3w/r7a/kf147_u3_bound_media_recovery/manifest.json` — R5 fail-closed authorization and expected-live binding;
  - `tests/tools/test_n3w_t1_kf147_u3_bound_media_recovery.py` — R5 regression guards;
  - `docs/development/N3W_CURRENT_STATE.md`, `docs/development/N3W_CURRENT_STATE_INDEX.md`, `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` — read only targeted KF-147 / current updater sections as needed; do not let older historical state override fresh PR #807 evidence.
- 已归档：
  - PR #807 comments listed in section 2;
  - R5 source design and CI runs listed above.
- 未归档重要资料：
  - 无。operator-local private SSH locator and temporary evidence paths are intentionally excluded from public GitHub; all state required for the next gate is archived in public-safe form.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

```text
阅读：
docs/development/N3W_T1_KF147_R4_TERMINAL_TO_R5_READONLY_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261111.md

同时按需读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_KF147_U3_BOUND_MEDIA_RECOVERY_AND_ERROR_VISIBILITY_SOURCE_DESIGN_20261110.md

交接模板 authority 使用 main commit：
3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
中的 V1.4；不要使用 PR #807 分支上的旧 V1.3 模板副本。

fresh rebind：
- repository main
- PR #807
- R5_SOURCE_HEAD=58b9887e227e6b02b200ee2d996751c231b597ea
- target-binding CI run 42862413016
- Manager A-to-B CI run 42862413541

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

只进入：
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_U3_PERMISSION_REPAIR_TO_U4_R5_READONLY_PREFLIGHT_20261111_01

本轮边界：
LIVE_RUNTIME_MUTATION=false
SERVICE_RESTART=false
USB_MUTATION=false
USB_FORMAT=false
USB_REPARTITION=false
DESTRUCTIVE_CONFIRMATION_REPLAY=false
U5_PLUS=false
BOARD_ACCESS=false
MERGE=false

先独立复核 exact R5 executor/manifest/test 和 CI，再执行 preflight-only。
R5 preflight PASS 后停止，不自动进入 live permission repair。
R4 及所有已消费 authorization 均不得 replay。
```
