# N3W T1 Golden Master R2C read-only evidence reexecution closure

Date: 2026-10-14  
PR: #541 (OPEN / DRAFT / unmerged)  
Execution source authority: `a7cf9b569133bcd6a08ace65027b4730cdd54a11`  
Execution ID: `r2c-20261014-46cf8e35f3daddf620cd209382937303`

## 1. Result

```text
GATE_EXECUTION=PASS
REMOTE_EXIT=0
REPORT_SCHEMA=PASS
SAME_BOOT=true
CAPTURE_STATUS=FAILED
POST_CAPTURE_STATIC_REVIEW=PASS_WITH_OPEN_E1_DIAGNOSTIC
POST_CAPTURE_PUBLIC_PROJECTION_REVIEW=PASS
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
T1_ACCESS=true
INTENTIONAL_TARGET_WRITE=false
SERVICE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_REQUIRED=true
DISK_CAPTURE_READY=false
```

The new exact one-shot authorization was bound to the repaired source package. Private
final-preclaim passed before the claim was written. Exactly one bounded SSH request completed
with remote exit zero and a valid report. The grant is consumed and cannot be replayed.

The evidence capture still failed closed. The source repair converted E6, E7 and E9 from generic
collector errors into bounded UNKNOWN classifications, but E1 still returned a generic
collection error. No target retry was attempted.

## 2. Exact execution package

```text
EXPECTED_SOURCE_HEAD=a7cf9b569133bcd6a08ace65027b4730cdd54a11
OBSERVED_SOURCE_HEAD=a7cf9b569133bcd6a08ace65027b4730cdd54a11
EXECUTOR_BLOB=5c2f7bf9dfe6e0cfe4814aba7f9fe859a93d6998
PROBE_SHA256=1da220fabaefa8d25ab5688ac15c7fc0d7b4e2ea67fe6841c587a05ecbc8e63a
CONTRACT_SHA256=f3f0213cca63918341b9b0221133d882eb8e24f444d8432f8fdf1f94929b6866
SOURCE_HEAD_CI=42_SUCCESS_1_CONDITIONAL_SKIP_0_FAILURE
TRACKED_WORKTREE_CLEAN=true
```

The streamed program was 194267 bytes. Its seven module blobs and contract blob matched the
executor's fixed bindings before claim.

## 3. Requirement result

| Requirement | Status | Complete | Reason code |
| --- | --- | --- | --- |
| E1 | ERROR | false | `STOP_E1_COLLECTION_ERROR` |
| E2 | UNKNOWN | false | `STOP_UNRESOLVED_IMPLEMENTATION` |
| E3 | UNKNOWN | false | `STOP_CONFIG_UNRESOLVED` |
| E4 | UNKNOWN | false | `STOP_SEMANTICS_GAP` |
| E5 | UNKNOWN | false | `STOP_SSH_IDENTITY_UNKNOWN` |
| E6 | UNKNOWN | false | `STOP_NETWORK_IDENTITY_UNKNOWN` |
| E7 | UNKNOWN | false | `STOP_JOURNAL_CLASSIFICATION` |
| E8 | OBSERVED | true | none |
| E9 | UNKNOWN | false | `STOP_BOOT_ORDER_CAPTURE_GAP` |

Compared with the previous one-shot capture:

- E6 no longer collapses usr-merge handling into `STOP_E6_COLLECTION_ERROR`;
- E7 no longer promotes a non-directory journal root to `STOP_EXPECTED_DIRECTORY`;
- E9 no longer collapses usr-merge handling into `STOP_E9_COLLECTION_ERROR`;
- E1 remains a generic collector error and requires a new repository-only diagnostic repair;
- E2, E3, E4 and E5 remain genuine semantics/provenance gaps;
- E8 remains complete.

The private report does not preserve the underlying E1 exception class. The post-capture source
review therefore does not guess the target-specific cause. It records the remaining defect:
`collect_e1()` still collapses controlled command/filesystem exceptions into
`STOP_E1_COLLECTION_ERROR`, which prevents a bounded diagnosis.

## 4. Transport and private artifact integrity

```text
STDOUT_BYTES=26047
STDERR_BYTES=0
STDOUT_SHA256=0cc54dbec18b382766ff2dc8313902e52a6523bcfd77b1de3e43ee558627b127
STDERR_SHA256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
PRIVATE_FILE_COUNT=9
PRIVATE_ROOT_MODE=0700
PRIVATE_FILE_MODE=0600
```

Private artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| start | `20d2ee10292d7aedd94205736761ef784b3589cdece76687f49db515823b5c0c` |
| authorization claim | `272ab4562dca0f058c01a33f5651e6054d60bf15a7a449992bc09db5c6b247d9` |
| command | `ce5acfe85d1b9695b8a5cdd988aedb7151ba1640667e0b8bb553606dc22cc41c` |
| stdout | `0cc54dbec18b382766ff2dc8313902e52a6523bcfd77b1de3e43ee558627b127` |
| stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| report | `8816ee9032421f6d49946a6361feff010154f637efde90d1736fc3f24dfad0bc` |
| public candidate | `d6a726bfdbac90a683a84f0b9ba34073234f27815d7dcd47ed71df9e55fc7552` |
| authorization result | `4cce88740e05bb94dd7dbb55d163e5008b12b3c986f3793bb961765a9ed1727e` |
| result | `5102be37adefdf9a707d15c8d4ab1975056e5284f8db95fbe42af640f5e70c6b` |

The private root and target locator are intentionally omitted. Raw stdout, report and private
target-binding material remain outside the repository.

## 5. Public projection review

The stored public candidate was rebuilt from the validated private report and matched exactly.
The post-capture review confirmed:

- exactly E1-E9 are projected;
- field values are omitted and no raw `value` key is present;
- no IPv4 address, MAC address, SSH public key or private target alias is present;
- the projection contains only requirement status, completeness, reason codes, method IDs and
  field statuses.

The immutable report still records `public_projection_review=NOT_REVIEWED` and
`static_review_status=NOT_EXECUTED` because those are capture-time fields. This closure records
the separate post-capture reviews without rewriting private evidence.

## 6. Boundary and next gate

This run does not prove OS identity semantics. Controlled clone boot remains mandatory, and disk
capture, Final Seal, board work and merge remain forbidden.

The next gate is repository-only E1 collection diagnostic review and repair. It must preserve
the historical report, replace generic controlled exceptions with bounded reason codes, add
tests and close CI. Any later target observation requires a fresh source/package rebind and a
new explicit one-shot authorization. This consumed grant is not replayable.
