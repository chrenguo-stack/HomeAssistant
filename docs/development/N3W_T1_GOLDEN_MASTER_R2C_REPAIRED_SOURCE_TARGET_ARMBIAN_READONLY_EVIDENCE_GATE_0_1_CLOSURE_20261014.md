# N3W T1 Golden Master R2C repaired-source target-Armbian read-only evidence Gate 0/1 closure

Date: 2026-10-14  
PR: #541 (OPEN / DRAFT / unmerged)  
Gate: `N3W_T1_GOLDEN_MASTER_R2C_REPAIRED_SOURCE_TARGET_ARMBIAN_READONLY_EVIDENCE_GATE_0_1_20261014_01`

## 1. Result

```text
RESULT=CLOSED_PASS_PREPARATION_ONLY
SOURCE_AUTHORITY=4898e519c317195dc22915a8d7b47f246a4121cf
HANDOFF_COMMIT=13bdaabcaa16212885e47ef38d65fc3c31c5af92
HANDOFF_DOCS_ADVANCE_VERIFIED=true
SOURCE_TEST_WORKFLOW_DRIFT_AFTER_SOURCE_AUTHORITY=false

EXECUTION_ID=NOT_APPLICABLE:preparation_only
AUTHORIZATION=NOT_GRANTED
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_OF_PRIOR_AUTHORIZATION=false

T1_ACCESS=false
SSH_EXECUTION=false
SSH_KEYSCAN=false
LIVE_RUNTIME_MUTATION=false
INTENTIONAL_TARGET_WRITE=false
SERVICE_MUTATION=false
BOARD_ACCESS=false
MERGE=false

GATE_0=PASS
GATE_1=PASS
EXECUTION_READY=false
ACTUAL_R2C_EVIDENCE_EXECUTION=false
PRIVATE_FINAL_PRECLAIM_EXECUTED=false
STOP=true
```

本 gate 只完成修复后源码重新绑定、确定性 streamed program 重建、模块/合同/hash 冻结，
以及下一次私有 final-preclaim 所需输入合同准备。没有连接 T1，也没有创建或消费新的
one-shot authorization。

## 2. Fresh rebind and drift proof

Fresh GitHub state:

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR541_STATE=OPEN_DRAFT
PR541_MERGED=false
CANDIDATE_REF=plan/n3w-t1-full-fresh-install-from-zero-20261010
CANDIDATE_HEAD_AT_GATE_START=13bdaabcaa16212885e47ef38d65fc3c31c5af92
HANDOFF_COMMIT=13bdaabcaa16212885e47ef38d65fc3c31c5af92
SOURCE_AUTHORITY=4898e519c317195dc22915a8d7b47f246a4121cf
COMMITS_AFTER_SOURCE_AUTHORITY=2
```

Comparison `4898e519...13bdaabc` contains only:

- `docs/development/N3W_CURRENT_STATE.md`
- `docs/development/N3W_CURRENT_STATE_INDEX.md`
- `docs/development/N3W_T1_GOLDEN_MASTER_R2C_E1_COLLECTION_DIAGNOSTIC_SOURCE_REPAIR_20261014.md`
- `docs/development/N3W_T1_GOLDEN_MASTER_R2C_E1_SOURCE_CLOSURE_TO_GATE_0_1_NEW_CHAT_HANDOFF_V1.0_20261014.md`

Therefore:

```text
SOURCE_DRIFT=false
TEST_DRIFT=false
WORKFLOW_DRIFT=false
DOCS_ONLY_ADVANCE=true
```

The source-repair closure records 42 successful checks, one conditional skip and zero failures.
A fresh workflow-run view of both `4898e519...` and the handoff head `13bdaabc...` shows
27/27 workflow runs completed successfully for each exact commit. No source authority promotion
to the docs head is made.

## 3. Exact package binding

Exact executor and contract:

```text
EXECUTOR_BLOB=7d18066b2a80701ced8f43f939c7a965a1a14d99
CONTRACT_BLOB=b575e33be67676f8b5e61fac6bc4a94a3dce37ff
CONTRACT_BYTES=21269
CONTRACT_SHA256=f3f0213cca63918341b9b0221133d882eb8e24f444d8432f8fdf1f94929b6866
STREAMED_PROGRAM_BYTES=195807
STREAMED_PROGRAM_SHA256=a1a4b86ec2aa1e27e74e00ee2e1c345379f5e340088f030e638e4f4137edf178
MODULE_BINDINGS=PASS
```

The streamed program was independently reconstructed from the executor's fixed seven-module
binding order and exact GitHub blobs. Current candidate-head blobs are identical to the
`4898e519...` source-authority blobs.

### Module bindings

| Module | Path | Git blob |
| --- | --- | --- |
| `n3w_t1_r2c_readonly_files` | `tools/n3w_t1_r2c_readonly_files.py` | `79ff9f8e9ceeca504d4b190120c69c9a981aa044` |
| `n3w_t1_r2c_readonly_commands` | `tools/n3w_t1_r2c_readonly_commands.py` | `8e66154edf9494141681ab76d969f9f1cdc38050` |
| `n3w_t1_r2c_evidence_schema` | `tools/n3w_t1_r2c_evidence_schema.py` | `84e8c0249c439beaf54ae09d8c5e2e6388621544` |
| `n3w_t1_r2c_firstrun` | `tools/n3w_t1_r2c_firstrun.py` | `3bca46f0f2b741586439c5d7302fdf96bec62fc8` |
| `n3w_t1_r2c_collectors_e5_e9` | `tools/n3w_t1_r2c_collectors_e5_e9.py` | `69e0438c4398f5bf0bcc91c77d8ebf0c7658e1b3` |
| `n3w_t1_r2c_collectors` | `tools/n3w_t1_r2c_collectors.py` | `5253ac1328e03eca81fc916f0a14d6074021a11b` |
| `n3w_t1_r2c_remote_probe` | `tools/n3w_t1_r2c_remote_probe.py` | `e29b140e0d9cee4853ffaf9e58547d98b2b5d9e3` |

## 4. Execution-safety contract review

Focused source review passed the Gate 0/1 requirements:

```text
REMOTE_PROGRAM_TRANSPORT=SSH_STDIN_ONLY
REMOTE_PROGRAM_FILE_CREATED=false
REMOTE_PYTHON_MODE=python3_-B_-
SUDO_MODE=sudo_-n
STRICT_HOST_KEY_CHECKING=yes
ACCEPT_NEW=false
KEYSCAN_IN_GATE_0_1=false

REMOTE_TOTAL_BUDGET_SECONDS=120
PER_COMMAND_TIMEOUT_SECONDS=10
OUTER_TIMEOUT_MIN_SECONDS=130
OUTER_TIMEOUT_MAX_SECONDS=180
OUTER_TIMEOUT_DEFAULT_SECONDS=150

PER_COMMAND_OUTPUT_MAX_BYTES=262144
PRIVATE_REPORT_MAX_BYTES=8388608
TRANSPORT_OUTPUT_MAX_BYTES=8388608

EVIDENCE_ROOT_OUTSIDE_REPOSITORY_REQUIRED=true
EVIDENCE_ROOT_MODE=0700
PRIVATE_FILE_MODE=0600
PRIVATE_FILE_CREATE=O_EXCL
AUTHORIZATION_CLAIM_BEFORE_FIRST_REMOTE_REQUEST=true
REPLAY_PERMITTED=false
```

The SSH argv requires `BatchMode=yes`, `StrictHostKeyChecking=yes`, one connection attempt,
bounded connect/keepalive settings, no forwarding and no TTY. The exact program is streamed to
`sudo -n python3 -B -`; it is not copied to the target filesystem.

The remote probe is observation-only by product intent. The contract explicitly forbids
machine-id/SSH/NetworkManager/journal/random-seed mutation, firstrun/keygen execution, service
start/stop/reload, network apply, Docker action, reboot/shutdown, disk capture and board access.
Normal SSH/sudo audit logging is not represented as bit-exact disk immutability.

The claim/result files are private local records. Existing/duplicate files fail closed because
private writes use exclusive creation. A timeout or output-limit after transport start consumes
the attempt and does not permit automatic replay.

## 5. Private final-preclaim preparation

No private target value is written to GitHub. The next separately authorized step must resolve
these values only in the user's private Mac context:

```text
PRIVATE_SSH_TARGET=<private; must already be known>
PRIVATE_EXISTING_HOST_KEY_BINDING=<private; exact existing trust only>
PRIVATE_TARGET_BINDING_ID=<private>
PRIVATE_EVIDENCE_ROOT=<private; outside repository; empty; owner current user; mode 0700>

EXPECTED_SOURCE_HEAD=4898e519c317195dc22915a8d7b47f246a4121cf
EXPECTED_EXECUTOR_BLOB=7d18066b2a80701ced8f43f939c7a965a1a14d99
EXPECTED_CONTRACT_BLOB=b575e33be67676f8b5e61fac6bc4a94a3dce37ff
EXPECTED_CONTRACT_SHA256=f3f0213cca63918341b9b0221133d882eb8e24f444d8432f8fdf1f94929b6866
EXPECTED_STREAMED_PROGRAM_BYTES=195807
EXPECTED_STREAMED_PROGRAM_SHA256=a1a4b86ec2aa1e27e74e00ee2e1c345379f5e340088f030e638e4f4137edf178
TIMEOUT_SECONDS=150

FUTURE_EXECUTION_ID=PENDING_NEW_AUTHORIZATION_DECISION
FUTURE_GRANT_ID=PENDING_NEW_AUTHORIZATION_DECISION
FUTURE_AUTHORIZATION_EXPIRY=PENDING_NEW_AUTHORIZATION_DECISION
CONFIRMATION_REQUIRED=READONLY R2C TARGET ARMBIAN EVIDENCE: YES
```

Before any future authorization claim or SSH request, the private final preclaim must prove:

1. local checkout is exactly `4898e519...` and tracked worktree is clean;
2. all seven module blobs, executor blob and contract blob match the values above;
3. rebuilt program size/hash and contract SHA-256 match exactly;
4. the private target is not a placeholder and the already-trusted host-key binding is unchanged;
5. no `ssh-keyscan`, `accept-new`, known-host deletion or trust relaxation is used;
6. evidence root is outside the repository, empty, 0700, and private files will be 0600/O_EXCL;
7. a new execution/grant/expiry is explicitly authorized and no claim with that identity already exists;
8. no previous unknown transport result is being replayed.

This gate does not perform those private target checks because doing so would require target/SSH
context that is explicitly outside Gate 0/1.

## 6. Boundary and next route

```text
PRIVATE_TARGET_PRECLAIM=PENDING
NEW_ONE_SHOT_AUTHORIZATION_REQUIRED=true
NEW_ONE_SHOT_AUTHORIZATION_GRANTED=false

E1_TARGET_OBSERVATION_PROVEN=false
OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_EVIDENCE_REQUIRED=true
DISK_CAPTURE_READY=false

NEXT_ROUTE=SEPARATE_PRIVATE_FINAL_PRECLAIM_AND_NEW_EXPLICIT_ONE_SHOT_AUTHORIZATION_DECISION
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

KF-113 remains active. Gate 0/1 PASS does not prove target-Armbian identity semantics, clone
uniqueness, Final Seal correctness or disk-capture readiness.

## 7. Final closure

```text
=== N3W_T1_GOLDEN_MASTER_R2C_REPAIRED_SOURCE_TARGET_ARMBIAN_READONLY_EVIDENCE_GATE_0_1_20261014_01 CLOSURE ===

EXECUTION_ID=NOT_APPLICABLE:preparation_only
AUTHORIZATION=NOT_GRANTED
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

SOURCE_AUTHORITY=4898e519c317195dc22915a8d7b47f246a4121cf
HANDOFF_DOCS_ADVANCE_VERIFIED=true
SOURCE_HEAD_CI=42_SUCCESS_1_CONDITIONAL_SKIP_0_FAILURE
FRESH_SOURCE_WORKFLOW_RUNS=27/27_SUCCESS
FRESH_HANDOFF_WORKFLOW_RUNS=27/27_SUCCESS

EXECUTOR_BLOB=7d18066b2a80701ced8f43f939c7a965a1a14d99
CONTRACT_BLOB=b575e33be67676f8b5e61fac6bc4a94a3dce37ff
CONTRACT_SHA256=f3f0213cca63918341b9b0221133d882eb8e24f444d8432f8fdf1f94929b6866
STREAMED_PROGRAM_BYTES=195807
STREAMED_PROGRAM_SHA256=a1a4b86ec2aa1e27e74e00ee2e1c345379f5e340088f030e638e4f4137edf178
MODULE_BINDINGS=PASS
PRIVATE_TARGET_PRECLAIM=PENDING

T1_ACCESS=false
SSH_EXECUTION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false

GATE_0=PASS
GATE_1=PASS
EXECUTION_READY=false
ACTUAL_R2C_EVIDENCE_EXECUTION=false
NEXT_ROUTE=SEPARATE_PRIVATE_FINAL_PRECLAIM_AND_NEW_EXPLICIT_ONE_SHOT_AUTHORIZATION_DECISION
STOP=true

=== END ===
```
