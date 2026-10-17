# N3W T1 F5 Production Process V1 — Provisioning Integration Closure and F4 Prepare New Chat Handoff

Date: 2026-10-17

## 1. Current task identity

```text
PROJECT=温室环境监测系统（ESP32-C6）
SUBPROJECT=N3-W / T1
PRIMARY_TASK=N3W_T1_PRODUCTION_PROCESS_V1_F5
PR=612
PR_STATE=OPEN_DRAFT
PR_BRANCH=feat/n3w-t1-f5-production-process-v1-source-20261017

MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb
PRODUCT_SOURCE_HEAD=91b5e9cb05ca4eddc43acb28a1ab565b1309d1c5

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This handoff closes the F5 Provisioning boundary integration source step and deliberately stops before any F4 source mutation.

## 2. Closed source blocks in this conversation

The following F5 source blocks are now closed at the current product source head:

```text
EVIDENCE_SET_COMMIT_BLOCKER=CLOSED_PASS
SSH_REAL_SSHD_INTEGRATION_BLOCKER=CLOSED_PASS
PROVISIONING_PHASE_CONTEXT_BLOCKER=CLOSED_PASS
```

### Evidence set

The final result uses immutable private/public result files plus a final evidence seal. A missing seal makes the evidence set unusable by the formal inspect/verify path. Private/public/seal failure injection tests exist.

### SSH

The normal SSH path has real OpenSSH sshd CI coverage. One password authentication is allowed per connection epoch; child ssh/scp calls reuse the controlled master and do not silently fall back to another authentication path. One planned reboot therefore uses two connection epochs and still one production approval.

### Provisioning

`tools/n3w_t1_device_provisioning_host.py` now supports two explicitly separated modes:

- historical/engineering explicit start: `start --confirm "START DEVICE PROVISIONING: YES"`;
- F5 normal production start: `start --production-phase-context <path>`.

The F5 route validates an already-consumed target production phase context for exact phase `PROVISION`, verifies source binding, creates an immutable local production execution claim before calling the existing provisioning state machine, and forbids replay of the same context.

The existing `device_firstboot.py` business state machine remains unchanged. The normal F5 path does not create a second human approval. It still reaches `DEVICE_READY` without starting production services.

Successful F5 provisioning completion is bound to the durable existing provisioning records by SHA256:

- `transaction.json`;
- `FIRSTBOOT_COMPLETE.json`.

Failure after the local production execution claim remains consumed/no-replay.

## 3. Provisioning closure review

Focused review at `91b5e9cb05ca4eddc43acb28a1ab565b1309d1c5` found no remaining blocker in this boundary step:

```text
PHASE_CONTEXT_REQUIRED=PASS
PHASE_EXACT_PROVISION=PASS
SOURCE_BINDING=PASS
LEGACY_AND_PRODUCTION_AUTHORITY_MODES_SEPARATED=PASS
SECOND_HUMAN_CONFIRMATION_IN_F5_PATH=FALSE
LOCAL_CLAIM_BEFORE_PRIMITIVE_EXECUTION=PASS
SAME_CONTEXT_REPLAY_BLOCKED=PASS
POST_CLAIM_FAILURE_REPLAY_BLOCKED=PASS
DEVICE_READY_REQUIRED=PASS
PRODUCTION_SERVICE_START_FALSE=PASS
TRANSACTION_HASH_BINDING=PASS
FIRSTBOOT_COMPLETE_HASH_BINDING=PASS
DEVICE_FIRSTBOOT_BUSINESS_STATE_MACHINE_CHANGED=FALSE
```

## 4. Exact CI evidence

All workflows observed on `91b5e9cb05ca4eddc43acb28a1ab565b1309d1c5` completed successfully.

Key runs:

```text
N3W_T1_F5_PRODUCTION_PROCESS_V1_SOURCE_CI=PASS
RUN_ID=39018192400

N3W_T1_EXPLICIT_PROVISIONING_SOURCE_CI=PASS
RUN_ID=39018192302

N3W_T1_FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=PASS
RUN_ID=39018192388
```

The same head also passed Public repository safety, greenhouse-manager, golden master source, M0, C-07 and the observed M2/H3 regression workflows.

The immediately preceding Explicit Provisioning run failed only Ruff checks because the executable bit was accidentally lost and the post-claim exception marker used a Ruff-rejected broad-exception pattern. Both were locally repaired in commit `91b5e9cb05ca4eddc43acb28a1ab565b1309d1c5`; no product behavior was expanded by that repair.

## 5. Repository state and stop boundary

```text
PR612_OPEN_DRAFT=true
PR612_MERGEABLE=true
PR612_MERGEABLE_STATE=clean
MAIN_MUTATION=false
MERGE=false
T1_ACCESS=false
BOARD_ACCESS=false
```

Do not merge PR #612 merely from this handoff. F4 boundary integration and remaining F5 source/release work are still open.

## 6. Next one gate

```text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_F4_PREPARE_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01
```

### Purpose

Integrate only the first F4 normal-production mutation boundary, `F4_PREPARE`, with the already-frozen F5 production run authority. Keep this gate short and independently reviewable.

### Read first

Fresh rebind:

- repository main;
- PR #612;
- branch `feat/n3w-t1-f5-production-process-v1-source-20261017`;
- current product source head;
- `tools/n3w_t1_production_contract.py`;
- `tools/n3w_t1_production_authority.py`;
- `tools/n3w_t1_f4_activation_host.py`;
- its focused tests/workflow;
- F4 closure/acceptance design documents needed to preserve the accepted F4 state machine.

### Required behavior

```text
REUSE_EXISTING_F4_BUSINESS_LOGIC=true
REWRITE_F4_STATE_MACHINE=false
REPAIR_COMMANDS_IN_NORMAL_PATH=false

NORMAL_F5_F4_PREPARE_REQUIRES_PRODUCTION_PHASE_CONTEXT=true
REQUIRED_PHASE=F4_PREPARE
TARGET_AUTHORITY_VALIDATION_REQUIRED=true
SOURCE_RELEASE_TARGET_PREDECESSOR_BINDING_REQUIRED=true
SECOND_HUMAN_APPROVAL=false
LOCAL_EXECUTION_CLAIM_BEFORE_MUTATION=true
REPLAY_ALLOWED=false
UNKNOWN_OR_AMBIGUOUS_RESULT=STOP

T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false
```

Keep the historical F4 engineering/recovery interfaces compatible unless the reviewed boundary proves a minimal compatibility change is required.

### Stop point

After F4_PREPARE source change, focused tests, relevant F4 CI, F5 source CI and regression CI have a classified result, perform one short source review and stop. Do not automatically chain F4_ACTIVATE, F4_ACCEPT, persistence/certificate, reboot or live T1 execution into the same gate.

## 7. Working rules carried forward

- Each reply starts with 主线任务 / 支线任务 / 当前任务.
- Development, source review, simulation tests and GitHub archival can proceed continuously without one-gate-one-authorization.
- Stop for user-local commands, design choices, scope expansion, live T1/board access or merge.
- Poll a GitHub workflow/CI at most three times; if still incomplete, stop polling and provide the run link.
- If a CI failure is localized, unambiguous and does not expand scope, fix it directly.
- Keep development progress and evidence in GitHub instead of relying on chat history.
