## Latest authority — 2026-11-03 KF-137 repaired updater exact package ready; A -> B apply authorized

~~~text
AUTHORITY_STATE=KF137_REPAIRED_EXACT_UPDATER_APPLY_AUTHORIZED

MAIN_AT_REPAIR_MERGE=2e3f1c72e5ac17a9c8a1ecb378148a0d6d2d8c29
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2

LAST_TRANSACTION_STATUS=ROLLED_BACK
LAST_TRANSACTION_PHASE=ROLLBACK_COMPLETE
LAST_RECOVERY_REQUIRED=false

KF137=SOURCE_REPAIR_CLOSED_PASS
UPDATER_PACKAGE_ARTIFACT_ID=13196564439
UPDATER_PYZ_SHA256=6222ab4bdcb53e0b612777a585111f5ab2ab114a1c52a4997252937ef27033cc

APPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_KF137_REPAIRED_20261103_01
APPLY_AUTHORIZATION_GRANTED=true
APPLY_AUTHORIZATION_CONSUMED=false
OLD_AUTHORIZATION_REPLAY_PERMITTED=false

BOARD_ACCESS_DEFAULT=false
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_KF137_REPAIRED_EXECUTION_20261103_01
~~~

The repaired updater is the current execution authority. One new A -> B apply is explicitly authorized. Execution must run a fresh exact precheck first, use the repaired package only, issue at most one apply, and capture post-status/post-inspect. Any failure stops without a second apply or blind explicit rollback.

## Latest authority — 2026-11-03 Manager A -> B fresh preauthorization CLOSED_PASS

~~~text
AUTHORITY_STATE=POST_RECONCILIATION_A_TO_B_PREAUTH_PASS_AWAITING_EXPLICIT_APPLY_AUTHORIZATION

MAIN=92e7dfaa5e508fae1bb6477b9cdb23712a33588c
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2

TRANSACTION_STATUS=ROLLED_BACK
TRANSACTION_PHASE=RECOVERY_COMPLETE_FAILED_EMERGENCY
RECOVERY_REQUIRED=false

FRESH_STATUS=PASS
FRESH_INSPECT=PASS
FRESH_PLAN=PASS
MANAGER_TAR_VERIFIED=true
TARGET_IMAGE_PRESTATE=PRESENT_AND_EXACT
ROLLBACK_AVAILABLE=true

OLD_R1_R2_AUTHORIZATION_REPLAY_PERMITTED=false
NEW_A_TO_B_APPLY_AUTHORIZED=false
BOARD_ACCESS_DEFAULT=false

PROPOSED_APPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_POST_RECONCILIATION_20261103_01
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_POST_RECONCILIATION_AUTHORIZATION_20261103_01
~~~

The post-reconciliation real-T1 read-only preauthorization is CLOSED_PASS. Manager A is still exact and healthy, Manager B is present and exact, the exact Manager tar is verified, and rollback is available. The next boundary is a new one-shot Manager A -> B apply authorization; no prior consumed authorization may be replayed, and no apply occurs until the user explicitly grants the new authorization.

## Latest authority — 2026-11-03 R2 reconciliation CLOSED_PASS; Manager A -> B fresh preauthorization next

~~~text
AUTHORITY_STATE=POST_RECONCILIATION_PREDECESSOR_A_HEALTHY_A_TO_B_PREAUTHORIZATION

MAIN=5aa000055b3ee48c424ceac4ef6437fb3f98c742
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2

R2_TRANSACTION_STATUS=ROLLED_BACK
R2_TRANSACTION_PHASE=RECOVERY_COMPLETE_FAILED_EMERGENCY
R2_RECOVERY_REQUIRED=false
R2_RECONCILIATION=CLOSED_PASS
R2_RECONCILIATION_T1_MUTATION=false

UPDATER_V2_PACKAGE_ARTIFACT_ID=13187736541
UPDATER_V2_ARTIFACT_EXPIRED=false

OLD_R1_R2_AUTHORIZATION_REPLAY_PERMITTED=false
NEW_A_TO_B_APPLY_AUTHORIZED=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_POST_RECONCILIATION_MANAGER_A_TO_B_READONLY_PREAUTH_20261103_01
~~~

The stale R2 transaction is terminal and no longer blocks a new Manager transaction. The next gate is fresh read-only `status / inspect / plan --manager-tar` against the exact V2 package. A new Manager A -> B apply remains forbidden until that gate closes PASS and the user separately grants a new V2-compatible authorization ID.

## Latest authority — 2026-11-03 real-T1 V2 read-only reconciliation preflight PASS

~~~text
AUTHORITY_STATE=PREDECESSOR_A_HEALTHY_STALE_R2_TRANSACTION_AWAITING_RECOVERY_AUTH

MAIN=41e3031d1fa097043374c7582e552f5a803a1f20
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_RUNTIME_CLASS=PREDECESSOR_HEALTHY

R2_TRANSACTION_STATUS=FAILED_EMERGENCY
R2_TRANSACTION_PHASE=ROLLBACK_FAILED
R2_RECOVERY_REQUIRED=true

V2_PACKAGE_BINDING=PASS
V2_STATUS=PASS
V2_INSPECT=PASS
HA_CONTINUITY=PASS
BROKER_CONTINUITY=PASS
LISTENER_CONTRACT=PASS
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
BROKER_RESTART_COUNT=0

R2_TRANSACTION_RECONCILIATION_AUTHORIZED=false
APPLY_RETRY=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_R2_TRANSACTION_RECONCILIATION_AUTHORIZATION_20261103_01
~~~

The next live action is a transaction-only V2 reconciliation under a separate explicit authorization. Because the runtime is already PREDECESSOR_HEALTHY, the expected V2 behavior is to update only the durable updater transaction to terminal ROLLED_BACK and return `t1_mutation=false`. A new A->B apply remains forbidden until that closure and a post-reconciliation baseline pass.

## Latest authority — 2026-11-03 Updater V2 merged and exact package bound; R2 transaction reconciliation next

~~~text
AUTHORITY_STATE=UPDATER_V2_READY_R2_TRANSACTION_RECONCILIATION_NEXT

MAIN=24fbc6cdf9b05796487459ad7cae038c0bdc7d5a
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

UPDATER_V2_REVIEWED_HEAD=43de966c70d527433a915f40b9b630227531580a
UPDATER_V2_MERGE_COMMIT=24fbc6cdf9b05796487459ad7cae038c0bdc7d5a
UPDATER_V2_PACKAGE_RUN=41544508199
UPDATER_V2_PACKAGE_ARTIFACT_ID=13187736541
UPDATER_V2_PACKAGE_DIGEST=sha256:e09fb86c8444e0510b0200e759551d3571496064c743b4171992d46ab73babb9
UPDATER_V2_PYZ_SHA256=e92c093c7028d57ddc1e2c9c1eeb3fb97a0791a27b262b472c75482eaa3026bf
MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0
MANAGER_REBUILT=false

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_RUNTIME_HEALTHY=true

R2_TRANSACTION_STATUS=FAILED_EMERGENCY
R2_TRANSACTION_PHASE=ROLLBACK_FAILED
R2_AUTHORIZATION_REPLAY_PERMITTED=false

KF135=SOURCE_V2_CLOSED_LIVE_ACCEPTANCE_PENDING
KF136=SOURCE_V2_CLOSED_LIVE_RECONCILIATION_PENDING

LIVE_T1_MUTATION=false
R2_TRANSACTION_RECONCILIATION_AUTHORIZED=false
APPLY_RETRY=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_R2_TRANSACTION_RECONCILIATION_READONLY_PREFLIGHT_20261103_01
~~~

The next T1 action is not another A->B apply. First use the V2 package for a fresh read-only preflight against the healthy predecessor-A runtime and the stuck R2 transaction. Any transaction mutation requires a separate explicit recovery authorization. Only after reconciliation to terminal ROLLED_BACK and another fresh PREDECESSOR_HEALTHY check may a new A->B authorization be considered.

## Latest authority — 2026-11-03 R2 incident contained; Updater V2 convergence before any further live apply

~~~text
AUTHORITY_STATE=R2_FAILED_RUNTIME_RECOVERED_UPDATER_V2_SOURCE_REPAIR

MAIN=ae67dc9da98b16c8bb6a23bc45afa2c5adbc4aee
SOLE_DEVELOPMENT_PR=754
INCIDENT_PR_753=CLOSED_SUPERSEDED

LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_RUNTIME_HEALTHY=true
R2_TRANSACTION_STATUS=FAILED_EMERGENCY
R2_TRANSACTION_PHASE=ROLLBACK_FAILED
R2_AUTHORIZATION_REPLAY_PERMITTED=false

KF135=OPEN_SOURCE_REPAIR
KF136=OPEN_SOURCE_REPAIR
UPDATER_V2_ARCHITECTURE_FROZEN=true
FAULT_MATRIX_REQUIRED=true

LIVE_T1_MUTATION=false
IMMEDIATE_LIVE_RETRY=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_SOURCE_REPAIR_CI_AND_EXACT_HEAD_REVIEW_20261103_01
~~~

The project must not treat CI green alone as permission to retry live A→B. Complete V2 architecture review, fault-matrix evidence and exact-head source review first. Only then build a new exact updater artifact, reconcile the stuck transaction under a separate recovery authorization, and later request a fresh apply authorization.

## Latest authority — 2026-11-02 portable-identity live revalidation PASS; R2 apply authorization boundary

~~~text
AUTHORITY_GATE=N3W_T1_CORE_UPDATER_PORTABLE_IMAGE_IDENTITY_LIVE_READONLY_REVALIDATION_CLOSURE_20261102_01
AUTHORITY_STATE=LIVE_READONLY_PASS_MANAGER_A_STILL_ACTIVE

MAIN=9a606e579e3431d2e37e1f4378dab80b10f794f8
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_IMAGE_PRESTATE=PRESENT_AND_EXACT
MANAGER_TAR_VERIFIED=true
PORTABLE_IDENTITY_REVALIDATION=PASS
KF106_LIVE_REVALIDATION=CLOSED_PASS

R1_AUTHORIZATION_REPLAY_PERMITTED=false
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_APPLY_R2_20261102_01
NEW_AUTHORIZATION_REQUIRED=true
BOARD_ACCESS_DEFAULT=false
~~~

Do not replay the R1 authorization. The next mutation boundary is a new Manager A->B R2 live apply using the replacement updater package. Until the user explicitly authorizes that gate, keep T1 mutation disabled and do not resume Board/R3 work.

## Latest authority — 2026-11-02 replacement updater merged; read-only portable-identity T1 revalidation next

~~~text
AUTHORITY_GATE=N3W_T1_CORE_UPDATER_REPLACEMENT_PACKAGE_AUTHORITY_ALIGNMENT_20261102_01
AUTHORITY_STATE=REPLACEMENT_UPDATER_READY_NOT_LIVE_APPLIED

MAIN=c80bd9f1374ca33926cc76acbc2f2e2da1ebb67b
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d

UPDATER_REVIEWED_HEAD=667299b6053822ce56c2b27adb8c3c61cca12542
UPDATER_PACKAGE_RUN=41465742145
UPDATER_PACKAGE_ARTIFACT_ID=13151876743
UPDATER_PACKAGE_DIGEST=sha256:42d8580c0e8e2f04363a49e4166ef4b8de0729fa4f25c05703594a2b9ad04b1c
UPDATER_PYZ_SHA256=69227fdb2d4778f53513ace1d9065848d7e2ad771c8291f52f0375a99a65c592

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LAST_FRESH_LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LAST_LIVE_APPLY=ROLLED_BACK_PRESTOP
OLD_LIVE_AUTHORIZATION_REPLAY_PERMITTED=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_PORTABLE_IMAGE_IDENTITY_LIVE_READONLY_REVALIDATION_20261102_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
~~~

Use the replacement updater package for the next live read-only gate. The old updater package is historical and must not be used for a successor apply. Any new live apply requires a fresh read-only PASS and a new authorization.

## Latest authority — 2026-11-02 post-merge main convergence; Manager A->B live preflight next

The stacked successor-authority chain has fully converged into protected `main`. Repository authority B and the reviewed T1_Core_Updater are now in main, but this does not prove the current live T1 runtime. The last recorded live Manager A state is historical until a fresh read-only `inspect / plan` rebind is executed.

~~~text
AUTHORITY_GATE=N3W_T1_CORE_STACK_POSTMERGE_MAIN_STATE_ALIGNMENT_20261102_01
AUTHORITY_STATE=MAIN_CONVERGED_LIVE_RUNTIME_REBIND_PENDING

MAIN=092c9fca70df4212110b4ad07eb8fba9e8c9ef9e
STACKED_PR_CONVERGENCE=COMPLETE
MAIN_TREE_DRIFT_FROM_FINAL_PR696_HEAD=false

CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d

LAST_RECORDED_LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_T1_MANAGER=UNKNOWN_FRESH
LIVE_A_TO_B_APPLIED=UNKNOWN_FRESH

R3_BOARD_CONTINUATION_DEFERRED_UNTIL_MANAGER_B_LIVE_ACCEPTANCE=true
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_READONLY_INSPECT_AND_PLAN_20261102_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
~~~

The next operational gate is read-only. It must freshly prove the current T1 runtime, predecessor authority, target-image prestate, updater transaction state, and Manager-only plan before any live A->B apply decision. Board identity/registration work remains paused until the Manager B live path is accepted.

## Latest authority — 2026-11-02 R3 sensorless real first-registration route

The current R3 product route is no longer gated by the pairing-readiness bridge. R3 is frozen to one real sensorless ESP32-C6 first registration against the already-running zero-node production T1, followed by semantic PRE/POST comparison.

~~~text
AUTHORITY_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_SENSORLESS_REAL_FIRST_REGISTRATION_20261102_01
AUTHORITY_STATE=FROZEN_PREEXECUTION
SOURCE_HEAD=ea1488845ba05d362454678f2801232010852ecf

NODE_PROFILE=ESP32_C6_PLUS_LCD_PLUS_USB
SENSORS_CONNECTED=false
NORMAL_PRODUCT_REGISTRATION_PATH=true
POST_CAPTURE_RULE=MANAGER_DURABLE_COMMIT_THEN_IMMEDIATE_NODE_POWER_OFF_THEN_T1_POST

READINESS_BRIDGE_ENTRY_GATE=false
READINESS_BRIDGE_DISPOSITION=HISTORICAL_DIAGNOSTIC_ONLY

KNOWN_GOOD_FIRMWARE_ARTIFACT_ID=13115966258
KNOWN_GOOD_FIRMWARE_ARTIFACT_DIGEST=sha256:0da0eefafc4b108e4dc76864942fb5946419eac10f79a71e5db7e6db8427c715

CURRENT_STOP_POINT=BOARD_USB_ENUMERATED_BEFORE_ESPTOOL_IDENTITY_READ
FLASH_MUTATION=false
NVS_MUTATION=false
FIRST_REGISTRATION_STARTED=false

NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_BOARD_USB_READONLY_IDENTITY_BINDING_20261102_01
~~~

The user explicitly paused before `chip-id` / `flash-id` and requested a new-chat handoff. Do not reuse the earlier continuation as Board authorization. Fresh rebind first, then wait for the user's continuation before local Board commands. Exact local USB locators and raw Board identities stay out of public GitHub.

# N3W_PROJECT_WORKING_CONTEXT

> Status: durable public project working context  
> Version: `N3W_PROJECT_WORKING_CONTEXT_VERSION=1.4`  
> Scope: N3-W development for the greenhouse monitoring system  
> Repository: `chrenguo-stack/HomeAssistant`

## 0. Purpose

This file is the durable **public long-term working context** for N3-W development.

It exists to keep stable project conventions out of individual chat handoffs. A new-chat handoff should describe only the current stage, current evidence, current authorization state, and the next bounded step. It should not repeatedly copy the same development habits, communication rules, GitHub workflow, evidence rules, or public/private boundaries.

```text
PUBLIC_LONG_TERM_CONTEXT=this file
CURRENT_DYNAMIC_STATE=docs/development/N3W_CURRENT_STATE.md
CURRENT_STATE_INDEX=docs/development/N3W_CURRENT_STATE_INDEX.md
KNOWN_FAILURE_GUARDS=docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
STAGE_DELTA=current formal handoff
PRIVATE_RUNTIME_CONTEXT=USER_MANAGED_OUTSIDE_PUBLIC_GIT
```

This file does **not** contain live passwords, private host locators, private network addresses, raw board identities, credentials, setup secrets, private keys, or other sensitive material.

---

## 1. Authority and freshness

Use the authority closest to the thing being proven.

When information conflicts, prefer:

```text
1. fresh exact repository / runtime / physical evidence
2. current N3W_CURRENT_STATE.md and N3W_CURRENT_STATE_INDEX.md
3. current stage-specific formal handoff
4. this long-term working context for stable conventions
5. historical handoffs and historical progress documents
6. conversation inference
```

A historical fact is not automatically a current fact.

Before claiming a live service, board, branch, pull request, artifact, or physical route is current, perform the smallest necessary fresh read-only check.

```text
FRESH_READONLY_REBIND_BEFORE_LIVE_CLAIM=true
HISTORICAL_STATE_IS_NOT_CURRENT_STATE=true
INFERENCE_IS_NOT_PROVEN_FACT=true
```

If a handoff names an exact historical handoff-standard authority, read that exact commit for its standard/process rules. Do not assume current `main` contains the same historical standard file.

Formal handoff template authority is separate from historical standard authority:

```text
SOLE_VALID_HANDOFF_TEMPLATE=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
HISTORICAL_TEMPLATE_COPIES=HISTORICAL_EVIDENCE_ONLY
HISTORICAL_STANDARD_MAY_NOT_REACTIVATE_OLD_TEMPLATE=true
```

A historical commit may remain authoritative for a process standard while its bundled historical handoff template is obsolete. New formal handoffs must use the current V1.3 template unless the repository later explicitly promotes a newer template.

---

## 2. Primary execution principle

The governing rule is:

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
TEST_PRODUCT_NOT_TEST_FRAMEWORK=true
```

Practical meaning:

- choose the simplest method that gives reliable evidence;
- use read-only inspection before mutation whenever possible;
- do not add an executor, framework, manifest layer, branch, or CI job unless it solves a real engineering need;
- do not turn acceptance tooling into a second product architecture;
- stop at the first substantive mismatch unless the current contract explicitly allows continuation;
- after a failure, classify what actually failed before designing a repair;
- do not automatically cross into the next physical or mutation gate.

---

## 3. Communication style

User-facing replies should be concrete and easy to follow.

```text
COMMUNICATION_STYLE=PLAIN_DIRECT_CONCRETE
ABSTRACT_TERM_DENSITY=LOW
EXPLAIN_WHAT_HAPPENED=true
EXPLAIN_WHY=true
EXPLAIN_NEXT_ACTION=true
```

Default order:

1. what is happening now;
2. why it matters;
3. what to do next;
4. exact fields, hashes, commands, or error codes only where they are useful.

Prefer ordinary Chinese over repeated abstract labels such as `authority`, `gate`, `rebind`, `contract`, and `closure`. When an exact project term is necessary, keep the term but explain its concrete meaning.

Commands and exact identifiers must remain precise even when the surrounding explanation is simplified.

---

## 4. GitHub working method

GitHub is the durable shared engineering workspace.

```text
TEAM_SHARED_WORKSPACE=GITHUB
CHAT_SESSIONS_ARE_EPHEMERAL=true
DURABLE_ENGINEERING_ARTIFACTS_GO_TO_GITHUB=true
```

Source, tests, reusable tools, important design decisions, current-state records, known-failure guards, formal handoffs, and reproducibility information should be committed when they have continuing engineering value.

Secrets and private runtime locators are excluded from this rule.

### 4.1 Use short, phased GitHub operations

Long GitHub operations are deliberately split into small stages so that a timeout, truncation, or tool failure does not force a large operation to be repeated.

```text
GITHUB_OPERATION_MODE=PHASED_SHORT_CALLS
LARGE_MONOLITHIC_GITHUB_CALLS=AVOID
VERIFY_AFTER_REPOSITORY_WRITE=true
BLIND_REPLAY_AFTER_TOOL_FAILURE=false
```

Preferred sequence:

```text
A. fresh read-only repository / PR / branch rebind
B. inspect the small set of relevant files
C. decide the exact change
D. write a small bounded file set
E. re-fetch / compare and verify the resulting commit
F. check CI separately
G. merge only after the required review/decision
```

Do not combine unrelated repository reads, large searches, multiple sequential writes to the same file, CI polling, and merge into one long operation.

If a repository operation is interrupted, resume from the last **proven Git commit or remote state**. Do not assume an unconfirmed mutation succeeded and do not blindly repeat it.

### 4.2 Branch and pull-request defaults

For active engineering changes:

- use a purpose-specific branch;
- use a Draft PR while review or physical validation is incomplete;
- preserve exact head SHA for reviews and artifacts;
- do not merge merely because CI is green;
- treat merge as a separate decision when the current stage requires user approval;
- keep documentation-only alignment distinct from product-source authority.

Historical frozen branches or artifacts are evidence, not automatically deployment candidates.

---



### 4.3 CI observation and same-gate continuation — hard execution rules

These rules are mandatory for routine GitHub CI handling and are not optional chat
preferences.

```text
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
CI_FAILURE_READ_JOB_AND_LOG=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
CROSS_GATE_AUTO_EXECUTE=false
```

Execution rules:

1. Poll the same CI head at most three times in one reply. If work is still pending,
   stop polling and give direct links for every unfinished workflow/run that matters.
2. If all required CI for the current exact head is complete and green, immediately
   continue the review/closure step already required by the current gate. Do not stop
   merely to ask the user to say “continue” or “start review” again.
3. If CI fails, inspect the failed job/step/log before reporting the result. When the
   cause is a small, clearly identified source/test/style defect inside the already
   authorized gate, repair it directly, trigger fresh CI, and continue the same gate.
4. The same rule applies when focused review finds a small, bounded, low-risk defect
   inside the current source-only gate: repair it directly rather than manufacturing a
   second approval step.
5. Stop and request a new decision only when the action would expand scope, cross into
   a new gate, perform live/T1/board/service/credential mutation, consume a new
   authorization, merge, or change an already frozen product/design decision.
6. Green CI is never by itself a closure result. Required focused/source review still
   runs before closure.

When a workflow remains unfinished, a run ID without a clickable/direct URL is
insufficient.

### 4.4 Stacked PR convergence

Nested pull requests converge from the innermost PR outward, exactly one layer at a time. A merge into the next PR creates a new target head; upstream CI is historical evidence only and cannot satisfy the fresh-CI gate for that target head.

```text
STACKED_PR_CONVERGENCE=INNER_TO_OUTER_ONE_LAYER_AT_A_TIME
TARGET_PR_NEW_HEAD_IS_NEW_CI_AUTHORITY=true
UPSTREAM_PR_CI_NOT_REUSABLE_FOR_TARGET_NEW_HEAD=true
TARGET_DRAFT_TO_READY_AFTER_INNER_MERGE=true
CI_POLL_MAX_PER_EXACT_HEAD=3
NEXT_LAYER_MERGE_REQUIRES_FRESH_REVIEW_OR_DECISION=true
FINAL_MAIN_MERGE_IS_SEPARATE_DECISION=true
```

## 5. Development environment convention

The Mac development environment is versioned and audited separately from handoffs.

Current environment authority is referenced by:

```text
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/local-environment-records/
```

Do not copy volatile package versions, disk state, worktree state, or local paths into every handoff. Read the current environment record when the task actually depends on them.

Stable environment rules:

- host-side Python development uses the project virtual environment;
- ESPHome remains isolated from the host project Python environment when dependency requirements conflict;
- do not casually install or upgrade packages in a working environment to make one command pass;
- rerun the versioned local-environment doctor after meaningful host/toolchain changes;
- local environment warnings are not product failures unless evidence shows they affect the product result;
- prefer existing installed tools; do not install tooling on T1 or another target merely for convenience unless explicitly approved.

```text
LOCAL_ENVIRONMENT_CHANGE_REQUIRES_RECHECK=true
DEPENDENCY_ISOLATION_PRESERVED=true
TARGET_HOST_TOOL_INSTALL_DEFAULT=false
```

---

## 6. Default physical roles

Unless a stage-specific handoff explicitly overrides the roles:

```text
BOARD_A_DEFAULT_ROLE=STATIONARY_RELAY_GATEWAY
BOARD_B_DEFAULT_ROLE=PRIMARY_DEVICE_UNDER_TEST
T1_DEFAULT_ROLE=MANAGER_BROKER_HOMEASSISTANT_HOST
```

These are working roles, not permanent hardware identities.

Public GitHub documentation should use role names and public-safe hashes when identity binding is required. Raw board identity material belongs outside the public repository.

A physical test must still freshly confirm power, location, role, and relevant runtime state before relying on them.

---

## 7. Evidence rules

Use the strongest evidence that directly proves the claim.

### 7.1 N3-W telemetry acceptance

For Manager-visible Direct/Relay acceptance, durable canonical state is preferred over the presence or absence of an INFO log line.

```text
MANAGER_CANONICAL_DURABLE_STATE=PRIMARY_ACCEPTANCE_ORACLE
INFO_LOG_ABSENCE_ALONE=NOT_PRODUCT_FAILURE
```

This preserves the existing KF-010 guard: a missing INFO line can be a logging false negative.

### 7.2 Radio and delivery evidence

- successful API submission is not automatically proof of asynchronous RF delivery;
- source review, CI, artifact binding, flashing, and physical behavior are separate proofs;
- a historical low-level radio error must not be claimed fixed without appropriate post-fix evidence;
- a timing gap must not be attributed to one internal phase without phase-specific evidence.

### 7.3 Serial is not a passive observer

Opening an application serial port can reset or disturb the board.

```text
APPLICATION_SERIAL_AS_PASSIVE_ORACLE=false
```

Use non-intrusive Manager/Broker/durable-state evidence when it can answer the question.

### 7.4 Evidence and conclusion must match

Use explicit classifications:

```text
PASS
FAIL
NOT_EXECUTED
INCONCLUSIVE
UNKNOWN_FRESH
```

Do not turn `NOT_EXECUTED`, missing logs, stale evidence, or an operator assumption into `PASS`.

---

### 7.5 Factory-image post-write verification

The write-stage internal hash verification is the authority for bytes written during flashing. After first boot, runtime-mutable partitions such as `otadata` must be classified separately from immutable firmware regions. Whole-image byte equality after boot is not a valid standalone corruption oracle.

```text
WRITE_FLASH_INTERNAL_HASH_VERIFY=WRITE_STAGE_ORACLE
POST_BOOT_FULL_IMAGE_BYTE_EQUALITY_REQUIRED=false
POST_BOOT_IMMUTABLE_REGION_EQUALITY_REQUIRED=true
RUNTIME_MUTABLE_PARTITIONS_CLASSIFIED_SEPARATELY=true
OTADATA_ONLY_POST_BOOT_DRIFT_IS_NOT_FIRMWARE_CORRUPTION=true
AUTO_REFLASH_AFTER_FULL_IMAGE_VERIFY_MISMATCH=false
```

## 8. Authorization and mutation rules

Read-only inspection does not grant mutation authority.

Any live, physical, credential, firmware, NVS, Broker, Manager, DynSec, or comparable mutation must stay inside the exact authorization granted for that action.

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTHORIZATION_SCOPE_EXPANSION=false
CONSUMED_AUTHORIZATION_REPLAY=false
```

For one-shot authorization:

- claim it only when entering the authorized action;
- once claimed, treat it as consumed according to its contract even if execution later fails;
- never silently reuse a consumed or superseded authorization;
- an operator override is evidence for that one bounded action only unless explicitly stated otherwise;
- a historical target override must not become a permanent identity rule.

After a substantive failure:

```text
AUTO_REPAIR=false
AUTO_RETRY=false
AUTO_REFLASH=false
STOP_AND_REVIEW=true
```

unless the exact current contract explicitly permits a bounded retry.

---

## 9. User / assistant execution split

The user is the physical operator and final decision maker. The assistant owns technical analysis, command design, safety boundaries, evidence interpretation, and repository-quality engineering work.

When the assistant cannot directly access a physical board or private T1 runtime, it should give the user a complete bounded command or operation package rather than pretending the action was executed.

For mechanical user operations, prefer a complete batch when the later commands do not depend on earlier safety results.

Do not default to:

```text
one tiny command
→ wait for one line
→ another tiny command
→ repeat
```

Use separate steps only where an earlier result genuinely determines whether the next action is safe.

---

## 10. Public / private information boundary

Public GitHub may contain:

- source and tests;
- public-safe architecture and process rules;
- sanitized runtime conclusions;
- artifact IDs and hashes;
- hashed device identities where necessary;
- sanitized timing and acceptance evidence;
- reproducibility and recovery instructions that do not expose secrets.

Do not commit:

- passwords or tokens;
- private keys or setup secrets;
- private host addresses or private SSH locators;
- raw credentials;
- raw NVS dumps;
- raw board identity material when a public-safe hash is sufficient;
- private runtime logs containing sensitive values.

```text
PUBLIC_REPOSITORY_SECRET_VALUES_ALLOWED=false
PRIVATE_RUNTIME_LOCATORS_ALLOWED=false
```

Private working context is maintained outside the public repository and may be loaded separately when needed.

---

## 11. What belongs in a handoff

A handoff is a **stage delta**, not a complete project encyclopedia.

It should contain only what the next session needs that is not already durable in this file or the current-state documents.

Required concepts:

- why the chat is switching;
- current project route and stop point;
- exact current repository/candidate/artifact authorities needed by the next step;
- fresh live baseline or explicit `UNKNOWN_FRESH` items;
- newly proven facts;
- current blocker, if any;
- relevant closed/forbidden routes only;
- authorization ledger entries that can still affect execution;
- exactly one next gate;
- exact allowed/forbidden scope for that gate;
- execution method;
- expected structured result;
- what happens after PASS or FAIL;
- any important artifact not yet durably shared to GitHub;
- a compact new-chat start prompt.

Do **not** repeat the full contents of this file in every handoff.

```text
HANDOFF_IS_STAGE_DELTA=true
DUPLICATE_LONG_TERM_RULES_IN_HANDOFF=false
```

A handoff may restate a long-term rule only when:

- the next gate is unusually sensitive to that rule;
- the stage introduces a temporary stricter override;
- the rule is required for a self-contained physical operation package.

---

## 12. Minimum new-chat read set

For an N3-W continuation, the default public read set is:

```text
1. current formal handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. exact handoff standard authority, only when the handoff specifies one
```

Then perform the smallest fresh read-only rebind needed for the current gate.

Do not reread the full project history unless current evidence is insufficient.

---

## 13. Team-workspace completeness

The existing project-wide collaboration standard remains applicable:

```text
docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md
```

A meaningful development result that exists only in chat or a temporary local directory is not durably shared.

Every formal handoff should state:

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=<n>
TEAM_SHARE_COMPLETENESS=PASS|FAIL
```

If a valuable artifact cannot be committed, record a public-safe recovery locator/hash and explain why it remains outside GitHub.

---

## 14. T1_Core_Stack naming and product boundary

The canonical name for the T1 production application stack is:

```text
T1_Core_Stack
```

It contains exactly:

```text
greenhouse-manager
Home Assistant
Mosquitto Broker
```

Armbian, Docker/Compose, systemd, provisioning, maintenance transactions, upgrade/recovery
executors and CI are platform/operations layers around T1_Core_Stack and are not part of the
stack name.

Upgrade design should use a clean T1_Core_Stack product reference and distinguish stable
product invariants from normal runtime drift.

```text
CLEAN_PRODUCT_REFERENCE_NOT_RUNTIME_SNAPSHOT=true
HARD_GATE_REQUIRES_STABLE_PRODUCT_INVARIANT=true
NORMAL_RUNTIME_DRIFT_DEFAULTS_TO_SOFT_OR_DIAGNOSTIC=true
MODULE_UPGRADE_DEFAULT_SCOPE=ONE_T1_CORE_STACK_COMPONENT
```

Design authority:

```text
docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_AND_STABLE_INVARIANTS_DESIGN_20261031.md
```

---

## 15. Dual-T1 clean-reference and upgrade-validation roles

The current canonical physical-role split is:

```text
T1_A_ROLE=LEGACY_UPGRADE_AND_FAILURE_SPECIMEN
T1_A_WIPE=false

T1_B_ROLE=CLEAN_REFERENCE_AND_CLEAN_UPGRADE_TARGET
T1_B_WIPE_AND_REINSTALL_ARMBIAN=true
```

T1_A preserves the real historical E03 successor-upgrade failure state and must not be
reformatted merely to create a second clean machine. It is used later to validate how the
new upgrade tooling handles a long-running/dirty/legacy T1. Any additional historical
Manager business bug present on T1_A must be freshly proven before being used as an
upgrade test case.

T1_B is the clean-reference machine. R0/R0H/R1/R2/R3 clean-reference work starts on T1_B.

The canonical upgrade tool name is:

```text
T1_Core_Updater
CLI=t1-core-updater
```

T1_Core_Updater owns T1_Core_Stack component inspection/planning/upgrade/rollback/status.
It does not own Armbian installation, kernel/host-platform update, initial T1 installation,
or board firmware update.

Clean-reference work and upgrade-validation work are separate phases:

```text
CLEAN_REFERENCE != UPGRADE
UPGRADE_REQUIRES_EXPLICIT_BASELINE_A_AND_TARGET_B=true
DEFAULT_UPGRADE_SCOPE=ONE_T1_CORE_STACK_COMPONENT
```

---

## 16. Maintenance rule

Update this file only when a **stable working convention** changes.

Do not update it for:

- a new sequence number;
- a new physical observation;
- a new candidate SHA;
- a new one-shot authorization;
- a temporary failure;
- a single gate result.

Those belong in current state, progress alignment, known failures, or the current handoff.

A change to this file should explain the durable process need it addresses and should update the handoff template when the change affects new-chat continuation.

```text
N3W_PROJECT_WORKING_CONTEXT_VERSION=1.4
STABLE_CONVENTIONS_ONLY=true
STAGE_SPECIFIC_VALUES_PROHIBITED=true
HANDOFF_TEMPLATE_EXPECTED_TO_REFERENCE_THIS_FILE=true
```
