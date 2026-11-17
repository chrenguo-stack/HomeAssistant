# N3-W T1 U13B P1 Attempt 01 safe STOP / repair CI PASS → read-only Attempt 02 新会话交接 V1.0 — 2026-11-17

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 N3-W T1 U13B 真实 T1 只读绑定 P1。Attempt 01 因本地 package authority 组合错误在 SSH 前安全 STOP；该问题已修复并完成 exact-head 16/16 CI。本轮按用户要求停止开发并切换新会话。
- 已完成到：
  - U13B repository-side read-only preexecution source已在 `c02335e728797c953e623cf439d314c0affc3d32` CLOSED_PASS。
  - 物理验收路线已冻结：成功的历史 `U13A_COMMITTED` 事务不得被改写成 U13B 测试夹具；后续真实回滚验收需新 clean OTA transaction。
  - P1 initial package 在 `a215818bf39dbf26ea2af4e5fe6f681ad5de58d2` 完成 source/test/CI closure 后执行 Attempt 01。
  - Attempt 01 execution `u13b-p1-readonly01-20261117T114522Z` 返回 RC=2 / STOP，原因是本地 wrapper 错误地用当前 P1 HEAD 重新校验历史 U13A live manifest；STOP 发生于 SSH 前。
  - Attempt 01 已证实 `T1_ACCESS=false`，且无 transaction/USB/service/image/HA-data/authorization/U13B mutation。
  - P1 wrapper 已修复为只绑定并调用历史 U13A status-only 依赖闭包，不再复用历史 live manifest gate；同时修复 remote STOP 后 `T1_ACCESS` 证据语义。
  - 修复后的 exact execution-package authority 为 `e41723d8fa278021db95fc497426678a8a52d3c2`，16/16 workflow SUCCESS。
- 当前状态：**可继续**。Attempt 02 尚未执行。新会话从同一个 P1 gate 继续，先 fresh rebind；若 exact package / CI 无漂移，则直接执行真实 T1 read-only Attempt 02。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR 状态在交接前：OPEN / DRAFT / UNMERGED / MERGEABLE
- 核对时 main／本任务源码：
  - default main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - PR base: `ab277001dc9b31dcccb4d36b1507cec5f26d5a1d`
  - U13B read-only preexecution source closure: `c02335e728797c953e623cf439d314c0affc3d32`
  - P1 Attempt 01 package head: `a215818bf39dbf26ea2af4e5fe6f681ad5de58d2`
  - **P1 Attempt 02 exact execution-package authority: `e41723d8fa278021db95fc497426678a8a52d3c2`**
  - 后续本交接/current-state 的 docs-only commit 如前移 PR HEAD，不替代上述 Attempt 02 execution authority。
- 证据入口：
  - P1 physical-acceptance plan: `docs/development/N3W_T1_U13B_REAL_T1_PHYSICAL_ACCEPTANCE_AND_READONLY_PREEXECUTION_PLAN_20261117.md`
  - P1 executor: `tools/execution_packages/n3w/r7a/u13b_real_t1_readonly_binding_preflight/executor.py`
  - P1 manifest: `tools/execution_packages/n3w/r7a/u13b_real_t1_readonly_binding_preflight/manifest.json`
  - P1 focused tests: `tests/tools/test_n3w_t1_u13b_real_t1_readonly_binding_preflight.py`
  - HA target-binding run `44077610483`: SUCCESS
  - Manager A-to-B run `44077610686`: SUCCESS
  - Core Stack current-authority run `44077610747`: SUCCESS
  - PR progress comments: `6946247953`, `6946511662`, `6947220140`
  - Attempt 01 raw evidence remains in the operator's private Mac evidence root; do not upload raw/private path or secrets to public GitHub.

## 3. 必须继承的结论

- 已证实：
  - Historical real-T1 terminal state remains the prior durable `U13A_COMMITTED / COMMITTED` result until fresh P1 evidence says otherwise.
  - Historical successful U13A transaction is terminal and must not be modified/replayed merely to manufacture a rollback fixture.
  - P1 Attempt 01 did **not** access T1. Its RC=2 STOP was local and occurred before SSH.
  - Attempt 01 root cause is not T1 drift: the initial wrapper invoked the historical U13A live CLI with the current P1 commit as package authority, causing the immutable old live manifest to reject later legitimate `n3w_t1_core_updater_ha_usb.py` source evolution.
  - Repair does not weaken production validation and changes no product runtime source.
  - Repaired P1 binds the frozen historical U13A status-only dependency closure, constructs only a status plan, excludes `transition_source_b64` / `transition_source_sha256`, and invokes only remote mode `status`.
  - If SSH starts and a future remote STOP occurs, P1 now preserves `T1_ACCESS=true` rather than incorrectly reverting to false.
  - Exact repair head `e41723d8...` completed 16/16 CI SUCCESS.
- 待确认：
  - Attempt 02 execution-time PR/package freshness.
  - Fresh real-T1 Host transaction, bound USB mirror/filesystem identity, recovery identities and runtime state. Until Attempt 02 succeeds, these remain `UNKNOWN_FRESH`.
- 已排除：
  - Do not re-run Attempt 01 package `a215818b...`.
  - Do not treat the Attempt 01 STOP as T1/runtime failure.
  - Do not reintroduce historical U13A full live-manifest validation into P1.
  - Do not use current docs-only PR HEAD as a substitute for exact P1 execution authority `e41723d8...`.
  - Do not enter new clean OTA, U13B rollback, board action or merge from this handoff.

## 4. 执行范围与授权

- 可继续：
  - fresh rebind repository main / PR #807 / candidate branch;
  - re-check exact package `e41723d8fa278021db95fc497426678a8a52d3c2` and its 16/16 CI;
  - execute **one** P1 real-T1 read-only Attempt 02 using that exact package;
  - archive public-safe result and keep raw evidence private;
  - if Attempt 02 STOPs after actual SSH access, inspect the returned read-only evidence and perform repository-side diagnosis/repair only.
- 暂停边界：
  - `T1_MUTATION=false`
  - `USB_MUTATION=false`
  - `SERVICE_MUTATION=false`
  - `IMAGE_MUTATION=false`
  - `HA_DATA_MUTATION=false`
  - `U13B_LIVE_EXECUTION_AUTHORIZED=false`
  - `NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false`
  - `CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false`
  - `BOARD_ACCESS=false`
  - `MERGE=false`
  - any package/source/target/host-key/transaction drift: STOP affected execution and rebind first.
- 授权状态：
  - 来源：用户已明确批准 `NEXT_ONE_GATE=N3W_T1_U13B_REAL_T1_READONLY_BINDING_PREFLIGHT_20261117_01` 并已继续该 gate。
  - 目标：真实 T1 的 P1 fresh read-only binding only。
  - 候选：exact package `e41723d8fa278021db95fc497426678a8a52d3c2`。
  - 有效条件：fresh rebind 无漂移；exact CI 仍 16/16 SUCCESS；使用 status-only P1；不扩大到任何 mutation。
  - 当前状态：READ_ONLY AUTHORIZED / Attempt 01 finished safe STOP / Attempt 02 NOT EXECUTED。
  - 交接不新增授权；上述只读授权继续适用于同一 P1 gate 的 Attempt 02。

## 5. 下一步

- 行动：
  1. fresh rebind PR #807、default main、candidate branch。
  2. 核对 P1 exact package authority 必须仍是 `e41723d8fa278021db95fc497426678a8a52d3c2`，16/16 CI 仍 SUCCESS。
  3. 核对执行包实际内容：P1 wrapper / manifest / focused test 与 repair authority 一致。
  4. 使用新的临时 worktree checkout exact `e41723d8...`，使用新的 execution ID 和新的空私有 evidence root，执行 P1 Attempt 02。
  5. 若 PASS，归档 fresh binding，状态预期：
     - `STATUS=U13B_REAL_T1_READONLY_BINDING_PASS`
     - `READ_ONLY=true`
     - `FRESH_BINDING=true`
     - `EXPECTED_TERMINAL_U13A=true`
     - `ROLLBACK_ELIGIBLE=false`
     - `NEW_CLEAN_OTA_REQUIRED=true`
     - all current-probe mutation flags false.
  6. P1 PASS 后停止在新 clean OTA mutation boundary；不得自动进入 P3/P5。
- 完成条件：
  - Attempt 02 RC=0；
  - fresh terminal Host/USB/runtime binding PASS；
  - current-probe transaction/USB/service/image/HA-data mutation all false；
  - no authorization claim / no U13A transition / no U13B transition；
  - public-safe closure、CURRENT_STATE/INDEX、PR comment 对齐完成。
- 失败／停点：
  - local pre-SSH STOP：记录 `T1_ACCESS=false`，只修本地 package/source 问题。
  - post-SSH read-only STOP：记录 `T1_ACCESS=true`，保留零 mutation，并基于只读证据建立最小 repair/forensic。
  - any mutation request after P1 PASS：STOP and request/separately establish the appropriate authorization; do not infer it from P1.

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
  - formal handoff template: `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`, V1.4, blob `885fd63131e80936e5e1fe907378be08a0060f12` on main.
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md`：先读最顶部 P1 Attempt 01/repair 增量。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：定位本轮 P1 状态。
  - `docs/development/N3W_T1_U13B_REAL_T1_PHYSICAL_ACCEPTANCE_AND_READONLY_PREEXECUTION_PLAN_20261117.md`：P1/P2/P3/P4/P5 边界及物理验收路线。
  - `tools/execution_packages/n3w/r7a/u13b_real_t1_readonly_binding_preflight/manifest.json`：Attempt 02 package authority。
  - `tools/execution_packages/n3w/r7a/u13b_real_t1_readonly_binding_preflight/executor.py`：P1 唯一执行入口。
  - `tests/tools/test_n3w_t1_u13b_real_t1_readonly_binding_preflight.py`：Attempt 01 regression guards。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：仅在 Attempt 02 暴露新的可复现 failure 时按需补读/更新。
- 已归档：
  - P1 initial package/source progress comments: PR #807 comments `6946247953`, `6946511662`。
  - Attempt 01 STOP + repair progress: PR #807 comment `6947220140`。
  - repair exact package head `e41723d8fa278021db95fc497426678a8a52d3c2` + 16/16 CI。
  - 本 handoff 与 CURRENT_STATE/INDEX 在本次 docs-only archive commit 中对齐。
- 未归档重要资料：
  - Attempt 01 raw private evidence remains on the operator Mac in the private evidence root. Public GitHub intentionally retains only execution ID, result and public-safe reason.
  - No important chat-only engineering conclusion remains outside GitHub after this handoff archive.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，fresh rebind PR #807、default main、candidate branch，以及 exact P1 package `e41723d8fa278021db95fc497426678a8a52d3c2` 和 16/16 CI。继续 `NEXT_ONE_GATE=N3W_T1_U13B_REAL_T1_READONLY_BINDING_PREFLIGHT_20261117_01`，从 Attempt 02 开始；只执行真实 T1 read-only binding，不进入新 clean OTA、U13B live rollback、board 或 merge。
