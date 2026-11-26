# N3-W T1 Core Stack OTA V1.3 — KF-144 source closed → live repair
# 新会话交接文档 V1.0 — 2026-11-23

```text
HANDOFF_TEMPLATE_VERSION=1.4
MINI_HANDOFF_TEMPLATE_VERSION=1.0
MINI_HANDOFF_ELIGIBLE=false
USE_FULL_HANDOFF_TEMPLATE_V1_4=true
```

本次用户要求使用 `mini-handoff-template`。exact mini V1.0 规则要求在存在跨会话 live/physical mutation pending、重要新故障/源码修复尚待 live closure 时 fail closed 到正式 V1.4。本任务下一阶段明确涉及备用 T1 updater patch、transaction retirement、Manager successor 和 monitoring activation，因此不能用 mini 隐去这些边界。

## 1. 目标与停点

- 任务／交接原因：关闭 KF-144，并继续 T1 Core Stack OTA V1.3 的 Home Assistant 维护事务。KF-144 的源码、CI、live baseline、Manager successor authority 和 exact artifacts 已闭环；当前切换会话，后续进入 live repair 前的 fresh read-only preflight。
- 已完成到：
  - PR #824 executable source head `1fbe674e25edb4c6fb1a3740042778adc55def68`；
  - 22/22 workflow SUCCESS；
  - KF-144 Manager-only successor package artifact `14819845760` 已 exact 绑定；
  - repaired HA recovery artifact `14818806074` 已 exact 绑定；
  - live Generic V2 baseline SHA256 `78404869cda4b6fe14226b514623880b76045cd9a58a149f063d61edf57dd199` 已归档；
  - Current State / State Index / KF-144 / source closure 已与 GitHub 对齐。
- 当前状态：源码、CI、artifact 已完成；备用 T1 live repair 尚未执行。下一会话先只读 fresh rebind，不直接写入。
- 当前停点：**STOP before any new T1 mutation**。先确认 live U4 failure、runtime、expired authority residue、live updater version 与 exact artifacts 未漂移。

## 2. 代码与证据

- 仓库／分支／PR：
  - repo: `chrenguo-stack/HomeAssistant`
  - PR: `#824`
  - branch: `review/t1-ota-r8-existing-tx-predecessor-prep-20261123`
- 核对时 main／本任务源码：
  - current main contains mini handoff V1.0 authority at commit `0c0401c95b8e8022158e72e355050fc5c3f7d5ae`;
  - executable source head: `1fbe674e25edb4c6fb1a3740042778adc55def68`;
  - docs alignment continues on PR #824 after that executable head; fresh rebind PR head before further work.
- 证据入口：
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` → KF-144
  - `docs/development/N3W_T1_OTA_V1_3_KF144_SOURCE_CI_PACKAGE_CLOSURE_20261123.md`
  - `infra/n3w-t1/clean-reference/kf144-manager-successor-baseline-20261123.json`
  - `infra/n3w-t1/upgrades/manager-1cae18039eee-kf144-compatibility.json`
  - `infra/n3w-t1/upgrades/manager-1cae18039eee-kf144.json`

Exact CI/artifact:

```text
EXECUTABLE_SOURCE_HEAD=1fbe674e25edb4c6fb1a3740042778adc55def68

CI_TOTAL=22
CI_SUCCESS=22
CI_FAILURE=0
CI_RUNNING=0
CI_PENDING=0

MANAGER_A_TO_B_RUN_ID=45175810919
KF144_MANAGER_PACKAGE_ARTIFACT_ID=14819845760
KF144_MANAGER_PACKAGE_ARTIFACT_DIGEST_SHA256=362c300922816730d4209d450b376769c19319a34d594d2c3a90ea2e31ab143a
KF144_GENERIC_V2_UPDATER_PYZ_SHA256=d43036f333872e2e25272b26552809c8d40cd822efc8f0d414e71878594bf2bc

KF144_MANAGER_TARGET_IMAGE=local/greenhouse-manager:fresh-1cae18039eee
KF144_MANAGER_TARGET_IMAGE_ID=sha256:9547078268e5f2550b46583abbd87d9f0a6bbaa727a0af2c19379ca906954867
KF144_MANAGER_TAR_SHA256=bbce0ee5c399b2fbc315dcf34affb6391f54864144faba4f9efb983b160c8734
KF144_MANAGER_TAR_SIZE_BYTES=62953984

HA_TARGET_BINDING_RUN_ID=45175810759
HA_RECOVERY_ARTIFACT_ID=14818806074
HA_RECOVERY_ARTIFACT_DIGEST_SHA256=46bc0cc890b791de8219cabb12eb162136027c2ad7d6ef1c4fb4d3c21a2f009d
HA_RECOVERY_INSTALL_MANIFEST_SHA256=ef8e040fabe2fa1619d1ee28fce1785a535ef85edd15f8f4d416ed780e08fe07

FRESH_EXACT_ARM64_RUN_ID=45175811054
FRESH_EXACT_ARM64_ARTIFACT_ID=14820191749
FRESH_EXACT_ARM64_ARTIFACT_DIGEST_SHA256=a40277a5646cec7e1f63c583f6de2c1dd52389f2fcd3eb4917c23f612f569405
```

## 3. 必须继承的结论

- 已证实：
  - KF-144 不是等待型故障。live HA 10.4 predecessor 未挂载 `n3w_ota_monitoring`，legacy Manager 没有 self-test publisher，自然 replay telemetry 已约 18 天不更新。
  - last verified live stack 仍健康：
    - HA `local/n3w-homeassistant:2026.10.4-5881590f`
    - Manager `local/greenhouse-manager:fresh-44e7d7472714`
    - Broker `local/n3w-mosquitto:2.1.2-3184566d`
  - last verified transaction:
    ```text
    STATUS=ACTIVE
    PHASE=U4_READY_TO_INSTALL
    TRANSACTION_FILE_SHA256=a22a4260401ddb04318afba1b03495edb23a32c68196372987501b50154c2a66
    FAILURE_CODE=ha_usb_predecessor_acceptance_baseline_unavailable
    AUTHORIZATION_CLAIMED=false
    AUTHORIZATION_CONSUMED=false
    TARGET_IMAGE_LOADED=false
    ```
  - source repair removes the `natural_only` false-ready route, adds bounded no-mutation U4 failure retirement, adds candidate monitoring runtime activation/rollback, requires real Manager→Broker→HA self-test, and binds installed HA version to the same compose env authority as the HA image.
  - exact Manager successor compatibility review SHA256: `5046d2e180db6a0c620cfc91a58577d80a9fac2199b7155ff20015ca61caae03`.
  - Broker OTA remains intentionally deferred until Home Assistant OTA work is complete.
- 待确认：
  - live transaction file still equals the last U4 hash;
  - stale install-authority file still exists or has been removed by another process;
  - live updater is still the schema-v3 pyz `0ec63d6527be8e583b087576cda20c543edc707401a01344c20f8a0f354a0e51`;
  - runtime image IDs / restart counts / USB mount binding remain exact.
  - These must be checked with one fresh read-only preflight before any write.
- 已排除：
  - blind retry U5: rejected; baseline cannot appear without runtime repair;
  - deleting/weakening acceptance gate: rejected;
  - using legacy Manager `natural_only`: rejected;
  - reusing Attempt 02 install authority or release pin: rejected; both expiry times are already in the past;
  - modifying Broker as part of KF-144: rejected/deferred.

## 4. 执行范围与授权

- 可继续：
  - repository fresh rebind;
  - source/artifact review;
  - read-only T1 preflight;
  - generation/review of a bounded live execution package;
  - GitHub documentation alignment.
- 暂停边界：
  - stop before any T1 file replacement, transaction retirement, Docker image load/apply, service restart, candidate-runtime activation, HA PREPARE, reboot, Broker mutation, merge or release.
  - Do not replay expired Attempt 02 authority.
- 授权状态：
  - current valid new live-mutation authorization: **无**；
  - prior schema-v3 install authority ID `N3W_T1_CORE_UPDATER_V1_3_U5_SCHEMA_V3_INSTALL_FULL_20261123_02` was never claimed/consumed but expired at `1795435177`; it is not reusable;
  - prior release pin expired at `1795436977`;
  - handoff itself grants no new live authority.

## 5. 下一步

- 行动：
  1. fresh rebind repository main、PR #824、current PR head、executable source head `1fbe674e...`、artifacts `14819845760` / `14818806074`;
  2. execute one **read-only** spare-T1 preflight proving transaction/runtime/updater/USB/expired-authority state;
  3. if exact, generate the bounded KF-144 live repair execution package and STOP before mutation.
- 完成条件：
  - fresh live state matches safe U4 predecessor failure or a newly classified safe equivalent;
  - source/artifact hashes exact;
  - no authorization is claimed;
  - no runtime mutation occurs;
  - execution package binds exact target, source, artifacts, rollback/stop conditions and first write boundary;
  - result archived to GitHub.
- 失败／停点：
  - any source/runtime/transaction/USB/authorization drift → STOP affected live route and classify;
  - do not auto-delete/edit transaction;
  - do not auto-retry old U5;
  - do not load Manager/HA images before the new execution package and explicit live authorization.

Expected later live sequence, after separate authorization:

```text
PATCH_EXACT_HA_RECOVERY_UPDATER
→ RETIRE_PROVEN_NO_MUTATION_U4_FAILURE
→ GENERIC_V2_MANAGER_SUCCESSOR fresh-44e7... → fresh-1cae...
→ ACTIVATE_CANDIDATE_MONITORING_RUNTIME
→ MANAGER_BROKER_HA_SELF_TEST=PASS
→ FRESH_HA_PREPARE
→ RESUME_10.4_TO_10.0_MAINTENANCE_TRANSACTION
```

## 6. 必读定位与归档

- 仓库规则：
  - applicable `AGENTS.md`;
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`;
  - formal template `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4;
  - mini template authority on main: `docs/development/templates/mini-handoff-template.md` V1.0.
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md` — active route;
  - `docs/development/N3W_CURRENT_STATE_INDEX.md` — evidence locator;
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` → KF-144;
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md` — OTA architecture;
  - `docs/development/N3W_T1_OTA_V1_3_KF144_SOURCE_CI_PACKAGE_CLOSURE_20261123.md` — current source/CI/artifact closure;
  - three KF-144 baseline/compatibility/target JSON files listed in section 2.
- 已归档：
  - all critical source changes, CI, artifact authority, live baseline and KF disposition are in GitHub PR #824 / current-state documents.
- 未归档重要资料：无。Earlier local diagnostic/execution shell scripts are superseded working copies and are not required authority for continuation.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
UNARCHIVED_CRITICAL_RESULT_COUNT=0
```

新会话启动语：

```text
继续 N3-W / T1 Core Stack OTA V1.3 的 KF-144 live repair。

先读取：
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md 中 KF-144
- docs/development/N3W_T1_OTA_V1_3_KF144_SOURCE_CI_PACKAGE_CLOSURE_20261123.md
- 本 handoff

fresh rebind：
- repository main
- PR #824 / branch review/t1-ota-r8-existing-tx-predecessor-prep-20261123
- executable source head 1fbe674e25edb4c6fb1a3740042778adc55def68
- Manager successor artifact 14819845760
- HA recovery artifact 14818806074
- spare T1 live U4 transaction/runtime/updater/USB/expired-authority state

当前停点：
KF-144 source/CI/package 已 CLOSED；真实备用 T1 仍停在 last verified healthy predecessor + ACTIVE U4 baseline failure，尚未执行 live repair。

下一任务：
先完成一次 bounded read-only live preflight；若 exact，生成 KF-144 live repair execution package并停在第一项 T1 mutation 之前。

按现有授权边界继续；如发现 source、runtime、authorization 或 evidence drift，停止受影响操作并重新判定。
```
