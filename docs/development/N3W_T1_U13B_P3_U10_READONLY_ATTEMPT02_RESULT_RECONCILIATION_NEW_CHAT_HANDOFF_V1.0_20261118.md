# N3-W T1 U13B P3 U10 Read-only Attempt 02 Result Reconciliation — New Chat Handoff V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

> 本交接严格使用 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4。  
> 只记录本轮 U9→U10 增量。公开文档不包含私网地址、SSH host key、密码、本地原始证据路径或原始设备 locator。

## 1. 目标与停点

- 任务／交接原因：继续 N3-W T1 mandatory USB Home Assistant OTA/recovery P3 实机链路；本轮已经完成 U9 正式写入闭环、U10 P3 专用只读预检源码与 CI、Attempt 01 false-STOP 根因定位与源码修复。用户将在新会话提供 U10 read-only Attempt 02 的实机结果，需要从该回执继续对账。
- 已完成到：
  - U9 real-T1 one-shot live authorization PASS，Host 与 bound USB 均已到 durable `U9_LIVE_AUTHORIZATION_CLAIMED`。
  - U9 授权已 claimed + consumed，禁止重放。
  - P3 专用 U10 read-only preflight 已实现；无 execute 模式、无 U10 grant、无 destructive mutation path。
  - Attempt 01 在 `bind_durable_u9` 因 `private_file_metadata_invalid` safe-stop；无 U10 mutation。
  - false-STOP 已定位为既有 U9 ledger 文件 mode 与后续严格 reader 不一致；源码已局部修复并通过替代 CI。
  - Attempt 02 exact candidate 已固定，用户已取得执行命令；本轮未执行 Attempt 02。
- 当前状态：`WAITING_FOR_OPERATOR_ATTEMPT02_RESULT`。新会话第一输入预计为 Attempt 02 receipt；先对账，不重跑 U9，不直接进入 destructive U10。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: `#807`，OPEN / DRAFT / UNMERGED
- 核对时 main／本任务源码：
  - formal template/main authority: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - handoff template blob: `885fd63131e80936e5e1fe907378be08a0060f12`
  - U9 frozen candidate: `816cf5f2f55c895b6112edbd563cf71df8b7be93`
  - U9 isolated grant: `31a7c5daed754db4a189c1d27b81795ef60abc0b`
  - U10 Attempt 01 candidate: `574e25498b7ef545652ea3d74c6c651fe83ae19a`
  - U9-ledger compatibility repair source: `4385b36c32a692e2e0c1d3484cb714551b37501a`
  - U10 Attempt 02 exact candidate: `c288303a638947fedb7ee504874f7a14a147bf87`
  - Current State alignment commits: `43bc7a0c7533561311b2c0608f6fa073c443c360`, `3006fb90d1830deedfc43dc9b04a993f5eea3ca8`
- 证据入口：
  - `docs/development/N3W_T1_U13B_P3_U9_LIVE_AUTHORIZATION_PHYSICAL_CLOSURE_20261118.md`
  - `docs/development/N3W_T1_U13B_P3_U10_READONLY_PREFLIGHT_SOURCE_CLOSURE_20261118.md`
  - `docs/development/N3W_T1_U13B_P3_U10_READONLY_PREFLIGHT_ATTEMPT01_FALSE_STOP_20261118.md`
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - replacement CI on Attempt 02 candidate:
    - Public repository safety run `44329875391` — SUCCESS
    - Core Stack current authority run `44329875446` — SUCCESS
    - P3 live/readonly source run `44329875510` — SUCCESS
    - HA 2026.10.4 target-binding run `44329875490` — SUCCESS
    - target-binding source + exact-binding jobs SUCCESS; full suite `974 passed`

## 3. 必须继承的结论

- 已证实：
  - real T1 current durable stage is `U9_LIVE_AUTHORIZATION_CLAIMED`.
  - current U9 transaction SHA-256 is `2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b`.
  - recovery-content manifest SHA-256 is `d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3`.
  - U9 live result was `P3_U9_LIVE_AUTHORIZATION_CLAIM_PASS / EXIT_CODE=0`; U9 authorization is consumed and cannot replay.
  - U9 did not enter U10; no predecessor delete, target load or service mutation occurred.
  - Attempt 01 returned `STOP / private_file_metadata_invalid` at `bind_durable_u9`, `EXIT_CODE=2`; local receipt SHA-256 `30922a0e0afe09dcd5e80ae11cb3bd52f2313dd9cbc3a584829db87a4178c888`.
  - Attempt 01 was read-only: `destructive_cutover=false`, `u10_transition=false`, `u11_plus=false`, `predecessor_runtime_delete=false`, `predecessor_image_delete=false`, `target_image_load=false`, `service_mutation=false`.
  - root cause is the first U9 ledger authority read: legacy U9 ledger records were written without a forced remote `umask 077`; later strict private-file metadata validation rejected that root-owned non-writable authority record.
  - repair accepts existing ledger only when parent remains root-private, record is regular/root-owned, and group/other write bits are absent; future U9 remote writes force `umask 077`.
  - Attempt 02 source/CI is verified at exact candidate `c288303a638947fedb7ee504874f7a14a147bf87`.
- 待确认：
  - Attempt 02 real-T1 receipt and exit code. Minimum check: compare receipt against `P3_U10_READONLY_PREFLIGHT_PASS` contract and confirm live transaction remains U9 with zero U10 mutation.
  - If Attempt 02 PASS, destructive U10 eligibility may be proven, but **destructive U10 is still not authorized by this handoff**.
  - Before any destructive U10 capacity release is authorized, the customer-facing bounded recovery requirement remains an independent delivery concern and must be explicitly reconciled against the current acceptance plan/source state.
- 已排除：
  - Historical generic U10 R37/R38 is not execution authority for this P3 sequence; it binds an older U9 transaction/media/container/authorization lineage.
  - Attempt 01 is not evidence of T1/U9 corruption and is not a reason to replay U9.
  - The two earlier cancelled repair-head workflows were superseded by later PR-head runs; current replacement runs listed above are SUCCESS.

## 4. 执行范围与授权

- 可继续：
  - Receive and reconcile the operator-provided Attempt 02 result.
  - Read-only GitHub/source/runtime evidence checks needed to classify Attempt 02.
  - If Attempt 02 reveals a local, unambiguous read-only tooling defect, source repair + tests + CI + GitHub archival may continue within existing project rules, without destructive T1 mutation.
- 暂停边界：
  - Do not replay U9.
  - Do not execute U10 destructive predecessor-capacity release.
  - Do not delete predecessor HA container/image.
  - Do not load/start target image.
  - Do not restart Manager/Home Assistant as part of this gate.
  - Do not enter U11+.
  - Do not mutate spare T1.
  - Do not merge PR #807.
  - Do not treat an Attempt 02 PASS as destructive authorization.
- 授权状态：
  - U7 authorization: consumed / no replay.
  - U8 authorization: consumed / no replay.
  - U9 authorization: consumed / no replay.
  - U10 Attempt 02: operator-authorized **read-only** execution only, exact candidate `c288303a638947fedb7ee504874f7a14a147bf87`.
  - U10 destructive authorization: `NOT_GRANTED`.
  - U11+: `NOT_AUTHORIZED`.
  - PR #807 merge: `NOT_AUTHORIZED`.
  - Handoff itself grants no new permission.

## 5. 下一步

- 行动：
  1. New chat fresh-rebind PR #807 and confirm Attempt 02 exact candidate `c288303a638947fedb7ee504874f7a14a147bf87` remains the execution source named by this handoff; later docs-only branch heads do not replace it.
  2. Read the operator's Attempt 02 receipt exactly as supplied.
  3. If receipt says `P3_U10_READONLY_PREFLIGHT_PASS`, verify at minimum:
     - `transaction_phase=U9_LIVE_AUTHORIZATION_CLAIMED`
     - `transaction_sha256=2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b`
     - `read_only=true`
     - `destructive_cutover=false`
     - `destructive_cutover_eligible=true`
     - `projected_phase=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED`
     - `u10_transition=false`
     - `u11_plus=false`
     - predecessor runtime/image delete, target load and service mutation all false
     - `EXIT_CODE=0`
  4. Archive the real Attempt 02 result and update Current State/Index.
  5. Stop before any destructive U10 grant/execution. Reconcile the customer bounded-recovery delivery requirement and request a new explicit destructive authorization only if the next design/acceptance gate supports it.
- 完成条件：
  - Attempt 02 classified and archived.
  - Host/USB remain at durable U9 after read-only probe.
  - No destructive mutation occurred.
  - Current State/Index point to the result and next one gate.
- 失败／停点：
  - Any non-PASS result: preserve receipt, identify the first failing read-only check, do not replay U9, do not infer corruption, and do not enter destructive U10.
  - If authority/source/target drifts from the exact candidate or durable U9 transaction, STOP the affected operation and fresh-rebind before continuing.
  - If result is ambiguous after any future destructive claim, reconciliation/status-only rules take precedence over replay.

## 6. 必读定位与归档

- 仓库规则：
  - applicable repository instructions / `AGENTS.md` if present
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` §12 minimum new-chat read set
  - formal handoff template: `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md` — current durable checkpoint and authorization boundary
  - `docs/development/N3W_CURRENT_STATE_INDEX.md` — latest U10 Attempt 02 stop index
  - `docs/development/N3W_T1_U13B_P3_U9_LIVE_AUTHORIZATION_PHYSICAL_CLOSURE_20261118.md` — durable U9 proof
  - `docs/development/N3W_T1_U13B_P3_U10_READONLY_PREFLIGHT_SOURCE_CLOSURE_20261118.md` — P3 U10 read-only source contract
  - `docs/development/N3W_T1_U13B_P3_U10_READONLY_PREFLIGHT_ATTEMPT01_FALSE_STOP_20261118.md` — Attempt 01 root cause and repair
  - `docs/development/N3W_T1_CUSTOMER_OTA_FAILURE_RECOVERY_ACCEPTANCE_PLAN_20261118.md` — read before considering destructive U10 authorization
  - `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u10_preflight.py` — exact read-only implementation at Attempt 02 candidate
- 已归档：
  - U9 physical closure, U10 source closure, Attempt 01 false-STOP, replacement CI evidence, Current State and Index are in PR #807.
  - This handoff is the authoritative new-chat delta for the next session once committed.
- 未归档重要资料：
  - operator-private raw Attempt 01 evidence remains local by design; its SHA-256 and public-safe result are archived.
  - Attempt 02 raw result does not yet exist in this chat; the operator will provide it in the new chat.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接、`N3W_CURRENT_STATE.md`、`N3W_CURRENT_STATE_INDEX.md` 和适用仓库指令，fresh rebind PR #807；用户会直接提供 U10 read-only Attempt 02 的实机回执。先对账该回执并归档，禁止重跑 U9；Attempt 02 即使 PASS，也停止在 destructive U10 之前，先处理所列恢复/授权边界。
