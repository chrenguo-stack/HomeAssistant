# N3-W T1 U13A live authorized CI PASS → real-T1 execution 新会话交接 V1.0 — 2026-11-17

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：完成 N3-W T1 mandatory-USB Home Assistant OTA 的正常成功终态 U13A。当前对话上下文已较长，因此在真实 U13A live commit 前切换新会话。
- 已完成到：
  - U12 已 durable PASS，host/USB 均停在 `U12_TARGET_ACCEPTANCE`。
  - real-T1 U13A commit read-only preflight 已 PASS，证明 `FORWARD_COMMIT_ELIGIBLE=true`、`rollback_required=false`。
  - U13A live source、focused tests、preauthorization review 已闭环。
  - 用户已明确授权 `EXECUTE U13A LIVE COMMIT: YES`。
  - 授权已绑定到独立 exact authorized package；该 exact head fresh CI 已 16/16 SUCCESS。
  - `N3W_CURRENT_STATE.md` 与 `N3W_CURRENT_STATE_INDEX.md` 已按本轮现场增量对齐。
- 当前状态：**可继续，但本轮按用户要求停止在 real-T1 执行前。** U13A 授权已经 granted，但尚未 claimed/consumed；真实 U13A commit 尚未启动。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state at handoff: OPEN / DRAFT / UNMERGED / MERGEABLE
- 核对时 main／本任务源码：
  - fresh PR base/main: `ab277001dc9b31dcccb4d36b1507cec5f26d5a1d`
  - exact authorized package source head: `b1d4ea98bc768ed26d626b895d494cd8ca38cc69`
  - U13A live source head: `e56eb75f02857b1b150accf371e91d852ee08709`
  - U13A preauthorization review commit: `48393a389023d7e0413d3bbc9da544ff4738c130`
  - U13A read-only source head: `fee2e1f4bb5d724e6821eb9e6534038e9646457d`
  - current-state alignment commit: `1101d1a5b3e0f767aa939de226fcb26d94f39d76`
  - current-state-index alignment commit: `61e00e7b72116db8c821c88ee55438ce5ac22a9a`
- Exact authorized package：
  - `tools/execution_packages/n3w/r7a/u13a_live_commit_authorized/executor.py`
  - `tools/execution_packages/n3w/r7a/u13a_live_commit_authorized/manifest.json`
  - authorization ID: `N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U13A_LIVE_20261117_01`
  - confirmation: `EXECUTE U13A LIVE COMMIT: YES`
- Exact authorized package CI at `b1d4ea98...`: **16/16 SUCCESS**。
  - HA target binding: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44000144714
  - Manager A-to-B: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44000144656
  - Core Stack current authority: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44000144538
  - Storage/image lifecycle: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44000145005
- 证据入口：
  - `docs/development/N3W_T1_U13A_COMMIT_READONLY_PREFLIGHT_CLOSURE_20261117.md`
  - `docs/development/N3W_T1_U13A_LIVE_COMMIT_SOURCE_DESIGN_20261117.md`
  - `docs/development/N3W_T1_U13A_LIVE_COMMIT_PREAUTHORIZATION_REVIEW_20261117.md`
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - PR #807 comments: `6935032849`, `6935396787`, `6935523181`, `6935580153`, `6935639707`.

## 3. 必须继承的结论

- 已证实：
  - U12 live 已 durable PASS；U12 authorization 已 claimed + consumed + no-replay。
  - 当前最后证实的 host transaction phase 是 `U12_TARGET_ACCEPTANCE`，SHA-256=`32a92edcd9fbdad1356b874a55d40f6e919518363c5740b495f9b5fa08a56071`。
  - 当前最后证实的 USB transaction phase 是 `U12_TARGET_ACCEPTANCE`，phase SHA-256=`ca5cbcaa0d915f9a0fe590d2beeeace846ce7029bdf6dcb8b46331d205212283`，USB mirror exact。
  - real-T1 U13A read-only preflight：RC=0 / `U13A_COMMIT_READONLY_PREFLIGHT_PASS`；`FORWARD_COMMIT_ELIGIBLE=true`；`ROLLBACK_REQUIRED=false`；power-loss classification=`FORWARD_COMMIT_ELIGIBLE`。
  - read-only preflight 重新验证了 target archive、predecessor recovery archive、HA backup、容量、target runtime、Broker/Manager/Home Assistant、MQTT auth 与 HA HTTP readiness；无 transaction/USB/service/image mutation。
  - U13A live source gate 16/16 SUCCESS，preauthorization review PASS，new blocker count=0。
  - 用户明确授权已绑定到 exact authorized package head `b1d4ea98...`；该 exact head 16/16 SUCCESS。
  - 授权状态：`granted=true / claimed=false / consumed=false / replay_permitted=false`。
  - real-T1 U13A execution 尚未开始；`U13A_COMMITTED=false`。
  - U13A live 只允许正常成功路线 `U12_TARGET_ACCEPTANCE -> U13A_COMMITTED`；不执行 U13B。
  - U13A commit 的 durable write order：USB U13A metadata → host U13A transaction → terminal read-only verification → success ledger。
  - U13A 不执行 service/image mutation，不恢复 HA backup，不恢复 predecessor image。
- 待确认：
  - 新会话开始时 PR #807、base/main、exact authorized package 与 CI 是否仍无漂移。
  - real-T1 执行当下 freshness 必须由 executor 内置的 fresh U13A read-only preflight 重新确认；在此之前视为 `UNKNOWN_FRESH`。
- 已排除：
  - 当前健康 U12 不应进入 U13B；read-only evidence 已证明 `rollback_required=false`。
  - 不得为了测试回滚而破坏当前成功现场。
  - 不得使用未授权 source-prepared package代替 exact authorized package。
  - 不得在 post-claim transport ambiguity 后盲目重放 execute。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind repository/PR/base/main/authorized-package exact authority；
  - 核对 exact authorized head `b1d4ea98bc768ed26d626b895d494cd8ca38cc69` 的 16/16 CI；
  - 在已绑定生产 T1 上执行 **一次** exact authorized U13A live commit；
  - executor 内置 fresh U13A read-only preflight；
  - claim 后若返回不明确，仅执行 read-only `--status-only` reconciliation。
- 暂停边界：
  - 若 PR/source/package/manifest/target authority 漂移，先 STOP/rebind，不执行 live。
  - 若 embedded fresh preflight 不 PASS，STOP；授权不得 claim/consume。
  - 一旦 claim，`replay_permitted=false`；任何超时、SSH 断连或不明确结果都不得再次 execute。
  - `STOP_PARTIAL_U13A_USB_ONLY`、`STOP_PARTIAL_U13A_HOST_ONLY` 或其他 post-claim 非终态必须进入独立只读 forensic/recovery gate。
  - 禁止 U13B、board access、merge、额外 service/image mutation、清理 recovery package/HA backup。
- 授权状态：
  - 来源：用户在本轮明确输入 `EXECUTE U13A LIVE COMMIT: YES`。
  - 目标：当前 mandatory-USB HA OTA transaction 的 U13A 正常成功提交。
  - 候选：exact authorized package head `b1d4ea98bc768ed26d626b895d494cd8ca38cc69`。
  - 有效条件：fresh rebind 无漂移；exact CI 仍为 16/16 SUCCESS；embedded U13A read-only preflight PASS；授权 state root 不存在残留。
  - 当前状态：`GRANTED / NOT_CLAIMED / NOT_CONSUMED / NO_REPLAY`。
  - 交接不新增授权；这里只继承上述已经明确授予且尚未消费的一次性 U13A 授权。

## 5. 下一步

- 行动：
  1. fresh rebind PR #807、fresh base/main、candidate branch head。
  2. 重新读取 exact authorized manifest/executor，确认 `b1d4ea98...` package source authority 与 16/16 CI。
  3. 确认本地执行工作树可安全 checkout exact authorized head；此前保存的本地 stash `pre-u13a-readonly-local-known-failures-20261117` 暂不恢复。
  4. 使用 exact authorized package 执行一次 real-T1 U13A live commit。
  5. 若 execute 返回明确 PASS，归档 terminal evidence；若 transport ambiguous，**不重放**，改用 status-only reconciliation。
- 完成条件：
  - `status=U13A_LIVE_COMMIT_PASS` 或经只读 reconciliation 得到 `U13A_LIVE_COMMIT_PASS_RECONCILED`；
  - host phase=`U13A_COMMITTED`；
  - host status=`COMMITTED`；
  - `recovery_required=false`；
  - USB phase=`U13A_COMMITTED`；
  - authorization `claimed=true / consumed=true / replay_permitted=false`；
  - target runtime、MQTT、HA HTTP terminal verification PASS；
  - `service_mutation=false / image_mutation=false / u13b_transition=false`；
  - public-safe closure、current state/index 与 PR #807 归档完成。
- 失败／停点：
  - preclaim failure：STOP，保留未消费授权事实并定位最小原因；
  - postclaim ambiguity：STOP，authorization 视为 consumed/no-replay，执行 read-only reconciliation；
  - USB-only 或 host-only partial terminal：STOP，不重放；建立独立 repair/recovery gate；
  - 任何新设计取舍、U13B、merge、board action 均另行授权。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` 的 minimum-new-chat-read-set 规则
  - 正式 handoff template：`docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`，V1.4，blob `885fd63131e80936e5e1fe907378be08a0060f12`
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md`：先读取最顶部 U13A authority 增量。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：定位本轮 U13A 证据。
  - `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_AND_DATA_ROLLBACK_ARCHITECTURE_V1.1_20261106.md`：U13A/U13B lifecycle authority。
  - `docs/development/N3W_T1_U13A_COMMIT_READONLY_PREFLIGHT_CLOSURE_20261117.md`：real-T1 read-only PASS。
  - `docs/development/N3W_T1_U13A_LIVE_COMMIT_SOURCE_DESIGN_20261117.md`：U13A live execution contract。
  - `docs/development/N3W_T1_U13A_LIVE_COMMIT_PREAUTHORIZATION_REVIEW_20261117.md`：preauthorization independent review。
  - `tools/execution_packages/n3w/r7a/u13a_live_commit_authorized/manifest.json`：exact authorization state / package binding。
  - `tools/execution_packages/n3w/r7a/u13a_live_commit_authorized/executor.py`：唯一允许的 U13A live execution entry。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：仅当 live STOP/partial/异常时按相关故障 guard 补读。
- 已归档：
  - GitHub current-state alignment commit `1101d1a5b3e0f767aa939de226fcb26d94f39d76`。
  - GitHub current-state-index alignment commit `61e00e7b72116db8c821c88ee55438ce5ac22a9a`。
  - authorized package exact source `b1d4ea98bc768ed26d626b895d494cd8ca38cc69` + 16/16 CI。
  - 上述 public-safe U13A closure/design/review 文档和 PR #807 comments。
- 未归档重要资料：
  - raw real-T1 evidence 保留在批准的私有 evidence root，不上传 GitHub。
  - Mac 本地 stash `pre-u13a-readonly-local-known-failures-20261117` 保存了进入 U13A 前已有的 `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 本地修改；它不是当前 live authority，真实 U13A 完成前不要 `stash pop`。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，fresh rebind PR #807、base/main、exact authorized package head `b1d4ea98bc768ed26d626b895d494cd8ca38cc69` 及其 16/16 CI。继承 `EXECUTE U13A LIVE COMMIT: YES` 的一次性授权，当前状态必须保持 granted=true / claimed=false / consumed=false。若无漂移，执行 exact authorized U13A live commit 一次；claim 后禁止重放，异常仅做 read-only reconciliation。不要进入 U13B、board、merge 或额外 service/image mutation。
