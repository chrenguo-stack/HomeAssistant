# N3-W / T1 Home Assistant Mandatory-USB OTA
# KF-147 R9 terminal STOP → R10 U5 source activation preflight
# 新会话交接文档 V1.0 — 2026-11-12

`HANDOFF_TEMPLATE_VERSION=1.4`

本 handoff 使用 main 上正式 V1.4 模板生成：
- main head: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
- template blob: `885fd63131e80936e5e1fe907378be08a0060f12`
- PR #807 分支内仍存在 V1.3 历史副本，禁止用于新的 formal handoff。

## 1. 目标与停点

- 任务／交接原因：继续 KF-147 mandatory-USB Home Assistant OTA。R9 一次性 U4→U5 install-intent live attempt 已终态 STOP 并消费授权；已完成根因定位和 R10 source-activation successor 源码/测试/CI 收口。本轮在 R10 实机 preflight 前停止并切换新会话。
- 已完成到：
  - R9 read-only preflight：PASS。
  - R9 live：STOP，`ha_ota_ipc_action_invalid`。
  - R9 authorization：claimed=true / consumed=true / replay=false。
  - R9 live 未产生 transaction/USB/U5/U6+ mutation。
  - 根因已证明：repository U5 source 支持 INSTALL，但 live T1 尚未部署对应三文件 U5 source slice。
  - R10 successor package、测试、KNOWN_FAILURES guard、CI 接线完成。
  - R10 syntax-only CI defect 修复后，四项适用 CI 全部 SUCCESS。
- 当前状态：**可继续**。新会话从 R10 `--preflight-only` 开始；本交接不授权 R10 live source deployment。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: #807，OPEN / DRAFT / UNMERGED
- 核对时 main／本任务源码：
  - main at alignment: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - R10 validated source head: `66a29f058f13cca34c7fdb8e7b4267f839295982`
  - later alignment commits are docs-only; fresh rebind PR head before any execution.
- R10 package:
  - `tools/execution_packages/n3w/r7a/kf147_u5_source_activation_successor/executor.py`
  - executor blob: `17a708c0d3189fc007dbef9ceeeb4253a4d20b00`
  - manifest blob: `f05fabad818625482d25a1f28a2881956d832a8b`
- R10 exact three-file source slice:
  - `tools/n3w_t1_core_updater_ha_ipc.py`
  - `tools/n3w_t1_core_updater_ha_prepare.py`
  - `tools/n3w_t1_core_updater_ha_prepare_host.py`
- CI evidence:
  - Target binding run `43125842749`: SUCCESS
  - Manager A-to-B run `43125842806`: SUCCESS
  - Fast source/exact closure run `43125843158`: SUCCESS
  - Public repository safety run `43125843096`: SUCCESS
- Historical failed Target-binding run `43054454694`:
  - failure = local R10 executor Python syntax error caused by nested triple-quoted IPC probe;
  - repaired by delimiter-only change + manifest blob rebind;
  - no architecture/product/T1-state impact.

## 3. 必须继承的结论

- 已证实：
  - R9 is terminal and non-replayable.
  - R9 live result:
    - `authorization_claimed=true`
    - `authorization_consumed=true`
    - `transaction_mutation=false`
    - `usb_mutation=false`
    - `u5_transition=false`
    - `u6_plus=false`
    - `split_state_detected=false`
  - R9 root cause is **source/deployment authority mismatch**, not a newly introduced U5 source defect.
  - live installed IPC accepts only `PREPARE / CONFIRM_USB_ERASE`; later U5 repository IPC adds `INSTALL`.
  - live installed `prepare.py` also lacks `revalidate_and_request_install()`; therefore successor must deploy the complete exact three-file slice, not an IPC-only patch.
  - last-proven host transaction = `U4_READY_TO_INSTALL`.
  - last-proven host transaction SHA-256 = `dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259`.
  - last-proven USB transaction metadata phase = `U4_READY_TO_INSTALL`.
  - exact target archive remains SHA-256 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`, size `835309535`.
  - R10 is source-activation only: no INSTALL intent, no transaction/USB metadata mutation, no U5/U6+ transition.
  - R10 uses dependency-safe lifecycle:
    `stop services-owner -> stop host OTA -> atomic 3-file activation -> start host OTA -> start services-owner`.
  - once lifecycle switching starts, failure requires at most one exact-source rollback.
- 待确认：
  - fresh R10 preflight must re-confirm consumed R9 terminal state, exact Host U4, exact USB U4 metadata, writable bound USB, exact target archive, predecessor three-file source, runtime dependencies, services/containers and IPC READY_TO_INSTALL.
  - PR head and R10 package authority must be fresh-rebound before execution because docs-only alignment commits followed the validated source head.
- 已排除：
  - **R9 replay**：永久关闭。
  - **绕过 IPC 直接写 U5**：关闭。
  - **只替换 IPC 白名单**：关闭；prepare/prepare_host 同属必要 U5 source slice。
  - **把 repository capability 当成 live deployed capability**：关闭；已写入 KF-147 regression guard。
  - **自动进入 U6/U9/HA replacement**：关闭。

## 4. 执行范围与授权

- 可继续：
  - fresh repository/PR/package rebind；
  - R10 source review、测试、CI 复核；
  - R10 `--preflight-only` real-T1 只读执行；
  - GitHub 归档。
- 暂停边界：
  - R10 三文件 live source deployment；
  - host/services lifecycle mutation；
  - 任何新的 INSTALL intent；
  - U5、U6+；
  - Home Assistant / Manager / Broker product mutation；
  - board access；
  - PR merge。
- 授权状态：
  - R9 authorization：claimed=true / consumed=true / replay=false / terminal STOP。
  - R10 authorization：
    - `live_execution_authorized=false`
    - `granted=false`
    - `claimed=false`
    - `consumed=false`
    - `replay_permitted=false`
  - **当前没有 R10 live source deployment 授权。**
- 用户提出的执行优化：
  - 新会话从 R10 `--preflight-only` 开始；
  - 可以评估将 fresh preflight 与后续新版本 source deployment 合并为一个受控 live task。
  - R10 `--execute` 本身已经在 staging/mutation 前执行 fresh remote preflight，因此技术上可采用“授权后的单次 execute 内置 preflight → PASS 才部署”的组合模式。
  - 若采用组合模式，仍必须先获得**新的明确 R10 live authorization**，把 manifest 授权态冻结并完成 authorized-source CI；本 handoff 不构成该授权。

## 5. 下一步

- 行动：
  1. fresh rebind PR #807、branch、R10 executor/manifest/test、四项 CI 与 current-state docs。
  2. 核对 R10 package 实际执行合同，特别是：preflight 在 staging 前、R9 terminal exact binding、U4 Host/USB binding、三文件 predecessor/target binding、rollback 触发条件。
  3. 默认先执行 R10 `--preflight-only`。
  4. 若用户希望减少一次重复 preflight，可在完成第 1–2 步后评估组合模式：
     - 先申请新的 R10 live authorization；
     - 授权 commit + tests + exact CI；
     - 只执行一次 R10 `--execute`，由 executor 内置 fresh preflight；preflight 不 PASS 时不得 staging 或 mutation。
- 完成条件：
  - standalone preflight 路线：
    - `status=PASS`
    - `read_only=true`
    - R9 consumed terminal exact；
    - Host=U4；
    - USB metadata=U4；
    - exact target/source/runtime/services/containers/IPC all bound；
    - mutation=false。
  - combined route 若后续被授权：
    - fresh preflight PASS 后才允许 staging；
    - exact three-file source activation PASS；
    - Host/USB 仍 U4；
    - IPC remains READY_TO_INSTALL；
    - no INSTALL / no U5 / no U6+；
    - STOP at `STOP_AFTER_U5_SOURCE_ACTIVATION_AND_U4_POSTVALIDATION_BEFORE_NEW_INSTALL_INTENT_PREFLIGHT`.
- 失败／停点：
  - preflight STOP：不修 live T1，先分类 drift/root cause。
  - live source activation 若后续授权并失败：禁止自动 retry；按 executor contract 最多一次 exact-source rollback；归档真实 host/service/source/U4 状态后 STOP。
  - 任何 authority/source/target/authorization drift：STOP。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`
- 任务资料：
  - 本 handoff；
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 中 KF-147 R9 source/deployment authority mismatch；
  - `tools/execution_packages/n3w/r7a/kf147_u5_source_activation_successor/manifest.json`
  - `tools/execution_packages/n3w/r7a/kf147_u5_source_activation_successor/executor.py`
  - `tests/tools/test_n3w_t1_kf147_u5_source_activation_successor.py`
  - 正式 V1.4 template authority：main `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d` / blob `885fd63131e80936e5e1fe907378be08a0060f12`。
- 已归档：
  - PR #807 中：
    - R9 read-only PASS；
    - R9 live terminal STOP；
    - R9 root-cause classification；
    - R10 successor preparation；
    - R10 Target-binding syntax failure/repair；
    - fresh exact CI closure。
  - public current-state / index / working-context 已更新到 R9→R10 状态。
- 未归档重要资料：
  - 无必须公开归档的关键工程结论。
  - operator-local raw evidence paths remain private/ephemeral and are not copied to GitHub；public-safe state/hash summaries already archived。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

```text
阅读：
docs/development/N3W_T1_KF147_R9_TERMINAL_STOP_TO_R10_SOURCE_ACTIVATION_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261112.md

同时读取：
- AGENTS.md
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- tools/execution_packages/n3w/r7a/kf147_u5_source_activation_successor/manifest.json
- tools/execution_packages/n3w/r7a/kf147_u5_source_activation_successor/executor.py
- tests/tools/test_n3w_t1_kf147_u5_source_activation_successor.py

正式 handoff 模板 authority：
main@3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
blob=885fd63131e80936e5e1fe907378be08a0060f12

fresh rebind PR #807 和当前 branch/head。
不要使用 PR 分支中的旧 V1.3 template 生成新 handoff。

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

本轮先从：
R10 --preflight-only
开始。

可以评估把 preflight 与 R10 新版本三文件 source deployment 合并到一个授权后的单次 execute；但当前没有 R10 live authorization。若采用组合模式，必须先完成新的明确授权、授权 source commit 与 exact CI，并确保 executor 在 staging/mutation 前 fresh preflight fail-closed。

禁止重放 R9 consumed authorization。
禁止自动进入 INSTALL/U5/U6+/U9。
禁止 board access 和 merge。
```
