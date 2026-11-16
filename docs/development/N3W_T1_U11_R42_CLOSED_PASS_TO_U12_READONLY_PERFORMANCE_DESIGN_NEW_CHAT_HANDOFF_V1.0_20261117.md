# N3-W T1 U11 R42 CLOSED_PASS → U12 只读预检与性能埋点设计 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：本轮已完成 R42 Attempt 02 超时后的 durable 状态对账，确认 U11 真实物理完成；随后把 U12 target acceptance 与 OTA 性能验证正式纳入下一阶段。用户要求本轮停止继续开发，在新对话中恢复。
- 已完成到：R42 `u11-r42-live02-20261116T152940Z` 的本地 `STOP_UNKNOWN` 已被只读证据纠正为 durable `U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS`；host/USB 都在 `U11_TARGET_INSTALLED_STARTED`；U12 未进入。U12 性能验证设计文档已归档。
- 当前状态：**已完成本轮归档并停在新会话边界**。下一阶段只从 U12 fresh read-only preflight + performance instrumentation source design 开始，不在本交接中执行 U12 live。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR 状态：OPEN / DRAFT / UNMERGED / mergeable
- 核对时 main／本任务源码：
  - `MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - `HANDOFF_PARENT_HEAD=79c11060e9493f8c16d5b419fa7bec25dd331b01`
  - `CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615`
  - R42 repair/execution source authority: `cc38a8405927814b650ee41ef2d65372f502af8b`
- 证据入口：
  - R42 timeout reconciliation closure: `docs/development/N3W_T1_U11_R42_ATTEMPT02_TIMEOUT_RECONCILED_CLOSED_PASS_20261116.md`
  - U12/performance design: `docs/development/N3W_T1_U12_TARGET_ACCEPTANCE_AND_OTA_PERFORMANCE_VALIDATION_DESIGN_20261117.md`
  - current state: `docs/development/N3W_CURRENT_STATE.md`
  - current state index: `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - KF authority: `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
  - R42 repair-head CI: 16/16 SUCCESS; HA target-binding run `43894473065`, Manager A-to-B run `43894473028`, Core Stack authority run `43894472797`, fast exact closure run `43894472777`.

按 authority 类型区分：
- repository product authority 仍是 `5b32e1ae...`，不能把 R42 recovery/docs head 当成 repository product source；
- 最后实机证据中实际运行：Manager `local/greenhouse-manager:fresh-44e7d7472714`、Broker `local/n3w-mosquitto:2.1.2-3184566d`、Home Assistant `local/n3w-homeassistant:2026.10.4-5881590f`；
- Home Assistant runtime image ID: `sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365`.

## 3. 必须继承的结论

- 已证实：
  - R42 Attempt 02 的本地 `STOP_UNKNOWN` 是 client/SSH 2400 s timeout false-negative；远端随后完成并写入 durable `success.json`。
  - `R42_AUTHORIZATION_CLAIMED=true`、`R42_AUTHORIZATION_CONSUMED=true`、`R42_REPLAY_PERMITTED=false`；R42 永久禁止 replay。
  - `LIVE_TRANSACTION_PHASE=U11_TARGET_INSTALLED_STARTED`，host transaction SHA-256=`33350ba47e0af43b4f0e11fac990e24924f22057da60d980b26453b4e80e0471`。
  - USB phase 同为 U11；USB phase SHA-256=`8f2ba37e93577452ffd2b6dfc1cc5febbf717d1bf8c3ed2de8ec57ccf69e6921`；R42 terminal evidence 记录 `usb_mirror_exact=true`。
  - R42 success ledger SHA-256=`a68199255967d63dd8f009aa71e254c16dee895649e57656d3da5c46ac011921`；R42 failure ledger 不存在。
  - Home Assistant target 正在运行，生产 `/config` RW bind 存在；Manager、Broker、services owner 均运行/active。
  - `U11_PHYSICAL_COMPLETE=true`；`U12_ACCEPTANCE=false`；`U13_PLUS=false`。
  - KF-162 的 closure condition 已满足，交接归档将其标记 CLOSED_PASS。
  - R42 约 47 分钟不是 normal-production OTA baseline。其恢复路径重复进行重型完整性校验；正常 OTA 性能仍需单独实测。
  - 性能验证已成为下一阶段正式验收项：U12 acceptance timing + 未来合法 clean OTA end-to-end baseline。
- 待确认：
  - 新对话开始时，实时 T1/USB/runtime 状态必须重新 fresh read-only 核对，标记 `UNKNOWN_FRESH`，不得把本轮最后快照直接当新会话实时状态。
  - normal clean OTA 的真实总时长和用户可见 downtime 尚未实测；不得以 R42 47 分钟替代。
- 已排除：
  - 不再执行 R42 Attempt 02；授权已消费。
  - 不把本地 `STOP_UNKNOWN` 解释为 R42 failure；durable remote PASS 已证明。
  - USB public fingerprint 跨会话变化不是 durable drift；该 fingerprint 含 device path/major:minor，仅是 session observation。跨会话绑定继续以 filesystem UUID 和 durable transaction/mirror authority 为准。
  - 不为性能基准主动 downgrade/re-upgrade，也不重放已消费事务。
  - R42 timeout false-negative 不新增重复 KF；已有 KF-154 覆盖同类 post-claim client-timeout/no-replay guard，本轮在 U12 性能设计中补充执行/观察解耦要求。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind main、PR #807、handoff/current-state/KF authority；
  - U12 read-only preflight source/design；
  - 性能埋点 source design、源码复核、focused/local simulation、GitHub CI 与文档归档；
  - 按项目规则在授权范围内连续推进这些非 live-mutation 工作。
- 暂停边界：
  - **禁止 R42 replay**；
  - 不执行 U12 target acceptance live mutation；
  - 不进入 U13+；
  - 不做 board access；
  - 不合并 PR #807；
  - 不为基准测试重启/降级/重复 OTA；
  - 需要真实 T1 只读命令时，由用户本地执行；任何 U12 durable mutation 前必须建立独立 gate 并获得所需明确授权。
- 授权状态：
  - R42 one-shot authorization：**claimed + consumed + no-replay**，永久不可复用。
  - U12 live authorization：**无**。
  - merge authorization：**无**。
  - board authorization：**无**。
  - 本交接不授予任何新权限。

## 5. 下一步

- 行动：
  1. 新对话先 fresh rebind `main`、PR #807、交接文件、`N3W_CURRENT_STATE.md`、`N3W_CURRENT_STATE_INDEX.md`、KF-162、R42 closure、U12 performance design。
  2. 确认 PR/head 未出现未解释 drift；如有 drift，只处理受影响部分。
  3. 执行 `NEXT_ONE_GATE=N3W_T1_U12_READONLY_PREFLIGHT_AND_PERFORMANCE_INSTRUMENTATION_SOURCE_DESIGN`。
  4. 先完成 U12 fresh read-only preflight 设计和轻量性能埋点设计；不直接执行 U12 live。
  5. 性能埋点至少覆盖：U12 acceptance、HA readiness、MQTT acceptance；未来 clean OTA 再补 download/prepare、archive verify、backup、predecessor recovery、image load、runtime verify、binding publish、services start、HA ready、user-visible downtime。
- 完成条件：
  - U12 read-only preflight/source design 独立复核通过；
  - 性能 timing contract 使用 monotonic elapsed time，且不为了计时额外 hash/reread 大文件；
  - 长时间 remote execution 与 client/SSH wait 解耦方案明确；
  - focused tests/适用 CI 通过；
  - 所有结果归档到 GitHub；
  - 在进入 U12 live 前停在新的明确授权边界。
- 失败／停点：
  - fresh runtime、host transaction、USB mirror、R42 ledger、target runtime 任一不符预期：STOP，先做只读取证；
  - 任何 post-claim/transport uncertainty：禁止 replay，按 durable remote state reconciliation；
  - CI 同一轮最多主动检查 3 次，仍未终态则给 run 直链并停止轮询；
  - 若性能方案需要改变安全校验顺序、弱化完整性、增加 live mutation 或扩大范围，先停下做设计决策。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` 的 minimum-new-chat-read-set 规则
- 任务资料：
  - 本交接：恢复入口和停点；
  - `N3W_CURRENT_STATE.md` / index：最新 machine-readable authority；
  - R42 closure：U11 durable PASS 和 timeout reconciliation；
  - U12/performance design：下一阶段验收范围、性能指标与安全边界；
  - `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：KF-162 CLOSED_PASS；KF-154 post-claim timeout guard；KF-157 长只读 worker/timeout guard；KF-142 SSH epoch/reuse guard；KF-078 executor stdin/SSH contract 按需补读。
- 已归档：
  - R42 closure、U12/performance design、current-state、KF 结论及本 handoff 均在 PR #807 分支持久化；
  - 原始 T1 forensic 仍保存在批准的 private evidence 区域，GitHub 只保存脱敏 durable 结论、hash 和执行 ID。
- 未归档重要资料：无。对话中的有价值结论已等价归档；私有原始证据不应进入公开仓库。

```text
ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=true
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=true
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
REGRESSION_GUARD_ARCHIVED=true
UNTRACKED_CRITICAL_ARTIFACTS=0
UNARCHIVED_CRITICAL_KNOWLEDGE=0
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
NEXT_SAFE_ENTRY_POINT=N3W_T1_U12_READONLY_PREFLIGHT_AND_PERFORMANCE_INSTRUMENTATION_SOURCE_DESIGN
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务。先 fresh rebind main、PR #807 和当前 authority，确认 U11 durable PASS / U12 未进入；随后仅执行 U12 read-only preflight + performance instrumentation source design，在任何 U12 live mutation、U13+、board 或 merge 边界前停止。
