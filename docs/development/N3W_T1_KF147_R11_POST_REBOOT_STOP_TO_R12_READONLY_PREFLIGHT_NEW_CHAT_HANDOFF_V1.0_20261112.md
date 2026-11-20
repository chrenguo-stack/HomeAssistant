# N3-W KF-147 R11 post-reboot STOP → R12 read-only preflight 新会话交接
# 2026-11-12

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 Home Assistant 2026.10.4 mandatory-USB OTA。R11 live U4→U5 INSTALL-intent attempt 在 durable authorization claim 之前因 `usb_mount_missing` fail-closed；用户随后补充说明 T1 在执行前重启。已完成 R12 post-reboot U4 mount-restoration successor 的源码、测试、CI 和 GitHub 状态归档。切换新会话是为了从清晰停点直接执行 R12 real-T1 `--preflight-only`。
- 已完成到：
  - R10 三文件 source activation 已实机 PASS；当前安装的三文件 SHA-256 仍绑定为 IPC `a7d335c597771b0297f690d0e97fb3288f5f1c83fd670d8af00d76ca983e56ac`、prepare `4dc6226ae493f18b3dab2c8773c1d3687a8f5f1750a6b4d9fa791cebe22db596`、prepare_host `d7f1e5468e24446f3ade0e22778cebecc8cda0fed07179a8fccb55b9f7e4ff8a`。
  - R11 preflight 曾 PASS；随后 R11 live execute 在 T1 reboot 后 fail-closed：`STOP:usb_mount_missing`、`authorization_claimed=false`、`authorization_consumed=false`、无 transaction/USB/U5/U6+ mutation。
  - R12 successor 已实现并通过最终 required CI。
- 当前状态：**可继续，只读**。新会话第一项动作是 R12 real-T1 `--preflight-only`。本交接不授权 R12 live mount mutation，也不授权重试 R11。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state: OPEN / DRAFT / UNMERGED
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - **R12 exact executable/source authority:** `52b0b8aecbd0641e369227b4c4f636bacf876a6d`
  - R12 executor blob: `9f238bb71f5aa19c7c705861fceea2e5b7ca9460`
  - R12 manifest blob: `5f0bd8c1290a647fa9bd4bd7fbcad2bd92426e85`
  - R12 test blob: `e58de8d322c053f68576e72af75959eb6bcad494`
  - 后续 `CURRENT_STATE / INDEX / WORKING_CONTEXT / KNOWN_FAILURES / 本交接` 提交均为 docs-only；**不得把 docs-only branch head 替代为 R12 executable source authority**。
- 证据入口：
  - R12 Target binding CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43225405440 — SUCCESS
  - R12 Manager A-to-B CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43225405926 — SUCCESS
  - R12 Core Stack current authority CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43225405781 — SUCCESS
  - R12 fast source/exact CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43225405725 — SUCCESS
  - R12 Public repository safety CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43225405752 — SUCCESS
  - 本轮最终对齐时上述 5 项均为 terminal SUCCESS；查询 1 次即确认终态。
  - R11 reboot STOP / R12 source public-safe archive：PR #807 comments，包含 comment `6824579948` 及后续 docs-only authority-link repair 记录。
  - R12 executor: `tools/execution_packages/n3w/r7a/kf147_post_reboot_u4_mount_restoration_successor/executor.py`
  - R12 manifest: `tools/execution_packages/n3w/r7a/kf147_post_reboot_u4_mount_restoration_successor/manifest.json`
  - R12 tests: `tests/tools/test_n3w_t1_kf147_post_reboot_u4_mount_restoration_successor.py`

## 3. 必须继承的结论

- 已证实：
  - **实机 R11 STOP 是 preclaim fail-closed。** 输出明确为 `reason=Stop:usb_mount_missing`、`remote_returncode=2`、`authorization_claimed=false`、`authorization_consumed=false`、`transaction_mutation=false`、`usb_mutation=false`、`u5_transition=false`、`u6_plus=false`。
  - 用户明确补充：R11 live execute 前 T1 重启过一次。
  - 源码复核证明 OTA mount 位于 volatile `/run/n3w-t1-ota/media`；systemd OTA unit 会重建 RuntimeDirectory，但不会恢复此前 transaction mount。
  - 产品 `SubprocessPrepareBackend.reopen_bound_media()` 本身能按持久化 UUID / public fingerprint 重新找到并 mount 已绑定 USB；当前 gap 是 R11 harness 在 durable claim 前要求现有 mount 已存在。
  - R12 的设计不放宽 R11：R12 preflight 只接受 exact U4 + exact bound USB present-but-unmounted；live execute 若未来另行授权，仅恢复 transaction-derived writable mount，postvalidate 后 STOP before U5。
  - R12 最终 required CI 全部 SUCCESS，源码 authority 为 `52b0b8aecbd0641e369227b4c4f636bacf876a6d`。
  - 最后有证据支持的 transaction 仍是 `U4_READY_TO_INSTALL`，transaction SHA-256 `dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259`；HA 2026.10.4 target archive SHA-256 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`，size `835309535`。
- 待确认：
  - **R12 real-T1 fresh baseline = UNKNOWN_FRESH**。下一会话必须用 R12 `--preflight-only` freshly prove：R10 terminal/source slice、U4 transaction SHA、stable runtime、bound USB UUID/fingerprint、USB present but unmounted、无占用 mount target。
  - R12 preflight PASS 后才讨论 R12 live mount-restoration authorization。
  - R11 authorization 当前 technically `granted=true / claimed=false / consumed=false / replay=false`；其后续 reuse eligibility **尚未判定**。只有 R12 PASS 恢复并验证 expected U4 mount state 后才能重新决定；不得仅因“未消费”自动重放。
- 已排除：
  - 不是 2026.10.4 target archive 已知损坏；R11 在验证 mount 之前 fail-closed，没有产生新的 target/transaction mutation 证据。
  - 不是 R11 authorization consumption；claim/consume 均为 false。
  - 不允许直接复用旧 R8 writable-mount-restoration package：R8 绑定的是更早 source slice 与已挂载 `ro/norecovery` 前态，与当前 R10 新三文件 + post-reboot unmounted 前态不一致。
  - 不允许绕过 R12 直接手工 mount 后重跑 R11；这样会丢失 exact pre/post evidence 与授权边界。

## 4. 执行范围与授权

- 可继续：
  - 用户已明确要求：**新会话从执行 R12 real-T1 read-only preflight 开始**。
  - 因此可以 fresh rebind 后执行 R12 `--preflight-only`，读取 T1 当前状态并保存私有 evidence。
  - 在该只读 gate 内允许：SSH read-only access、block/mount inventory、transaction/source/runtime/IPC/USB identity readback、exact binding checks。
- 暂停边界：
  - R12 preflight 结束即暂停 live mutation。
  - **禁止**在本授权下创建 transaction mount directories、mount/remount USB、领取/消费 R12 authorization、推进 U5、重试 R11、进入 U6+、停止/替换 Home Assistant、修改 Manager/Broker/HA 产品、source deployment、board access、merge。
  - 若 R12 preflight STOP，先归因和归档，不自动修复实机状态。
- 授权状态：
  - R12 manifest：`live_execution_authorized=false`。
  - R12 authorization：`granted=false / claimed=false / consumed=false / replay_permitted=false`。
  - R12 live execute 需要新的明确授权；本交接不授予。
  - R11：用户先前一次性 authorization 仍 `granted=true / claimed=false / consumed=false / replay=false`，但当前 **AUTO_RETRY_R11=false**，直到 R12 closes 后另行判断 reuse eligibility。
  - R10 authorization 已 claimed+consumed，永久 non-replayable。

## 5. 下一步

- 行动：
  1. 读取本交接、`AGENTS.md`、minimum new-chat read set。
  2. fresh rebind PR #807、branch docs-only head、R12 exact source authority `52b0b8aecbd0641e369227b4c4f636bacf876a6d`；确认 R12 executor/manifest/test blobs仍精确匹配。
  3. **不要要求 branch HEAD 等于 R12 source authority**：交接后的 branch head 含 docs-only 归档。执行时建立 detached worktree at exact R12 source authority，并让 executor 的 `--expected-package-commit` 使用该 SHA。
  4. 使用私有上下文中的 T1 SSH/known-host/host-key 参数执行：
     `tools/execution_packages/n3w/r7a/kf147_post_reboot_u4_mount_restoration_successor/executor.py --preflight-only`。
  5. preflight 完成后，把 public-safe result 对齐 GitHub；私有 IP、known-host path、host key、原始设备身份和本地 evidence path 不写公开仓库。
- 完成条件：
  - 预期 `status=PASS`、`RC=0`、`read_only=true`、`restoration_eligible=true`。
  - `authorization_claimed=false`、`authorization_consumed=false`。
  - `runtime_directory_creation_attempted=false`、`writable_mount_attempted=false`、`writable_mount_restored=false`。
  - `host_state_mutation=false`、`usb_mutation=false`、`transaction_mutation=false`、`u5_transition=false`、`u6_plus=false`。
  - fresh baseline 必须证明 exact U4 transaction、current R10-activated three-file source、stable containers/service/IPC，以及 exact bound USB present but unmounted。
  - evidence 保存于用户私有本地 evidence root；公开 GitHub 只归档脱敏摘要。
- 失败／停点：
  - `STOP` / `RC=2` 时不得自动 rerun，也不得手工 mount。
  - 优先检查完整 JSON 的 `reason` 与 claim/mutation fields；如果仍在 preclaim，只按实际原因设计下一 gate。
  - 若意外出现任何 claim/mutation true，立即按 consumed/mutated state 处理，禁止把同一 authorization 当作未使用。
  - R12 preflight PASS 后下一停点是 **R12 live mount-restoration explicit authorization**，不是 R11 retry。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - [工作上下文的读取规则](../N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md` — 最新 R11 STOP / R12 CI closure / next gate。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md` — 当前状态索引。
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` — minimum read set 与稳定规则。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` — 优先读取最新 “KF-147 R11 post-reboot U4 mount precondition — R12 successor source CLOSED_PASS”。
  - `tools/execution_packages/n3w/r7a/kf147_post_reboot_u4_mount_restoration_successor/manifest.json` — exact gate/authorization/prestate/stop boundary。
  - `tools/execution_packages/n3w/r7a/kf147_post_reboot_u4_mount_restoration_successor/executor.py` — exact preflight/execute implementation。
  - `tests/tools/test_n3w_t1_kf147_post_reboot_u4_mount_restoration_successor.py` — fail-closed regression contract。
  - `docs/development/N3W_T1_KF147_U5_WRITABLE_MOUNT_RESTORATION_SOURCE_DESIGN_AND_PREEXECUTION_20261111.md` — 仅用于理解旧 R8 设计历史；**不得作为当前 executable authority**。
  - exact handoff template authority：main@`3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`，`docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`，blob `885fd63131e80936e5e1fe907378be08a0060f12`。
- 已归档：
  - PR #807: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - R12 source authority: https://github.com/chrenguo-stack/HomeAssistant/commit/52b0b8aecbd0641e369227b4c4f636bacf876a6d
  - CI runs：见第 2 节。
  - GitHub current-state / index / known-failure records已更新到 R12 CI CLOSED_PASS / read-only preflight next。
- 未归档重要资料：
  - R11 原始私有本地 evidence 仍保存在用户 Mac；出于安全原因，路径、SSH target、known-host path、host-key fingerprint 和原始设备标识不进入公开 GitHub。public-safe terminal result 与结论已归档，因此不影响团队继续。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。fresh rebind R12 exact source authority `52b0b8aecbd0641e369227b4c4f636bacf876a6d` 后，直接执行 real-T1 R12 `--preflight-only`；该步骤只读。到达 R12 live mount-restoration authorization boundary 时停止。
