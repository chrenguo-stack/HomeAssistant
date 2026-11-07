# 温室环境监测系统（ESP32-C6）N3-W
# T1 Home Assistant mandatory-USB OTA R4 收敛完成 → R5 真实 T1 只读预检
# 新会话交接文档 V1.0 — 2026-11-07

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
HISTORICAL_TEMPLATE_COPIES=HISTORICAL_EVIDENCE_ONLY
HISTORICAL_HANDOFF_STANDARD_DOES_NOT_AUTHORIZE_OLD_TEMPLATE=true
PROJECT_WORKING_CONTEXT_VERSION=1.9
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
HANDOFF_TEMPLATE_AUTHORITY=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
HANDOFF_TEMPLATE_BLOB_SHA=613ea57c74521610f25c576f25b7ce738d5a045f
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存 R4 收敛完成到 R5 真实 T1 只读预检所需的当前增量。长期规则引用
> `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`。fresh repository/runtime/live evidence
> 与本文冲突时，以 fresh 直接证据为准并停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=HA_USB_MANDATORY_OTA_R4_CLOSED_AND_CLEAN_SUCCESSOR_CONVERGED_TO_MAIN
CURRENT_STOP_POINT=BEFORE_R5_REAL_T1_READONLY_PREFLIGHT
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

R4 已完成源码、CI、closure，并经 PR #798 clean successor 收敛进入 canonical `main`。
本会话停止在真实 T1 访问之前；新会话直接从 R5 真实 T1 **只读**预检开始。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.9
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=2
STAGE_OVERRIDES=
  1:R5_REAL_T1_ACCESS_IS_AUTHORIZED_READONLY_ONLY_BY_2026_11_07_USER_INSTRUCTION;
  2:NO_R5_MUTATION_AUTHORITY_IS_GRANTED
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=
T1_Core_Stack_OTA_PRODUCT_ARCHITECTURE
-> T1_Core_Updater_PRIVILEGED_ENGINE
-> Manager_Generic_V2
-> Broker_Generic_V2
-> HomeAssistant_Mandatory_USB

FINAL_ACCEPTANCE_TARGET=
END_USER_T1_CORE_STACK_OTA_WITH_ONE_PRODUCT_UPDATE_SURFACE_AND_COMPONENT_SPECIFIC_SAFE_EXECUTION

DEFERRED_OR_OUT_OF_SCOPE=
BROKER_PRODUCT_OTA_IMPLEMENTATION;
FULL_SIGNED_STACK_RELEASE_PUBLICATION;
R5_OR_LATER_MUTATION;
USB_FORMAT;
SERVICE_STOP;
DOCKER_IMAGE_MUTATION;
BOARD_ACCESS;
MERGE
```

Current product architecture authority:

`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.0_20261106.md`

Frozen relationship:

```text
PUBLIC_PRODUCT_CONCEPT=T1_Core_Stack_OTA
PRIVILEGED_EXECUTION_ENGINE=T1_Core_Updater
MANAGER_STRATEGY=GENERIC_V2_SUCCESSOR
BROKER_STRATEGY=GENERIC_V2_SUCCESSOR
HOMEASSISTANT_STRATEGY=MANDATORY_USB_SUCCESSOR
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
TREE=f15bec7c33c4d44d27c7068e5579b07027dd5ea5
MAIN_ROLE=CANONICAL_PRE_HANDOFF_DOC_EXECUTION_AND_STATE_AUTHORITY

CANDIDATE_REF=docs/n3w-r5-readonly-preflight-handoff-20261107
CANDIDATE_HEAD=<filled by this docs-only commit>
CANDIDATE_TREE=<filled by GitHub after commit>
CANDIDATE_ROLE=HANDOFF_DOCUMENT_ONLY_NO_EXECUTABLE_DELTA

ARTIFACT_ID=NOT_APPLICABLE:R5_IS_READONLY_PREFLIGHT
ARTIFACT_SHA256=NOT_APPLICABLE:R5_IS_READONLY_PREFLIGHT

DEPLOYED_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
DEPLOYED_SOURCE_TREE=6497ce2b53be973eaee709092296545765d480a5

OTHER_REQUIRED_AUTHORITY=
  docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R4_CLOSURE_20261106.md;
  docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R4_DESIGN_20261106.md;
  docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.0_20261106.md;
  docs/development/N3W_T1_CORE_STACK_OTA_BASELINE_AND_REPOSITORY_CONVERGENCE_SOURCE_ALIGNMENT_20261106.md;
  infra/n3w-t1/production/t1-core-stack-current.json

CURRENT_PRODUCTION_AUTHORITY=infra/n3w-t1/production/t1-core-stack-current.json@blob:07ceb3b352f21d925127caa71304cc3b29827fdb
CURRENT_STACK_RELEASE=T1_Core_Stack_1.0.0
STACK_RELEASE_ROLE=BOOTSTRAP_ACCEPTED_PRE_OTA_RELEASE
COMPONENT_UPGRADE_BASELINE=R5_MUST_FRESH_READ_REAL_T1_BEFORE_ANY_LATER_MUTATION
```

Repository convergence:

```text
PR788_STATE=CLOSED_UNMERGED_HISTORICAL_BRANCH
PR798_STATE=MERGED_CLEAN_SUCCESSOR
PR798_HEAD=559686ffe4b0eb55da2ba5d446b5ce9b4dab9c20
PR798_MERGE_COMMIT=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
PR798_VISIBLE_EXACT_HEAD_WORKFLOW_RUNS=24_SUCCESS_0_FAILURE
R4_HISTORICAL_EXECUTABLE_HEAD=506136a8f1fc42bb8788f8a3c0fae9220d689af4
R4_HISTORICAL_FINAL_DOCS_HEAD=5ad015c23b0522640c48a84b4da7e00507ee757b
R4_IMPLEMENTATION_BLOB_PARITY=PASS
R4_ARCHIVE_DOC_BLOB_PARITY=PASS
```

Some old/integration branches still physically exist. Their existence is not authority. New work must fresh-rebind `main`.

---

## 4. Current Live Baseline

No real T1 was freshly read during this handoff preparation. Repository authority records the last accepted live stack, but R5 exists specifically to refresh that evidence.

```text
MANAGER_STATE=UNKNOWN_FRESH
MANAGER_STATE_REQUIRES_FRESH_READONLY_RECHECK=true
MANAGER_RESTART_STATE=UNKNOWN_FRESH
MANAGER_RESTART_STATE_REQUIRES_FRESH_READONLY_RECHECK=true

BROKER_STATE=UNKNOWN_FRESH
BROKER_STATE_REQUIRES_FRESH_READONLY_RECHECK=true

HOMEASSISTANT_STATE=UNKNOWN_FRESH
HOMEASSISTANT_STATE_REQUIRES_FRESH_READONLY_RECHECK=true

BOARD_A_POWER_STATE=NOT_APPLICABLE:R5_T1_ONLY_BOARD_ACCESS_FORBIDDEN
BOARD_A_LOCATION_ROLE=NOT_APPLICABLE:R5_T1_ONLY_BOARD_ACCESS_FORBIDDEN
BOARD_B_POWER_STATE=NOT_APPLICABLE:R5_T1_ONLY_BOARD_ACCESS_FORBIDDEN
BOARD_B_LOCATION_ROLE=NOT_APPLICABLE:R5_T1_ONLY_BOARD_ACCESS_FORBIDDEN

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

Last repository-recorded accepted live authority, not a substitute for R5 fresh evidence:

```text
REPOSITORY_RECORDED_LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
REPOSITORY_RECORDED_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
REPOSITORY_RECORDED_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
REPOSITORY_RECORDED_BROKER=local/n3w-mosquitto:2.1.2-3184566d
REPOSITORY_RECORDED_MANAGER_RUNTIME_CLASS=TARGET_BOUND_RUNNING
REPOSITORY_RECORDED_HEALTH_STATE=HEALTHY
REPOSITORY_RECORDED_RECOVERY_REQUIRED=false
```

---

## 5. Proven Current Facts

```text
R4_SOURCE_RESULT=CLOSED_PASS
R4_MANAGER_BASELINE_NON_DRIFT=PASS
R4_MANAGER_A_TO_B_REGRESSION=PASS
R4_HA_TARGET_BINDING=PASS
R4_PRIVILEGE_BOUNDARY=PASS

R4_MANAGER_TO_HOST_TRANSPORT=AF_UNIX_SOCK_STREAM
R4_SO_PEERCRED_UID_CHECK=true
R4_HOST_INDEPENDENT_ADMISSION_RESOLUTION=true
R4_PREPARE_IPC_MAX_PHASE=U1_PREPARE_REQUESTED
R4_INSTALL_REQUIRES_U4_READY_TO_INSTALL=true
R4_INSTALL_IPC_MAX_PHASE=U5_INSTALL_REQUESTED_REVALIDATING

GREENHOUSE_MANAGER_DOCKER_SOCKET_ACCESS=false
GREENHOUSE_MANAGER_BLOCK_DEVICE_ACCESS=false
GREENHOUSE_MANAGER_ROOT_PRIVILEGE=false
SECOND_MANAGER_MQTT_CLIENT=false
FOURTH_DOCKER_SERVICE=false

PRODUCTION_COMPOSE_CHANGED_BY_R4=false
CURRENT_AUTHORITY_MANIFEST_CHANGED_BY_R4=false
LIVE_T1_MUTATION_BY_R4=false

R4_SUCCESSOR_CONVERGED_TO_MAIN=true
R4_CLEAN_SUCCESSOR_PR=798
PR788_DIRECT_MERGE_AUTHORITY=false
```

```text
INFERENCE_R5_PRIMARY_PURPOSE=
REFRESH_REAL_T1_BASELINE_AND_PROVE_HOST_IS_SAFE_FOR_A_LATER_SEPARATELY_AUTHORIZED_ACTIVATION_GATE
```

This inference does not authorize activation or mutation.

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
CURRENT_BLOCKER=NONE
ROOT_CAUSE=NOT_APPLICABLE
PROVEN_BY=R4_CLOSURE_PLUS_PR798_CLEAN_SUCCESSOR_CI
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false

FRESH_REAL_T1_STATE_REQUIRED=true
FRESH_REAL_T1_STATE_IS_GATE_PURPOSE_NOT_BLOCKER=true
```

---

## 7. Closed / Forbidden Routes

```text
OLD_P5_IMAGE_ONLY_INTERNAL_DUAL_RESIDENCY=CLOSED:RETIRED_FOR_PRODUCT_EXECUTION
OLD_P5_LIVE_APPLY_AUTHORIZATION=CLOSED:SUPERSEDED_UNCLAIMED_AND_NOT_VALID_FOR_MANDATORY_USB_SUCCESSOR
PR788_OLD_BRANCH_AS_EXECUTION_AUTHORITY=CLOSED:PR798_CLEAN_SUCCESSOR_IS_CANONICAL
INTERRUPTED_PR788_CONVERGENCE_BRANCHES=CLOSED:FORENSIC_ONLY_NOT_MERGE_OR_EXECUTION_AUTHORITY
R4_REENTRY=CLOSED:R4_ALREADY_CLOSED_PASS_AND_CONVERGED_TO_MAIN
```

Do not restore stale historical ancestry merely to make historical package tests pass. Successor source must reject stale ancestry/source drift fail-closed.

---

## 8. Authorization Ledger

The current user instruction explicitly directs the new conversation to start from R5 real-T1 read-only preflight.

```text
AUTHORIZATION=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01
CLAIMED=false
CONSUMED=false
RESULT=GRANTED_FOR_R5_READONLY_ENTRY_ONLY
REPLAY_PERMITTED=NOT_APPLICABLE:READONLY_GATE
SUPERSEDED_BY=NONE

R5_T1_ACCESS=true
R5_T1_MUTATION=false
R5_USB_FORMAT=false
R5_SERVICE_STOP=false
R5_DOCKER_MUTATION=false
R5_BOARD_ACCESS=false
R5_MERGE=false
```

Historical mutation authorization:

```text
LEGACY_P5_AUTHORIZATION_DISPOSITION=SUPERSEDED_UNCLAIMED
LEGACY_P5_AUTHORIZATION_MAY_AUTHORIZE_R5_OR_LATER_MUTATION=false
```

No mutation authorization is implied by this handoff.

---

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
```

If any command would require rollback, it is outside R5 and must not be run.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01
```

### Purpose

R5 must freshly classify the real T1 without changing it.

It must prove enough of the following to decide whether a later activation/mutation gate can be safely designed and authorized:

- current Manager / Broker / Home Assistant live identities still match accepted production authority;
- current services and updater transaction state are terminal/healthy enough for preflight;
- there is no unexpected recovery-required or stale active upgrade state;
- the host-side prerequisites relevant to the R4 Unix-socket / mandatory-USB design can be inspected safely;
- removable-media state, if inspected, is inventory only and not write authority.

R5 cannot prove successful USB formatting, package download, backup, HA stop, image cutover or rollback because all of those are forbidden in this gate.

### Inputs

```text
INPUT_1=canonical main fresh rebind
INPUT_2=infra/n3w-t1/production/t1-core-stack-current.json
INPUT_3=R4 design + R4 closure
INPUT_4=R4 clean successor / PR798 convergence evidence
INPUT_5=operator-local real T1 SSH locator supplied outside public GitHub
```

### Operations

```text
1. Fresh-rebind repository main and verify R4 clean-successor authority has not drifted.
2. Establish read-only SSH access to the real T1 using the project's trusted transport/host-key rules.
3. Read current Manager, Broker and Home Assistant image/container/service state and compare with current production authority.
4. Read updater/transaction/recovery state; reject unknown active or recovery-required state.
5. Read only the host/runtime facts needed to classify future R4 IPC activation readiness, including current Manager UID/runtime contract and whether OTA runtime paths/config are absent or already present.
6. Inventory block/removable-media state only if useful for the preflight; do not mount, label, partition, format or write.
7. Produce public-safe R5 evidence with private locators/credentials excluded.
8. STOP after classification. Do not enter the next mutation/activation gate automatically.
```

### PASS / FAIL / STOP

```text
PASS_IF=
  repository authority is fresh and coherent;
  real T1 current stack identity is compatible with accepted authority;
  no unexpected active/recovery-required updater state exists;
  read-only host prerequisites needed for the later mandatory-USB route are classifiable;
  all R5 commands remain read-only

FAIL_IF=
  current stack identity materially drifts from accepted authority;
  recovery_required or unknown nonterminal transaction is observed;
  required host facts contradict the frozen R4 privilege/topology assumptions;
  any required evidence cannot be obtained without mutation

STOP_BOUNDARY=
  after R5 read-only evidence/classification;
  before creating/changing OTA runtime directories or mounts;
  before production compose/env/systemd changes;
  before USB mount/partition/label/format/write;
  before Docker image mutation;
  before Home Assistant stop or data backup;
  before any live INSTALL/apply/rollback

AUTO_EXECUTE_NEXT_GATE=false
```

If access, host-key trust, or required operator-local information is missing, STOP and request only that missing input. Do not broaden scope.

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- fresh GitHub/main/authority reads
- real T1 SSH connection for read-only inspection
- systemctl/docker/ps/inspect-style read-only queries
- updater status/inspect-style read-only queries where source contract guarantees no mutation
- read-only filesystem metadata/stat/listing
- read-only block-device inventory such as lsblk/blkid-style queries
- public-safe evidence capture outside the T1 when no T1 state is changed
```

### FORBIDDEN

```text
- USB partition, label, mkfs, mount-write, wipefs or any block write
- mkdir/chown/chmod/install/copy/write on the T1 solely to prepare OTA
- production compose/env changes
- systemd unit installation or service stop/restart/start
- docker pull/load/tag/rm/prune or image/container mutation
- Home Assistant stop, backup, restore or /config mutation
- creation/claim of a live install authorization
- updater apply or rollback
- board access or board mutation
- merge or automatic entry to the next gate
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
BOUNDED_WRITE_SCOPE=NOT_APPLICABLE:R5_READONLY
```

---

## 12. Execution Contract

```text
EXECUTOR=assistant-guided operator Mac Terminal for real-T1 reads + GitHub tools for repository reads
EXECUTION_METHOD=mac-terminal
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

R5 is not a source-development gate by default. If fresh evidence proves a source defect, STOP the live preflight before mutation and classify the required source gate separately. Local, unambiguous documentation/test-only repair may continue only if it does not expand R5 or touch live T1 state.

---

## 13. Expected Closure

```text
=== N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01 CLOSURE ===

EXECUTION_ID=<fresh R5 execution id>
AUTHORIZATION=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=NOT_APPLICABLE:READONLY_GATE

REPOSITORY_MAIN=<fresh>
CURRENT_AUTHORITY_BLOB=<fresh>
REAL_T1_STACK_IDENTITY=<PASS|FAIL|UNKNOWN>
MANAGER_STATE=<fresh>
BROKER_STATE=<fresh>
HOMEASSISTANT_STATE=<fresh>
UPDATER_TRANSACTION_STATE=<fresh>
RECOVERY_REQUIRED=<fresh>
R4_IPC_HOST_PREREQUISITE_CLASSIFICATION=<PASS|FAIL|STOP>
USB_INVENTORY_CLASSIFICATION=<PRESENT_READONLY|ABSENT|NOT_REQUIRED_FOR_THIS_PREFLIGHT>

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

R5_RESULT=<PASS|FAIL|STOP>
NEXT_ROUTE=<freeze after review>
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=NOT_YET_FROZEN:R5_CLOSURE_MUST_DEFINE_THE_NEXT_BOUNDED_GATE
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

No destructive successor gate may be inferred from R5 PASS.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF-142_IF_PROJECT_SSH_TRANSPORT_IS_REUSED
NEW_KF_REQUIRED=false
```

If R5 proves a new failure with a new root cause, then create a new KF only after the root cause is established. If root cause is unknown, record `TBD`.

---

## 16. New Chat Start Prompt

默认读取集：

```text
1. 本 handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R4_CLOSURE_20261106.md
7. docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.0_20261106.md
```

建议启动文本：

```text
阅读《docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R4_CONVERGED_TO_R5_REAL_T1_READONLY_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261107.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R4_CLOSURE_20261106.md
- docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.0_20261106.md

fresh rebind repository main、PR #798 convergence result 和 current production authority。
继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

当前用户已授权进入 R5 的真实 T1 只读预检，但没有授权任何 mutation。

只进入：

NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01

R5_SCOPE=REAL_T1_READONLY_PREFLIGHT
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
USB_FORMAT=false
SERVICE_STOP=false
DOCKER_MUTATION=false

先做当前 gate 所需的最小 fresh 只读确认。
不要重放 consumed/superseded authorization，不要重新进入 closed routes，不要自动跨越下一阶段。
```

任何 SSH 地址、私网地址、密码、设备原始身份等 operator-local 值留在新会话/本地，不写入公开 GitHub。

---

## 17. Final Frozen State

```text
CURRENT_STAGE=R4_CLOSED_PASS_AND_PR798_CLEAN_SUCCESSOR_MERGED_TO_MAIN
CURRENT_STOP_POINT=BEFORE_R5_REAL_T1_READONLY_PREFLIGHT
CURRENT_BLOCKER=NONE
LIVE_SYSTEM_STATE=UNKNOWN_FRESH_REQUIRES_R5_READONLY_RECHECK
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.9
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

Canonical convergence is complete at the source/history level. Physical branch deletion is not required for authority; remaining historical/integration branches must not be treated as current execution authority.

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.9

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
