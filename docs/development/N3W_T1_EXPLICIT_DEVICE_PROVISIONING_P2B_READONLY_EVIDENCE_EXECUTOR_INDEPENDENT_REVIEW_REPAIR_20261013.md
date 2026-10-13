# N3-W T1 P2B Read-only Evidence Executor Independent Review Repair（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_READONLY_EVIDENCE_EXECUTOR_INDEPENDENT_REVIEW_REPAIR`

## 0. Review authority

```text
REVIEW_HEAD=674e5e9362662ecd7d0d6c0b80b9221a56cc433b
PR=541
REVIEW_CI=26/26 PASS
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

CI was green, but independent source review found execution-readiness blockers. CI success did not override them.

## 1. A1 — remote Python read-only boundary

The original remote command was:

`sudo -n python3 - --root /`

That did not disable Python bytecode-cache writes. On a target where an imported stdlib cache is absent or stale, the interpreter could create `__pycache__/*.pyc`, contradicting the package's no-file-write intent.

Repair:

`sudo -n python3 -B - --root /`

Result:

```text
A1_REMOTE_PYTHON_BYTECODE_WRITE=REPAIRED_SOURCE
```

## 2. A2 — exact local execution authority

The original executor bound the probe blob but did not prove that the Mac was executing the authorized repository head with a clean tracked worktree.

A locally modified executor could therefore still send the unchanged probe and emit a nominal PASS.

Repair now requires before SSH:

- explicit 40-character expected source head;
- local `HEAD` equals that exact head;
- tracked worktree is clean;
- the authorized probe path at that exact head resolves to the frozen probe blob.

Result:

```text
A2_EXACT_EXECUTOR_SOURCE_AUTHORITY=REPAIRED_SOURCE
```

The later live authorization must name the exact final source head supplied to `--expected-source-head`.

## 3. A3 — transport failure evidence

The original timeout/nonzero paths preserved stdout/stderr but did not always persist a structured terminal result, and local SSH launch errors could escape as an unclassified exception.

Repair:

- timeout persists `result.json` with `status=STOP`, hashes, byte counts and `timed_out=true`;
- SSH launch failure becomes structured `ssh_transport_error`;
- nonzero remote exit persists structured STOP evidence;
- invalid report persists structured STOP evidence.

Result:

```text
A3_TRANSPORT_FAILURE_CLASSIFICATION=REPAIRED_SOURCE
```

## 4. A4 — local private evidence authority

The original evidence root checked mode and emptiness but not owner, and evidence files were created by ordinary `write_bytes()` before chmod.

Repair:

- evidence-root symlink rejected;
- current-user ownership required;
- exact 0700 root required;
- evidence files use exclusive create + no-follow where available;
- exact 0600/current-owner/nlink=1 required before write;
- file data is fsync'd.

Result:

```text
A4_PRIVATE_EVIDENCE_AUTHORITY=REPAIRED_SOURCE
```

## 5. Scope boundary

This repair does not execute T1, does not prove target-Armbian clone semantics and does not authorize OS identity mutation.

Normal SSH/sudo/audit logging by the operating system is outside the product/configuration mutation contract; the executor itself performs no intentional T1 product/configuration write.

## 6. Current status

```text
REVIEW_BLOCKER_COUNT_BEFORE_REPAIR=4
A1=REPAIRED_SOURCE
A2=REPAIRED_SOURCE
A3=REPAIRED_SOURCE
A4=REPAIRED_SOURCE

CI=PENDING
INDEPENDENT_CLOSURE_REVIEW=PENDING

T1_ACCESS=false
T1_READONLY_AUTHORIZATION_GRANTED=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

Do not enter live read-only execution until this repair head reaches terminal CI success and receives focused closure review.
