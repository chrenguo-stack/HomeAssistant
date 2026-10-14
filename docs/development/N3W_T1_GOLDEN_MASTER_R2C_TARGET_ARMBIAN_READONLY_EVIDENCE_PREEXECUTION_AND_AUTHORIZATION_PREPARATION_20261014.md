# N3-W T1 Golden Master R2C Target-Armbian Read-only Evidence
# Preexecution and Explicit Authorization Preparation — 2026-10-14

```text
TASK=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_READONLY_EVIDENCE_PREEXECUTION_AND_AUTHORIZATION_PREPARATION_20261014_01
GATE_0_RESULT=PASS
GATE_1_RESULT=PASS_PREPARED_NOT_GRANTED
NEXT_ONE_GATE=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
T1_ACCESS=false
SSH_EXECUTION=false
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
```

## 0. Result and boundary

Gate 0 fresh-rebound repository main, PR #541 and the candidate branch. Gate 1 freezes the
exact repository-side execution package and the requirements for a future private target
preclaim. This document does not grant the authorization and does not execute SSH.

Source closure and preexecution readiness are different claims:

```text
R2C_REMOTE_EXECUTOR_SOURCE=CLOSED_SOURCE
PREEXECUTION_PACKAGE=PREPARED
PRIVATE_TARGET_BINDING=REQUIRED_AT_FINAL_PRECLAIM
EXECUTION_READY=false
ACTUAL_R2C_EVIDENCE_EXECUTION=false
OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_EVIDENCE_REQUIRED=true
DISK_CAPTURE_READY=false
```

## 1. Gate 0 fresh repository binding

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR=541
PR_STATE=OPEN_DRAFT
PR_MERGED=false
CANDIDATE_REF=plan/n3w-t1-full-fresh-install-from-zero-20261010
CURRENT_HEAD=403413f89373d0650579c3886274e59be37783bc
REMOTE_EXECUTOR_VALIDATION_HEAD=7f7daca7f62e964147b715063d8ed17cf9be7767
VALIDATION_TO_CURRENT_COMMITS=5
VALIDATION_TO_CURRENT_DELTA=DOCS_ONLY
SOURCE_TEST_WORKFLOW_DRIFT=false
CURRENT_HEAD_CI=27/27_PASS
OPEN_CI_FAILURE_COUNT=0
```

The five commits after the reviewed validation head change only the remote-executor handoff,
progress, current-state and current-state-index documents. No source, test or workflow file
changed. Exact current-head CI includes:

- Golden Master source CI `38488174586`: success;
- Public repository safety CI `38488175700`: success;
- Production stack staging payload CI `38488174567`: success;
- all other PR workflows: success.

## 2. Exact execution package authority

The current clean checkout passes `validate_local_source_authority()` for the current HEAD.
The deterministic streamed program and contract digest were generated from that exact checkout.

```text
EXPECTED_SOURCE_HEAD=403413f89373d0650579c3886274e59be37783bc
EXECUTOR_PATH=tools/n3w_t1_r2c_remote_executor.py
EXECUTOR_BLOB=389a76848c2897290b102b61d2636e70e53315e9
CONTRACT_BLOB=b575e33be67676f8b5e61fac6bc4a94a3dce37ff
CONTRACT_SHA256=f3f0213cca63918341b9b0221133d882eb8e24f444d8432f8fdf1f94929b6866
STREAMED_PROGRAM_BYTES=186987
STREAMED_PROGRAM_SHA256=6d24ac8e7eff38be165c69eaaff4042808017887969e79c08a1c87ab9518ac25
TRACKED_WORKTREE_CLEAN=true
```

| Bound module | Git blob |
| --- | --- |
| `tools/n3w_t1_r2c_readonly_files.py` | `79ff9f8e9ceeca504d4b190120c69c9a981aa044` |
| `tools/n3w_t1_r2c_readonly_commands.py` | `6bc8cf35029955d4168a8077a13059a39a1c6218` |
| `tools/n3w_t1_r2c_evidence_schema.py` | `84e8c0249c439beaf54ae09d8c5e2e6388621544` |
| `tools/n3w_t1_r2c_firstrun.py` | `3bca46f0f2b741586439c5d7302fdf96bec62fc8` |
| `tools/n3w_t1_r2c_collectors_e5_e9.py` | `8041c776f2e49018639bd9d5bef33c7403f5792f` |
| `tools/n3w_t1_r2c_collectors.py` | `4fc776f9d920be82ea3c5d2afe00f40e99eec841` |
| `tools/n3w_t1_r2c_remote_probe.py` | `e29b140e0d9cee4853ffaf9e58547d98b2b5d9e3` |

Any source-head, executor, contract, module-blob or computed-digest difference invalidates this
preexecution package and requires a fresh repository-only rebind before authorization.

## 3. Proposed one-shot authorization

```text
PROPOSED_GATE=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE
PROPOSED_GRANT_ID=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_READONLY_EVIDENCE_20261014_01
PROPOSED_CONFIRMATION=READONLY R2C TARGET ARMBIAN EVIDENCE: YES
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
EXECUTION_ID=TO_BE_CREATED_AT_FINAL_PRECLAIM
AUTHORIZATION_EXPIRES_AT=TO_BE_FIXED_AT_FINAL_PRECLAIM
```

The exact confirmation above is only a proposal in this document. It is not granted by approval
of Gate 0/Gate 1. A future user message must explicitly grant that separate one-shot action.
The expiry must be a fresh UTC value fixed after the explicit grant and should be bounded to the
immediate execution window. The execution ID must be new and must not reuse a P2B identifier.

Historical P2B state remains:

```text
P2B_AUTHORIZATION_CLAIMED=true
P2B_AUTHORIZATION_CONSUMED=false
P2B_AUTHORIZATION_REPLAY_PERMITTED=false
```

## 4. Private target final-preclaim requirements

The following facts stay on the operator Mac and must not be committed or pasted into public
GitHub evidence:

- private SSH locator and address;
- raw known-host key or fingerprint;
- target binding token;
- raw hostname, machine-id, MAC, IP, SSID, UUID or NetworkManager profile values;
- raw stdout/stderr and private evidence report.

Immediately before claim, the operator-side preclaim must prove all of the following:

```text
PRIVATE_TARGET_LOCATOR_PRESENT=true
PRIVATE_TARGET_LOCATOR_IS_NOT_PLACEHOLDER=true
EXISTING_KNOWN_HOST_BINDING_PRESENT=true
KNOWN_HOST_BINDING_MATCHES_EXPECTED_TARGET=true
HOST_KEY_CHANGE=false
TARGET_BINDING_ID_PRESENT=true
PRIVATE_EVIDENCE_ROOT_OUTSIDE_REPOSITORY=true
PRIVATE_EVIDENCE_ROOT_OWNER=CURRENT_OPERATOR
PRIVATE_EVIDENCE_ROOT_MODE=0700
PRIVATE_EVIDENCE_ROOT_EMPTY=true
LOCAL_SOURCE_HEAD_MATCH=true
LOCAL_TRACKED_WORKTREE_CLEAN=true
AUTHORIZATION_NOT_EXPIRED=true
```

An unknown or changed host key is a STOP. Do not use accept-new, delete known_hosts entries,
set UserKnownHostsFile=/dev/null or disable StrictHostKeyChecking. Any legitimate target
replacement requires a separate private identity review before a new authorization decision.

## 5. Frozen execution contract

The future executor invocation is conceptually:

```text
python3 tools/n3w_t1_r2c_remote_executor.py
  --execute
  --target $R2C_PRIVATE_TARGET
  --target-binding-id $R2C_TARGET_BINDING_ID
  --evidence-root $R2C_PRIVATE_EVIDENCE_ROOT
  --confirm "READONLY R2C TARGET ARMBIAN EVIDENCE: YES"
  --grant-id $R2C_GRANT_ID
  --authorization-expires-at $R2C_AUTHORIZATION_EXPIRES_AT
  --execution-id $R2C_EXECUTION_ID
  --expected-source-head 403413f89373d0650579c3886274e59be37783bc
  --timeout-seconds 150
```

This is a contract description, not an instruction to run it before the separate authorization.
The actual command must be generated from fresh private values after the final preclaim.

Frozen transport and resource limits:

```text
SSH_STDIN_STREAMING=true
REMOTE_PROBE_FILE_CREATED=false
STRICT_HOST_KEY_CHECKING=true
SSH_BATCH_MODE=true
SSH_TTY=false
SSH_FORWARDING=false
SUDO_NONINTERACTIVE=true
PYTHON_BYTECODE_WRITE_DISABLED=true
CONNECTION_ATTEMPTS=1
CONNECT_TIMEOUT_SECONDS=10
EXECUTION_TIMEOUT_SECONDS=150
ALLOWED_TIMEOUT_RANGE_SECONDS=130..180
MAX_STDOUT_STDERR_BYTES=8388608
EVIDENCE_DIRECTORY_MODE=0700
EVIDENCE_FILE_MODE=0600
EVIDENCE_FILE_CREATE=O_EXCL
```

The authorization claim is written before the first remote request. Once the claim exists,
replay is forbidden even if local or remote execution later fails. A local spawn failure may
remain not-consumed, but it still does not permit automatic replay.

## 6. Allowed and forbidden scope

Allowed after the separate grant:

- one bounded SSH request to stream the exact read-only probe;
- E1–E9 observation and metadata/config/source reading allowed by the frozen contract;
- Mac-local private evidence persistence and positive-allowlist public projection.

Forbidden:

- machine-id, D-Bus identity, SSH key, NetworkManager, netplan, journal or random-seed mutation;
- executing Armbian firstrun, firstboot or SSH key-generation helpers;
- systemctl start/stop/restart/reload/enable/disable/daemon-reload;
- netplan apply/generate or nmcli mutation;
- Docker queries or container/service operation;
- reboot, shutdown, Seal, disk capture, clone write or factory acceptance;
- Broker/Manager/Home Assistant mutation;
- board access, credentials, firmware, NVS or PR merge.

## 7. Required result and STOP classification

A future execution must preserve separate outcomes:

```text
CAPTURE_STATUS=COMPLETE|INCOMPLETE|FAILED
STATIC_REVIEW_STATUS=NOT_EXECUTED
PUBLIC_PROJECTION_REVIEW=NOT_REVIEWED
OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_REQUIRED=true
DISK_CAPTURE_READY=false
```

Important STOP cases include:

- `STOP_TARGET_DRIFT` for unexpected platform/version/binding;
- `STOP_TARGET_CHANGED` for boot or source/config continuity drift;
- `STOP_EVIDENCE_GAP` for incomplete E1–E9 evidence;
- `STOP_BOUNDARY_VIOLATION` for any unintended active write or service operation;
- transport timeout, output truncation, invalid report binding or unknown result.

No STOP result authorizes automatic retry, repair, host-key acceptance or mutation. Preserve the
private evidence, report the exact boundary reached and require a new decision.

## 8. Gate 1 closure and next boundary

```text
GATE_0=PASS
GATE_1=PASS_PREPARED_NOT_GRANTED
EXACT_PACKAGE_BOUND=true
PRIVATE_PRECLAIM_PENDING=true
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
T1_ACCESS=false
SSH_EXECUTION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE
NEXT_ACTION_REQUIRES_EXPLICIT_CONFIRMATION=true
STOP=BEFORE_PRIVATE_TARGET_PRECLAIM_AUTHORIZATION_AND_SSH
```

Gate 1 completion does not automatically enter the evidence execution gate.
