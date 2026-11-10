# N3-W T1 Home Assistant Mandatory-USB OTA
# KF-147 exact reclaim audit PASS → HA image cleanup preexecution
# 新会话交接文档 V1.0 — 2026-11-10

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
HISTORICAL_TEMPLATE_COPIES=HISTORICAL_EVIDENCE_ONLY
HISTORICAL_HANDOFF_STANDARD_DOES_NOT_AUTHORIZE_OLD_TEMPLATE=true
PROJECT_WORKING_CONTEXT_VERSION=1.5
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

本文只保存当前 KF-147 容量阻塞阶段增量。长期规则统一引用
`docs/development/N3W_PROJECT_WORKING_CONTEXT.md`。fresh repository/runtime/live
证据与本文冲突时，以 fresh 直接证据为准并先停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=KF147_EXACT_RECLAIM_AUDIT_CLOSED_PASS
CURRENT_STOP_POINT=BEFORE_ANY_T1_IMAGE_DELETE_OR_CLEANUP_AUTHORIZATION
NEXT_ONE_GATE=N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_PREEXECUTION_AND_AUTHORIZATION_REVIEW_20261110_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本轮已完成 fresh 容量 STOP、审计采集器修复、实机只读回收审计和完整
镜像分类。用户要求停止推进；新会话只能从 HA 2026.10.4 精确删除的
preexecution/authorization review 继续，不得直接删除。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.5
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=1
STAGE_OVERRIDES=NEXT_GATE_IS_PREEXECUTION_AND_AUTHORIZATION_REVIEW_ONLY;LIVE_DELETE_REMAINS_FORBIDDEN
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=remove proven unused internal HA target residue; re-prove capacity; then resume U1-preserving Manager IPC V3 image-only apply and mandatory-USB HA OTA
FINAL_ACCEPTANCE_TARGET=Manager IPC V3 live while preserving active U1; later complete exact Home Assistant 2026.10.4 mandatory-USB transaction
DEFERRED_OR_OUT_OF_SCOPE=Manager predecessor finalize; historical Manager tar cleanup; package/manifest binding before capacity PASS; USB erase/format; U2+; board work; PR merge
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
TREE=f15bec7c33c4d44d27c7068e5579b07027dd5ea5

CANDIDATE_REF=feat/n3w-ha-usb-r7a-prepare-pipeline-20261107
CANDIDATE_HEAD=3c46874c8470f80cde4436dc936fc78bfbebd93f
CANDIDATE_TREE=1dc136df75ec91108b334e7fc960fe02393e8a70
EXECUTABLE_RECLAIM_AUDIT_SOURCE_HEAD=b43d47f401d1b3f5624f116e4da68da5d464a2d1

ARTIFACT_ID=13391983948
ARTIFACT_SHA256=df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2
HA_TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
HA_TARGET_ARCHIVE_SIZE_BYTES=835309535

DEPLOYED_SOURCE_HEAD=7807271e4c48161f2fad96a7886fa4c24b038321
DEPLOYED_SOURCE_TREE=3d2893914d62645011a9a4badc7f939d10f9029e

OTHER_REQUIRED_AUTHORITY=exact audit SHA d15a55ae125f046ba7eaad3b63fc15a483cce95e9a5837fd6555cac904ff152c; HA target manifest infra/n3w-t1/upgrades/homeassistant-2026.10.4.json; mandatory-USB architecture V1.1; handoff-template blob 613ea57c74521610f25c576f25b7ce738d5a045f

CURRENT_PRODUCTION_AUTHORITY=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_STACK_RELEASE=Manager fresh-7807271e4c48; Home Assistant 2026.10.0-0c73235a; Broker 2.1.2-3184566d
STACK_RELEASE_ROLE=REAL_T1_RUNNING_BASELINE_WITH_ACTIVE_HA_USB_U1_TRANSACTION
COMPONENT_UPGRADE_BASELINE=Manager fresh-7807271e4c48 -> fresh-44e7d7472714; Home Assistant 2026.10.0 -> 2026.10.4 mandatory-USB
```

PR #800 is `OPEN / DRAFT / MERGEABLE`. Its base remains
`docs/n3w-r5-readonly-preflight-handoff-20261107@462018cb...`; do not assume that
the PR is directly based on current main.

---

## 4. Current Live Baseline

Fresh read-only evidence was created at `2026-11-10T11:00:00+0800`.

```text
MANAGER_STATE=RUNNING:local/greenhouse-manager:fresh-7807271e4c48;runtime_id=sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b
MANAGER_RESTART_STATE=0
BROKER_STATE=RUNNING:local/n3w-mosquitto:2.1.2-3184566d;runtime_id=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563;restart_count=0
HOMEASSISTANT_STATE=RUNNING:local/n3w-homeassistant:2026.10.0-0c73235a;runtime_id=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306;restart_count=0

HA_USB_TRANSACTION=ACTIVE:U1_PREPARE_REQUESTED
HA_USB_TRANSACTION_SHA256=6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49
USB_CONFIRMATION_REQUIRED=true
USB_CONFIRMATION_CONSUMED=false
USB_CANDIDATE_PRESENT=true
USB_CANDIDATE_MODEL=Extreme
USB_CANDIDATE_CAPACITY_BYTES=32017047552

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=NOT_APPLICABLE:HOST_STORAGE_CLEANUP_GATE
BOARD_B_POWER_STATE=UNKNOWN_FRESH
BOARD_B_LOCATION_ROLE=NOT_APPLICABLE:HOST_STORAGE_CLEANUP_GATE

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

Board state is intentionally not refreshed for this host-only gate.

---

## 5. Proven Current Facts

```text
FACT_1=Fresh capacity remains STOP: free 589463552 bytes; required 1736515716; deficit 1147052164
FACT_2=Capacity stopped before remote staging; Manager tar was not sent; mutation=false
FACT_3=Repaired audit returned read_only=true, mutation=false, runtime_stable=true
FACT_4=T1 has exactly five images and exactly three containers; all containers are running
FACT_5=HA 2026.10.4 exact image ID sha256:31bc185b... is non-running with zero container references
FACT_6=Docker reports HA 2026.10.4 shared size 0B and unique size 5.221GB
FACT_7=Mandatory-USB architecture retired the old P5 preexisting-internal-target requirement
FACT_8=Active U1 binds target ref/manifest/archive authority; it does not require internal target-image residency at U1
FACT_9=Broker has no old or unused image
FACT_10=Manager bf38e388497b predecessor has zero container references but remains the rollback predecessor of committed Manager 7807271 A0R
FACT_11=/var/tmp totals 254140416 bytes and includes four historical Manager tar files totaling 251648512 bytes
FACT_12=Fast Source run 42746005400 and Storage run 42746005381 are SUCCESS for repair/archive head ce2eaa06
FACT_13=PR800 state is OPEN/DRAFT/MERGEABLE; merge=false

INFERENCE_CAPACITY_AFTER_HA_CLEANUP=expected to PASS because the reported unique target allocation greatly exceeds the deficit; must be proven by fresh post-delete preflight
```

Private raw evidence stays local by policy. Public-safe bindings:

```text
CAPACITY_RESULT_SHA256=18a9fd87eee45fe36cca5f5715fca338e110cf24ed6da24d22494de7f8ac764a
CAPACITY_RESULT_SIZE=1974
RUNTIME_MUTABLE_REPORT_SHA256=d569bc372ecdcef5a27ce06c664c8f3903daac07e7df2ef7d98f390215b23c1c
RUNTIME_MUTABLE_REPORT_SIZE=2371
STORAGE_REPORT_SHA256=32e48742de6c03c6beb05fc759836c381d28012d721286b5a058ac115d737e06
STORAGE_REPORT_SIZE=617
STORAGE_RECLAIM_AUDIT_SHA256=d15a55ae125f046ba7eaad3b63fc15a483cce95e9a5837fd6555cac904ff152c
STORAGE_RECLAIM_AUDIT_SIZE=30024
SECRET_VALUES_INCLUDED=false
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=2
CURRENT_BLOCKER=capacity insufficient while unused internal HA 2026.10.4 target consumes unique image-store allocation; exact cleanup live authorization not granted
ROOT_CAUSE=retired P5 route left predecessor and target HA generations resident on a 16GB-class T1; current mandatory-USB route requires only the predecessor internally before U9
PROVEN_BY=fresh capacity report + full Docker image/container audit + mandatory-USB source/architecture review
SOURCE_DEFECT_PROVEN=HISTORICAL_ONLY:old P5 preexisting-target assumption is retired and must not be reused
RUNTIME_DEFECT_PROVEN=true:unused exact HA target is resident with zero references and capacity gate stops
```

---

## 7. Closed / Forbidden Routes

```text
BROAD_DOCKER_PRUNE=CLOSED:can delete current/rollback/product authority
DELETE_RUNNING_HA_2026_10_0=CLOSED:current production and pre-U9 predecessor authority
DELETE_MANAGER_BF38_WITH_HA_CLEANUP=CLOSED:separate Generic V2 finalize and rollback-window decision required
DELETE_VAR_TMP_BY_AGE_OR_WILDCARD=CLOSED:execution-package ownership and ledger classification required
REUSE_OLD_KF147_PACKAGE_OR_AUTHORIZATION=CLOSED:fresh rebind invalidated old package/authority
PACKAGE_BINDING_BEFORE_FRESH_CAPACITY_PASS=CLOSED:capacity admission must pass first
DIRECT_LIVE_DELETE_FROM_HANDOFF=CLOSED:preexecution/source/authorization review is next
```

---

## 8. Authorization Ledger

Historical Manager authorization:

```text
AUTHORIZATION=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_20261109_01
CLAIMED=false
CONSUMED=false
RESULT=SUPERSEDED_BY_FRESH_REBIND_AND_CAPACITY_ROUTE
REPLAY_PERMITTED=false
SUPERSEDED_BY=fresh cleanup -> capacity PASS -> new package/manifest binding -> new live authorization
```

Proposed cleanup authority:

```text
PROPOSED_AUTHORIZATION=N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_20261110_01
GRANTED=false
CLAIMED=false
CONSUMED=false
REPLAY_PERMITTED=false
```

The user did not grant this authorization before requesting dialogue stop.

---

## 9. Rollback Authority

The next gate is non-mutating, but the eventual delete design must bind:

```text
ROLLBACK_BASELINE=exact HA 2026.10.4 archive SHA256 eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973; exact target image ID sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
ROLLBACK_AUTHORITY_PATH_OR_ID=infra/n3w-t1/upgrades/homeassistant-2026.10.4.json plus exact public OTA artifact authority
RESTART_SCOPE_ALLOWED=NONE
SECOND_ATTEMPT_ALLOWED=false
ROLLBACK_FAILURE_CLASS=ROLLBACK_INCOMPLETE
```

No rollback action is authorized by this handoff.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_PREEXECUTION_AND_AUTHORIZATION_REVIEW_20261110_01
```

### Purpose

Prepare and independently review a fail-closed, exact-ID cleanup path for the proven
unused HA 2026.10.4 image. Rebind fresh runtime/U1 state and produce an exact
one-shot authorization request. This gate does not delete the image, prove post-delete
capacity PASS, apply Manager V3 or advance the USB transaction.

### Inputs

```text
AUDIT_EVIDENCE_SHA256=d15a55ae125f046ba7eaad3b63fc15a483cce95e9a5837fd6555cac904ff152c
TARGET_IMAGE_REF=local/n3w-homeassistant:2026.10.4-5881590f
TARGET_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
RUNNING_HA_REF=local/n3w-homeassistant:2026.10.0-0c73235a
RUNNING_HA_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
U1_TRANSACTION_SHA256=6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49
```

### Operations

```text
1. Fresh-rebind PR #800 repository head and verify no cleanup-source/authority drift.
2. Review the exact HA target, active predecessor and U1 lifecycle boundary.
3. Prepare or validate a repository-owned exact cleanup executor with pre/post checks and no broad cleanup primitive.
4. Add focused tests and run applicable local validation and GitHub CI.
5. Run one fresh read-only preclaim proving exact target ID, zero references, three-service stability and unchanged U1/confirmation state.
6. Emit the exact proposed live authorization scope and STOP before any docker image rm.
```

### PASS / FAIL / STOP

```text
PASS_IF=exact cleanup executor/source/CI PASS; fresh preclaim binds target ID with zero references; current three services and U1 remain stable; authorization remains unclaimed
FAIL_IF=source/authority drift, target absent or ID drift, any container reference, runtime/U1/USB drift, unsafe cleanup primitive, incomplete rollback authority or CI failure
STOP_BOUNDARY=after exact authorization package/request is ready; before authorization grant/claim and before image deletion

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
- repository/source/test/docs review and bounded implementation for exact cleanup preexecution
- local simulation and applicable GitHub CI
- fresh T1 read-only inventory/preclaim after source/CI review
- GitHub progress/closure archive
```

### FORBIDDEN

```text
- docker image rm, docker rm, any force deletion, any prune or wildcard cleanup
- deleting HA 2026.10.0, Manager bf38 predecessor, Broker, volumes or /var/tmp residues
- Manager tar transfer, remote staging, package/manifest binding or Manager live apply
- changing U1, consuming confirmation, formatting/erasing/mounting USB, U2+
- board access, firmware/NVS mutation or PR merge
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=Mac private evidence root plus repository/GitHub source-test-doc archive only
```

---

## 12. Execution Contract

```text
EXECUTOR=TO_BE_PREPARED_OR_REVIEWED:repository-bound exact HA target cleanup preexecution
EXECUTION_METHOD=mac-terminal for interactive SSH read-only preclaim; repository tools for source/tests/CI
DIRECT_CODE_SUPPLIED=false
DSL_COMPILATION_USED=false
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

Do not use a raw ad-hoc `docker image rm` command as the executor. The final live
gate must be exact-ref/exact-ID bound, reject all container references including
stopped containers, verify U1 and runtime before/after, and produce private evidence.

---

## 13. Expected Closure

```text
=== N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_PREEXECUTION_AND_AUTHORIZATION_REVIEW_20261110_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_20261110_01
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

EXACT_TARGET_REF=local/n3w-homeassistant:2026.10.4-5881590f
EXACT_TARGET_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
TARGET_CONTAINER_REFERENCE_COUNT=0
RUNNING_PREDECESSOR_EXACT=true
THREE_SERVICE_RUNTIME_STABLE=true
U1_TRANSACTION_UNCHANGED=true
CONFIRMATION_UNCONSUMED=true
SOURCE_TESTS=PASS
GITHUB_CI=PASS

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

PREEXECUTION_REVIEW_RESULT=PASS
NEXT_ROUTE=REQUEST_EXPLICIT_EXACT_CLEANUP_LIVE_AUTHORIZATION
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_LIVE
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

After eventual live cleanup PASS, the only next operation is a fresh capacity
preflight. Do not infer capacity PASS from Docker size accounting.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF150 exact lifecycle/capacity guard; 2026-11-10 reclaim-audit timeout guard
NEW_KF_REQUIRED=false
```

The first audit `command_failed:ssh:1` is already guarded by repair
`b43d47f401d1b3f5624f116e4da68da5d464a2d1`; the repaired live retry PASS.

---

## 16. New Chat Start Prompt

```text
阅读《docs/development/N3W_T1_KF147_EXACT_RECLAIM_AUDIT_PASS_TO_HA_IMAGE_CLEANUP_PREEXECUTION_NEW_CHAT_HANDOFF_V1.0_20261110.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“N3-W T1 KF-147 容量阻塞解除”。

先 fresh rebind PR #800 和当前实机只读基线，然后只进入：

NEXT_ONE_GATE=N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_PREEXECUTION_AND_AUTHORIZATION_REVIEW_20261110_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

不要直接删除镜像，不要重放旧 Manager authorization，不要使用 prune，不要删除 Manager predecessor 或 /var/tmp 历史包，不要自动跨越到 live cleanup、Manager apply、USB 或 merge。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=KF147_EXACT_RECLAIM_AUDIT_CLOSED_PASS
CURRENT_STOP_POINT=BEFORE_EXACT_HA_TARGET_CLEANUP_PREEXECUTION_AND_AUTHORIZATION
CURRENT_BLOCKER=unused HA 2026.10.4 image causes capacity STOP; cleanup authorization not granted
LIVE_SYSTEM_STATE=three services running/restart_count=0; HA 2026.10.0 active; HA 2026.10.4 present/unreferenced; U1 active/unconsumed
NEXT_ONE_GATE=N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_PREEXECUTION_AND_AUTHORIZATION_REVIEW_20261110_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
PRIVATE_LOCAL_EVIDENCE_COUNT=4
PRIVATE_LOCAL_EVIDENCE_PUBLIC_BINDINGS_ARCHIVED=true
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.5
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.5

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
HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
