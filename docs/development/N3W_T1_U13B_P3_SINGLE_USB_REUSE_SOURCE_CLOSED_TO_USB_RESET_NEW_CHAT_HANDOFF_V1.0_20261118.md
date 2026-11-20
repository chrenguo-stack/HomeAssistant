# N3-W T1 U13B P3 单 USB复用源码 CLOSED_PASS → USB Reset 新会话交接 V1.0 — 2026-11-18

`HANDOFF_TEMPLATE_VERSION=1.4`

> 本文只保存当前阶段增量。长期工作规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> 本 handoff 使用当前唯一有效的 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4 / blob `885fd63131e80936e5e1fe907378be08a0060f12`。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并暂停受影响操作。  
> 公开 handoff 不保存私网地址、凭据、SSH 私有定位或原始设备 locator。

## 1. 目标与停点

- 任务／交接原因：继续 U13B P3 同版本、不同 Docker image identity 的物理验收；在 T1 只有一个 USB host 接口、操作者没有第二只 USB 的现实约束下，复用当前历史 U13A USB。当前对话到此停止，下一轮执行已授权的历史 USB 卸载／旧文件系统签名擦除。
- 已完成到：
  - P3 same-version exact artifact 已冻结并 CLOSED_PASS：run `44199389702`，artifact ID `14381710716`，target `local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1`。
  - fresh real-T1 readonly Attempt 01 / 02 均进入真实 T1 并安全 STOP，原因都是 fresh USB candidate count = 0；两次均无 transaction / USB / service / image / HA-data mutation。
  - Attempt 01 诊断证明 public USB fingerprint 只能作 session observation；`d16207ce8923832bec34c2f656823df752f046e1` 增加历史 filesystem UUID guard。
  - 操作者随后明确说明 T1 只有一个 USB host 接口且没有第二只 USB，并明确授权销毁／复用当前历史 USB。
  - 单 USB reset gate、post-reset readonly preflight 和 live preclaim 的下游闭环已完成；exact source authority 为 `3bce3afb61454017ec951301cb5376e0357a0c59`。
  - 本地对话现场已对齐到 GitHub docs-only alignment head `7182607348ba23d9cf6b4d48d898aa7fcf3c4a4b`。
- 当前状态：可继续。下一轮只执行 `N3W_T1_U13B_P3_SINGLE_USB_REUSE_RESET_20261118_01`；本轮没有执行 USB 卸载或擦除。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state: OPEN / DRAFT / UNMERGED / MERGEABLE
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - P3 single-USB product/source authority: `3bce3afb61454017ec951301cb5376e0357a0c59`
  - current-state alignment head: `7182607348ba23d9cf6b4d48d898aa7fcf3c4a4b`
- 关键源码：
  - `tools/execution_packages/n3w/r7a/u13b_p3_single_usb_reuse_reset/executor.py`
  - `tools/execution_packages/n3w/r7a/u13b_p3_single_usb_reuse_reset/manifest.json`
  - `tools/execution_packages/n3w/r7a/u13b_p3_fresh_readonly_preflight/executor.py`
  - `tools/execution_packages/n3w/r7a/u13b_p3_fresh_readonly_preflight/manifest.json`
  - `tools/execution_packages/n3w/r7a/u13b_p3_live_to_u11/executor.py`
  - `tools/execution_packages/n3w/r7a/u13b_p3_live_to_u11/manifest.json`
- CI：
  - P3 live + readonly source: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44219668667 — SUCCESS，17 focused tests passed。
  - fast source + exact closure: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44219668645 — SUCCESS。
  - P3 acceptance clean OTA source: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44219668801 — SUCCESS。
- exact artifact：
  - run: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44199389702
  - artifact ID: `14381710716`
  - GitHub artifact digest SHA-256: `22b36b6141eb5b50f976341725c7d56f46eccd9817b241844a22a4a276df6092`
  - inner target archive SHA-256: `be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d`
  - target archive size: `835299595`
- 现场／设计归档：
  - PR #807 comment `6966686680`: single-USB reuse source closure pending CI 的完整边界记录。
  - `docs/development/N3W_T1_U13B_P3_LIVE_EXECUTOR_AND_FRESH_READONLY_PREFLIGHT_SOURCE_DESIGN_20261117.md`
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`

## 3. 必须继承的结论

- 已证实：
  - 真实 T1 只有一个 USB host 接口；当前没有第二只 USB 可用于“历史盘 + fresh 盘同时在线”的路线。
  - 当前唯一 USB 是历史 U13A 恢复介质；Attempt 01/02 的 `fresh_usb_candidate_count_invalid:0` 不是 T1/HA/runtime 故障。
  - historical public fingerprint 是 session-scoped observation，不能单独作为跨会话恢复身份；历史 filesystem UUID guard 已加入。
  - 当前运行 Home Assistant predecessor 在两次 readonly Attempt 中均通过 exact runtime 检查；两次 Attempt 都未发生 live mutation。
  - reset gate 在执行 destructive action 前必须先委托 exact historical U13A status-only binding。
  - reset 只允许：验证 exact historical media → 卸载 exact product-owned mount → 清除历史 filesystem signature → 验证旧 filesystem identity 消失 → STOP。
  - reset gate 不 repartition、不 mkfs、不写 transaction、不改 service/image/HA data、不 claim P3 live authorization。
  - post-reset readonly preflight 仅接受同一已诊断 USB，要求历史 filesystem UUID 已消失、设备未挂载且其余资格检查通过。
  - P3 live preclaim 必须看到 `single_usb_reuse_after_reset=true`；否则 fail closed。
  - 真正 GPT 重建和 ext4 格式化仍归产品 `confirm_and_prepare()` 所有。
- 待确认：
  - 下一轮执行前必须 fresh rebind main、PR #807、当前 PR head 以及 reset package source authority；任一漂移先停止。
  - reset 执行后的实际结果尚未知；成功后需要新的 post-reset readonly preflight，不能直接跳到 P3 live。
- 已排除：
  - “必须准备第二只 USB 并与历史 USB 同时在线”路线：与真实单 USB host 硬件和现有物料条件不符。
  - “直接手工 mkfs 当前 USB”路线：会绕过产品 `confirm_and_prepare()` 的标准格式化所有权，不采用。
  - “只看 session fingerprint 判断历史／fresh USB”路线：已证明不可靠并被 filesystem UUID guard 替代／补强。

## 4. 执行范围与授权

- 可继续：
  - 用户已明确授权销毁／复用当前历史 U13A USB，并在本轮结束时再次明确指定：下一轮执行 USB 卸载／擦除。
  - 已授权 gate：`N3W_T1_U13B_P3_SINGLE_USB_REUSE_RESET_20261118_01`。
  - 允许的 live mutation 仅限 reset manifest 精确绑定的历史 USB：exact product mount 卸载 + 历史 filesystem signature 擦除。
- 暂停边界：
  - reset PASS 后立即 STOP；不得在同一授权下进入 P3 live clean OTA。
  - 禁止：repartition、mkfs、transaction mutation、service mutation、image mutation、HA-data mutation、P3 live execution、board access、PR merge。
  - 若 reset 在卸载后、signature erase 前后出现失败，必须相信结果中的实际 `usb_mutation/destructive_usb_reset` 状态，先做 fresh inventory／binding forensic，禁止盲目重跑。
- 授权状态：
  - 来源：当前用户会话明确授权“可以把现在插着的这只格式化”，随后明确要求“新一轮对话中执行 USB 卸载/擦除”。
  - 目标：reset manifest 精确绑定的当前历史 U13A USB；公开 handoff 不复述原始 locator、serial、WWN、私网地址或凭据。
  - 候选源码：`3bce3afb61454017ec951301cb5376e0357a0c59`；后续 docs-only head 可执行前提是 package authority fresh 核对无漂移。
  - 当前状态：`GRANTED=true / EXECUTED=false / CLAIMED=false / CONSUMED=false`。
  - 交接本身不新增或扩大授权。

## 5. 下一步

- 行动：
  1. fresh rebind repository main、PR #807 和 current head；确认 source/product blobs 仍对应 `3bce3afb61454017ec951301cb5376e0357a0c59` 的单 USB闭环。
  2. 读取 reset package 的 `executor.py` 与 `manifest.json`，确认 `destructive_usb_reset_authorized=true`，且 transaction/service/image/HA-data/P3-live 权限仍为 false。
  3. 使用 exact current worktree 执行 `u13b_p3_single_usb_reuse_reset/executor.py --mode execute-reset`；SSH 目标、known-hosts 和凭据使用操作者私有上下文，不写入公开仓库。
  4. executor 必须先完成 pre-reset exact historical U13A status-only binding，随后才允许 exact unmount + signature erase。
  5. reset 完成后将结果和 evidence 归档到 GitHub，然后 STOP。
- 完成条件：
  - `status=P3_SINGLE_USB_REUSE_RESET_PASS`
  - `historical_terminal_binding_pass=true`
  - `t1_access=true`
  - `usb_mutation=true`
  - `destructive_usb_reset=true`
  - `historical_filesystem_uuid_removed=true`
  - `transaction_mutation=false`
  - `service_mutation=false`
  - `image_mutation=false`
  - `ha_data_mutation=false`
  - `authorization_claim=false`
  - `p3_live_execution=false`
  - evidence 写入新的、空的 operator-private evidence root，并将脱敏结果归档到 PR / current-state。
- 失败／停点：
  - 任一 source/head/target/host-key/historical binding 漂移：STOP before USB mutation。
  - 任何 remote STOP：不得用同一命令盲目重跑；先读取实际 mutation flags 和当前 USB mount/signature inventory。
  - reset PASS 后仍 STOP；下一 gate 是 post-reset single-USB readonly preflight，之后才可能讨论新的 P3 live authorization。

## 6. 必读定位与归档

- 仓库规则：
  - 读取适用 `AGENTS.md`。
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
  - 正式 handoff template：`docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4。
- 任务资料：
  - 本 handoff：恢复当前停点与授权边界。
  - `docs/development/N3W_CURRENT_STATE.md`：读取最顶部 2026-11-18 U13B P3 single-USB snapshot。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：定位本轮最新增量。
  - `docs/development/N3W_T1_U13B_P3_LIVE_EXECUTOR_AND_FRESH_READONLY_PREFLIGHT_SOURCE_DESIGN_20261117.md`：读取 single-USB hardware constraint 与 downstream closure 两节。
  - reset package `manifest.json`：下一轮 destructive target/authority 的机器可读 authority；执行前必须 fresh 核对。
  - 如 reset 失败，再按实际失败点补读 prepare host / USB state 源码，不提前扩展读取范围。
- 已归档：
  - current-state alignment commit：`7182607348ba23d9cf6b4d48d898aa7fcf3c4a4b`
  - exact source authority：`3bce3afb61454017ec951301cb5376e0357a0c59`
  - PR #807及上述 CI / artifact / comment。
- 未归档重要资料：无。私网 SSH 定位、凭据和原始设备 locator 按模板规定保留在操作者私有上下文，不作为团队共享文档内容。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

> 阅读 `docs/development/N3W_T1_U13B_P3_SINGLE_USB_REUSE_SOURCE_CLOSED_TO_USB_RESET_NEW_CHAT_HANDOFF_V1.0_20261118.md`、适用仓库指令和最小读取集，fresh rebind main / PR #807 / current head。确认单 USB reset package authority 无漂移后，执行已授权的 `N3W_T1_U13B_P3_SINGLE_USB_REUSE_RESET_20261118_01`，仅允许历史 USB 的 exact unmount + filesystem signature erase；归档结果后停止，不进入 P3 live。
