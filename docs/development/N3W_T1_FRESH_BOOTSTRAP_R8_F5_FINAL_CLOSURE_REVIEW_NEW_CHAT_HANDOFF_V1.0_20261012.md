> **SUPERSEDED — 2026-10-12**  
> 本文件误用了旧通用 process/DSL handoff 结构，不能作为新会话 current handoff authority。  
> 正式替代文件：docs/development/N3W_T1_FRESH_BOOTSTRAP_R8_F5_FINAL_CLOSURE_REVIEW_NEW_CHAT_HANDOFF_V1.1_20261012.md。  
> 保留本文件仅作历史记录，不得据此执行下一 gate。

# 温室环境监测系统（ESP32-C6） / N3-W
# T1 fresh bootstrap R8 F5 final closure review
# 新会话交接文档 V1.0 — 2026-10-12

~~~text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
~~~

> 本文符合 \`docs/development/NEW_CHAT_HANDOFF_STANDARD.md\`。  
> 如本文与 exact repository/runtime/live evidence 冲突，以更高 authority 为准，并先停止执行、完成 rebind。

---

## 0. 会话切换结论

本轮已完成 Astra R3 唯一剩余 F5 blocker 的最小 source repair、两次测试夹具修正和 exact-head 25/25 CI closure。为了避免继续拉长当前会话，最终独立源码复核放到新会话。

~~~text
CURRENT_STAGE=N3W_T1_FRESH_BOOTSTRAP_R8_F5_SOURCE_REPAIR_CI_CLOSED
CURRENT_STOP_POINT=F5_SOURCE_REPAIR_CI_GREEN_FINAL_INDEPENDENT_REVIEW_NOT_RUN
NEXT_ONE_GATE=N3W_T1_FRESH_BOOTSTRAP_R8_F5_FINAL_CLOSURE_REVIEW_20261012_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
~~~

下一会话不是重新复盘全部 fresh bootstrap 历史，而是 fresh rebind 后只执行上述最终复核 gate。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 exact source / PR / CI authority；
- 判断 F5 是否真正 CLOSED；
- 判断 \`DOWNSTREAM_SOURCE_BLOCKER\` 是否为 NO；
- 维护 authorization/no-replay 边界；
- 决定是否允许进入 replacement artifact binding + T1 read-only preflight；
- 不把测试夹具问题误判为产品问题。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL review contract；
- 读取 Git/PR/CI/source/test evidence；
- 只读解析和结构化 closure；
- 第一处 substantive mismatch 后 STOP；
- 不修复、不提交、不授权、不进入 T1。

Codex 不得扩大 scope、重放 authorization、跨越下一 gate。

### 1.3 DSL execution semantics

~~~text
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false
~~~

### 1.4 标准交互循环

~~~text
高阶模型：final source-review gate
        ↓
Codex：fresh rebind / source+CI evidence / structured closure
        ↓
高阶模型：PASS / BLOCK
        ↓
STOP
~~~

本 gate 不需要 mutation authorization。

---

## 2. Product North Star

当前产品路线：

~~~text
minimal-host T1
→ exact offline fresh-product bootstrap
→ stopped fresh-product postcheck
→ later separately authorized activation
~~~

最终阶段目标：

~~~text
在真实 T1 上从最小宿主基线安全建立 fresh product state，
保持 exact image/source/credential/no-replay authority，
且任何失败可 fail-closed 并保持生产服务未启动。
~~~

当前不得进入：

~~~text
live apply
production service start
board/USB/serial/Flash/NVS/RF
PR merge
retained R3 payload cleanup
artifact binding before final source review PASS
~~~

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

~~~text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
TREE=ee977996a4c962097684519841dce2e3bcba23f2

PR=541
PR_BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010
PR_BASE=main
PR_STATE=OPEN_DRAFT
REVIEW_SOURCE_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
~~~

\`5ed613673ec1ead29a1153d0e3916bdd3539a3fb\` 是新会话最终复核的 exact source/test authority，且已有 25/25 CI PASS。

F5 production/harness logic was introduced at:

~~~text
F5_IMPORTS_FAILCLOSED_COMMIT=0957958c535d67c29cec411df98829d00e7a9028
~~~

后续两笔只修改 storage-probe test fixture：

~~~text
0ad32499c6545ced0614baa2274cafdb60061204
5ed613673ec1ead29a1153d0e3916bdd3539a3fb
~~~

### 3.2 Candidate / artifact / image

~~~text
CANDIDATE_REF=PR#541@5ed613673ec1ead29a1153d0e3916bdd3539a3fb
CANDIDATE_ID=SOURCE_REVIEW_ONLY
VERSION=R8_F5_FINAL_CLOSURE
REVISION=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
ARCH=aarch64-target
~~~

Replacement artifact is intentionally not frozen yet:

~~~text
REPLACEMENT_ARTIFACT_AUTHORITY=NOT_APPLICABLE:FINAL_SOURCE_REVIEW_MUST_PASS_FIRST
~~~

### 3.3 Successor / deployment material

~~~text
SUCCESSOR_AUTHORITY=NOT_APPLICABLE:ARTIFACT_BINDING_IS_AFTER_NEXT_GATE
~~~

Prospective live authorization constant in current source:

~~~text
PROPOSED_LIVE_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_08
GRANTED=false
CLAIMED=false
CONSUMED=false
~~~

### 3.4 Target host / runtime authority

~~~text
TARGET_HOST=T1
TARGET_ARCH=aarch64
TARGET_DOCKER_LAST_PROVEN=29.7.1
TARGET_STORAGE_MODEL=containerd-image-store-path-requires-fresh-readonly-rebind-before-prelive
PRIVATE_T1_ADDRESS_PUBLIC_DOCS=FORBIDDEN
~~~

No T1 access is needed or allowed in the next gate.

---

## 4. Current Live Baseline

Last proven real-T1 post-R3 cleanup baseline:

~~~text
LAST_PROVEN_T1_BASELINE=minimal_host
CONTAINERS=0
IMAGES=0
VOLUMES=0
NETWORKS=bridge,host,none
PRODUCT_PATHS_PRESENT=0
PRODUCT_UNITS=0
PRODUCT_LISTENERS=0
INVENTORY_SHA256=e38273381de031789fff2f5c2fb37725c328cfaa9710603b6c74ba920422842d
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
~~~

Retained forensic payload intentionally remains:

~~~text
R3_RETAINED_PAYLOAD=/var/tmp/n3w-fresh-bootstrap.EOmzn8
R3_AUTHORIZATION=_03
R3_AUTHORIZATION_CONSUMED=true
R3_REPLAY_ALLOWED=false
R3_RETAINED_PAYLOAD_CLEANUP_AUTHORIZED=false
~~~

This is historical last-proven live state, not fresh current-state authority:

~~~text
T1_BASELINE_REQUIRES_FRESH_READONLY_REBIND_BEFORE_PRELIVE=true
MANAGER_STATE_REQUIRES_FRESH_READONLY_REBIND=true
BROKER_STATE_REQUIRES_FRESH_READONLY_REBIND=true
HOMEASSISTANT_STATE_REQUIRES_FRESH_READONLY_REBIND=true
~~~

Physical defaults:

~~~text
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
~~~

---

## 5. Proven Current Facts

~~~text
ASTRA_R3_D1=CLOSED
ASTRA_R3_A8=CLOSED
ASTRA_R3_F5=OPEN_BLOCKER_BEFORE_R8_REPAIR

F5_REPAIR_NONEMPTY_CONTAINERD_IMPORTS=FAIL_CLOSED
F5_REPAIR_HAPPENS_PRETRANSFER_PRECLAIM=true

DIRECT_ROOT_GENERATED_PROBE_TEST=PASS
NONEMPTY_IMPORTS_GENERATED_PROBE_TEST=PASS

EXACT_REVIEW_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
EXACT_HEAD_WORKFLOW_TOTAL=25
EXACT_HEAD_WORKFLOW_PASS=25
EXACT_HEAD_WORKFLOW_FAIL=0

DEPLOYABLE_RUN=38245536856
DEPLOYABLE_FOCUSED_TESTS=71_PASS
PRODUCTION_STACK_STAGING_RUN=38245536675
PRODUCTION_STACK_FOCUSED_TESTS=47_PASS

LIVE_T1_ACCESSED_THIS_REPAIR=false
LIVE_RUNTIME_MUTATED_THIS_REPAIR=false
BOARD_ACCESSED_THIS_REPAIR=false
~~~

The first two R8 CI failures were proven test-fixture-only:

~~~text
FIXTURE_FAILURE_1=fake_systemctl_service_argument_index
FIXTURE_FAILURE_2=python_-c_collision_with_containerd_-c
PRODUCT_GUARD_WEAKENED_BY_FIXES=false
~~~

Inference kept separate:

~~~text
INFERENCE_F5_READY_FOR_FINAL_CLOSURE_REVIEW=true
~~~

This is not yet equivalent to \`F5=CLOSED\`; that decision belongs to NEXT_ONE_GATE.

---

## 6. Current Root Cause / Blockers

Current source-repair blocker count before independent closure:

~~~text
CURRENT_BLOCKER_COUNT=1
CURRENT_BLOCKER=F5_PENDING_FINAL_INDEPENDENT_CLOSURE
~~~

The original F5 concrete defect was:

~~~text
ROOT_CAUSE=primary_containerd_TOML_was_treated_as_complete_effective_config_even_when_nonempty_imports_could_override_root
PROVEN_BY=Astra_R3_counterexample_and_generated_probe_review
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=false
~~~

The source repair exists and CI is green, but project process requires one final independent review before classifying it CLOSED.

No other known downstream source blocker remains from Astra R3:

~~~text
D1=CLOSED
A8=CLOSED
NEW_BLOCKERS_AT_ASTRA_R3=0
~~~

---

## 7. Closed / Forbidden Routes

Unless new direct counter-evidence appears:

~~~text
F1_PORTABLE_IMAGE_IDENTITY=CLOSED
F2_DYNSEC_LOG_VOLUME_LIFECYCLE=CLOSED
F3_CREDENTIAL_BUNDLE_IMMUTABILITY=CLOSED
F4_DURABLE_NO_REPLAY=CLOSED
F6_SAFE_FAILURE_OBSERVABILITY=CLOSED
D1_POSTCHECK_STATE_OWNER_MISMATCH=CLOSED
A8_ARTIFACT_DOWNLOAD_TIMEOUT_FALLBACK=CLOSED
~~~

Forbidden:

~~~text
R3_AUTHORIZATION_03_REPLAY=FORBIDDEN
_04_REPLAY_OR_GRANT=FORBIDDEN:SUPERSEDED_UNGRANTED
_05_REPLAY_OR_GRANT=FORBIDDEN:SUPERSEDED_UNGRANTED
_06_REPLAY_OR_GRANT=FORBIDDEN:SUPERSEDED_UNGRANTED
_07_REPLAY_OR_GRANT=FORBIDDEN:SUPERSEDED_UNGRANTED
FULL_CONTAINERD_IMPORT_MERGE_IMPLEMENTATION=OUT_OF_SCOPE
T1_LIVE_APPLY_BEFORE_FINAL_REVIEW=FORBIDDEN
R3_RETAINED_PAYLOAD_DELETE_IN_NEXT_GATE=FORBIDDEN
PR541_MERGE_IN_NEXT_GATE=FORBIDDEN
~~~

Do not reopen F1/F2/F3/F4/F6/D1/A8 merely for completeness.

---

## 8. Authorization Ledger

~~~text
AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_01
CLAIMED=false
CONSUMED=false
RESULT=STOP_PRECLAIM_SOURCE_SUPERSEDED
REPLAY_PERMITTED=false
SUPERSEDED_BY=_02

AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_02
CLAIMED=false
CONSUMED=false
RESULT=STOP_PRECLAIM_SOURCE_SUPERSEDED
REPLAY_PERMITTED=false
SUPERSEDED_BY=_03

AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_03
CLAIMED=true
CONSUMED=true
RESULT=STOP_PARTIAL_CLEANUP_PROVEN
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

AUTHORIZATION=_04
CLAIMED=false
CONSUMED=false
RESULT=SUPERSEDED_UNGRANTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=_05

AUTHORIZATION=_05
CLAIMED=false
CONSUMED=false
RESULT=SUPERSEDED_UNGRANTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=_06

AUTHORIZATION=_06
CLAIMED=false
CONSUMED=false
RESULT=SUPERSEDED_UNGRANTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=_07

AUTHORIZATION=_07
CLAIMED=false
CONSUMED=false
RESULT=SUPERSEDED_UNGRANTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=_08

AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_08
CLAIMED=false
CONSUMED=false
RESULT=PROSPECTIVE_NOT_GRANTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
~~~

For the next gate:

~~~text
LIVE_AUTHORIZATION_REQUIRED=false
READY_TO_GRANT_08=false
~~~

A PASS in the next gate still does not grant _08.

---

## 9. Rollback Authority

The next gate is repository/source/CI read-only:

~~~text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
SECOND_ATTEMPT_ALLOWED=NOT_APPLICABLE
~~~

Future retained-payload cleanup and live work require separate fresh authority and are not covered here.

---

## 10. Next ONE Gate

~~~text
NEXT_ONE_GATE=N3W_T1_FRESH_BOOTSTRAP_R8_F5_FINAL_CLOSURE_REVIEW_20261012_01
~~~

### 10.1 Purpose

Independently verify only that the R8 non-empty-containerd-imports fail-closed repair closes Astra R3 F5 and that the repaired current source has no remaining downstream source-visible blocker. Do not perform artifact binding or T1 work.

### 10.2 Frozen inputs

~~~text
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR=541
REVIEW_SOURCE_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
F5_REPAIR_COMMIT=0957958c535d67c29cec411df98829d00e7a9028
CI_EXPECTED=25/25_PASS
ASTRA_R3_D1=CLOSED
ASTRA_R3_A8=CLOSED
PROSPECTIVE_AUTHORIZATION=_08_NOT_GRANTED
~~~

Primary source/evidence:

~~~text
tools/n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_fresh_product_bootstrap.py
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml

docs/development/N3W_T1_FRESH_BOOTSTRAP_R7_ASTRA_R3_CLOSURE_REVIEW_BRIEF_20261012.md
docs/development/N3W_T1_FRESH_BOOTSTRAP_R8_F5_IMPORTS_FAILCLOSED_SOURCE_REPAIR_CLOSURE_20261012.md
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
~~~

### 10.3 Required proof / operations

~~~text
1. Fresh rebind main, PR #541 and REVIEW_SOURCE_HEAD.
2. Confirm PR remains OPEN/DRAFT and not merged.
3. Confirm REVIEW_SOURCE_HEAD exact workflows are 25/25 PASS.
4. Verify F5 production path:
   - external containerd effective config path is resolved from process/config authority;
   - config.get("imports") is checked;
   - any non-empty imports raise containerd_imports_unsupported;
   - no fallback converts this uncertainty into DockerRootDir authority;
   - this path executes before remote payload staging/authorization claim.
5. Verify actual generated-probe regressions:
   - direct primary root case executes and resolves exact root;
   - imported-config case executes and fails with containerd_imports_unsupported;
   - the two later commits modify only test fixture mechanics and do not weaken the product guard.
6. Focused downstream source scan:
   - only check whether R8 changes introduce a new source-visible blocker;
   - do not reopen already CLOSED F1/F2/F3/F4/F6/D1/A8 without direct counter-evidence.
7. Return the exact closure below.
8. STOP.
~~~

### 10.4 PASS

~~~text
F5=CLOSED
DOWNSTREAM_SOURCE_BLOCKER=NO
R8_PRELIVE_RECOMMENDATION=PROCEED_TO_ARTIFACT_BINDING_AND_READONLY_PREFLIGHT
READY_FOR_REPLACEMENT_ARTIFACT_BINDING=true
LIVE_APPLY_AUTHORIZED=false
STOP=true
~~~

### 10.5 FAIL

~~~text
F5=OPEN_BLOCKER|OPEN_NONBLOCKER
or
DOWNSTREAM_SOURCE_BLOCKER=YES

R8_PRELIVE_RECOMMENDATION=BLOCK
READY_FOR_REPLACEMENT_ARTIFACT_BINDING=false
STOP=true
~~~

Codex must not repair or execute any successor gate.

---

## 11. Hard Allowed / Forbidden Scope

Default:

~~~text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
~~~

### ALLOWED

~~~text
- GitHub repository/PR/commit/workflow read-only inspection
- exact source/test diff review
- CI job/log read-only inspection
- public documentation read-only inspection when necessary
- local reasoning over source evidence
~~~

### FORBIDDEN

~~~text
- source/docs commit or branch mutation
- PR merge
- T1 SSH or any T1 access
- artifact binding/download for live use
- retained R3 payload cleanup
- authorization grant/claim/consume
- Docker mutation on T1
- production service start
- board/USB/serial/Flash/NVS/RF access
- automatic repair or retry
~~~

~~~text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
~~~

---

## 12. Codex DSL Execution Contract

~~~text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required unless
this protocol explicitly says so.

Mechanically compile this DSL into the minimum necessary commands
using already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not retry unless explicitly permitted.
Do not enter the next gate.
~~~

~~~text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================

GATE=N3W_T1_FRESH_BOOTSTRAP_R8_F5_FINAL_CLOSURE_REVIEW_20261012_01
READ_ONLY=true
LIVE_AUTHORIZATION=NONE
PROSPECTIVE_LIVE_AUTHORIZATION=_08_NOT_GRANTED
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false

============================================================
1. FROZEN INPUTS
============================================================

REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR=541
REVIEW_SOURCE_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
F5_REPAIR_COMMIT=0957958c535d67c29cec411df98829d00e7a9028
EXPECTED_CI_TOTAL=25
EXPECTED_CI_PASS=25

============================================================
2. HARD SCOPE
============================================================

ALLOWED:
- read repository/PR/commits/CI/logs
- inspect exact files and diffs
- classify source evidence

FORBIDDEN:
- modify repository
- access T1
- bind live artifact
- cleanup retained payload
- grant/claim authorization
- merge
- repair/retry/next-gate execution

============================================================
3. FRESH REBIND
============================================================

Resolve current main.
Resolve PR #541 state/head/base.
Confirm REVIEW_SOURCE_HEAD is in the PR lineage.
Confirm the two post-repair commits after 0957958c535d67c29cec411df98829d00e7a9028
touch test fixture only.
Confirm exact REVIEW_SOURCE_HEAD CI = 25/25 PASS.

If any frozen authority is contradicted:
  RESULT=STOP_AUTHORITY_DRIFT
  STOP.

============================================================
4. F5 SOURCE CLOSURE
============================================================

Inspect the exact storage-probe source.

Prove:
- non-empty containerd imports cannot be treated as a complete primary config;
- the source raises containerd_imports_unsupported;
- no catch/fallback converts that condition into a guessed image-store root;
- storage report/capacity code consumes actual image-store free-space authority;
- all occurs before payload transfer and authorization claim.

Classify:
F5=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER

============================================================
5. F5 EXECUTION REGRESSION
============================================================

Inspect the exact generated-probe execution tests and successful CI logs.

Prove both:
DIRECT_PRIMARY_ROOT_EXECUTION=PASS
NONEMPTY_IMPORTS_FAILCLOSED_EXECUTION=PASS

Verify 0ad32499... and 5ed61367... are test-fixture-only.

============================================================
6. DOWNSTREAM DELTA SCAN
============================================================

Review only the R8 delta and its immediate callers for a newly introduced
source-visible blocker.

Do not reopen F1/F2/F3/F4/F6/D1/A8 without new direct evidence.

Classify:
DOWNSTREAM_SOURCE_BLOCKER=YES | NO

============================================================
7. DECISION
============================================================

PASS only if:
F5=CLOSED
DOWNSTREAM_SOURCE_BLOCKER=NO
CI=25/25 PASS
_08 remains NOT_GRANTED

If PASS:
R8_PRELIVE_RECOMMENDATION=
PROCEED_TO_ARTIFACT_BINDING_AND_READONLY_PREFLIGHT

Otherwise:
R8_PRELIVE_RECOMMENDATION=BLOCK

============================================================
8. HARD STOP
============================================================

Do not bind an artifact.
Do not access T1.
Do not clean retained payload.
Do not authorize _08.
Do not merge.
Do not execute the successor.
Return closure and STOP.
~~~

---

## 13. Expected Closure

~~~text
=== N3W_T1_FRESH_BOOTSTRAP_R8_F5_FINAL_CLOSURE_REVIEW_20261012_01 CLOSURE ===

REVIEW_SOURCE_HEAD=
PR_HEAD_AT_REVIEW=
MAIN_AT_REVIEW=
PR_STATE=
CI_STATE=

F5=
DIRECT_PRIMARY_ROOT_EXECUTION=
NONEMPTY_IMPORTS_FAILCLOSED_EXECUTION=
DOWNSTREAM_SOURCE_BLOCKER=

NEW_BLOCKERS=
TOTAL_BLOCKERS=

R8_PRELIVE_RECOMMENDATION=
R8_LIVE_APPLY_RECOMMENDATION=NOT_YET_AUTHORIZED
MERGE_RECOMMENDATION=NO_MERGE

REQUIRED_SOURCE_REPAIRS=
REQUIRED_TESTS=
REQUIRED_PRELIVE_STEPS=

LIVE_RUNTIME_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
AUTHORIZATION_08_GRANTED=false

NEXT_ROUTE=
STOP=true

=== END ===
~~~

---

## 14. After PASS / FAIL

### PASS 后

~~~text
AFTER_PASS_NEXT_STAGE=N3W_T1_FRESH_BOOTSTRAP_R8_REPLACEMENT_ARTIFACT_BINDING_AND_READONLY_PREEXECUTION_PREPARATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=false
~~~

PASS 只允许设计/进入 replacement artifact binding + bounded retained-payload cleanup boundary + T1 read-only preflight。它不授权 cleanup/live apply。

### FAIL 后

~~~text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
~~~

---

## 15. KNOWN_FAILURES Updates

~~~text
KNOWN_FAILURES_UPDATE_REQUIRED=true
KF_ID=KF-111
DOMAIN=PRODUCT
SYMPTOM=containerd_effective_storage_root_authority_could_be_wrong_when_primary_config_uses_imports
ROOT_CAUSE=primary_TOML_was_treated_as_complete_config_without_imports_guard
FIX_OR_GUARD=fail_closed_on_nonempty_imports_plus_generated_probe_execution_regressions
STATUS=SOURCE_REPAIR_CI_GREEN_PENDING_FINAL_INDEPENDENT_REVIEW
~~~

No new KF number is allocated.

---

## 16. New Chat Start Prompt

~~~text
阅读：

docs/development/N3W_T1_FRESH_BOOTSTRAP_R8_F5_FINAL_CLOSURE_REVIEW_NEW_CHAT_HANDOFF_V1.0_20261012.md

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #541
- REVIEW_SOURCE_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_FRESH_BOOTSTRAP_R8_F5_IMPORTS_FAILCLOSED_SOURCE_REPAIR_CLOSURE_20261012.md
- docs/development/N3W_T1_FRESH_BOOTSTRAP_R7_ASTRA_R3_CLOSURE_REVIEW_BRIEF_20261012.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

本轮继续采用：
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

当前只进入：
NEXT_ONE_GATE=N3W_T1_FRESH_BOOTSTRAP_R8_F5_FINAL_CLOSURE_REVIEW_20261012_01

本轮严格只读：
LIVE_MUTATION_DEFAULT=false
T1_ACCESS=false
BOARD_ACCESS_DEFAULT=false
PRODUCTION_SERVICE_START=false
MERGE=false

只复核：
- F5
- DIRECT_PRIMARY_ROOT_EXECUTION
- NONEMPTY_IMPORTS_FAILCLOSED_EXECUTION
- DOWNSTREAM_SOURCE_BLOCKER

必须承认：
- Astra R3 已 CLOSED D1 与 A8；
- F1/F2/F3/F4/F6 已 CLOSED，除非出现新的直接反证，不重开；
- 5ed613673ec1ead29a1153d0e3916bdd3539a3fb exact CI 已 25/25 PASS；
- _03 已 consumed/no-replay；
- _04/_05/_06/_07 均 superseded-ungranted，不得使用；
- _08 仍 NOT_GRANTED；
- 不访问 T1；
- 不清 R3 retained payload；
- 不绑定 replacement artifact；
- 不 merge PR #541。

先 fresh rebind current authority，再严格执行 handoff 中的 DSL review gate。
不要自动跨越下一阶段。
~~~

---

## 17. Final Frozen State

~~~text
CURRENT_STAGE=N3W_T1_FRESH_BOOTSTRAP_R8_F5_SOURCE_REPAIR_CI_CLOSED
CURRENT_STOP_POINT=FINAL_INDEPENDENT_F5_CLOSURE_REVIEW_PENDING

SOURCE_DEFECT_PROVEN=true
SOURCE_REPAIR_PRESENT=true
SOURCE_REPAIR_CI=25/25_PASS
CURRENT_BLOCKER=F5_PENDING_FINAL_INDEPENDENT_CLOSURE

LIVE_SYSTEM_STATE=LAST_PROVEN_MINIMAL_BASELINE_REQUIRES_FRESH_READONLY_REBIND_BEFORE_PRELIVE
R3_RETAINED_PAYLOAD=PRESERVED
LIVE_AUTHORIZATION_08=NOT_GRANTED

NEXT_ONE_GATE=N3W_T1_FRESH_BOOTSTRAP_R8_F5_FINAL_CLOSURE_REVIEW_20261012_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

HANDOFF_STANDARD_VERSION=1.0
~~~

---

## 18. Handoff Compliance Audit

~~~text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.0

EXECUTION_MODEL_EXPLICIT=PASS
HIGH_LEVEL_CODEX_ROLE_BOUNDARY=PASS
DSL_EXECUTION_SEMANTICS_EXPLICIT=PASS

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
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS

HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
~~~
