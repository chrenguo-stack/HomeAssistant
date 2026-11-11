# N3-W T1 KF-147 U4 Mount Recovery PASS → Official U5 Preflight Binding Repair
# 新会话交接文档 V1.0 — 2026-11-11

`HANDOFF_TEMPLATE_VERSION=1.4`

> 本交接按 main commit `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d` 的正式 V1.4 模板生成；template blob `885fd63131e80936e5e1fe907378be08a0060f12`。
> PR #807 分支中的历史模板副本不得用于生成新交接。

## 1. 目标与停点

- 任务／交接原因：
  - 继续“温室环境监测系统（ESP32-C6）”N3-W 的 KF-147 Mandatory USB Home Assistant OTA 收口；
  - 本轮在正式 U5 只读资格预检发现历史设备路径漂移和 USB 未挂载后，完成同一 U 盘身份取证、原 U4 挂载恢复、精确目标归档复核、失败脚本修复、GitHub 归档及状态对齐；
  - 用户明确要求本轮不再推进开发，在新会话修正正式 U5 预检对 `/dev/sdb1` 的固定判断，并验证当前挂载条件。
- 已完成到：
  - 正式 U5 preflight 已通过严格 SSH 绑定访问 T1，但在 `usb_partition_drift` fail-closed；当时未发生远端暂存、源码、USB、Home Assistant、Manager 或 Broker 修改；
  - 独立只读取证确认文件系统 UUID 和交易绑定的 USB 公共身份连续，同一分区由历史 `/dev/sdb1` 重新编号为 `/dev/sda1`；
  - SSH 进程与 OTA service 共用同一 mount namespace，二者当时均确认该 USB 未挂载；
  - 用户明确批准 U4 挂载恢复；执行工具 Attempt 01 因缺少 `lsblk --tree` 在挂载前停止，Attempt 02 因原 mountpoint 不存在在挂载前停止；两次均 `mount_attempted=false`；
  - 修复后的 Attempt 03 创建两个私有 runtime 目录，以 `ro,noload,nodev,nosuid,noexec` 恢复原事务 mountpoint，精确目标验证通过；
  - Attempt 03 终态为 `U4_MOUNT_RECOVERY_PASS / rc=0`；transaction 仍为 `U4_READY_TO_INSTALL`，运行时未变化，未部署源码、未重启服务、未进入 U5/U6+；
  - current state、index、known-failure guards、恢复执行工具、测试和 public-safe 现场结论均已归档。
- 当前状态：
  - `STOPPED_BY_USER_AFTER_U4_MOUNT_RECOVERY_PASS_BEFORE_OFFICIAL_U5_PREFLIGHT_SOURCE_REPAIR`；
  - `official_u5_preflight_pass=false`；
  - U4 恢复授权已完成其唯一用途，不得重放；
  - 下一会话可在用户本次明确指令范围内连续执行正式 U5 preflight 的源码修复、测试、GitHub 归档和当前挂载条件的有界只读验证；不得进入 U5 安装或改变 mount mode。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - PR #807: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR source branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - recovery/archive branch: `exec/kf147-u4-readonly-mount-recovery-20261111`
  - PR state at handoff: OPEN / DRAFT / MERGEABLE / not merged
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - official U5 source/package authority: `7a641462f321fd5d738eff78624d675839c0a63d`
  - PR #807 current head: `da5c16886e4d129e3398caa9df61a1ebb07ecdf8`
  - `7a641462... → da5c1688...`：正好一个 formal handoff 文档提交，没有产品源码或 package 漂移；
  - U4 recovery executed operator head: `b4f0dd23edf8b96cd4d2354973b9a9774b40947e`
  - recovery closure head before current-state alignment: `715416a4be8fa2caf56ddc6f73121965ba4c0f7b`
  - current-state/index alignment head before this handoff: `9f0ef19f839fa32b7e9f8076c5068e355e615c85`
  - 新会话必须 fresh rebind 本交接所在分支的当前 HEAD；不得把 recovery/archive branch 误当作 U5 产品源码 authority。
- official U5 preflight frozen files at `7a641462...`：
  - `tools/execution_packages/n3w/r7a/kf147_u4_to_u5_install_intent_preflight/executor.py`
    - Git blob `948621386d869b28a7fad072cb3b857205465d44`
    - 当前缺陷：`partition != plan["usb_partition"]` 时直接 `usb_partition_drift`
  - `tools/execution_packages/n3w/r7a/kf147_u4_to_u5_install_intent_preflight/manifest.json`
    - Git blob `8e29f1c64489104dfe94866b7a8a6a364552c490`
    - 当前缺陷：`usb_partition=/dev/sdb1` 被作为未来仍必须相同的资格条件
  - `tests/tools/test_n3w_t1_kf147_u4_to_u5_install_intent_preflight.py`
    - Git blob `9c353c4166c420a15314e7a7887822a597fd939d`
    - 现有测试没有覆盖同一 USB 因内核枚举顺序变化而从 `sdb1` 变为 `sda1`
- U4 recovery archive：
  - operator: `tools/execution_packages/n3w/r7a/kf147_u4_mount_recovery/executor.py`
  - tests: `tools/execution_packages/n3w/r7a/kf147_u4_mount_recovery/test_executor.py`
  - executed operator SHA-256: `ad84aa7794474f7341989cc0d12f56c11815fd26a98db95c1b67af062ea88a8c`
  - local validation: Python compilation PASS；15 unittest methods PASS
  - 这些测试和 U4 实机 PASS 只证明本次恢复工具；没有新的 CI，也不证明 official U5 preflight 已修复。
- U4 exact evidence：
  - transaction file SHA-256: `dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259`
  - phase/status: `U4_READY_TO_INSTALL / ACTIVE`
  - target size: `835309535` bytes
  - target SHA-256: `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`
  - same USB identity: true
  - current kernel partition observation: `/dev/sda1`
  - recovered mount mode: `read_only_no_journal_replay`
  - transaction/runtime unchanged: true/true
- CI authority retained from source head `7a641462...`：
  - target-binding run `43019235001`: SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43019235001
  - Manager A-to-B run `43019234910`: SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43019234910
  - 两个 run 仍为 completed/success；它们不覆盖下一会话尚未产生的 preflight source repair。
- 证据入口：
  - first known-host binding STOP: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6796155145
  - official preflight `usb_partition_drift` STOP: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6796244190
  - same USB / path renumbering evidence: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6796476813
  - host-view unmounted evidence: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6796680023
  - shared mount namespace / service-view unmounted evidence: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6796749262
  - U4 recovery package preparation: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6796881116
  - recovery Attempt 01 STOP / `lsblk --tree` repair: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6796970385
  - recovery Attempt 02 STOP / mountpoint repair: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6797044777
  - recovery Attempt 03 PASS: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6797091202

## 3. 必须继承的结论

- 已证实：
  - `/dev/sda1` 与历史 `/dev/sdb1` 是同一交易绑定 USB 上、同一 filesystem UUID 所定位的分区；Linux 临时设备路径不是稳定身份；
  - 原 USB 在 Attempt 03 后已恢复到原 transaction-derived mount target，读取目标归档并重新计算 SHA-256 成功；
  - mount 是只读、禁止 journal replay，并带 `nodev,nosuid,noexec`；这足以完成本次只读恢复验证；
  - U4 transaction、installed predecessor source、OTA service、Manager/Home Assistant/Broker 容器和 Manager IPC 在恢复前后保持一致；
  - U4 recovery 没有部署 U5 source、重启 service、修改 transaction、进入 U5 或 U6+；
  - official U5 preflight 在当前源码下必定因历史 `/dev/sdb1` path equality 对当前 `/dev/sda1` fail-closed；不得把 recovery PASS 写成 official preflight PASS；
  - U4 recovery Attempt 01/02 均在 mount 前停止；Attempt 03 是唯一执行 mount 的成功 attempt，已经完成且不可重放；
  - PR #807 从 official U5 source authority 到当前 PR head 只有旧交接文档，source/package authority 仍为 `7a641462...`。
- 待确认：
  - official U5 preflight 的稳定 USB 合同应从现有产品代码和 U4 transaction 独立复核；预期至少包括唯一 filesystem UUID、交易绑定 USB 公共指纹、USB/removable/read-write device properties、root-device exclusion、ext4、expected mount target 和实际 block-device source；
  - 需判定 mount source 比较应使用 canonical block device 或 major:minor，而非不稳定的 `/dev/sdX` 文本；
  - 需复核 OTA service mount namespace 与 preflight 进程的视图是否应作为正式资格条件；
  - 当前 read-only/no-journal-replay mount 是否足够用于“U5 install intent eligibility”尚未由正式产品合同证明。它不能被默认为 writable installation readiness；
  - 如果 U5 intent 或紧随其后的安装阶段需要向 USB 写入 transaction/recovery assets，则应由 preflight fail-closed 并另立 mount-mode 恢复/写入授权；本交接不授权 remount read-write；
  - 当前 mount 在新会话开始时仍是否存在属于 `UNKNOWN_FRESH`，必须在 source repair 后通过用户私有 SSH binding 做最小只读核对。
- 已排除：
  - USB 已更换或目标归档损坏作为当前原因；
  - T1/OTA service 使用不同 mount namespace 作为此前“未挂载”观察的解释；
  - U5 preflight STOP 是 U4 transaction、target size/SHA、containers 或 IPC drift；
  - 将内核临时路径 `/dev/sda1` 或 `/dev/sdb1` 固化为设备身份；
  - 重放 R5、R6 或 U4 mount recovery authorization；
  - 把旧 CI SUCCESS、U4 recovery PASS 或交接文档解释为 U5 installation authorization。

## 4. 执行范围与授权

- 可继续：
  - 用户已明确要求在新会话继续修正 official U5 preflight 对 `/dev/sdb1` 的固定判断，并验证当前挂载条件；
  - 在 fresh rebind 无漂移后，可连续完成 official preflight executor/manifest/test 的最小源码修复、本地聚焦测试、适用 CI、GitHub 状态/KF/交接归档；
  - 可通过用户私有 T1 SSH locator、strict known-hosts 和既有可信 host-key binding 做与此任务直接相关的只读挂载验证；
  - 可执行修复后仍为 read-only、preflight-only、ungranted 的 official U5 eligibility preflight，并归档 public-safe 结果。
- 暂停边界：
  - 不得重放成功的 U4 mount recovery；
  - 不得 remount read-write、unmount、fsck、格式化、重分区、清理或写入 USB；
  - 不得部署 U5 product source、重启 OTA service、执行 U4→U5 transition；
  - 不得停止 Home Assistant、创建 recovery assets、删除或载入镜像、改变 Manager/Broker/Home Assistant；
  - 不得进入 U6+ 或 U9 destructive/install phase；
  - 不得访问板卡；
  - 不得合并 PR #807 或 recovery/archive branch。
- 授权状态：
  - R5/R6 及以前一次性授权：已认领、已消费、不可重放；
  - U4 mount recovery：用户明确批准，Attempt 03 已成功完成；授权用途已完成，按 non-replayable 处理；
  - official U5 preflight source/test/read-only validation：由用户本次交接指令明确允许在新会话推进；
  - U5 live install/source deployment authorization：未授予；
  - U5 authorization claimed=false / consumed=false；manifest 的 `live_execution_authorized=false` 保持；
  - 本交接不授予 U5 安装、mount-mode 变更、service mutation、U6+、merge 或 deployment 权限。

## 5. 下一步

- 行动：
  1. 阅读本交接和适用仓库规则；fresh rebind main、PR #807、official U5 source authority `7a641462...`、current PR head、recovery/archive branch current head；
  2. 确认 `7a641462... → da5c1688...` 仍只有旧交接文档；确认 recovery branch 后续只包含本轮 source/test/KF/state/index/handoff 归档；
  3. 复核 official U5 executor、manifest、tests 和 `SubprocessPrepareBackend.reopen_bound_media()` 的稳定 USB 身份算法；
  4. 设计并实现最小 repair：
     - 取消历史 `/dev/sdb1` 作为资格 authority；
     - 使用唯一 filesystem UUID 定位当前 partition；
     - 将 partition 绑定到唯一 USB parent disk，按产品 canonical 算法核对 transaction-bound public fingerprint；
     - 保留 USB/removable/read-only device properties、root-device exclusion、ext4、expected mount target 和实际 source 校验；
     - 使用 explicit `lsblk --tree` 或同等稳定 parent binding，使用 canonical path/major:minor 判断 mount source；
     - 明确读取并验证当前 mount options；不要预设 read-only 一定可接受；
  5. 增加回归测试：同一 USB `sdb1→sda1` PASS、错 USB、重复 UUID、非 USB/非 removable/只读 block device、root disk、非 ext4、未挂载、挂到别处、错误 source、错误 mount namespace，以及 read-only mount policy 分支；
  6. 运行聚焦测试和适用 CI；新源码提交后不得复用 `7a641462...` 的 CI 证明新 head；
  7. source/test/CI 通过后，fresh bind 私有 SSH identity，以 bounded read-only official preflight 核对当前 mount；
  8. 将 public-safe 结果归档到 PR #807 和 current state。
- 完成条件：
  - official preflight 不再依赖 `/dev/sdb1` 或任何固定 `/dev/sdX`；
  - UUID、USB public fingerprint、filesystem、root exclusion、mount target/source/namespace/mode 合同均有源码和回归测试；
  - 修复后 exact head 的适用 CI PASS；
  - fresh T1 read-only preflight 明确返回 PASS，或对 read-only mount 给出准确 fail-closed reason；
  - 若 PASS：`status=PASS`、`read_only_preflight=true`、`u5_intent_eligible=true`、authorization claimed/consumed=false/false、所有 mutation=false；
  - 结果、SHA、测试和证据已归档；
  - 即使 PASS，也停止在 `FRESH_EXPLICIT_U5_INSTALL_AUTHORIZATION_REQUIRED`。
- 失败／停点：
  - repository/source/runtime/USB identity/target/container/IPC 任一 fresh drift => STOP，只读分类并归档；
  - 当前 mount 已丢失或 source/namespace 不匹配 => STOP；不得自动重放 U4 recovery；
  - read-only mount 不满足正式 U5 资格 => STOP 并给出源码依据；不得自动 remount；
  - 新测试或 CI 非 PASS => 修复局部明确源码问题；不得执行实机 preflight；
  - official preflight PASS => 本任务完成并停止；不得自动部署 U5 source 或执行安装。

## 6. 必读定位与归档

- 仓库规则：
  - root `AGENTS.md` 及其引用规则；
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` 中与任务相关的稳定规则；
  - [工作上下文的 minimum new-chat read set](N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)；
  - V1.4 template authority 使用 main commit `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`。
- 任务资料：
  - 本交接；
  - `docs/development/N3W_T1_KF147_U4_READY_TO_U5_READONLY_PREFLIGHT_ATTEMPT01_STOP_REPAIR_CI_PASS_NEW_CHAT_HANDOFF_V1.0_20261111.md`：上一停点、official U5 source/CI authority；
  - `docs/development/N3W_T1_KF147_U3_BOUND_MEDIA_RECOVERY_AND_ERROR_VISIBILITY_SOURCE_DESIGN_20261110.md`：稳定 USB/恢复产品设计；
  - `docs/development/N3W_CURRENT_STATE.md` 最新 KF-147 U4 mount recovery 条目；
  - `docs/development/N3W_CURRENT_STATE_INDEX.md` 最新索引条目；
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 最新三个 U4 mount operator 条目和此前 KF-147 条目；
  - official U5 preflight executor/manifest/test；
  - `tools/n3w_t1_core_updater_ha_prepare_host.py` 中 stable fingerprint 与 `reopen_bound_media()`；
  - recovery executor/tests 仅用于理解已完成恢复和故障，不作为 U5 product authority。
- 已归档：
  - PR #807 public-safe evidence comments（第 2 节链接）；
  - recovery operator/tests/KF guards/state/index 在 `exec/kf147-u4-readonly-mount-recovery-20261111`；
  - official source/CI 在 PR #807 source authority `7a641462...`；
  - 本交接文件。
- 未归档重要资料：
  - 无。operator-local SSH locator、known-hosts、可信 host key、Mac private evidence directories 和原始设备身份故意保留在用户私有上下文；public-safe 结果已归档，未来必须 fresh bind，不能从公共 GitHub 推导私有执行 identity。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

```text
阅读：
docs/development/N3W_T1_KF147_U4_MOUNT_RECOVERY_PASS_TO_OFFICIAL_U5_PREFLIGHT_BINDING_REPAIR_NEW_CHAT_HANDOFF_V1.0_20261111.md

同时按需读取：
- AGENTS.md 及其引用规则
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_KF147_U4_READY_TO_U5_READONLY_PREFLIGHT_ATTEMPT01_STOP_REPAIR_CI_PASS_NEW_CHAT_HANDOFF_V1.0_20261111.md
- docs/development/N3W_T1_KF147_U3_BOUND_MEDIA_RECOVERY_AND_ERROR_VISIBILITY_SOURCE_DESIGN_20261110.md

V1.4 template authority：
main commit 3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
template blob 885fd63131e80936e5e1fe907378be08a0060f12

fresh rebind：
- repository main
- PR #807
- OFFICIAL_U5_SOURCE_AUTHORITY_HEAD=7a641462f321fd5d738eff78624d675839c0a63d
- PR_HEAD=da5c16886e4d129e3398caa9df61a1ebb07ecdf8
- recovery/archive branch current head
- CI runs 43019235001 and 43019234910

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

当前状态：
KF147_U4_READONLY_MOUNT_RECOVERY_CLOSED_PASS_U5_PREFLIGHT_REPAIR_PENDING
OFFICIAL_U5_PREFLIGHT_PASS=false
CURRENT_MOUNT_FRESH_STATE=UNKNOWN_FRESH

NEXT_ONE_GATE=
N3W_T1_KF147_OFFICIAL_U5_PREFLIGHT_DYNAMIC_USB_BINDING_SOURCE_REPAIR_AND_CURRENT_MOUNT_VALIDATION_20261111_01

用户已授权在新会话连续推进 official U5 preflight 的最小源码修复、测试、CI/GitHub 归档及当前挂载条件的 bounded read-only verification。

必须修复：
- 不得再把 /dev/sdb1 或任何 /dev/sdX 作为稳定 USB 身份；
- 用 UUID + transaction-bound USB public fingerprint + filesystem/root-exclusion + actual mount source/target/namespace/mode 做 fail-closed 验证；
- 独立判断当前 read-only/no-journal-replay mount 是否满足 U5 eligibility，不能把 recovery PASS 自动写成 writable install readiness。

边界：
SOURCE_DEPLOYMENT=false
SERVICE_RESTART=false
U4_TO_U5_TRANSITION=false
USB_WRITE_OR_REMOUNT=false
HOMEASSISTANT_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
U6_PLUS=false
BOARD_ACCESS=false
MERGE=false

修复后 CI PASS 才能执行 bounded read-only T1 preflight。
若 official preflight PASS，停止在 FRESH_EXPLICIT_U5_INSTALL_AUTHORIZATION_REQUIRED。
若 read-only mount 不满足产品合同，STOP 并归档，不自动 remount 或安装。
R5、R6、U4 mount recovery 及所有已消费授权不得 replay。
```
