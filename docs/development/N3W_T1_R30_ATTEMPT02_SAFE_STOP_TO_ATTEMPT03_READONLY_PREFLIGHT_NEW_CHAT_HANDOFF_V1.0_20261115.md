# N3-W T1 R30 Attempt02 SAFE_STOP → Attempt03 Read-only Preflight 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 N3-W T1 mandatory-USB Home Assistant OTA 的 U7 R30 路径。当前目标不是执行 R30 live，而是用已修复的 R30 preflight 完成 real-T1 read-only Attempt03；本轮对话在源码修复、CI 与归档闭环后结束。
- 已完成到：
  - R30M writable-mount live execution 已 CLOSED_PASS；其一次性授权已 claimed + consumed，永久 no-replay。
  - R30 read-only Attempt01 因旧 local SSH timeout 安全停止；远端 orphan preflight 被物理证明、显式清理，R30 state root 仍 absent。
  - R30 read-only Attempt02 在 remote `1170s` / local `1200s` 双层 timeout 下执行；现场采样证明远端 Python 约 95.7% CPU 且持续读盘，不是 deadlock/stall；最终 remote timeout 安全停止，未 claim/consume R30 live authorization，未发生 service/transaction/USB/U7/U8+ mutation。
  - Attempt02 根因已修复：R30 preflight 不再对两个已冻结的大归档重复做完整 portable-image reconstruction，而是验证冻结 recovery identity 文档，并对 target / predecessor 各做一次 full SHA-256 + size continuity；其余 transaction、R26/R29/R30S、runtime、capacity、HA source-tree、SQLite、root-key、required tools 检查保持。
  - GNU timeout 124/137 现在显式分类为 `remote_process_timeout`，不再退化为 `remote_result_invalid`。
  - 最终 source repair exact head `4cb3c0dd44ad0251a63e594b4cb8db3c0e20671a` 已完成 16/16 fresh CI SUCCESS。
  - 当前状态、状态索引和 KF-157 已对齐到 GitHub。
- 当前状态：可在新会话继续，但必须先 fresh rebind，并做最小 real-T1 read-only baseline；随后才执行 Attempt03。当前对话不再推进实机。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: #807, OPEN / DRAFT / UNMERGED / MERGEABLE
  - PR base: `fix/kf147-post-destructive-stop-readonly-forensic-20261110`
- 核对时 main／本任务源码：
  - `main=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - R30 source/test authority: `4cb3c0dd44ad0251a63e594b4cb8db3c0e20671a`
  - R30 executor blob: `3f9a9dad5b7da51bbdc33d7f82bd27e8866cc006`
  - R30 manifest blob: `d7e0e5d1e257eb94303f9b2c36e76cdc02987251`
  - R30 focused test blob: `6065a7684256230f4893d52a41cfade17ec005ed`
  - docs-only alignment commits after source authority must not be treated as a new executable-source authority.
- 证据入口：
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` → KF-157；SSH transport 异常另见 KF-156。
  - PR #807 comment `6890447001`: Attempt02 SAFE_STOP / full portable revalidation exceeds bounded budget.
  - PR #807 comment `6890462058`: exact-archive-continuity source repair and CI progress.
  - source authority fresh CI: 16/16 SUCCESS.
  - HA target-binding run: `43686290709` SUCCESS.
  - Manager A-to-B run: `43686290706` SUCCESS.
- 当前 durable lifecycle：
  - transaction phase: `U6_PREDECESSOR_RECOVERY_PREPARING`
  - transaction SHA-256: `7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe`
  - R26 / R29 / R30S predecessor/source authorities均为 consumed + no-replay。
  - R30 live authorization remains ungranted / unclaimed / unconsumed.

## 3. 必须继承的结论

- 已证实：
  - Attempt01 的 local SSH timeout 可以让远端 read-only worker 成为 orphan；该旧 orphan 已清理。source guard 已增加 remote-side lifetime bound。
  - Attempt02 不是卡死。物理现场采样证明其高 CPU 与持续 I/O；超时来自重复 portable-image reconstruction 的真实计算/读盘成本。
  - 旧 preflight 对 target 与 predecessor 调用 full portable reconstruction，会多次读取、hash、tar-walk / layer decompress；在 T1 上超过 1170 秒。
  - 修复后仍对两个归档各做一次完整 SHA-256 + size continuity，因此仍能发现归档任意字节漂移；portable recovery identity 继续由已冻结 transaction/plan authority 验证。
  - source repair exact head `4cb3c0dd...` fresh CI 16/16 SUCCESS，0 failure，0 pending。
  - Attempt01 / Attempt02 都没有 R30 authorization claim/consume，没有 service stop/restart，没有 transaction/USB mutation，没有 U7/U8+ transition。
- 待确认：
  - Attempt02 结束后的 fresh T1 runtime/media/orphan 状态尚未重新实测；新会话必须先做一次最小 read-only baseline。
  - exact repair 在 real T1 上是否能在 bounded timeout 内 PASS，必须由 Attempt03 证明；CI 不能替代。
- 已排除：
  - “密码未提交”不是 Attempt02 原因；
  - “SSH child 未启动”不是 Attempt02 原因；
  - “远端 Python deadlock / stall”不是 Attempt02 原因；
  - 继续机械增加 timeout 不是当前修复路线；
  - 不允许重放 R30M、R26、R29、R30S 已消费的一次性授权。

## 4. 执行范围与授权

- 可继续：
  - repository fresh rebind、source review、docs review；
  - real-T1 bounded read-only baseline；
  - 在 baseline 满足后执行 `N3W_T1_U7_R30_READONLY_PREFLIGHT_ATTEMPT03`；
  - Attempt03 结果的源码/证据复核与 GitHub public-safe 归档。
- 暂停边界：
  - Attempt03 PASS 后必须停止在 `R30_HA_QUIESCE_DATA_BACKUP_EXPLICIT_AUTHORIZATION`；
  - 不得自行 grant/materialize/execute R30 live；
  - 不得 stop Home Assistant/Manager、不得写 transaction/USB、不得进入 U7 mutation/U8+、不得访问板卡、不得 merge PR #807；
  - 如果出现 SSH banner/preauth/transport failure，先按 KF-156 分类，不得把 transport failure 直接当成 R30 source failure；
  - 如果 Attempt03 timeout，新的 expected reason 应为 `remote_process_timeout`；不得 blind retry。
- 授权状态：
  - R30M：claimed=true / consumed=true / replay=false，已关闭，不可重放。
  - R30：live_execution_authorized=false / granted=false / claimed=false / consumed=false / replay=false。
  - Attempt03 是只读验证，不授予后续 live mutation。
  - MERGE=false，BOARD_ACCESS=false，U8_PLUS=false。

## 5. 下一步

- 行动：
  1. fresh rebind `main`、PR #807、当前 PR head，并确认从 executable source authority `4cb3c0dd...` 到当前 PR head 仅有 docs/known-failure/handoff 对齐，无 R30 executable-source drift；
  2. 读取当前 `N3W_CURRENT_STATE.md`、`N3W_CURRENT_STATE_INDEX.md`、KF-157 和本交接；
  3. real-T1 最小只读 baseline：确认不存在 R30 orphan preflight；R30 state root absent；transaction 仍 exact U6；exact bound USB 仍在预期 rw mount；Manager/HA/Broker 与 owner units healthy；
  4. baseline PASS 后，以 detached exact-source worktree `4cb3c0dd...` 执行 R30 read-only preflight Attempt03；使用现有 operator-private SSH binding，不把私有 target/known_hosts/host-key 写入 GitHub；
  5. Attempt03 PASS 后归档 public-safe result，然后停止并请求 R30 live explicit authorization。
- 完成条件：
  - Attempt03 `status=PASS`, `R30_PREFLIGHT_RC=0`;
  - `read_only=true`, `u7_live_eligible=true`, `live_execution_authorized=false`;
  - authorization claimed/consumed=false；
  - service_stop/restart=false；
  - transaction_mutation=false；
  - usb_mutation=false；
  - u7_transition=false；
  - u8_plus=false；
  - repaired archive continuity reports target/predecessor exact；
  - evidence archived to PR #807 / current state before any next boundary。
- 失败／停点：
  - any unexpected R30 state root, transaction drift, USB binding drift, runtime unhealthy, orphan process, or mutation flag => STOP and classify before retry；
  - `remote_process_timeout` => inspect bounded process termination and expensive stage; no blind retry；
  - transport failure => KF-156 path first；
  - any executable source drift => invalidate Attempt03 entry until fresh CI + exact review。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md`：当前动态 authority；
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：本轮 R30/KF-157 定位；
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：KF-157，必要时 KF-156；
  - `tools/execution_packages/n3w/r7a/u7_ha_quiesce_data_backup_r30/executor.py`：Attempt03 executable contract；
  - `tools/execution_packages/n3w/r7a/u7_ha_quiesce_data_backup_r30/manifest.json`：R30 ungranted manifest / exact source binding；
  - `tests/tools/test_n3w_t1_u7_ha_quiesce_data_backup_r30.py`：timeout + archive continuity focused guards。
- 已归档：
  - source/test repair：PR #807 exact source authority `4cb3c0dd44ad0251a63e594b4cb8db3c0e20671a`；
  - Attempt02 forensic/root-cause：PR #807 comment `6890447001`；
  - source repair/CI progress：PR #807 comment `6890462058`；
  - current state/index/KF-157 与本交接均在 PR #807 branch。
- 未归档重要资料：无 public-safe continuation artifact。operator-private T1 SSH target / known_hosts / host-key binding 按安全规则仅保留在操作者私有上下文，不进入 GitHub；新会话复用现有 private binding，不重新公开。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
UNARCHIVED_CRITICAL_RESULT_COUNT=0
NEXT_SAFE_ENTRY_POINT=N3W_T1_U7_R30_READONLY_PREFLIGHT_ATTEMPT03
```

新会话启动语：阅读本交接、AGENTS.md、当前状态/索引和 KF-157，fresh rebind main、PR #807 与 exact R30 source authority `4cb3c0dd44ad0251a63e594b4cb8db3c0e20671a`。先执行最小 real-T1 read-only baseline；通过后执行 R30 read-only preflight Attempt03。Attempt03 PASS 后归档并停止在 R30 live explicit authorization boundary，不自动进入 live mutation。
