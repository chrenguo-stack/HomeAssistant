# N3-W T1 U7 R30M source CLOSED_PASS → real-T1 read-only preflight 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

> 本交接严格使用 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4（blob `885fd63131e80936e5e1fe907378be08a0060f12`）。只记录本阶段增量。公开内容不包含密码、私网 SSH locator、原始 USB 身份值或私有证据路径。

## 1. 目标与停点

- 任务／交接原因：继续 N3-W T1 Home Assistant USB Mandatory OTA R7A / U7 收口。R30S 已完成；R30 read-only Attempt01 因运行时 USB 挂载在重启后未恢复而安全 STOP。本轮已完成 R30M 可写挂载恢复 successor 的源码、测试、CI 和归档，按用户要求停止开发并切换新对话。
- 已完成到：R30M exact executable source authority `f814f604666273c2d8259a394a1bda44bae4b81f`，fresh CI 16/16 SUCCESS；HA source 651 tests PASS，HA exact-binding SUCCESS，Manager A-to-B SUCCESS。
- 当前状态：可继续，但下一步仅允许 `R30M_REAL_T1_READONLY_PREFLIGHT`。R30M live writable mount 未授权；R30 live execution 未授权。

## 2. 代码与证据

- 仓库／分支／PR：`chrenguo-stack/HomeAssistant` / `fix/kf147-u3-recovery-and-error-visibility-20261110` / https://github.com/chrenguo-stack/HomeAssistant/pull/807
- 核对时 main／本任务源码：
  - main = `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - R30M executable-source authority = `f814f604666273c2d8259a394a1bda44bae4b81f`
  - PR #807 在源码闭环时为 OPEN / DRAFT / MERGEABLE。
- R30M exact blobs：
  - executor = `5718ae2b281877c3faf32b998037c4bf91cde255`
  - manifest = `fda133d8457029b2f166cf663dad9998cda5cd61`
  - focused test = `e9aeb3d69a29e54194ca4d649127335c721924b2`
  - HA target-binding workflow = `87041a0a5139046ee2710195172b827fa30f8d7b`
- 关键 CI：
  - HA target-binding: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43676613091 — SUCCESS；source=651 passed；exact-binding=SUCCESS
  - Manager A-to-B: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43676613283 — SUCCESS
  - exact source head total = 16/16 SUCCESS
- 关键公开证据：
  - R30S live closure: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6887152193
  - R30 Attempt01 safe STOP: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6888741085
  - controlled reboot boundary: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6888979732
  - R30M source candidate: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6889072283
  - R30M final CI closure: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6889212438
- 私有原始证据：operator-local 保留；未公开凭据、原始设备身份或 SSH locator。

## 3. 必须继承的结论

- 已证实：
  - R30S 单文件 `prepare_host` live activation = `U7_R30S_PREPARE_HOST_SOURCE_ACTIVATION_PASS`，authorization claimed + consumed，`replay_permitted=false`；不得重放。
  - durable transaction 仍为 `U6_PREDECESSOR_RECOVERY_PREPARING`，SHA-256 `7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe`。
  - R30 Attempt01 = SAFE STOP，原因 `u7_media_not_already_mounted`；未 claim、未停服务、未 quiesce HA、未改 transaction/USB、未进入 U7/U8+。
  - controlled reboot 后的只读证据证明：transaction-bound removable media 仍是同一绑定介质，文件系统为 ext4、标签 N3W-UPDATE、状态 clean，但未挂载；运行时挂载目录没有跨 reboot 自动恢复。
  - Manager / Home Assistant / Broker 在重启后恢复 running；该证据是历史快照，当前 fresh 状态必须重新核对。
  - R30M 不固定 `/dev/sdX`，使用 transaction-bound media identity；preflight 要求介质 present + clean + unmounted。
  - R30M source `f814f604666273c2d8259a394a1bda44bae4b81f` 已 16/16 CI SUCCESS；前两轮 embedded-script 重复函数定义错误已局部修复，最终 HA suite 651 passed。
  - KF-156：T1 eth0 间歇性 Link Down/Up 已实机证明，并与 SSH banner/preauth 超时同阶段出现；sshd/password 故障不受当前证据支持。具体物理/驱动根因仍未证明。
- 待确认：
  - `CURRENT_FRESH_MEDIA_STATE=UNKNOWN_FRESH`；由 R30M real-T1 read-only preflight 重新证明。
  - `CURRENT_FRESH_RUNTIME=UNKNOWN_FRESH`；同一 preflight 必须重新核对 units/containers/source/transaction。
  - 若 SSH 再次卡住，先做 bounded transport/network read-only 诊断；不要把 transport failure 当成 mutation failure。
- 已排除：
  - 不重放 R30S。
  - 不在 USB 未挂载状态直接重跑 R30。
  - 不使用固定 `/dev/sda1` / `/dev/sdb1` 作为 durable authority。
  - 不用临时手工 mount 绕过 R30M gate。
  - 不把瞬时干净的网卡错误计数当成“历史没有 link flap”的证据。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind main / PR #807 / `f814f604666273c2d8259a394a1bda44bae4b81f`；
  - 验证 docs-only archive 没有改变 executable-source authority；
  - 重新读取 R30M manifest/executor；
  - 执行 **R30M real-T1 `--preflight-only`**；
  - 对 preflight 结果做源码/实机证据复核并归档。
- 暂停边界：
  - R30M preflight PASS 后必须停在 **writable-mount explicit authorization boundary**。
  - 禁止未经新授权执行 R30M `--execute`、创建运行时挂载、触发 ext4 rw journal write。
  - 禁止直接执行 R30 live HA quiesce/data-backup。
  - 禁止 U7 transition、U8+、板卡访问、PR merge。
- 授权状态：
  - R30S：claimed=true / consumed=true / replay=false，终态，不可重用。
  - R30：live_execution_authorized=false；granted=false / claimed=false / consumed=false。
  - R30M：live_execution_authorized=false；granted=false / claimed=false / consumed=false / replay=false。
  - 交接本身不授予新 live 权限。

## 5. 下一步

- 行动：
  1. 读取本交接、根目录 `AGENTS.md`、V1.4 template、Current State/Index/Working Context 和 R30M package。
  2. fresh rebind main、PR #807、source authority `f814f604666273c2d8259a394a1bda44bae4b81f`；若 PR 已 docs-only 前进，证明 `f814f604666273c2d8259a394a1bda44bae4b81f` 之后只有归档文档变化，不能把 docs head 当 executable authority。
  3. 确认 R30M exact source 16/16 SUCCESS，manifest 仍 ungranted。
  4. 执行 R30M real-T1 read-only preflight only。
  5. PASS 则归档并停止于 explicit writable-mount authorization；STOP 则按实际 stop code 归档并修复，不自动 mount、不自动重试 live。
- 完成条件：
  - `status=PASS`
  - `read_only=true`
  - `restoration_eligible=true`
  - authorization claimed/consumed 均 false
  - runtime directory creation / writable mount attempt / USB mutation / transaction mutation 均 false
  - exact U6 transaction、R26/R29/R30S consumed/no-replay、current installed-source hashes、healthy runtime、bound media present-clean-unmounted 均重新验证
  - 证据保存到 operator-private evidence root，并将 public-safe closure 归档到 GitHub。
- 失败／停点：
  - source/manifest/PR authority 漂移 → STOP，先重新绑定。
  - SSH transport 再次不稳定 → STOP 受影响操作，先 bounded network/SSH forensic；若 authorization 未 claim 不得误报 mutation。
  - bound media identity / filesystem / mount state 与预期不一致 → STOP，不手工修复。
  - preflight PASS 后没有显式 writable-mount 授权 → STOP，不执行 `--execute`。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
- 任务资料：
  - `tools/execution_packages/n3w/r7a/u7_media_writable_mount_restoration_r30m/{manifest.json,executor.py}` — R30M exact execution contract
  - `tests/tools/test_n3w_t1_u7_media_writable_mount_restoration_r30m.py` — focused guards
  - `tools/execution_packages/n3w/r7a/u7_ha_quiesce_data_backup_r30/{manifest.json,executor.py}` — downstream R30 contract；仅在 R30M closure 后按需补读
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` — KF-156 SSH/eth0 link-flap guard
  - `docs/development/N3W_CURRENT_STATE.md` / `N3W_CURRENT_STATE_INDEX.md` — 当前阶段索引
- 已归档：
  - PR #807 public evidence comments listed above
  - exact CI run links listed above
  - 本交接及同步的 Current State / Index / Working Context / KF-156 由本轮 docs-only commit 保存
- 未归档重要资料：无。原始 T1/SSH/USB 私有证据只保存在 operator-private evidence context；GitHub 已保存 public-safe 结论和 exact bindings。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind main、PR #807 和 R30M executable-source authority `f814f604666273c2d8259a394a1bda44bae4b81f`，确认 docs-only advance 无 executable-source drift，然后执行 R30M real-T1 read-only preflight；PASS 后停止于 writable-mount explicit authorization boundary。
