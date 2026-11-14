# N3-W KF-153 R22 生命周期就绪修复 → 真实 T1 只读预检 新会话交接

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续“温室环境监测系统（ESP32-C6）”N3-W 的 Home Assistant mandatory-USB OTA 收口。R20 live IPC source activation 已失败并消费一次性授权；R21 只读取证已证明自动 rollback 最终恢复到稳定 predecessor U5；R22 successor 已针对两处 lifecycle readiness race 完成源码修复并通过 fresh 16/16 CI。本轮在新对话切换点停止。
- 已完成到：
  - R20 exact authorized head `fcc821ffa298b9927b105f510e826cdecb5b64b7` 实机执行后 STOP；外层 authorization 已 claimed+consumed，永久不可 replay。
  - R21 真实 T1 只读 forensic：`ROLLBACK_RUNTIME_RECOVERED`，无需额外 live recovery。
  - R22 exact source authority `aa5eb8b8ccb7628aae782d00d4b97fa8fe741239` / tree `482b191e8115886a02e5f8f5af7d20181779bd3d`，fresh CI 16/16 SUCCESS。
- 当前状态：可继续，但第一步不是立即执行 preflight。新对话必须先交叉复核旧设计／旧执行链与当前 V1.2 架构／R22 successor，确认没有继承已淘汰假设；之后才执行 R22 真实 T1 `--preflight-only`。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR #807: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR 状态：OPEN / DRAFT / UNMERGED
- 核对时 main／本任务源码：
  - repository main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - current repository product-source authority 仍为：`5b32e1ae82104a42f9e4e6907fe44d9172e87615`
  - R22 frozen source authority: `aa5eb8b8ccb7628aae782d00d4b97fa8fe741239`
  - R22 tree: `482b191e8115886a02e5f8f5af7d20181779bd3d`
  - executor blob: `051f0a96a6acdf4d9a39fbceb082b7d801b0a2cd`
  - manifest blob: `3ab67158be4f19fb90bdcebdb819dc0e0b042518`
  - focused test blob: `d917bbd2b51821ed5b30ca0fb0917e977cae9ffc`
  - HA target-binding workflow blob: `73786719b60de962a1ddacc2046ac557be3ad4fb`
- 证据入口：
  - R20 live STOP / rollback incomplete：https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6857336854
  - R21 recovered forensic closure：https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6857414545
  - R22 source repair / CI pending：https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6857470544
  - R22 fresh CI 16/16 closure / handoff boundary：https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6857645934
  - key CI: Manager A-to-B https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43453269782
  - key CI: HA target binding https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43453269916
- authority split：后续 docs-only handoff commit 不得把 R22 source authority 从 `aa5eb8b8...` 漂移到文档 head。真实 T1 preflight 必须明确绑定 frozen R22 source authority，或先独立证明新的 exact head 对执行包无漂移且 fresh CI authority 仍适用。

## 3. 必须继承的结论

- 已证实：
  - R20 outer one-shot authorization 已 `claimed=true / consumed=true / replay=false`；R20 永久禁止重放。
  - R20 首个 forward failure 是 `runtime_root_invalid`；自动 rollback 最终检查停止于 `container_drift:homeassistant`。
  - R21 只读取证证明当前真实 T1 已恢复 predecessor IPC SHA-256 `b080e20bf272ed22c51a91c96832759fcc88175825ab1740ae6b98aff8ff3a1b`。
  - 当前 live transaction 仍为 `U5_INSTALL_REQUESTED_REVALIDATING`，SHA-256 `adfcf60d958c112edf61e2f4e31d73b16229fd027180ed68b87b8953231f0144`；transaction 内 authorization 仍未 claimed/consumed。
  - R21 证明 USB 已挂回 transaction-derived target，host/services/broker owner active/running/NRestarts=0，Manager/Home Assistant/Broker running/restart_count=0；无需额外 live recovery。
  - target IPC 相比 R19 predecessor 只有预期的 response-send OSError containment，不存在已发现的 companion-module compatibility delta。
  - R22 修复两项：host start 后先有界等待 systemd `RuntimeDirectory=/run/n3w-t1-ota` exact metadata；rollback services start 后使用最多 180 秒、2 秒轮询的 exact runtime convergence 验收。
  - R22 fresh CI = 16/16 SUCCESS；当前 R22 manifest 完全未授权。
- 待确认：
  - R22 尚未在真实 T1 上执行新的 read-only preflight。
  - 新对话必须 fresh rebind PR/source，并重新确认当前 T1 仍保持 R21 predecessor U5 基线；任何漂移都不得用历史 R21 证据自动覆盖。
  - 在 preflight 前必须完成下面“旧／新架构与开发记录交叉复核”，输出是否存在新的设计 blocker。
- 已排除：
  - R20 STOP 不是持久 T1 runtime corruption；R21 已实机排除。
  - 当前证据不支持“target IPC 与 predecessor companion modules 不兼容”；source delta 仅为 intended OSError guard。
  - `/dev/sda1` 只能是现场 locator，不能成为固定设备 authority。
  - 不能通过重新提交 INSTALL、重放 R18/R20 或清除 consumed authorization 来绕过失败。

## 4. 执行范围与授权

- 可继续：
  - GitHub fresh rebind、源码/设计独立复核、模拟测试、文档归档；
  - 真实 T1 **只读** R22 preflight；用户已明确要求下一阶段先做 read-only preflight。
- 暂停边界：
  - R22 preflight PASS 后必须停止在新的 live source-activation one-shot authorization boundary；不得自动进入 `--execute`。
  - R22 preflight STOP 时只分类与取证；不得自动修改 T1、mount/unmount、restart service、stage/deploy source 或重试 live。
  - 禁止 R20 replay、INSTALL resubmit、U6+、board access、merge。
- 授权状态：
  - R20：consumed=true，replay=false，永久失效。
  - R22：`live_execution_authorized=false`，`granted=false`，`claimed=false`，`consumed=false`，`replay_permitted=false`。
  - 交接本身不授予 R22 live 写权限。

## 5. 下一步

- 行动：
  1. fresh rebind repository main、PR #807、branch 与 frozen R22 source authority `aa5eb8b8...`；确认 docs-only advance 不造成 source drift。
  2. **强制交叉复核旧／新设计与开发过程记录，先于任何 T1 preflight：**
     - 旧执行链／失败证据：
       - `tools/execution_packages/n3w/r7a/kf152_r17_dependency_safe_source_activation_successor/`
       - `tools/execution_packages/n3w/r7a/kf152_r18_u4_to_u5_install_intent_successor/`
       - `tools/execution_packages/n3w/r7a/kf153_r19_post_r18_ipc_timeout_readonly_forensic/`
       - `tools/execution_packages/n3w/r7a/kf153_r20_u5_ipc_source_activation_successor/`
       - PR #807 上述 R20/R21 comments。
     - 当前架构／successor：
       - `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_REMOVABLE_MEDIA_CONTENT_AUTHORITY_ARCHITECTURE_V1.2_20261112.md`
       - `docs/development/N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_DESIGN_20261112.md`
       - `tools/execution_packages/n3w/r7a/kf153_r22_u5_ipc_source_activation_successor/`
       - `tests/tools/test_n3w_t1_kf153_r22_u5_ipc_source_activation_successor.py`
       - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 的 KF-151/KF-152/KF-153 与通用 executor guards。
     - 必须逐项比较：生命周期 owner、systemd `RuntimeDirectory`/socket readiness、USB authority 与 locator 边界、container convergence、preflight→claim→mutation→rollback 顺序、一次性 authorization claim/consume/replay、exact source self-binding、raw transport evidence、远端脚本依赖完整性、CI/harness false-PASS 路径。
     - 交叉复核不得把“旧实现曾经工作”直接当作新架构 authority；也不得因为新架构已冻结就忽略旧实机失败中暴露的 executor lifecycle 规则。
  3. 若交叉复核 `NEW_BLOCKER_COUNT=0`，执行 R22 真实 T1 `--preflight-only`；不执行 live activation。
- 完成条件：
  - fresh exact-source rebind PASS；
  - cross-architecture/execution review 输出 `NEW_BLOCKER_COUNT=0`；
  - R22 real-T1 preflight `status=PASS`；
  - preflight 证明 predecessor IPC、exact U5 transaction、USB binding/mount、host/services/broker units、Manager/HA/Broker runtime 与 R22 expected prestate 一致；
  - 证据归档到 PR #807，并停止在新的 live authorization boundary。
- 失败／停点：
  - source drift、架构 blocker、T1 prestate drift、raw transport failure 或任何 preflight STOP：停止受影响操作并归因，不自动修 T1。
  - 任何需要 live source activation 的动作都必须新建／固化新的 R22 one-shot authorization；不得继承 R20。

## 6. 必读定位与归档

- 仓库规则：
  - 读取适用 `AGENTS.md`。
  - 按 `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set` 恢复项目最小上下文。
  - 正式 handoff authority：`docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4。
- 任务资料：
  - 本 handoff：`docs/development/N3W_T1_KF153_R22_LIFECYCLE_READINESS_TO_REAL_T1_READONLY_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261113.md`
  - `docs/development/N3W_CURRENT_STATE.md`：当前 authority。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：阶段索引。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：KF-153 及通用执行器 guard。
  - V1.2 architecture/source-design 与 R17/R18/R19/R20/R22 package/test：按第 5 节强制交叉复核。
- 已归档：
  - R20 failure：https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6857336854
  - R21 forensic closure：https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6857414545
  - R22 source repair：https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6857470544
  - R22 16/16 CI closure：https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6857645934
- 未归档重要资料：无。R21 原始现场日志保留在私有 evidence/对话附件中，但影响下一步的 public-safe 结论和关键 SHA/状态均已进入 PR comment、CURRENT_STATE、KNOWN_FAILURES 与本 handoff；新会话不依赖原始私有日志才能恢复任务。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind；然后必须先交叉复核旧执行链与当前 V1.2/R22 设计，确认没有重复旧失败模式；仅在 `NEW_BLOCKER_COUNT=0` 后执行 R22 真实 T1 只读 preflight。preflight PASS 后停止在新的 live one-shot authorization boundary，不进入写操作。
