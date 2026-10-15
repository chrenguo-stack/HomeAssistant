# N3W T1 F3 claim-marker payload-set failure and R2 source repair — 2026-10-14

## 1. Live failure classification

Gate:

```text
N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_20261014_01
```

Observed terminal result:

```text
REMOTE_BOOTSTRAP_STATUS=STOP_PARTIAL
REMOTE_BOOTSTRAP_REASON=payload_file_set_invalid
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false

HOST_WRAPPER_STATUS=STOP_PARTIAL
REMOTE_PAYLOAD_PRESERVED=true
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

The consumed authorization MUST NOT be replayed.

## 2. Deterministic source root cause

Exact deployed artifact source:

```text
SOURCE_HEAD=3e05e82a7d7e871d2966e78e8cb5caff601a0152
```

The host wrapper deliberately performs a durable claim before live product apply.

`_claim_authorization()` writes the root-level marker:

```text
.authorization-claimed
```

inside the extracted payload directory.

The later `execute_apply()` immediately calls `_load_manifest(payload_root)`.

Before this repair, `_load_manifest()` built its actual file inventory by excluding only
`payload-manifest.json`. Therefore the legitimate claim marker itself was interpreted as an unexpected
payload file and deterministically caused:

```text
payload_file_set_invalid
```

This is a source defect in the split claim -> apply path, not evidence of target payload corruption.

## 3. Mutation boundary at failure

The failure occurs at the first `_load_manifest()` inside `execute_apply()`, before construction of the
live installer adapters and before product public staging starts.

The host wrapper source path performs fresh-host Docker/Compose baseline installation after authorization
claim and before invoking remote apply when the preclaim baseline was MISSING. Therefore the post-failure
target is expected to be Docker-ready, but this remains a source-derived expectation until a new read-only
target probe confirms it.

Current conservative classification:

```text
PUBLIC_PRODUCT_STAGING=NOT_STARTED_BY_EXECUTE_APPLY
PRODUCTION_SERVICE_START=false
F4_NOT_ENTERED=true

DOCKER_BASELINE_POSTFAILURE=EXPECTED_INSTALLED_PENDING_READONLY_CONFIRMATION
OLD_REMOTE_PAYLOAD=PRESERVED
OLD_AUTHORIZATION_LEDGER=PRESENT_BY_CLAIM_EVIDENCE
OLD_AUTHORIZATION_REPLAY_ALLOWED=false
```

No target cleanup or retry is authorized by this document.

## 4. R2 source repair

Repair branch:

```text
fix/n3w-t1-f3-claim-marker-payload-set-20261014
```

Repair semantics:

1. `_load_manifest()` excludes only the exact root-level `CLAIM_MARKER_NAME` from immutable payload-file
   inventory comparison, in addition to `payload-manifest.json`.
2. Every other unknown file remains a hard payload-file-set failure.
3. Authorization marker correctness remains independently validated by
   `_authorization_record_matches()`.
4. A regression test proves that the claim marker is not treated as payload inventory drift.
5. The consumed authorization ID is rotated for any future retry.

Old consumed authorization:

```text
N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_20261014_01
```

R2 source-bound candidate authorization:

```text
N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R2_20261014_01
```

The R2 authorization is a source/artifact binding only at this stage. It is NOT live-authorized.

## 5. Required next sequence

```text
SOURCE_REPAIR_CI
  -> NEW_EXACT_R2_ARTIFACT_BUILD_AND_BINDING
  -> FRESH_READONLY_POSTFAILURE_TARGET_PROBE
  -> EXPLICIT_NEW_R2_LIVE_AUTHORIZATION_DECISION
  -> R2_LIVE_APPLY
```

A new exact artifact is mandatory because the old artifact contains both the claim-marker defect and the
already-consumed authorization ID.

F4 production service activation remains separately unauthorized.

## 6. Safety boundary

```text
OLD_AUTHORIZATION_REPLAY=false
TARGET_MUTATION_DURING_SOURCE_REPAIR=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
F4_AUTHORIZATION=false
NEW_R2_LIVE_AUTHORIZATION_GRANTED=false
```
