# N3-W T1 U9+ Phase A U10 missing-media status repair — new chat handoff V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

> 本文按 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4 生成，只保存当前阶段增量。长期规则以 `N3W_PROJECT_WORKING_CONTEXT.md` 为准；fresh repository/runtime/live evidence 优先。公开交接不包含私网地址、SSH host key、known-hosts 路径、凭据或原始设备身份。

## 1. 目标与停点

- 任务／交接原因：完成已授权的 real-T1 U9+ bounded-recovery Phase A。当前目标不是继续向新版 U11 前进，而是先修复 U10 缺少绑定恢复介质时的 status 投影，再证明 `RECOVERY_MEDIA_REQUIRED` 可只读观察，随后用同一恢复介质自动 U13B 回滚并恢复旧版健康。因本轮已完成源码修复、CI 绑定传播和 OTA V1.1.4 架构讨论，切换新会话以减少上下文负担。
- 已完成到：Phase A A1 已真实执行 destructive U10；第一次 missing-media boot 已完成；第一次 `observe-missing` 因 `ota_status_rejected` STOP。产品 status defect 已在 `b47e4e5e747a3337f992159e7c65ec1e49c86ca4` 修复，随后两处 exact source binding 漏项已传播到最终源码 authority `ebdccfd471a56df377094bf82aeec6c1617dd93d`。
- 当前状态：**等 CI**。最终源码 authority 第三次/最后允许主动检查为 `18 SUCCESS / 0 FAILURE / 4 NON_TERMINAL`。关键 P3 clean-source、P3 live/read-only source、fast closure、Core Stack current authority 和 public-safety 均已 SUCCESS；剩余 4 条构建/绑定 workflow 尚未终态。按项目规则已停止主动轮询。

当前实机停点：

```text
TRANSACTION_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
U10_TRANSACTION_SHA256=5d58cfc99d5bf55a7fd38dda00cb40de241ca500269573316a60040de71e5b34
FIRST_OBSERVE_MISSING=STOP
FIRST_OBSERVE_REASON=ota_status_rejected
MISSING_MEDIA_CHECKPOINT_WRITTEN=false
TARGET_IMAGE_LOAD=false
U11_PLUS=false
PRODUCT_U9_REPLAYED=false

T1_POWER=ON
BOUND_RECOVERY_USB=PHYSICALLY_REMOVED
DO_NOT_POWER_CYCLE=true
DO_NOT_REINSERT_USB_YET=true
DO_NOT_INSERT_OTHER_USB=true
```

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state at handoff: OPEN / DRAFT / UNMERGED / mergeable
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - initial requested check head: `b47e4e5e747a3337f992159e7c65ec1e49c86ca4`
  - clean-source binding repair: `7cb81c784fff21264dae829407ac1e7772fe11a0`
  - **current executable/source authority: `ebdccfd471a56df377094bf82aeec6c1617dd93d`**
  - this handoff commit is docs-only and must not replace the executable/source authority above.
- exact source binding chain at executable authority:
  - product IPC blob: `48558556169a045da092aef94d4c5244d2c48775`
  - P3 clean-OTA manifest blob: `be922028ada20d1debe4f85e90a9c7ecb9df5005`
  - P3 live-to-U11 manifest blob: `e9721c5413c5a47357d3ced2f1be6e3b7a3d66c2`
  - Phase A fault manifest blob: `701c32206c3644116a98911048ee57cdf5f181b7`
- 证据入口：
  - PR alignment comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-7005572609
  - U10 read-only physical closure: `docs/development/N3W_T1_U13B_P3_U10_READONLY_ATTEMPT05_PHYSICAL_CLOSURE_20261119.md`
  - bounded-recovery source review: `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_INDEPENDENT_SOURCE_REVIEW_CLOSED_PHYSICAL_ACCEPTANCE_PENDING_20261119.md`
  - Phase A plan: `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE_PHASE_A_PLAN_20261119.md`
  - exact execution package: `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance.py`
  - exact Phase A manifest: `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance_manifest.json`

CI at third/final allowed poll on source authority:

```text
SUCCESS=18
FAILURE=0
NON_TERMINAL=4
CI_POLL_LIMIT_REACHED=true
```

Key SUCCESS runs:
- P3 clean OTA source: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44499564306
- P3 live/read-only source: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44499564867
- fast source/exact closure: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44499563944
- Core Stack current authority: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44499564018
- public repository safety: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44499563971

Still non-terminal; next chat may check these once, especially after the user reports CI completion:
- Manager A-to-B: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44499564251
- HA 2026.10.3 target binding: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44499564321
- HA 2026.10.4 target binding: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44499564155
- HA 2026.10.4 same-version acceptance artifact: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44499564142

Separately archived product architecture discussion:
- branch: `docs/t1-core-stack-ota-architecture-v1-1-20261119`
- architecture version: `V1.1.4`
- architecture head: `ec56a0d123b77bf623bf3760057da66557c470f3`
- file: `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.1.4_20261119.md`
- status: design/progress archived; not implemented in current product source; not merged to main.

## 3. 必须继承的结论

- 已证实：
  - U10 destructive capacity release 已真实完成；旧 HA predecessor container/image 已释放；target image 未加载；U11 未进入。
  - 第一次缺介质 boot 已真实发生，且 product U9 authorization 未重放。
  - 第一次 `observe-missing` 的 `ota_status_rejected` 是**真实产品 status-projection defect**，不是“U13B recovery 已证明失败”。根因是 post-claim U10 status 继续调用 prepare-phase-only capacity projection。
  - `b47e4e5...` 的产品修复使 prepare-phase-invalid capacity projection 在 post-claim status 中降级，不再覆盖 U9+ recovery core phase；新增 `repair-missing-status` 只修复 staged candidate IPC 并重启 OTA daemon。
  - clean-source 和 live/read-only source 的后续失败均为 exact authority 传播遗漏；最终链式 binding 已在 `ebdccfd...` 修复，关键 source CI 已 SUCCESS。
  - OTA 架构 V1.1.4 已在独立 GitHub 分支归档：终态严格二态 SUCCESS/FAILURE；升级/恢复执行与 status/checker/UI 解耦；CORE GATE 要少、稳定；非 CORE 永不决定 OTA 成败；未来需要对当前 hard-fail acceptance 做 `CORE / CONDITIONAL_CORE / DIAGNOSTIC / REMOVE_FROM_ACCEPTANCE` inventory。
- 待确认：
  - source authority 仍有 4 个 workflow 未终态；在执行 real-T1 status repair 前必须确认这 4 条最终没有 failure。
  - 由于第一次 `observe-missing` 在 IPC status 层停止，`missing-media-observed.json` 尚未写入；必须在修复后重新执行 `observe-missing`。
  - Phase A 还未证明 same-media second boot 自动 U13B、旧版业务恢复以及 KF-140-safe completion oracle。
  - 当前跨长时间人工暂停的事务不能证明客户停机时间目标；Phase B fresh continuous timing 未执行。
- 已排除：
  - 不把 `ota_status_rejected` 当作 recovery engine failure。
  - 不重新 claim/replay product U9 authorization。
  - 不通过重新触发相同 CI 规避轮询上限。
  - 不插入替代 U 盘，不格式化，不进入 U11，不加载 target，不合并 PR #807。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind main / PR #807 / exact source authority；
  - 检查上述 4 个剩余 CI 的终态；
  - 在 exact source + applicable CI 全部通过后，继续已授权 Phase A 的 `repair-missing-status`；
  - repair PASS 后执行只读 `observe-missing`；
  - `observe-missing` PASS 后，按 Phase A 既定物理步骤关闭 T1、插回**同一绑定恢复 U 盘**、重新上电，再执行 `verify-recovered`；
  - 归档脱敏证据。
- 暂停边界：
  - 在剩余 exact-head CI 未全部成功前，不执行 `repair-missing-status`。
  - 在 `observe-missing` 未 PASS 前，**不要**插回 U 盘或再次 power-cycle。
  - 禁止 target load、U11/U12/U13A、fresh product U9 claim/replay、Phase B fresh timing transaction、board access、PR merge。
  - 若 repair 或 observe 返回 STOP/FAIL，保持当前电源/介质状态并先复核 exact output/source；不要自行进入下一物理步骤。
- 授权状态：
  - Phase A gate: `N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE`
  - Phase A authorization ID: `N3W_T1_U9_PLUS_BOUNDED_RECOVERY_PHASE_A_LIVE_20261119_01`
  - authorized execution ID: `u9plus-phase-a-20261119-01`
  - acceptance claim 已在 A1 持久化为 claimed=true / consumed=true / replay=false。
  - product U9 authorization 在进入本 gate 前已 claimed=true / consumed=true / replay=false，禁止重放。
  - `repair-missing-status` 不重新 claim product/acceptance authorization；它依赖现有 claim、相同 execution ID 和 exact candidate source bundle。
  - 交接本身不授权 Phase B 或 merge。

## 5. 下一步

- 行动：
  1. fresh rebind `main`、PR #807 和 source authority，要求 PR head/source authority 未发生未解释 drift。
  2. 检查上节 4 个剩余 workflow。若任一 FAILURE，先判断原因；局部、无歧义、只涉及 exact binding 的 CI 修复可直接修复并验证；设计/范围扩大/实机边界则停止。
  3. 若 source authority 全部 applicable CI SUCCESS，读取 exact `u9plus_fault_acceptance.py` 与 manifest 后，使用 operator-local 私有 SSH inputs 执行 `--mode repair-missing-status`。不要复用旧 evidence root。
  4. repair 预期：
     ```text
     status=U9PLUS_PHASE_A_MISSING_STATUS_REPAIR_PASS
     transaction_phase=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
     transaction_sha256=5d58cfc99d5bf55a7fd38dda00cb40de241ca500269573316a60040de71e5b34
     recovery_media_required=true
     bound_usb_present=false
     candidate_status_repair=true
     ota_daemon_restarted=true
     target_image_load=false
     u11_plus=false
     product_u9_replayed=false
     next_action=REPEAT_OBSERVE_MISSING_READONLY
     ```
  5. repair PASS 后，用新的 evidence root 执行 `--mode observe-missing`。预期 `U9PLUS_PHASE_A_MEDIA_REQUIRED_PASS`，并写入 missing-media checkpoint。
  6. 只有 observe PASS 后，用户物理操作：T1 彻底关机 → 插回同一绑定恢复 U 盘 → T1 开机。
  7. 第二次 boot 后执行 exact `--mode verify-recovered`；要求自动进入 U13B/ROLLED_BACK、predecessor image/data/runtime/业务恢复、target absent、authorization unchanged、三服务各一个实例、KF-140-safe telemetry/HA MQTT evidence PASS。
- 完成条件：
  - Phase A terminal `U9PLUS_PHASE_A_RECOVERED_PASS`；
  - `transaction_phase=U13B_ROLLED_BACK` / status ROLLED_BACK；
  - predecessor recovered，target absent；
  - `product_u9_replayed=false`；
  - `customer_downtime_sla_proven=false` 必须保持，因为本事务包含人工暂停；
  - 脱敏 evidence 归档到 PR #807。
- 失败／停点：
  - 任一步 STOP/FAIL 时，不推进下一物理动作；记录最后成功步骤、实际变更和当前介质/电源状态。
  - Phase A PASS 后停在 `PHASE_B_FRESH_CONTINUOUS_DOWNTIME_ACCEPTANCE_OR_STOP`；Phase B 不是本交接自动授予的执行权限。
  - PR #807 继续 OPEN/DRAFT/UNMERGED。

## 6. 必读定位与归档

- 仓库规则：
  - 适用仓库内 `AGENTS.md`（若当前路径存在）；
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`，按其 minimum new-chat read set 执行；
  - formal handoff template authority: `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4，main blob `885fd63131e80936e5e1fe907378be08a0060f12`。
- 任务资料：
  - `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance.py`：下一执行入口和 live safety assertions；执行前必须 exact re-read。
  - `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance_manifest.json`：Phase A grant/boundary/source authority。
  - `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE_PHASE_A_PLAN_20261119.md`：A0–A3 sequence 与 hard stop。
  - `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_INDEPENDENT_SOURCE_REVIEW_CLOSED_PHYSICAL_ACCEPTANCE_PENDING_20261119.md`：U9+ recovery architecture 与 KF-140 oracle。
  - `docs/development/N3W_T1_U13B_P3_U10_READONLY_ATTEMPT05_PHYSICAL_CLOSURE_20261119.md`：pre-U10 recovery assets/baseline。
  - architecture V1.1.4（独立设计分支）：`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.1.4_20261119.md`；仅在讨论后续 OTA 架构/CORE GATE inventory 时读取，不替代当前 Phase A exact execution contract。
- 已归档：
  - PR #807 alignment comment `7005572609`；
  - source authority `ebdccfd471a56df377094bf82aeec6c1617dd93d`；
  - architecture V1.1.4 head `ec56a0d123b77bf623bf3760057da66557c470f3`。
- 未归档重要资料：无团队共享必需材料。私网地址、known-hosts、SSH host-key fingerprint 和 operator-local raw evidence 故意不进入公开 GitHub；下一会话使用既有私有上下文并在 live execution 前 fresh rebind。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind PR #807 / source authority 并检查 4 个剩余 CI；全部 applicable CI SUCCESS 后，保持 T1 通电且绑定恢复 U 盘仍拔出，读取 exact execution package，继续 `repair-missing-status`。到达所列物理/授权暂停边界时停止。
