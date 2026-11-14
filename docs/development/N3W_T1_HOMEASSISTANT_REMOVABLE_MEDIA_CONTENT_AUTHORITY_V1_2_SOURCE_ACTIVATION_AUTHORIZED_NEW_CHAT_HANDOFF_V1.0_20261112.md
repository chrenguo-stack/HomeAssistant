# N3-W Home Assistant removable-media content-authority V1.2
# 真实 T1 8 文件源码激活
# 新会话交接文档 V1.0 — 2026-11-12

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：V1.2“可替换介质 + 内容权威”源码修复、真实 T1 只读预检、8 文件源码激活包设计与授权均已完成。当前会话在真实写入前结束；新会话执行已明确授权的 8 文件 V1.2 source activation。
- 已完成到：
  - Source Repair 已 `CLOSED_PASS`，authority head `2639538a9c00a3ac1d9655681a49bef1d821ba1c`。
  - real-T1 read-only preexecution 已 `CLOSED_PASS` / RC 0；legacy schema /1 U4 transaction 精确保持，服务、三容器、IPC 均健康，兼容 `ext4 + N3W-UPDATE` 介质可通过 fresh inventory 重新发现；零 T1/USB/transaction/U5 mutation。
  - 真实 T1 已采集 8 个 predecessor source SHA-256，并固化到 source-activation manifest。
  - source-activation package 的未授权 head `d61bd73c505255bedb89461e5a9c32a978b2f608` 已 16/16 workflow SUCCESS。
  - 用户在本会话明确授权下一会话执行真实 T1 8 文件源码激活。
  - grant-only manifest commit `f1d2ab8e99f6637a7f3ef3c00deb1b4ec50d89f9` 已建立；其 target-binding CI 仅因两条测试仍断言 UNGRANTED 而失败，未发生任何 T1 访问或 mutation。
  - 同 gate 测试修复后，当前授权执行候选 head 为 `edc3d2b76c5a7a75382f056c11786f00d32c0fa6`。
- 当前状态：**等授权执行候选 head 的 fresh CI 终态**。新会话第一步核对 `edc3d2...` 全部适用 CI；只有全绿且真实 T1 fresh preflight 仍通过，才执行 source activation。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: `#807`，OPEN / DRAFT / UNMERGED
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - main tree: `26a4cca2280f921ca3e51a91d3a393437cf039b4`
  - source-repair authority: `2639538a9c00a3ac1d9655681a49bef1d821ba1c`
  - real-T1 readonly package head: `24671c19b72f58e069f63b97992826681caca8e2`
  - authorized execution candidate head: `edc3d2b76c5a7a75382f056c11786f00d32c0fa6`
  - authorized candidate tree: `34f385999eacf615fbcbe23cc15744b0c4391f6a`
- exact execution package:
  - executor: `tools/execution_packages/n3w/r7a/kf147_removable_media_content_authority_v1_2_source_activation/executor.py`
  - executor blob: `bfa1f0b4e5f345b0cfda30725bd6f72f76a41c3d`
  - manifest: `tools/execution_packages/n3w/r7a/kf147_removable_media_content_authority_v1_2_source_activation/manifest.json`
  - authorized manifest blob: `68618d76b40dfa169e2b0c61e56240cfcac66c7e`
  - focused test blob at candidate head: `66f0b8ae1c066ebce29bb0210e8b7c149a7fb60d`
- manifest exact live authority:
  - `live_execution_authorized=true`
  - `authorization_state={granted:true,claimed:false,consumed:false,replay_permitted:false}`
  - scope: `activate_exact_8_file_v1_2_source_slice_on_real_t1_only`
- 上一未授权 package head `d61bd73...` 的 16 个 workflow 均 SUCCESS。关键 run：
  - HA target binding: `43249285682` SUCCESS
  - Manager A-to-B: `43249285835` SUCCESS
  - Core Stack current authority: `43249285756` SUCCESS
  - fast source/exact: `43249285481` SUCCESS
  - Public repository safety: `43249285708` SUCCESS
- 当前授权候选 `edc3d2...` 的 fresh CI 必须在新会话重新确认；旧 head 的绿灯不能代替授权候选的 fresh CI。
- 证据入口：
  - `docs/development/N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_REPAIR_CLOSURE_20261112.md`
  - `docs/development/N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_READONLY_PREEXECUTION_CLOSURE_20261112.md`
  - `docs/development/N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_ACTIVATION_DESIGN_20261112.md`
  - source-activation manifest / executor / focused test named above。

## 3. 必须继承的结论

- 已证实：
  - V1.2 physical-media identity continuity 已被源码层移除；跨会话不再以 `/dev/sdX`、filesystem UUID 或 public fingerprint 作为业务权威。
  - real-T1 read-only preexecution PASS：exact transaction phase=`U4_READY_TO_INSTALL`，transaction SHA-256=`dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259`；authorization 未 claim/consume。
  - OTA service active/running、restart 0；Manager / Home Assistant / Broker 均 running、restart 0；IPC=`READY_TO_INSTALL`、error=null。
  - fresh inventory 发现恰好一个安全兼容、未挂载的 `ext4 + N3W-UPDATE` removable medium；该结果不依赖旧 UUID/fingerprint。
  - real-T1 read-only gate 无 mount/umount、无 source/state/USB/transaction mutation、无 U5/U6+。
  - 8 个 predecessor source SHA-256 与 8 个 repository target SHA-256/Git blob 已由 activation manifest 精确绑定；target hashes 另有 CI focused test 重新计算校验。
  - source-activation 只替换 8 个文件：`usb_state / usb / usb_media / backup / recovery / prepare / prepare_host / ipc`；`capacity / daemon / v2_common / v2_state / portable_image_identity` 保持未修改并由 runtime blob 校验。
  - 激活成功必须保持原 U4 transaction SHA 完全不变，且 postvalidation 仍为 READY_TO_INSTALL；本 gate 不执行 INSTALL。
- 待确认：
  - `edc3d2b76c5a7a75382f056c11786f00d32c0fa6` 的全部适用 GitHub CI 必须 fresh 终态 SUCCESS。
  - 真正执行时必须由 executor 自带的 remote preflight fresh 验证：legacy U4 transaction、8 predecessor source、未修改依赖、服务/容器/IPC、唯一安全兼容介质。
- 已排除：
  - R12 live mount-restoration route 已被 V1.2 supersede，不得恢复。
  - 旧 physical UUID/fingerprint continuity route 已关闭。
  - 旧 R10 三文件 source-activation package 不得用于当前 V1.2 八文件激活。
  - `f1d2ab8e...` 的失败仅为授权后测试合同未更新；已由 `edc3d2...` 测试修复 successor 替代，禁止执行旧失败 head。

## 4. 执行范围与授权

- 可继续：
  - 新会话 fresh rebind repository / branch / PR / `edc3d2...`；
  - 检查授权候选 fresh CI；
  - CI 全绿后，使用 exact source-activation executor 在真实 T1 执行已授权的 8 文件源码激活；
  - executor 内置 read-only preflight、private staging、predecessor backup、一次性 authorization claim、服务 stop/start、8 文件 atomic replacement、postvalidation；
  - 若 lifecycle/source mutation 后失败，允许 executor 合同内 **最多一次** 自动 source rollback。
- 暂停边界：
  - 本次授权只覆盖 **8 个 V1.2 源码文件激活并恢复到 U4 READY_TO_INSTALL**。
  - source activation 成功后立即 STOP；不得自动发送 INSTALL，不得进入 U5/U6+。
  - 禁止 mount/umount、USB filesystem write、USB mutation、transaction mutation、target archive mutation、HA/Manager/Broker image mutation、board access、merge。
  - 若 fresh preflight 失败：未 claim 授权，直接 STOP。
  - 若 authorization 已 claim 后失败：授权视为 consumed；最多执行 executor 内的一次 rollback；无论 rollback PASS/FAIL 都不得自动重试。
- 授权状态：
  - 来源：用户在 2026-11-12 当前会话明确同意“在新对话中执行在真实 T1 上激活这 8 个 V1.2 源码文件”。
  - gate: `N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_ACTIVATION_20261112_01`
  - authorized candidate: `edc3d2b76c5a7a75382f056c11786f00d32c0fa6`
  - grant manifest blob: `68618d76b40dfa169e2b0c61e56240cfcac66c7e`
  - `GRANTED=true`
  - `CLAIMED=false`
  - `CONSUMED=false`
  - `REPLAY_PERMITTED=false`
  - 有效条件：candidate exact、fresh CI 全绿、executor remote preflight PASS、state_root/staging 无冲突；任一漂移则受影响操作 STOP。

## 5. 下一步

- 行动：
  1. 新会话读取本交接、当前仓库指令、`N3W_PROJECT_WORKING_CONTEXT.md` 相关规则、current state/index、source-activation design、readonly closure、exact executor/manifest/test。
  2. fresh rebind PR #807、branch，并确认 authorized candidate `edc3d2b76c5a7a75382f056c11786f00d32c0fa6` 仍存在且 manifest/executor/source blobs 无漂移。
  3. 检查 `edc3d2b76c5a7a75382f056c11786f00d32c0fa6` 的全部适用 CI；必须全绿。CI 同一 head 最多主动轮询 3 次。
  4. 以 `edc3d2b76c5a7a75382f056c11786f00d32c0fa6` 创建 exact detached worktree；不要使用最终 handoff docs-only head 作为实机执行 authority。
  5. 使用 source-activation executor 的 `--execute` 模式。该模式在任何 staging/claim 前会先运行完整 remote read-only preflight。
  6. preflight PASS 后才 staging；随后 executor claim 一次性授权并执行 8 文件激活。
  7. 保存私有执行证据；将 public-safe 结果归档 GitHub；STOP before INSTALL/U5。
- 完成条件：
  - `status=V1_2_SOURCE_ACTIVATION_PASS`
  - `source_activated=true`
  - `u4_preserved=true`
  - 8 target source hashes exact
  - transaction SHA 仍为 `dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259`
  - OTA host / services owner healthy
  - Manager/HA/Broker running
  - IPC=`READY_TO_INSTALL`
  - `transaction_mutation=false`
  - `usb_mutation=false`
  - `u5_transition=false`
  - `u6_plus=false`
  - `rollback_required=false`
- 失败／停点：
  - preflight STOP：不 staging、不 claim、不 mutation；归档原因后停止。
  - claim 后失败：授权 consumed；允许一次自动 rollback。rollback 后无自动第二次 activation。
  - rollback incomplete：`ROLLBACK_INCOMPLETE`，立即停止并进入只读 forensic/recovery 设计。
  - activation PASS：只归档并停在 U4；下一 INSTALL/U5 是新的 gate，不在本授权内。

## 6. 必读定位与归档

- 仓库规则：
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`：重点读 GitHub/CI、授权与 mutation、最小新会话 read set、公开/私有信息边界。
  - 正式模板：`docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`，V1.4。
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：按 KF-147 / HA USB OTA 相关条目补读。
  - `docs/development/N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_ACTIVATION_DESIGN_20261112.md`
  - `docs/development/N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_READONLY_PREEXECUTION_CLOSURE_20261112.md`
  - exact source-activation executor / manifest / focused test。
- 已归档：Source Repair closure、real-T1 readonly closure、activation design、current state/index、exact package、CI 记录和 PR #807 Conversation。
- 未归档重要资料：
  - 真实 T1 的私有 SSH locator、known-host material、host-key 信息和本地 private evidence 路径按项目规则不进入公开 GitHub；新会话从私有上下文恢复，不要求用户重复提供。
  - 无重要工程结论仅存在聊天中；public-safe 结论均已写入 GitHub。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind `edc3d2b76c5a7a75382f056c11786f00d32c0fa6` 并确认其 CI 全绿；若 exact authority 和真实 T1 remote preflight 均无漂移，直接执行已授权的 8 文件 V1.2 source activation；成功后停在 U4，不进入 INSTALL/U5。
