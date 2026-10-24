# 温室环境监测系统（ESP32-C6）
# N3-W / KF-130 post-merge exact-main release rebuild
# 新会话交接文档 V1.0 — 2026-10-24

```text
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
FORMAL_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
EXACT_HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD_VERSION=1.0
```

> 本文只保存当前阶段增量。长期规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> 公开 handoff 不包含 T1 私网地址、SSH 密码、Host Key 原始值、Setup Secret、Board 原始 identity 或其他私有 locator。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=KF130_SOURCE_REPAIR_MERGED_EXACT_RELEASE_REBUILD_PENDING
CURRENT_STOP_POINT=PR665_MERGED_POSTMERGE_ALIGNMENT_COMPLETE
NEXT_ONE_GATE=N3W_T1_KF130_POSTMERGE_EXACT_MAIN_RELEASE_REBUILD_20261024_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

PR #665 已合并，KF-130 源码修复进入 main；当前会话在新的 exact production release
重建之前停止。新会话从 merged main fresh rebind 开始，只执行仓库/CI/本地 release
验证，不访问 T1/Board。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=4
STAGE_OVERRIDES=
1) PR #665 merge 后 acceptance-tool bytes 已变化，旧 production release 全部仅为历史证据，不得复用；
2) 历史失败 production run 已 terminal，marker STARTED / reflash_required=true，不得 replay 或 retroactive PASS；
3) 下一 gate 只做 exact-main release rebuild + Mac local verify，不访问 T1/Board；
4) 本 handoff/post-merge alignment 保存在独立 docs-only 分支，不合并，以避免在新 exact-release 链开始前再次改变 main authority。
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=
KF-130 source repair merged
→ fresh exact-main F3/F4/F5 production release rebuild
→ Mac local exact-release validation
→ fresh Armbian reflash / F2 qualification
→ new F5 V2 production run
→ post-reboot readiness + strict acceptance + 90s continuity
→ marker ACCEPTED / T1_PRODUCTION_READY=true
→ no-board dynamic pairing open/close/timeout acceptance
→ new Board D first-pair authorization
→ Board D first secure pairing
→ later MQTT/HA/Direct/Relay acceptance

FINAL_ACCEPTANCE_TARGET=
T1 使用包含 KF-130 修复的 exact production release 完成完整 F5 V2 production acceptance，
随后动态首配窗口与 Board D 首次安全配对在真实产品路径闭环。

DEFERRED_OR_OUT_OF_SCOPE=
本 next gate 不 reflash T1；
不启动 production executor；
不打开 pairing window；
不访问 Board D；
不做 MQTT/HA/Direct/Relay/RF physical acceptance。
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=f8b16f70867324b57ea65aef2a3b579fcb00917a
TREE=07cc4ba0acc1b64189d4da92d94bf668c405a43d

CANDIDATE_REF=NOT_APPLICABLE:PR665_ALREADY_MERGED
CANDIDATE_HEAD=ddf2b3826c4bff8aa8992d0f2884018ce4cfac6a
CANDIDATE_TREE=07cc4ba0acc1b64189d4da92d94bf668c405a43d

SOURCE_TEST_AUTHORITY=d63cba066201df355bf9ceb0fbb330c00dfee24d
SOURCE_TEST_TREE=58feb07d69aea49003f5549c5a184367f6423709
PR665_MERGE_COMMIT=f8b16f70867324b57ea65aef2a3b579fcb00917a

ARTIFACT_ID=NOT_APPLICABLE:new exact-main release chain not built yet
ARTIFACT_SHA256=NOT_APPLICABLE:new exact-main release chain not built yet

DEPLOYED_SOURCE_HEAD=b31d86a66d7c4fc10370606b610aab3203a91d94
DEPLOYED_SOURCE_TREE=4db4db8c0349e9dbf83294f91798f8d25aa4b556

OTHER_REQUIRED_AUTHORITY=
historical failed release_id=eddccfab855efca2a4804e234358dc7c9cae32868532d73b80f25ad5994f2cbe;
historical failed release_sha256=1e501e936bbcc7883cc29690e92df68e822be3570528e54c835356d933f139f5;
historical failed run_id_sha256=e1d2155f11f1c30adfbf97327a51ecdad3e8de47e58f4fd22ed2de64c3a0bc12;
OLD_RELEASE_REUSE=false;
FAILED_RUN_REPLAY=false。
```

下一 gate 开始前必须 fresh rebind `repository main`。若 main 已不等于
`f8b16f708...`，不得继续使用本文 frozen MAIN；先判断 drift 是 docs-only 还是 executable-source
变化，并据此重新确定 release authority。

---

## 4. Current Live Baseline

交接时没有再次访问 T1/Board，因此 live 字段按模板保守冻结：

```text
MANAGER_STATE=UNKNOWN_FRESH
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH
HOMEASSISTANT_STATE=UNKNOWN_FRESH

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=UNKNOWN_FRESH
BOARD_B_POWER_STATE=UNKNOWN_FRESH
BOARD_B_LOCATION_ROLE=UNKNOWN_FRESH

T1_PRODUCTION_AUTHORITY=false
T1_FAILED_RUN_TERMINAL=true
T1_REFLASH_REQUIRED_FOR_NEXT_PRODUCTION_AUTHORITY=true
BOARD_D_FIRST_PAIR_COMPLETE=false

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

最近一次直接只读证据（不是 handoff 时 fresh live claim）：

```text
LAST_PROVEN_POSTFAIL_SNAPSHOT_COUNT=2
LAST_PROVEN_POSTFAIL_SNAPSHOT_INTERVAL_SECONDS=15
BROKER_RESTART_COUNT=0
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
HOMEASSISTANT_HTTP_READY=true
MANAGER_CURRENT_AUTHENTICATED_BROKER_EVIDENCE=true
HOMEASSISTANT_CURRENT_AUTHENTICATED_BROKER_EVIDENCE=true
MANAGER_8883_OWNED_SOCKET_COUNT=1
HOMEASSISTANT_1883_OWNED_SOCKET_COUNT=1
PERSISTENT_RUNTIME_FAILURE_EVIDENCE=false
```

下一 gate 不依赖 fresh T1 live state，因此无需为 release rebuild 访问 T1。

---

## 5. Proven Current Facts

```text
PR665_FINAL_HEAD=ddf2b3826c4bff8aa8992d0f2884018ce4cfac6a
PR665_FINAL_HEAD_CI=14_OF_14_SUCCESS
PR665_MERGED=true
PR665_MERGE_COMMIT=f8b16f70867324b57ea65aef2a3b579fcb00917a
PR665_MERGE_TREE=07cc4ba0acc1b64189d4da92d94bf668c405a43d

KF130_SOURCE_REPAIR=CLOSED_PASS_MERGED
KF130_LIVE_REVALIDATION=PENDING

F4_FOCUSED_TESTS=167_PASS
F5_V2_R3_FOCUSED_TESTS=202_PASS
NEW_SOURCE_BLOCKER_COUNT=0
OPEN_NEW_FALSE_PASS_PATH_COUNT=0

KF125_REOPENED=false
KF130_IS_SUCCESSOR_GAP=true

OLD_FAILED_RUN_REPLAY=false
OLD_FAILED_RELEASE_REUSE=false
T1_PRODUCTION_READY=false
```

KF-130 直接根因证据：

```text
FAILED_STAGE=POST_REBOOT_ACCEPTANCE
FAILED_ERROR_CODE=homeassistant_mqtt_socket_missing
POST_REBOOT_READINESS_PREVIOUSLY_PASSED=true
LATER_TWO_SNAPSHOTS_PASS=true
LATER_RUNTIME_RESTART_COUNT_ZERO=true
ROOT_CAUSE_CLASS=POST_REBOOT_MQTT_SESSION_READINESS_RACE
ROOT_CAUSE_CONFIDENCE=HIGH
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=1
CURRENT_BLOCKER=NEW_EXACT_RELEASE_AND_REAL_T1_LIVE_REVALIDATION_REQUIRED_BEFORE_PAIRING
ROOT_CAUSE=KF-125 readiness did not wait for Manager/Home Assistant MQTT session convergence before strict verifier entry
PROVEN_BY=terminal error_code homeassistant_mqtt_socket_missing + later stable PASS/PASS read-only snapshots
SOURCE_DEFECT_PROVEN=true
SOURCE_DEFECT_REPAIRED_AND_MERGED=true
RUNTIME_DEFECT_PROVEN=false
```

源码 blocker 已关闭；当前 blocker 是生产 authority 尚未重新建立，不是新的源码问题。

---

## 7. Closed / Forbidden Routes

```text
OLD_FAILED_RUN_REPLAY=CLOSED:terminal run / replay forbidden
OLD_EXACT_RELEASE_REUSE=CLOSED:PR665 changed acceptance-tool bytes
TARGET_LOCAL_FIX_FORWARD=CLOSED:failed target must not be promoted to production authority
RETROACTIVE_ACCEPTANCE_OF_FAILED_RUN=CLOSED:later snapshots cannot change terminal result
REOPEN_KF125=CLOSED:KF130 is a separate successor gap
PAIRING_BEFORE_NEW_F5_PASS=CLOSED:T1_PRODUCTION_READY must be true first
BOARD_D_PAIRING_WITH_OLD_CONSUMED_AUTH=CLOSED:new one-shot authorization required later
DOCS_HANDOFF_BRANCH_AUTO_MERGE=CLOSED:keep main stable for next exact-release chain
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=F5_V2_PRODUCTION_RUN_405fc..._20261024
CLAIMED=true
CONSUMED=true
RESULT=FAIL_POST_REBOOT_ACCEPTANCE
REPLAY_PERMITTED=false
SUPERSEDED_BY=NEW_RUN_REQUIRED_AFTER_REFLASH

AUTHORIZATION=F5_V2_CONTROLLED_REBOOT_405fc..._20261024
CLAIMED=true
CONSUMED=true
RESULT=EXECUTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

AUTHORIZATION=PR665_MERGE
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=NOT_APPLICABLE
SUPERSEDED_BY=MERGED_MAIN_f8b16f70867324b57ea65aef2a3b579fcb00917a

NEXT_GATE_AUTHORIZATION=NOT_REQUIRED:repository/artifact build and local validation only
NEXT_LIVE_PRODUCTION_AUTHORIZATION=NEW_ONE_SHOT_REQUIRED_AFTER_REFLASH
GRANTED=false
```

公开文档只保留旧 run 的 public-safe SHA256；不发布原始私有 locator/secret。

---

## 9. Rollback Authority

下一 gate 不修改 T1/Board：

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:REPOSITORY_ARTIFACT_ONLY_GATE
LIVE_TARGET_ROLLBACK_REQUIRED=false
```

GitHub/release chain fail-closed 规则：

```text
MAIN_DRIFT_DURING_CHAIN=RESTART_INCOMPLETE_CHAIN
MISMATCHED_SOURCE_ARTIFACT=REJECT
FAILED_WORKFLOW_ARTIFACT=REJECT
OLD_RELEASE_FALLBACK=FORBIDDEN
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_KF130_POSTMERGE_EXACT_MAIN_RELEASE_REBUILD_20261024_01
```

### Purpose

从 PR #665 合并后的 fresh exact main 重新建立唯一可用于下一次 T1 production 的 release authority。

本 gate 要证明：

- F3 deployable payload 与当前 exact main 绑定；
- F4 control + reboot successor 与同一 exact main 绑定；
- F5 release-inputs 精确消费上述成功 artifacts；
- final exact production release 为 `production_authority=true`；
- Mac 本地 verify-bundle 对 final release 完整 PASS。

本 gate **不能**证明 T1 live production、KF-130 live revalidation、动态 pairing 或 Board D pairing 已通过。

### Inputs

```text
EXPECTED_START_MAIN=f8b16f70867324b57ea65aef2a3b579fcb00917a
EXPECTED_START_TREE=07cc4ba0acc1b64189d4da92d94bf668c405a43d

F3_WORKFLOW=.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
F4_WORKFLOW=.github/workflows/n3w-t1-f4-exact-control-package.yml
F5_RELEASE_INPUTS_WORKFLOW=.github/workflows/n3w-t1-f5-v2-release-inputs-ci.yml
F5_FINAL_RELEASE_WORKFLOW=.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml

REQUIRED_RELEASE_ARTIFACT_COUNT=6
SECRET_VALUES_INCLUDED=false
```

### Operations

```text
1. fresh rebind repository main and verify PR #665 merge is present.
2. verify main/tree and inspect the exact F3/F4/F5 producer workflow source.
3. dispatch F3 deployable payload from exact main.
4. dispatch F4 exact control package from the same exact main.
5. collect successful run IDs, artifact IDs, digests and inner source bindings.
6. verify main did not drift; if drift occurred, restart the incomplete chain.
7. dispatch F5 V2 release-inputs with exact operator values only.
8. validate release-input component binding / artifact_count=6 / same source head+tree.
9. dispatch final exact production release using the exact successful release-input run.
10. verify production_authority=true, secret_values_included=false and exact source binding.
11. download final artifact to private Mac workspace.
12. run local verify-bundle and independently compare release_id/release_sha/source_head/source_tree/run binding.
13. archive only sanitized hashes/status to GitHub.
14. structured closure and STOP before any T1 reflash/access.
```

### PASS / FAIL / STOP

```text
PASS_IF=
F3=PASS on one exact main;
F4=PASS on same exact main;
release-inputs=PASS with artifact_count=6;
final release production_authority=true;
secret_values_included=false;
all component/source/tree bindings exact;
Mac local verify-bundle=PASS;
main drift rule satisfied.

FAIL_IF=
source/tree mismatch;
failed/stale/expired artifact substituted;
wrong operator field/value format;
artifact_count != 6;
production_authority != true;
secret_values_included != false;
local verify-bundle mismatch;
unclassified main drift.

STOP_BOUNDARY=
LOCAL_EXACT_RELEASE_VALIDATION=CLOSED_PASS;
do not reflash/access T1;
do not start production executor;
do not open pairing.

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- fresh GitHub main/PR/workflow/source inspection
- exact workflow dispatch for F3/F4/F5 release production
- workflow/job/log inspection
- artifact metadata/digest inspection
- private Mac artifact download
- local verify-bundle
- sanitized GitHub progress/archive comments
- bounded same-gate repair only if a clear low-risk source/test/workflow-input defect is found before authority is frozen
```

### FORBIDDEN

```text
- T1 SSH
- T1 mutation
- T1 reflash/reinstall
- production executor start
- new production approval claim
- Board D access
- firmware/OTA/USB/serial/NVS action
- pairing window open
- Board D first pair
- reuse of historical failed release or run
- merge of unrelated PRs
- merge of this docs-only handoff branch during the exact-release chain
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=private Mac release download/verify workspace + sanitized GitHub evidence only
```

---

## 12. Execution Contract

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

EXECUTOR=HIGH_LEVEL_MODEL_PLUS_GITHUB_TOOLS_AND_MAC_TERMINAL
EXECUTION_METHOD=chat-tool+mac-terminal
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=true

CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

GitHub 调用保持短、分阶段；CI 未完成最多轮询 3 次。全绿后直接完成本 gate 已约定的
exact-binding/closure review，不制造额外“继续”确认。任何 live/T1/Board/reflash/pairing
动作都属于下一 gate，不能自动进入。

---

## 13. Expected Closure

```text
=== N3W_T1_KF130_POSTMERGE_EXACT_MAIN_RELEASE_REBUILD CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=NOT_APPLICABLE_REPOSITORY_ARTIFACT_ONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

SOURCE_MAIN=
SOURCE_TREE=

F3_RUN_ID=
F3_ARTIFACT_ID=
F3_ARTIFACT_DIGEST=
F3_RUNTIME_PAYLOAD_SHA256=
F3_PAYLOAD_MANIFEST_SHA256=

F4_RUN_ID=
F4_CONTROL_ARTIFACT_ID=
F4_CONTROL_ARTIFACT_DIGEST=
F4_REBOOT_ARTIFACT_ID=
F4_REBOOT_ARTIFACT_DIGEST=

RELEASE_INPUTS_RUN_ID=
RELEASE_INPUTS_ARTIFACT_ID=
COMPONENT_BINDING_SHA256=
RELEASE_INPUT_SHA256=
ARTIFACT_COUNT=

FINAL_RELEASE_RUN_ID=
FINAL_RELEASE_ARTIFACT_ID=
FINAL_RELEASE_ZIP_DIGEST=
RELEASE_ID=
RELEASE_SHA256=
PRODUCTION_AUTHORITY=
SECRET_VALUES_INCLUDED=

LOCAL_EXACT_RELEASE_VALIDATION=
MAIN_DRIFT=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

GATE_RESULT=
NEXT_ROUTE=N3W_T1_KF130_FRESH_ARMBIAN_REFLASH_AND_F2_QUALIFICATION_PREPARATION
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_KF130_FRESH_ARMBIAN_REFLASH_AND_F2_QUALIFICATION_PREPARATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

PASS 后必须先停止。T1 reflash/fresh qualification/new production run 属于新的 live/physical
阶段，不由 release rebuild gate 自动授权。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
EXISTING_KF_GUARD_USED=KF-125 readiness; KF-126 SSH boot epoch; KF-127 partial unit evidence; KF-128 runtime snapshot evidence; KF-129 dynamic pairing supervision; KF-130 MQTT readiness race
NEW_KF_REQUIRED=false

KF_ID=KF-130
SYMPTOM=POST_REBOOT_READINESS PASS 后 strict verifier 立即 homeassistant_mqtt_socket_missing
ROOT_CAUSE=readiness 未等待 HA MQTT session convergence
FIX_OR_GUARD=Manager 0 WAIT/1 ready/>1 FAIL; HA 0 WAIT/>=1 ready; strict verifier unchanged
STATUS=SOURCE_REPAIR_MERGED_LIVE_REVALIDATION_PENDING
```

若新 exact-release rebuild 发现新的独立源码/构建缺陷，再单独判断是否需要新 KF；不要把
artifact/operator-input 错误自动升级为产品缺陷。

---

## 16. New Chat Start Prompt

默认读取集：

```text
1. 本 handoff（从 handoff docs-only branch/PR 的 exact head 读取）
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md（从同一 handoff docs-only head 读取）
4. docs/development/N3W_CURRENT_STATE_INDEX.md（从同一 handoff docs-only head 读取）
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md（从同一 handoff docs-only head 读取）
6. exact handoff standard authority=4300890dff0ce63d5a547df21426e287d084d9ee
7. current formal template authority blob=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
```

建议启动文本：

```text
阅读《docs/development/N3W_T1_KF130_POSTMERGE_EXACT_RELEASE_REBUILD_NEW_CHAT_HANDOFF_V1.0_20261024.md》。

从该 handoff 所在的 exact docs-only commit 同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee
- docs/development/NEW_CHAT_HANDOFF_STANDARD.md

读取当前 formal template authority：
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
- HANDOFF_TEMPLATE_VERSION=1.3
- blob=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0

并 fresh rebind：
- repository main
- PR #665
- merged main expected at handoff creation=f8b16f70867324b57ea65aef2a3b579fcb00917a
- merged tree expected=07cc4ba0acc1b64189d4da92d94bf668c405a43d
- source/test authority=d63cba066201df355bf9ceb0fbb330c00dfee24d
- docs/development/N3W_T1_F5_V2_POST_REBOOT_HA_MQTT_READINESS_RACE_SOURCE_REPAIR_20261024.md
- F3/F4/F5 production-release workflow sources

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_T1_DYNAMIC_FIRST_PAIRING_CLEAN_ARMBIAN_REINSTALL_AND_EXACT_RELEASE_ACCEPTANCE
当前任务：N3W_T1_KF130_POSTMERGE_EXACT_MAIN_RELEASE_REBUILD_20261024_01

必须先承认：
- PR #665 已 merge；KF-130 source repair 已 CLOSED_PASS_MERGED；
- historical failed run terminal/no-replay，不能 retroactive PASS；
- historical exact release 不得复用；
- 当前 T1 不具 production authority，后续 live run 前仍需 reflash/fresh qualification；
- 下一 gate 只重建 exact production release + Mac local validation；
- 本 gate T1_ACCESS=false、T1_MUTATION=false、BOARD_ACCESS=false；
- pairing/Board D 均不在本 gate；
- 若 main 已偏离 handoff frozen main，先分类 drift，不要盲目继续旧 release chain。

先 fresh rebind，然后只进入：

NEXT_ONE_GATE=N3W_T1_KF130_POSTMERGE_EXACT_MAIN_RELEASE_REBUILD_20261024_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

不要重放 consumed authorization，不要使用旧 release，不要自动进入 T1 reflash/production/pairing。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=KF130_SOURCE_REPAIR_MERGED_EXACT_RELEASE_REBUILD_PENDING
CURRENT_STOP_POINT=PR665_MERGED_POSTMERGE_HANDOFF_READY
CURRENT_BLOCKER=NEW_EXACT_RELEASE_AND_REAL_T1_LIVE_REVALIDATION_REQUIRED_BEFORE_PAIRING

LIVE_SYSTEM_STATE=
UNKNOWN_FRESH at handoff;
last proven post-failure snapshots showed stable Broker/Manager/Home Assistant runtime with restart_count=0,
but failed production marker remains terminal STARTED and T1_PRODUCTION_READY=false.

NEXT_ONE_GATE=N3W_T1_KF130_POSTMERGE_EXACT_MAIN_RELEASE_REBUILD_20261024_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1

PROJECT_WORKING_CONTEXT_REFERENCED=PASS
LONG_TERM_RULE_DUPLICATION_MINIMIZED=PASS
STAGE_SPECIFIC_OVERRIDES_EXPLICIT=PASS
PRIVATE_CONTEXT_EXCLUDED_FROM_PUBLIC_HANDOFF=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS
PROVEN_FACTS_SEPARATED_FROM_INFERENCE=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS
ALLOWED_FORBIDDEN_SCOPE_EXPLICIT=PASS
EXECUTION_CONTRACT_SELF_CONTAINED=PASS
CI_CONTINUATION_HARD_RULES_PRESENT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
TEAM_WORKSPACE_STATUS_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS
HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
