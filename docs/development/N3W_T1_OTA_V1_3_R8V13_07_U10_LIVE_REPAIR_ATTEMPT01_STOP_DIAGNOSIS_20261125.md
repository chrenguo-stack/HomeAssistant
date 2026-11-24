# N3-W T1 OTA V1.3 R8V13-07 U10 live-repair Attempt 01 stop diagnosis

Date: 2026-11-25

## Physical execution result

Attempt 01 entered the exact live-repair executor after the prior read-only preflight had passed.

Observed output:

```text
PHASE=LOCAL_ARTIFACT_BINDING
LOCAL_ARTIFACT_BINDING=PASS
PHASE=REMOTE_STAGE
PHASE=LIVE_REPAIR_PRECHECK
TRANSACTION_EXACT=PASS
TARGET_ENV_EXACT=PASS
CANDIDATE_RECOVERY_NORMALIZATION=PASS
PHASE=QUIESCE_RECOVERY_CONTROL_PLANE
RECOVERY_STARTED=false
RESULT=R8V13_07_U10_LIVE_REPAIR_AND_RECOVERY_STOP
```

No `PHASE=ATOMIC_RECOVERY_PYZ_PATCH` was reached. Therefore the successor recovery pyz was not published by this attempt.

## Source-level false-STOP defect

The Attempt 01 executor admitted the retry service before mutation when its state was either `inactive` or `failed`, but after stopping the recovery control plane it required the same service to be exactly `inactive`.

That is internally inconsistent: a failed service is already quiesced and can remain in `failed` after `systemctl stop`. Treating `failed` as non-quiesced at the second gate can produce a false STOP without any application/recovery mutation.

The exact quiesce gate was repaired to:

- require retry timer = `inactive`;
- accept retry service = `inactive` or `failed`;
- accept IPC socket/service = `inactive` or `failed`;
- emit all four quiesced states before later hash/candidate checks.

The executor fix commit is `eb8fa691ce73c7df89f9bcb5c56e948795c473c7`.
The focused regression test commit is `507c80bf7c872fda6eac8793e4f604036bd898fd`.

## Current boundary

```text
INSTALL_REPLAY_ALLOWED=false
SECOND_TRANSACTION_ALLOWED=false
RECOVERY_STARTED=false
SUCCESSOR_PYZ_PUBLISHED_BY_ATTEMPT01=false
R8V13_08_BLOCKED=true
LIVE_REPAIR_RETRY_PENDING_EXACT_CI=true
```

Focused CI run for exact head `507c80bf7c872fda6eac8793e4f604036bd898fd`:
`45514240797`.

At the time of this archival update it had not reached a terminal result. Per project polling policy no additional active polling is performed after three non-terminal checks.

Before another live-repair attempt, run the bounded read-only post-stop forensic check and require exact transaction/env/old-pyz state to remain compatible with the original U10 preflight. Then require the new focused CI to complete SUCCESS.
