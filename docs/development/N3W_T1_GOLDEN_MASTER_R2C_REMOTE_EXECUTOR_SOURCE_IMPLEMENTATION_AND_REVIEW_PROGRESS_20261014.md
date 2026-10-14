# N3-W T1 Golden Master R2C remote executor source implementation and review progress — 2026-10-14

## 1. Current result

```text
TASK=N3W_T1_GOLDEN_MASTER_R2C_REMOTE_EXECUTOR_SOURCE_IMPLEMENTATION_AND_REVIEW_20261014_01
SOURCE_CANDIDATE=01256f67fc6b7496b476963ede37496abe099327
VALIDATION_HEAD=7f7daca7f62e964147b715063d8ed17cf9be7767
CURRENT_CANDIDATE_HEAD=0fb4a6787c81e180925e203aa687d2f47b99dc0d
VALIDATION_HEAD_CI=27/27_PASS
PR=541
PR_STATE=OPEN_DRAFT
R2C_E5_E9_SOURCE=CLOSED_SOURCE
R2C_REMOTE_EXECUTOR=CLOSED_SOURCE
FOCUSED_SOURCE_REVIEW=PASS_NO_OPEN_SOURCE_BLOCKER
EXACT_SOURCE_CI_CLOSURE=PASS
EXECUTION_READY=false
ACTUAL_R2C_EVIDENCE_EXECUTION=false
ACTUAL_T1_EXECUTION_AUTHORIZATION_GRANTED=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

This gate is repository-only. No SSH/T1 request, target write, service mutation, Seal
mutation, disk capture, clone boot, board access or merge occurred.

## 2. Implemented source

The exact source candidate adds and integrates:

- `tools/n3w_t1_r2c_remote_probe.py`;
- `tools/n3w_t1_r2c_remote_executor.py`;
- `tests/tools/test_n3w_t1_r2c_remote_probe.py`;
- `tests/tools/test_n3w_t1_r2c_remote_executor.py`;
- an E4 completion repair in `tools/n3w_t1_r2c_collectors.py`;
- focused E4 regression coverage in `tests/tools/test_n3w_t1_r2c_collectors.py`.

The executor binds the frozen preparation contract and every streamed probe module by exact
Git blob, requires an exact clean local source HEAD, and streams the bound program through SSH
stdin to `sudo -n python3 -B -`. It does not use scp or create a remote probe file.

SSH transport is fail-closed: BatchMode, StrictHostKeyChecking=yes, one connection attempt,
bounded connect/liveness settings, no TTY and no forwarding. No accept-new or host-key bypass
is present.

Operator-side evidence is outside the repository, root mode 0700, file mode 0600 and O_EXCL.
The new authorization claim is written before the first remote request. A used or ambiguous
claim is not replayable.

## 3. Focused review findings and repairs

The focused source review found five same-gate issues and repaired them before closure:

1. The first integration candidate had a broad collector exception catch and Ruff-only source
   issues. The broad catch was removed so programming faults fail the remote process instead of
   being silently converted to evidence.
2. SSH stdout/stderr was initially bounded only after `subprocess.run` returned. It is now
   read through a bounded streaming transport; the combined private transport output cannot grow
   past the 8 MiB contract before STOP_TRUNCATED.
3. E4 still had `boot_condition_contract` and `fallback_sources` hard-coded NOT_EXECUTED.
   It now captures the target systemd unit contract and bounded installed systemd machine-id
   manual evidence through the frozen C3/C4/R1 path. Missing evidence remains UNKNOWN/STOP.
4. E2/E3 previously re-read the Armbian firstrun source independently. The remote probe now
   shares one analysis and verifies source/config continuity around E2/E3; drift becomes
   STOP_TARGET_CHANGED and the evidence is invalidated.
5. A local SSH spawn failure was initially conflated with authorization consumption/T1 access.
   The executor now distinguishes a claimed-but-not-consumed local failure from a transport that
   actually started, while replay remains forbidden after a claim.

## 4. Focused review checklist

```text
A1_EXACT_SOURCE_AND_CONTRACT_BINDING=PASS
A2_STRICT_SSH_HOSTKEY_AND_SINGLE_REQUEST=PASS
A3_ONE_SHOT_AUTHORIZATION_CLAIM_NO_REPLAY=PASS
A4_BOUNDED_REMOTE_COMMAND_AND_TRANSPORT_OUTPUT=PASS
A5_PRIVATE_EVIDENCE_0700_0600_O_EXCL=PASS
A6_E1_E9_INTEGRATION_AND_E4_CAPTURE_PATH=PASS
A7_FIRSTRUN_SOURCE_CONFIG_CONTINUITY=PASS
A8_PRIVATE_TO_PUBLIC_ALLOWLIST_PROJECTION=PASS
A9_SAME_BOOT_AND_TARGET_DRIFT_FAIL_CLOSED=PASS
A10_NO_SEAL_DISK_CAPTURE_CLONE_OR_SERVICE_AUTHORITY=PASS
OPEN_SOURCE_BLOCKER_COUNT=0
```

The executor intentionally leaves `static_review_status=NOT_EXECUTED`,
`os_identity_semantics_proven=false`, `controlled_clone_boot_required=true` and
`disk_capture_ready=false`. A successful capture therefore cannot auto-enter Seal or clone
acceptance.

## 5. Exact-source CI closure

The exact validation head 7f7daca7f62e964147b715063d8ed17cf9be7767 has a complete
27/27 PASS workflow snapshot. The key gate runs are:

- Golden Master source CI: 38482867521 — success;
- Public repository safety CI: 38482867451 — success;
- Production stack staging payload CI: 38482867190 — success.

All 27 workflow runs associated with the validation head completed successfully; there is
no pending or failed workflow in this exact-head snapshot.

Fresh compare from validation head to current candidate head
0fb4a6787c81e180925e203aa687d2f47b99dc0d is one commit, adding only
docs/development/N3W_T1_GOLDEN_MASTER_R2C_REMOTE_EXECUTOR_SOURCE_CLOSURE_ARCHIVE_NEW_CHAT_HANDOFF_V1.0_20261014.md.
There is no source, test, or workflow drift after validation.

The remote executor source blob and its focused test blob remain unchanged from the reviewed
implementation. The 01256f67... → 7f7daca7... delta contains only the previously reviewed
Ruff bytes-fixture correction in tests/tools/test_n3w_t1_r2c_collectors.py; it does not
weaken remote-executor coverage.

## 6. Current closure and STOP point

```text
R2C_REMOTE_EXECUTOR_SOURCE_IMPLEMENTATION=COMPLETE
R2C_REMOTE_EXECUTOR_FOCUSED_REVIEW=PASS
R2C_REMOTE_EXECUTOR_SOURCE_CLOSURE=CLOSED_SOURCE
REMOTE_EXECUTOR_IMPLEMENTATION_HEAD=01256f67fc6b7496b476963ede37496abe099327
REMOTE_EXECUTOR_VALIDATION_HEAD=7f7daca7f62e964147b715063d8ed17cf9be7767
VALIDATION_HEAD_CI=27/27_PASS
CURRENT_CANDIDATE_HEAD=0fb4a6787c81e180925e203aa687d2f47b99dc0d
HANDOFF_ADVANCE=DOCS_ONLY
OPEN_SOURCE_BLOCKER_COUNT=0
EXECUTION_READY=false
ACTUAL_T1_EXECUTION_AUTHORIZATION_GRANTED=false
ACTUAL_R2C_EVIDENCE_EXECUTION=false
REAL_SEAL_MUTATION=false
DISK_CAPTURE=false
CLONE_ACCEPTANCE=false
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false
STOP=BEFORE_R2C_TARGET_ARMBIAN_READONLY_EVIDENCE_PREEXECUTION
```

This source gate is closed. Actual T1 read-only evidence still requires a fresh
target/host-key binding and a new explicit R2C authorization; it is not implied by
this repository source closure. No target execution, authorization claim, Seal/disk/clone
operation, board access, or merge is entered automatically.
