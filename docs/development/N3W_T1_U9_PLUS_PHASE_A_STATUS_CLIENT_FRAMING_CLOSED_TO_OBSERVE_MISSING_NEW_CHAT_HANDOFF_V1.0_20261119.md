# N3-W T1 U9+ Phase A status-client framing closed → observe-missing — new chat handoff V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

> 本文按 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4 生成，只保存当前阶段增量。长期规则以 `N3W_PROJECT_WORKING_CONTEXT.md` 为准；fresh repository/runtime/live evidence 优先。公开交接不包含私网地址、SSH host key、known-hosts 路径、凭据或原始设备身份。

## 1. 目标与停点

- 任务／交接原因：继续已授权的 real-T1 U9+ bounded-recovery Phase A。当前目标是从已经真实完成的 destructive U10 + missing-media boot 继续，先用修复后的 Phase-A acceptance IPC client 只读证明 `RECOVERY_MEDIA_REQUIRED`，然后到达物理暂停边界；本轮因已完成根因闭环、源码修复和 22/22 CI closure，切换新会话降低上下文负担。
- 已完成到：
  - destructive U10 已真实执行；
  - 第一次缺绑定恢复介质 boot 已完成；
  - 早先 `repair-missing-status` 已把 exact candidate IPC 写入 staged candidate 并重启 candidate OTA daemon，但随后被验收脚本自身 IPC framing 缺陷误判为 `ota_status_rejected`，因此 repair receipt 未写入；
  - 12/12 raw IPC status 样本稳定复现 `accepted=false / code=ota_host_rejected / phase=RECOVERY_MEDIA_REQUIRED / error_code=null`；
  - 同一真实 U10 持久状态 + 同一 candidate 源码在独立进程中直接 `executor.status()` 和 dispatcher 均正常返回 `accepted=true / code=status / phase=RECOVERY_MEDIA_REQUIRED`；
  - 根因已精确证明为 Phase-A acceptance client `ipc_status()` 缺少 `sock.shutdown(socket.SHUT_WR)`，不是 recovery engine、durable transaction、product Manager IPC 或新的 status-projection 产品缺陷；
  - 修复与回归测试已提交，当前 source head `c8e7d71aa2118fa3e1c6599d8da560097f6841ac` 的 22 个 applicable workflow 全部 SUCCESS。
- 当前状态：**可继续到 read-only `observe-missing`，但当前会话在交接处停止，不执行新的 T1 操作。**

当前最后实机证据：

```text
TRANSACTION_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
TRANSACTION_STATUS=ACTIVE
TRANSACTION_SHA256=5d58cfc99d5bf55a7fd38dda00cb40de241ca500269573316a60040de71e5b34
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

BOUND_RECOVERY_USB_PRESENT=false
PREDECESSOR_IMAGE_PRESENT=false
TARGET_IMAGE_PRESENT=false
MISSING_MEDIA_CHECKPOINT_EXISTS=false
STATUS_REPAIR_RECEIPT_EXISTS=false

CANDIDATE_IPC_SHA256=8c0172124a7ad41d0834dc98c44a16e0486ccd8450a6a367d34e396bb499d513
CANDIDATE_DAEMON_SHA256=0083f1cdeeb502a5250f8ef9b0c35a8ee714fde6d90d71cee1d63d6fada83966
OTA_DAEMON=ACTIVE_RUNNING
CANDIDATE_OVERRIDE=ACTIVE

T1_POWER=ON
BOUND_RECOVERY_USB=PHYSICALLY_REMOVED
DO_NOT_POWER_CYCLE_YET=true
DO_NOT_REINSERT_USB_YET=true
```

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: `#807`
  - PR state at source closure: OPEN / DRAFT / UNMERGED / mergeable
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - prior executable authority: `ebdccfd471a56df377094bf82aeec6c1617dd93d`
  - acceptance-client framing fix: `1c733de0064fb5bff8158eaeb45d146cffb58699`
  - **current executable/source authority: `c8e7d71aa2118fa3e1c6599d8da560097f6841ac`**
  - compare `ebdccfd...c8e7d71`: exactly +3 commits, consisting of one earlier handoff document, one acceptance-client framing repair, and one regression-test commit.
  - this handoff commit is docs-only and must not replace `c8e7d71...` as executable/source authority.
- source changes:
  - `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance.py`: after `sock.sendall(...)`, now calls `sock.shutdown(socket.SHUT_WR)` before `recv()`;
  - `tests/tools/test_n3w_t1_u9plus_fault_acceptance.py`: regression requires send → SHUT_WR → recv ordering.
- exact candidate bytes currently proven on T1:
  - IPC SHA-256: `8c0172124a7ad41d0834dc98c44a16e0486ccd8450a6a367d34e396bb499d513`
  - daemon SHA-256: `0083f1cdeeb502a5250f8ef9b0c35a8ee714fde6d90d71cee1d63d6fada83966`
- evidence entry:
  - PR root-cause/source-closure alignment comment: `#issuecomment-7010192569`
  - persistent 12/12 sampling comment: `#issuecomment-7009743684`
  - direct-source/dispatcher forensic comment: `#issuecomment-7008560851`
  - root-cause repair comment: `#issuecomment-7009858995`
  - previous Phase-A handoff: `docs/development/N3W_T1_U9_PLUS_PHASE_A_U10_MISSING_MEDIA_STATUS_REPAIR_CI_WAIT_NEW_CHAT_HANDOFF_V1.0_20261119.md`
  - Phase-A plan: `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE_PHASE_A_PLAN_20261119.md`
  - exact execution package: `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance.py`
  - exact manifest: `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance_manifest.json`

CI on executable/source authority `c8e7d71aa2118fa3e1c6599d8da560097f6841ac`:

```text
TOTAL=22
SUCCESS=22
FAILURE=0
PENDING=0
CI_GATE=PASS
```

Representative SUCCESS runs:
- fast source/exact closure: `44529230537`
- P3 live/read-only source: `44529230649`
- P3 acceptance clean OTA source: `44529230547`
- Core Stack current authority: `44529230660`
- storage/image lifecycle: `44529230383`
- Manager A-to-B: `44529230613`
- HA 2026.10.3 target binding: `44529230481`
- HA 2026.10.4 target binding: `44529230447`
- HA 2026.10.4 same-version acceptance artifact: `44529230714`
- public repository safety: `44529230811`

## 3. 必须继承的结论

- 已证实：
  - real T1 仍处于 U10；transaction SHA-256 仍为 `5d58cfc...`，authorization claimed/consumed 未漂移。
  - bound recovery USB 仍缺失；predecessor image 和 target image 均不存在；没有进入 U11。
  - candidate IPC/daemon 与 expected bytes 完全一致，candidate OTA daemon 正常 active/running。
  - 12/12 rejection 不是 transient race；但它也不是 recovery 状态失败。response 内的 `phase=RECOVERY_MEDIA_REQUIRED` 一直稳定。
  - 独立同源码/同持久状态调用证明产品 status 逻辑和 dispatcher 均可正常返回 accepted=true。
  - exact root cause：Phase-A acceptance client 没有按既有 IPC framing contract 在发送请求后 half-close 写端；server 等 EOF 时触发 read timeout，外层异常包装成 `accepted=false/code=ota_host_rejected`，fallback status 又正确投影 `RECOVERY_MEDIA_REQUIRED`。
  - production Manager client 和 product IPC tests 原本就使用 `shutdown(SHUT_WR)`，因此这是 acceptance-tool-only defect。
  - `c8e7d71...` 已通过 22/22 applicable CI。
- 待确认：
  - 新会话执行前，fresh runtime 必须重新确认 T1 仍是同一 U10 SHA、USB 仍缺失、candidate override/daemon 仍健康；如有 drift，停止受影响操作。
  - `missing-media-observed.json` 尚未写入，因此 Phase A 的 A2 observation checkpoint 仍未闭合。
  - same-bound-media second boot 自动 U13B、predecessor/data/runtime/customer-visible recovery 仍未验证。
  - Phase B fresh continuous downtime acceptance 未授权、未执行。
- 已排除：
  - 不再把本次问题归类为 recovery-engine failure。
  - 不再把本次问题归类为产品 status-projection defect；早先对该层的初步判断已被后续 direct-source evidence supersede。
  - 不需要为此给 OTA V1.2 判断合同新增个案规则；该事故属于验收工具 framing regression，保留为回归测试即可。
  - 不需要默认重跑 `repair-missing-status`：之前的 repair attempt 已完成 exact candidate IPC replacement + daemon restart，失败发生在随后 acceptance-client status request；当前 status-repair receipt 未写入，但 `observe_missing()` 并不要求该 receipt。
  - 不 claim/replay product U9，不加载 target，不进入 U11，不插替代 U 盘，不合并 PR #807。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind main / PR #807 / executable authority `c8e7d71...`；
  - read exact execution package + manifest；
  - 对当前 T1 做最小只读状态核对；
  - 状态无 drift 时，直接执行 exact `--mode observe-missing`，不默认重跑 `repair-missing-status`；
  - `observe-missing` PASS 后归档脱敏证据并停在物理边界；
  - 已授权 Phase A 范围内的源码复核、测试、GitHub 归档可继续。
- 暂停边界：
  - 当前 handoff 之后不要在本会话执行新 T1 动作。
  - 新会话中若 fresh runtime/source/authorization/USB/image invariants 任一漂移，停止。
  - `observe-missing` 未 PASS 前不要 power-cycle，不要插回恢复 U 盘。
  - `observe-missing` PASS 后，到达明确物理暂停边界：T1 power-off → 插回**同一绑定恢复 U 盘** → power-on。按用户要求，在进入该物理动作前先停止并报告。
  - 禁止 target load、U11/U12/U13A、fresh product U9 claim/replay、Phase B fresh timing transaction、board access、PR merge。
- 授权状态：
  - Phase A authorization ID: `N3W_T1_U9_PLUS_BOUNDED_RECOVERY_PHASE_A_LIVE_20261119_01`
  - authorized execution ID: `u9plus-phase-a-20261119-01`
  - acceptance claim: claimed=true / consumed=true / replay=false
  - product U9 authorization: claimed=true / consumed=true / replay=false
  - existing Phase A physical-power-cycle/bound-media-missing authorization remains the governing execution contract, but the current handoff itself grants no new permission.
  - `repair-missing-status` is not the next default action; any decision to rerun it after a fresh drift finding must be justified from current exact state rather than replayed mechanically.

## 5. 下一步

- 行动：
  1. fresh rebind main, PR #807, current PR head and executable/source authority `c8e7d71...`; verify later docs-only head has not introduced source drift.
  2. re-read:
     - `u9plus_fault_acceptance.py`
     - `u9plus_fault_acceptance_manifest.json`
     - this handoff
     - Phase-A plan.
  3. fresh read-only runtime reconciliation:
     - U10 phase;
     - transaction SHA `5d58cfc99d5bf55a7fd38dda00cb40de241ca500269573316a60040de71e5b34`;
     - authorization unchanged;
     - bound USB absent;
     - predecessor/target images absent;
     - candidate override active;
     - candidate IPC/daemon exact if explicitly checked;
     - missing-media checkpoint absent before execution.
  4. if all exact, execute **only**:
     ```text
     mode=observe-missing
     expected_commit=c8e7d71aa2118fa3e1c6599d8da560097f6841ac
     execution_id=u9plus-phase-a-20261119-01
     ```
     with a fresh evidence root and existing operator-local private SSH inputs.
  5. expected result:
     ```text
     status=U9PLUS_PHASE_A_MEDIA_REQUIRED_PASS
     read_only=true
     transaction_phase=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
     recovery_media_required=true
     bound_usb_present=false
     target_image_load=false
     u11_plus=false
     product_u9_replayed=false
     next_action=POWER_OFF_T1_THEN_REINSERT_SAME_BOUND_USB_THEN_POWER_ON
     ```
  6. on PASS, archive the sanitized result and **STOP before the physical power/media action**.
- 完成条件：
  - `observe-missing` PASS；
  - durable `missing-media-observed.json` written;
  - transaction remains exact U10;
  - no target load/U11+/authorization replay;
  - GitHub sanitized evidence archived;
  - physical state still unchanged until operator proceeds at the next boundary.
- 失败／停点：
  - any STOP/FAIL or invariant drift: no retry loop, no repair replay by default, no physical action; preserve T1 powered-on / recovery USB removed and diagnose from exact receipt/state.
  - after `observe-missing` PASS, stop before power-off/reinsert/power-on.
  - after later same-media boot and `verify-recovered` PASS, Phase A ends at `PHASE_B_FRESH_CONTINUOUS_DOWNTIME_ACCEPTANCE_OR_STOP`; Phase B is not authorized here.

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`，按 minimum new-chat read set 恢复。
- 任务资料：
  - 本交接：Phase-A current stop / root-cause / next read-only gate。
  - `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance.py`：下一 exact execution entry；执行前必须 re-read。
  - `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance_manifest.json`：Phase-A authorization/source/boundary。
  - `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE_PHASE_A_PLAN_20261119.md`：A0–A3 sequence / physical stop。
  - `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_INDEPENDENT_SOURCE_REVIEW_CLOSED_PHYSICAL_ACCEPTANCE_PENDING_20261119.md`：recovery architecture / completion oracle。
  - `docs/development/N3W_T1_U9_PLUS_PHASE_A_U10_MISSING_MEDIA_STATUS_REPAIR_CI_WAIT_NEW_CHAT_HANDOFF_V1.0_20261119.md`：上一交接，仅作历史；其中“产品 status-projection defect”结论已被本轮更强 direct-source evidence 部分 supersede。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：KF-168 long-term recovery acceptance context；本轮 acceptance-client framing defect 已由代码回归测试固定，不应扩张为新的 OTA success/failure 判断合同。
- 已归档：
  - source authority `c8e7d71aa2118fa3e1c6599d8da560097f6841ac`
  - root-cause/source-closure PR alignment comment `7010192569`
  - prior forensic comments `7008560851`, `7009743684`, `7009858995`
  - all applicable CI at source authority: 22/22 SUCCESS
  - this V1.4 handoff document.
- 未归档重要资料：
  - operator-local raw forensic JSON remains private by design; its continuation-critical sanitized facts, hashes and state are archived above.
  - private SSH target, known-hosts path and host-key fingerprint remain operator-local/private and are intentionally excluded from GitHub.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=not-required
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=true
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
REGRESSION_GUARD_ARCHIVED=true
UNTRACKED_CRITICAL_ARTIFACTS=0
UNARCHIVED_CRITICAL_KNOWLEDGE=0
NEXT_SAFE_ENTRY_POINT=U9PLUS_PHASE_A_OBSERVE_MISSING_READONLY
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind PR #807 / current source authority，确认后续 docs-only head 未引入 source drift；读取 exact Phase-A execution package/manifest 并 fresh 核对 T1 仍为同一 U10、恢复 U 盘仍拔出、candidate override/daemon 健康。状态无 drift 后直接执行 read-only `observe-missing`，不要默认重跑 `repair-missing-status`。若 `U9PLUS_PHASE_A_MEDIA_REQUIRED_PASS`，归档结果并在 T1 power-off / 插回同一绑定恢复 U 盘 / power-on 的物理边界前停止。
