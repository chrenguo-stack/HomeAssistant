# N3-W T1 U10 read-only CLOSED_PASS / KF-168 U9+ bounded recovery source-design new-chat handoff V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`
`DATE=2026-11-19`

## 1. 目标与停点

- 任务／交接原因：结束本轮 U10 read-only / KF-167 物理闭环，把下一阶段切换到 KF-168 的 U9+ bounded recovery 产品化设计。下一阶段在新对话继续。
- 已完成到：真实 T1 Attempt 05 对 exact candidate `4bca19ff857239c4e86e8417cf61e076c686f834` 返回 `P3_U10_READONLY_PREFLIGHT_PASS / EXIT_CODE=0`；KF-167 已 `CLOSED_PASS / PHYSICALLY_VALIDATED`。随后完成产品源码复核并证明 KF-168：常驻 HA OTA daemon 没有把 U9+ 自动恢复协调器接入启动路径。
- 当前状态：可在新对话继续源码设计／实现／测试／GitHub 归档；实机 destructive U10 仍明确阻塞。当前 T1 仍停在 durable U9，Manager 与 Home Assistant 保持 quiesced，Broker continuity 已验证。

## 2. 代码与证据

- 仓库／分支／PR：`chrenguo-stack/HomeAssistant` / `fix/kf147-u3-recovery-and-error-visibility-20261110` / PR #807（OPEN / DRAFT / UNMERGED）。
- 核对时 main／本任务源码：main=`3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`；交接父 head=`62d1ed4d268288eeb1ec38ff355595e688738996`；Attempt 05 exact source candidate=`4bca19ff857239c4e86e8417cf61e076c686f834`；Core Stack product source authority=`5b32e1ae82104a42f9e4e6907fe44d9172e87615`。
- 证据入口：
  - `docs/development/N3W_T1_U13B_P3_U10_READONLY_ATTEMPT05_PHYSICAL_CLOSURE_20261119.md`：Attempt 05 实机闭环。
  - `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_PRE_U10_GATE_20261119.md`：U10 destructive 前恢复门禁与 KF-168 初始源码复核。
  - `docs/development/N3W_T1_CUSTOMER_OTA_FAILURE_RECOVERY_ACCEPTANCE_PLAN_20261118.md`：客户可见恢复与 5/15 分钟首轮试验目标。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：KF-168 OPEN；KF-167 CLOSED_PASS。
  - Attempt 05 receipt SHA-256=`e4a08d555656d20d3ef5bd3bc9a36929ca4b4ee9daa3ff138d7d9232bb9e5126`；原始证据保持操作者本地私有，不进入公开 GitHub。
- CI：交接父 head `62d1ed4...` 已查询 2 次；第二次为 22 个 workflow 中 20 SUCCESS、0 FAILURE、2 IN_PROGRESS：
  - `44346576862` — N3W U13B P3 Home Assistant 2026.10.3 target binding CI — IN_PROGRESS
  - `44346577295` — N3W U13B P3 Home Assistant 2026.10.4 same-version acceptance artifact CI — IN_PROGRESS
  - Core Stack current authority、Manager A-to-B、P3 live/read-only source、P3 acceptance source、public safety、fast exact closure 均已 SUCCESS。

## 3. 必须继承的结论

- 已证实：
  - durable live state=`U9_LIVE_AUTHORIZATION_CLAIMED`，transaction SHA-256=`2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b`；U9 authorization 已消费且不可 replay。
  - Attempt 05 read-only PASS；`destructive_cutover_eligible=true` 只表示技术预检资格，不等于 destructive U10 授权。
  - Attempt 05 未删除 predecessor runtime/image、未加载 target、未修改 service、未写入 U10、未进入 U11+。
  - KF-167 已物理关闭。
  - KF-168 已 source-proven：`n3w_t1_core_updater_ha_daemon.py` 启动时调用 `HaUsbIpcExecutor.start_background_recovery()`，但该方法只恢复 U1 发现与 U2/U3 prepare；IPC action 只含 PREPARE / CONFIRM_USB_ERASE / INSTALL。U9-U13 状态机／rollback primitives／工程执行器存在，但尚未形成常驻产品 U9+ 恢复协调器。
  - 客户恢复完成不能以“容器运行”判定；至少要验证 predecessor exact binding、HA 页面、Manager、Broker、新温室数据、预期历史数据、host/USB terminal state 一致及 no-replay。
  - 切换前 <=5min、切换后 <=15min 当前只是首轮工程验收目标，未完成代表性实测前不能作为客户正式承诺。
- 待确认：
  - 新对话先 fresh rebind PR #807/head/main；核对上述 2 个交接时仍运行的 CI 是否终态。
  - 对生产路径进行完整 U9-U13 recovery ownership/source review，确认哪些现有 backend/provider 可以复用，哪些缺少真实 host implementation、boot reconciliation、health oracle 或 fault-injection hook。
- 已排除：
  - 不再继续修 KF-167；Attempt 01–05 已形成完整原因链和实机 PASS。
  - 不允许用 engineering stage executors 的存在替代产品常驻 recovery coordinator。
  - 不允许用当前长时间人工分阶段 P3 流程测得的总停机时间作为客户恢复时间证据。

## 4. 执行范围与授权

- 可继续：在新对话内连续执行 KF-168 的源码复核、恢复协调器设计、源码修改、单元／模拟／故障注入测试、CI 修复和 GitHub 归档；无需逐门确认。
- 暂停边界：任何真实 T1 destructive U10、predecessor runtime/image 删除、target load/start、服务恢复/重启、U11+、备用 T1 写入、不可逆操作、PR #807 merge 都必须停下并取得相应授权。
- 授权状态：
  - U9：`CONSUMED_NO_REPLAY`，禁止重放。
  - Attempt 05：已完成的一次性 read-only 物理执行，不可作为新执行授权。
  - U10 destructive：无授权。
  - U11+：无授权。
  - PR #807 merge：无授权。
  - 交接本身不授予任何新实机或 merge 权限。

## 5. 下一步

- 行动：
  1. fresh rebind main、PR #807、最新 head、Current State / Index / KF-168；检查交接时仍运行的两个 workflow 终态。
  2. 只读完成生产 U9-U13 recovery source ownership review，重点读取 `tools/n3w_t1_core_updater_ha_daemon.py`、`tools/n3w_t1_core_updater_ha_ipc.py`、`tools/n3w_t1_core_updater_ha_usb.py`、`tools/n3w_t1_core_updater_ha_recovery.py`、`tools/n3w_t1_core_updater_ha_backup.py` 及 U10/U11/U12/U13B execution packages。
  3. 冻结 KF-168 source design：一个 host-owned、boot-started、single-coordinator 的 U9+ recovery path；同一 USB UUID；合法相邻阶段 forward-resume 或 image+data rollback；缺原盘则 RECOVERY_MEDIA_REQUIRED；绝不 replay U9。
  4. 把 customer-visible completion oracle 与停机计时纳入代码和测试合同，补齐确定性 fault injection。
  5. 完成源码、测试、CI 和独立复核后再形成实机 recovery/timing acceptance 计划；到实机 destructive boundary 必须停止等待用户授权。
- 完成条件：KF-168 source/CI closed；无 false-PASS；重启/断电/阶段中断/缺盘/错盘路径均有 deterministic tests；恢复完成条件绑定 image+data+customer-visible health；GitHub 归档完整。实机部分只有在单独授权且代表性恢复/计时验收通过后才可关闭。
- 失败／停点：源码／CI 小而明确的问题可直接修复；若涉及恢复策略选择、产品范围扩大、真实 T1 destructive、服务写入或 merge，暂停并说明影响。任何 U9+ 不可判定现场必须 fail closed，不得 replay、猜测 success 或自动替换 USB。

## 6. 必读定位与归档

- 仓库规则：根 `AGENTS.md`；按 `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set` 恢复最小上下文；交接模板 authority=`docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4。
- 任务资料：
  - `docs/development/N3W_T1_U10_READONLY_CLOSED_KF168_SOURCE_GAP_TO_U9_PLUS_BOUNDED_RECOVERY_NEW_CHAT_HANDOFF_V1.0_20261119.md`：本交接。
  - `docs/development/N3W_CURRENT_STATE.md`：最新 durable U9 / Attempt 05 / KF-168 状态。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：最新证据入口。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：优先读 KF-168、KF-167。
  - `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_PRE_U10_GATE_20261119.md`：下一门设计/验收合同。
  - `docs/development/N3W_T1_CUSTOMER_OTA_FAILURE_RECOVERY_ACCEPTANCE_PLAN_20261118.md`：客户恢复目标与时序。
  - 按需补读 `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_DESIGN_DELTA_20261106.md` 与 `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_AND_DATA_ROLLBACK_ARCHITECTURE_V1.1_20261106.md`。
- 已归档：Attempt 05 public-safe closure、KF-168 source-gap archive、bounded recovery gate、Current State/Index/KF 状态均已在 PR #807 分支。
- 未归档重要资料：Attempt 05 原始本地 evidence 文件不公开；其 receipt SHA-256 已归档，可用于后续私有证据绑定。无其他必须依赖的 chat-only 工程事实。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind PR #807/main/head 和交接时仍运行的 CI，然后进入 `N3W_T1_U9_PLUS_BOUNDED_RECOVERY_SOURCE_REVIEW_AND_ACCEPTANCE_DESIGN`。在明确授权范围内连续推进源码复核、设计、实现、测试和 GitHub 归档；到真实 T1 destructive U10、服务写入、U11+ 或 merge 边界时停止。
