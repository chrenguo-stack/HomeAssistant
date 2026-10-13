# N3-W T1 Golden Master R2C remote executor source implementation and review progress — 2026-10-14

## 1. Current result

```text
TASK=N3W_T1_GOLDEN_MASTER_R2C_REMOTE_EXECUTOR_SOURCE_IMPLEMENTATION_AND_REVIEW_20261014_01
SOURCE_CANDIDATE=01256f67fc6b7496b476963ede37496abe099327
PR=541
PR_STATE=OPEN_DRAFT
R2C_E5_E9_SOURCE=CLOSED_SOURCE
R2C_REMOTE_EXECUTOR=IMPLEMENTED_REVIEWED_CI_PENDING
FOCUSED_SOURCE_REVIEW=PASS_NO_OPEN_SOURCE_BLOCKER
EXACT_SOURCE_CI_CLOSURE=PENDING
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

## 5. Exact-source CI stop

For exact source candidate `01256f67fc6b7496b476963ede37496abe099327`, the third allowed
CI observation still showed the relevant runs queued:

- Golden Master source CI: run `38481657513`;
- Public repository safety CI: run `38481657467`.

There was no completed failure on this exact head at the stop. Per
`N3W_PROJECT_WORKING_CONTEXT.md`, do not continue polling this exact head in this reply.

Direct links:

- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/38481657513
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/38481657467
- https://github.com/chrenguo-stack/HomeAssistant/pull/541/checks

## 6. Current STOP point

```text
R2C_REMOTE_EXECUTOR_SOURCE_IMPLEMENTATION=COMPLETE
R2C_REMOTE_EXECUTOR_FOCUSED_REVIEW=PASS
R2C_REMOTE_EXECUTOR_SOURCE_CLOSURE=PENDING_EXACT_SOURCE_CI
EXECUTION_READY=false
ACTUAL_T1_EXECUTION_AUTHORIZATION_GRANTED=false
ACTUAL_R2C_EVIDENCE_EXECUTION=false
REAL_SEAL_MUTATION=false
DISK_CAPTURE=false
CLONE_ACCEPTANCE=false
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false
STOP=EXACT_SOURCE_CI_PENDING_AFTER_THIRD_POLL
```

If the exact-source CI becomes green, the next repository action is source closure/archive only.
Actual T1 read-only evidence still requires a fresh target/host-key binding and a new explicit
R2C authorization; it is not implied by this source gate.
