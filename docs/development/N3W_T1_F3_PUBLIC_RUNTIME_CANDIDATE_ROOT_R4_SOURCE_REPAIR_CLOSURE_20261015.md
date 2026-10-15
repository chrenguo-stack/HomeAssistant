# N3W T1 F3 public-runtime candidate-root R4 source repair closure — 2026-10-15

```text
GATE=N3W_T1_F3_PUBLIC_RUNTIME_CANDIDATE_ROOT_SOURCE_REPAIR_20261015_01
RESULT=CLOSED_PASS_SOURCE_AND_EXACT_ARTIFACT

SOURCE_REPAIR_HEAD=6ac82ae0872b05644e59470ffef7307dad14d359
CI=15_SUCCESS_0_FAILURE_0_PENDING

R4_AUTHORIZATION_ID=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R4_20261015_01
R4_AUTHORIZATION_GRANTED=false
R4_AUTHORIZATION_CLAIMED=false
R4_AUTHORIZATION_CONSUMED=false

R4_ARTIFACT_RUN_ID=38667524241
R4_ARTIFACT_JOB_ID=116202761687
R4_ARTIFACT_ID=11942497052
R4_ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-6ac82ae0872b05644e59470ffef7307dad14d359
R4_ARTIFACT_DIGEST=sha256:1a8813b788fc4d597acfaafee417daa4bf6fc4bd3ea547d22dd1d689c462c4af
R4_ARTIFACT_SIZE_BYTES=2535581756
R4_RUNTIME_PAYLOAD_SHA256=684ba798157b285916d20b9ad837c4c00d26da969dfdc44ee7153266a997feba
R4_PAYLOAD_MANIFEST_SHA256=fbc92e7d9fe45096385a1b7ba99b7c391308cc4c5bd415bc33d002aff5d750ed

FRESH_CROSS_STORE_IMAGE_BINDING=PASS
FRESH_DOCKER_ARCHIVE_CONFIG_BINDING=PASS
FRESH_BOOTSTRAP_INNER_BINDING=PASS
FRESH_TRANSPORT_V2_POST_UPLOAD_BINDING=PASS
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
F4_AUTHORIZATION_GRANTED=false
MERGE=false
```

## Repair

The public-only live adapter now rejects a symlink or pre-existing candidate root, creates the exact fresh
candidate root with mode 0700, then creates its stage child. The legacy `reuse_stage=True` path remains
fail-closed and requires an already-existing real candidate directory and stage directory.

Regression coverage now includes:
- fresh public candidate-root creation;
- pre-existing candidate-root rejection;
- symlink candidate-root rejection;
- reuse-stage rejection when stage is missing.

The first exact-head CI attempt exposed only an incomplete test manifest fixture (`source_head` missing);
that test-only defect was repaired at the final exact source head above. Final exact-head CI is 15/15 SUCCESS.

KF-116 remains live-revalidation pending. No R4 live authorization has been granted.

```text
NEXT_ONE_GATE=N3W_T1_F3_R4_READONLY_PREAUTH_PREFLIGHT_20261015_01
AUTO_EXECUTE_R4_LIVE_APPLY=false
```
