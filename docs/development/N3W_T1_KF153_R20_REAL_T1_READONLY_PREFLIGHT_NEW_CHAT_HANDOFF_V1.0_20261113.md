# N3-W T1 KF-153 R20 真实 T1 只读预检新会话交接 V1.0

HANDOFF_TEMPLATE_VERSION=1.4

说明：本交接归档在独立 docs-only archive branch。R20 生产候选源码 authority 仍固定为 a81708cfc821bc0df9feff9318b6752d743d497e，不要把本交接提交当作新的 R20 执行源码 head。

## 1. 目标与停点

- 任务／交接原因：继续“温室环境监测系统（ESP32-C6）”N3-W / T1 Home Assistant mandatory-USB OTA。当前会话已完成 R18→R19→KF-153 物理归因、IPC BrokenPipe 最小源码修复、R20 U5-safe source-activation successor 设计/加固及 fresh CI。为控制上下文长度，在新会话直接进入 R20 真实 T1 只读 preflight。
- 已完成到：R18 one-shot 已消费且永久不可重放；R19 真实 T1 forensic PASS 并证明 R18 实际延迟完成 U5；KF-153 根因已物理证实；IPC response-write BrokenPipe containment 已进入 R20 exact source；R20 successor 已完成二轮自审；R20 exact head fresh CI = 16/16 SUCCESS。
- 当前状态：可继续。新会话不再重做 R20 设计，不再询问只读 preflight 授权；fresh rebind exact source authority 后直接执行 R20 --preflight-only。R20 live source activation 仍未授权。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: chrenguo-stack/HomeAssistant
  - source branch: fix/kf147-u3-recovery-and-error-visibility-20261110
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR 状态：OPEN / DRAFT / UNMERGED
- 核对时 main／本任务源码：
  - MAIN_HEAD_AT_HANDOFF=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
  - R20_EXACT_HEAD=a81708cfc821bc0df9feff9318b6752d743d497e
  - R20_EXACT_TREE=901b3e496199bec5f3e2d604d07c2a2468224138
- R20 exact blobs：
  - executor=1f5c44c1788255ce58f933d9eef03a46d70ff2ee
  - manifest=0b2ba751bf39b9c258a18e0c9b20522d3877c46e
  - focused_test=d5e1242eb30144baa46a00557c381e40ce6e2d87
  - workflow=0be23a6c43c87cb5835e2e9f4b6fbfe33fabf911
  - repaired_ipc_source=ad3978f0b4cea0a611073c189b0d45abd1cf3a0a
- predecessor：
  - R19_SOURCE_HEAD=f6a2cc18f9f7029e3dbe67d00635900005407552
  - KF153_SOURCE_REPAIR_HEAD=e788f4f2207b350212199c9cc567661524e7f85d
- 证据入口：
  - R19 physical closure + R20 progress: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6854503660
  - R20 final 16/16 CI + next gate: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6854698818
  - Manager A-to-B CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43434849424
  - HA target-binding CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43434848780
- 为保持 R20 exact source head + 16/16 CI authority 不漂移，本交接不提交到 PR #807 source branch，而归档到独立 docs-only branch。

## 3. 必须继承的结论

- 已证实：
  - R19 实机 status=PASS，classification=DELAYED_U5_TRANSITION_COMPLETE。
  - live host transaction 与 USB transaction metadata 都已稳定处于 U5_INSTALL_REQUESTED_REVALIDATING。
  - LIVE_TRANSACTION_SHA256=adfcf60d958c112edf61e2f4e31d73b16229fd027180ed68b87b8953231f0144。
  - exact USB 已挂载在 transaction-derived target，UUID/公共指纹一致，mount contract 为 rw,nosuid,nodev,noexec。
  - USB_PHASE_SHA256=acec5c51c5b8dc4ef5b1860dc61c77d377c923730c13a74ede0bf41d1e88d468。
  - R18 的 5 秒客户端 IPC timeout 后，host 同步 INSTALL 继续完成 U5；随后 response write 命中 BrokenPipeError，杀死 IPC serving thread，但 host daemon 主进程、services owner、Manager、Home Assistant、Broker 均保持运行且 zero restart。
  - KF-153 ROOT_CAUSE_STATUS=PHYSICAL_PROVEN。
  - R20 产品源码修复只处理 response-write OSError containment，不改变 INSTALL/U5 业务语义。
  - R20 禁止 INSTALL resubmit；固定 /dev/sda1 或 /dev/sdb1 不再作为 authority。
  - R20 exact head fresh CI = 16/16 SUCCESS。
- 待确认：
  - R20 真实 T1 read-only preflight 尚未执行。
  - preflight 需要 fresh 证明 exact U5 transaction/hash、exact mounted USB identity/phase、8-file predecessor source set、host/services/Broker owner 与三个容器健康、R20 state/staging 无残留。
  - IPC 当前预期仍不可用；R20 preflight 明确 require_ipc=false，因此 IPC 不可达不是 preflight blocker。
- 已排除：
  - 禁止重跑 R18；其 authorization 已 claimed + consumed + no-replay。
  - 禁止重新提交 INSTALL；系统已经在 U5。
  - 禁止把 /dev/sdX 当作 durable identity。
  - 禁止直接 stop/restart host daemon 而不先处理 services owner 和 U5 USB mount 生命周期。
  - 禁止在本阶段进入 U6+、板端访问或 merge。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind repository / PR #807 / exact R20 commit；
  - 读取 R20 manifest/executor/test 与必要当前状态；
  - 执行 R20 真实 T1 --preflight-only；
  - 对 preflight 结果做脱敏 GitHub 归档；
  - preflight PASS 后可准备 grant-only successor，但实际 live source activation 必须等待新的明确 one-shot 写授权。
- 暂停边界：
  - R20 preflight 是只读，不允许 remote staging、源码替换、USB unmount/remount、service restart、transaction/USB metadata mutation、U6+、board access、merge。
  - R20 preflight PASS 后停在 R20 live U5 IPC source activation explicit authorization boundary。
  - exact source/manifest/CI/真实 U5 前态发生漂移时 STOP，先分类漂移；不得自动继承旧授权或旧 PASS。
- 授权状态：
  - R20_LIVE_EXECUTION_AUTHORIZED=false
  - R20_AUTHORIZATION_GRANTED=false
  - R20_AUTHORIZATION_CLAIMED=false
  - R20_AUTHORIZATION_CONSUMED=false
  - REPLAY_PERMITTED=false
  - 用户已明确要求新会话直接进入 R20 只读 preflight；这不构成 live write/source-activation 授权。
  - source activation、USB unmount/remount、service lifecycle mutation 需要 preflight PASS 后另行建立一次性授权。

## 5. 下一步

- 行动：
  1. fresh rebind PR #807 head、source branch head、main、exact R20 commit a81708cfc821bc0df9feff9318b6752d743d497e、R20 manifest/executor/test/workflow blobs，以及 exact head CI 16/16 SUCCESS。
  2. 确认没有新的 source-authority supersession；不要因为本 docs-only handoff commit 改写 R20 source authority。
  3. 直接运行 R20 executor --preflight-only，使用既有私有 T1 SSH target / known_hosts / host-key binding；这些敏感 locator 不写入公共 GitHub。
  4. 取得结果后立即判定并脱敏归档。
- 完成条件：
  - local/remote result status=PASS、read_only=true、activation_eligible=true；
  - transaction phase/hash 精确仍为 U5；
  - USB exact UUID/公共指纹/mount target/USB phase 均匹配；
  - predecessor ipc.py 仍为 live SHA-256 b080e20bf272ed22c51a91c96832759fcc88175825ab1740ae6b98aff8ff3a1b，其余 7 个 source SHA 仍匹配 manifest；
  - host/services/Broker owner healthy，Manager/HA/Broker running，restart count 不漂移；
  - R20 state root 与 staging root 在 preflight 前无残留；
  - host_source_mutation=false、usb_mount_mutation=false、transaction_mutation=false、usb_transaction_metadata_mutation=false、service_restart=false、u6_plus=false。
- 失败／停点：
  - 任一 preflight STOP：不执行 source activation，不创建写授权；先归档 exact failure 与最后已证实 U5 状态。
  - state/staging residue：按 provenance 分类，不删除、不覆盖。
  - U5 transaction 或 USB phase 漂移：停止并进入只读取证，禁止回退到 U4 或重提 INSTALL。
  - preflight PASS 后的新写授权仅覆盖 R20 U5-safe activation；R18/R17 等历史授权不可复用。

## 6. 必读定位与归档

- 仓库规则：
  - AGENTS.md
  - docs/skills/greenhouse-github-development-efficiency/SKILL.md
  - docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set
- 任务资料：
  - 本交接：恢复本轮停点和下一动作。
  - docs/development/N3W_CURRENT_STATE.md 顶部 KF-153 authority：live U5 / IPC serving-thread failure 基线。
  - docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md 顶部 KF-153：物理根因与 regression guard。
  - tools/execution_packages/n3w/r7a/kf153_r20_u5_ipc_source_activation_successor/manifest.json：R20 exact contract / expected live entry / authorization state。
  - tools/execution_packages/n3w/r7a/kf153_r20_u5_ipc_source_activation_successor/executor.py：preflight/execute 实际行为；执行前核对 exact blob。
  - tests/tools/test_n3w_t1_kf153_r20_u5_ipc_source_activation_successor.py：fixed-dev 禁用、claim durability、lifecycle order 回归。
  - systemd ownership 仅在 preflight 异常或后续 activation 复核时按需补读：infra/n3w-t1/systemd/n3w-t1-ha-ota.service 与 infra/n3w-t1/systemd/n3wfc4-services-activation.ha-ota.conf。
- 已归档：
  - PR #807 final alignment comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6854698818
  - PR #807 R19/KF-153/R20 progress comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6854503660
  - R20 exact source commit: https://github.com/chrenguo-stack/HomeAssistant/commit/a81708cfc821bc0df9feff9318b6752d743d497e
- 未归档重要资料：
  - R19 raw evidence 保存在操作者本地私有 evidence root；公开 GitHub 仅保存脱敏结论，这是有意的安全边界。
  - T1 SSH target、known_hosts 本地路径、host-key binding 继续保留在私有执行上下文，不写入公共仓库；新会话从私有上下文恢复，不要求用户重新提供。

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=1
TEAM_SHARE_COMPLETENESS=PASS

新会话启动语：阅读本交接和适用仓库指令，fresh rebind PR #807 与 exact R20 source head a81708cfc821bc0df9feff9318b6752d743d497e，确认 16/16 CI authority 未被 supersede。不要重新设计 R20，不要重跑 R18；直接执行 R20 真实 T1 --preflight-only。preflight PASS 后归档，并停在 R20 live U5 IPC source activation 的新一次性写授权边界。
