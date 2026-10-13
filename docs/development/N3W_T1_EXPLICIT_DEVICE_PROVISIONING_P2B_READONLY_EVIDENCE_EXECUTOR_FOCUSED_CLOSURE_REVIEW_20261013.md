# N3-W T1 P2B Read-only Evidence Executor Focused Closure Review（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_READONLY_EVIDENCE_EXECUTOR_FOCUSED_CLOSURE_REVIEW`

## 0. Exact authority

```text
ORIGINAL_REVIEW_HEAD=674e5e9362662ecd7d0d6c0b80b9221a56cc433b
REPAIR_HEAD=664a253f40bf0c780077c01a1ee57e463b7d734c
TEST_HARNESS_FIX_HEAD=9155855a71f4750ebf7a7b22d9b4e000627e2f98
EXECUTION_SOURCE_HEAD=9155855a71f4750ebf7a7b22d9b4e000627e2f98
PROBE_SOURCE_COMMIT=a43c5750a8051946a9f08e3b3b2af3c5d7b9de69
PROBE_BLOB_SHA=26a2f47c9c83fef5637f551ea75ba6b5d5ba3866
PR=541
PR_STATE=OPEN_DRAFT
```

No T1 access occurred during this review.

## 1. Exact-head CI closure

At exact execution source head `9155855a71f4750ebf7a7b22d9b4e000627e2f98`:

```text
TOTAL=26
COMPLETED=26
SUCCESS=26
FAILURE=0
PENDING=0
N3W_T1_EXPLICIT_PROVISIONING_SOURCE_CI=PASS
```

The prior `664a253...` dedicated CI failure was a test-harness defect only:
the test monkeypatched `subprocess.run` before computing its own local Git HEAD.
The production executor had already rejected the wrong confirmation before any
subprocess call. The test was corrected without changing executor behavior.

## 2. A1 — remote Python write boundary

Reviewed source now executes:

`sudo -n python3 -B - --root /`

The probe is streamed through SSH stdin; no probe file is copied to T1.
`-B` disables Python bytecode-cache writes.

```text
A1_REMOTE_PYTHON_BYTECODE_WRITE=CLOSED
```

This is a no-intentional-product/configuration-write contract. Normal operating
system SSH/sudo/audit logging is not claimed absent.

## 3. A2 — exact local source authority

Before SSH, the executor requires:

- an explicit 40-character expected source HEAD;
- local HEAD equality to that exact value;
- clean tracked worktree;
- exact probe blob binding at that HEAD;
- local probe bytes matching the frozen blob.

Therefore the later live command must execute from exact source head
`9155855a71f4750ebf7a7b22d9b4e000627e2f98`.

```text
A2_EXACT_EXECUTOR_SOURCE_AUTHORITY=CLOSED
```

## 4. A3 — transport failure classification

Reviewed failure paths preserve private evidence for:

- timeout;
- SSH process launch failure;
- nonzero remote exit;
- invalid/nonconforming probe report.

Timeout/nonzero paths persist stdout/stderr plus structured STOP metadata.
No transport failure is reclassified as product PASS.

```text
A3_TRANSPORT_FAILURE_CLASSIFICATION=CLOSED
```

## 5. A4 — private evidence authority

Reviewed local evidence rules require:

- evidence root outside repository;
- no evidence-root symlink;
- current-user ownership;
- exact mode 0700;
- initially empty evidence directory;
- exclusive 0600 evidence-file creation;
- no-follow where supported;
- regular file/current owner/nlink=1 validation;
- file fsync.

```text
A4_PRIVATE_EVIDENCE_AUTHORITY=CLOSED
```

## 6. Independent closure result

```text
A1=CLOSED
A2=CLOSED
A3=CLOSED
A4=CLOSED
NEW_BLOCKER_COUNT=0

P2B_READONLY_EVIDENCE_EXECUTOR_SOURCE_REVIEW=PASS
P2B_READONLY_EVIDENCE_EXECUTOR_SOURCE=CLOSED_PASS
TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION_READY=true
```

This PASS applies only to the Mac-side read-only evidence executor and the
already-closed probe source.

It does **not** prove:

- clone-time machine-id behavior;
- SSH host-key regeneration behavior;
- NetworkManager/DHCP clone uniqueness;
- final writable `ensure_os_identity()` policy;
- Golden Master Final Seal;
- R3 per-device provisioning completion;
- R4 factory clone acceptance.

## 7. Live boundary / next gate

```text
T1_ACCESS=false
T1_READONLY_AUTHORIZATION_GRANTED=false
T1_MUTATION=false
T1_FILE_WRITE=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
ACTIVATION_TOPOLOGY_LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

Next gate:

```text
NEXT_ONE_GATE=
N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION

EXECUTION_SOURCE_HEAD=
9155855a71f4750ebf7a7b22d9b4e000627e2f98

T1_READONLY_AUTHORIZATION_REQUIRED=true
```

Do not implement real machine-id / SSH-host-key mutation until the target-Armbian
evidence gate has been executed and independently interpreted.
