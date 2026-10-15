# N3W T1 F3 R3 public-runtime candidate-root failure — 2026-10-15

## Live result

```text
GATE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R3_20261014_01
RESULT=STOP_PARTIAL

AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false
AUTOMATIC_RETRY=false

HOMEASSISTANT_IMAGE_REQUESTED=true
HOMEASSISTANT_IMAGE_LOADED=true
HOMEASSISTANT_STAGED_TAR_DELETED=true
MANAGER_IMAGE_REQUESTED=true
MANAGER_IMAGE_LOADED=true
MANAGER_STAGED_TAR_DELETED=true
BROKER_IMAGE_REQUESTED=true
BROKER_IMAGE_LOADED=true
BROKER_STAGED_TAR_DELETED=true

FAILED_STAGE=public_runtime
FAILURE_CODE=adapter_failure
CLEANUP_RESULT=PASS
REMOTE_PAYLOAD_PRESERVED=true
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

## KF-115 closure

R3 crossed the exact R2 failure point and successfully completed request, transfer, exact verification,
atomic publication, Docker load and staged-tar deletion for all three images. This is live evidence that the
KF-115 final-path publication race repair works on the real path.

```text
KF_115=CLOSED_PASS_LIVE_REVALIDATED
```

## New root cause: public-only candidate root is never created

The exact R3 source selects a fresh, non-existent transaction candidate path:

```python
candidate = Path("/var/tmp") / f"n3w-fresh-bootstrap-{secrets.token_hex(8)}"
```

The public-staging orchestration intentionally rejects a pre-existing candidate root, then calls
`stage_public_runtime(candidate)` directly after image loading. No earlier public-only stage creates the
candidate directory.

The exact live adapter then executes:

```python
stage = candidate_root / "stage"
...
stage.mkdir(mode=0o700)
```

without first creating `candidate_root` and without `parents=True`. Therefore the first real public-runtime
filesystem mutation deterministically raises a FileNotFoundError for the missing parent candidate directory.

The orchestration sanitizes non-contract adapter exceptions. A FileNotFoundError message contains spaces and
filesystem path characters, so it is collapsed to the generic public failure code `adapter_failure`.
This exactly matches the R3 live result:

```text
FAILED_STAGE=public_runtime
FAILURE_CODE=adapter_failure
```

This defect was not exercised by the current tests. The orchestration tests use fake adapters, while the
live-adapter tests do not call `stage_public_runtime()` with a non-existent public-only candidate root.

## Repair boundary

The source repair must preserve fail-closed transaction ownership:

1. On the public-only path, create the exact fresh candidate root atomically before creating `stage`.
2. Reject an already-existing or symlink candidate root.
3. Preserve the existing `reuse_stage=True` path used after instance staging.
4. Add a live-adapter regression test with a non-existent candidate root that proves the candidate and stage
   are created and the public runtime is staged.
5. Add a negative symlink/existing-root test.
6. Do not weaken cleanup, authorization, image binding, service-start, or production-activation guards.

A repaired live run requires a new exact source, new exact deployable artifact and a new one-shot authorization.
R3 is permanently consumed and must never be replayed.

```text
NEXT_ONE_GATE=N3W_T1_F3_PUBLIC_RUNTIME_CANDIDATE_ROOT_SOURCE_REPAIR_20261015_01
AUTO_EXECUTE_LIVE_RETRY=false
```
