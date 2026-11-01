# N3W T1 F3 image-tar atomic publish R3 source repair — 2026-10-14

## 1. Gate

```text
TASK=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_IMAGE_TAR_ATOMIC_PUBLISH_SOURCE_REPAIR_20261014_01
RESULT=CLOSED_SOURCE_WITH_EXACT_R3_ARTIFACT

PR=544
BRANCH=fix/n3w-t1-f3-claim-marker-payload-set-20261014
REPAIRED_SOURCE_HEAD=4887a76ef61d176b38e3656a9b04f7e0f13bce2f
REPAIRED_SOURCE_TREE=8cdbd3ec5b83aa168d0559e2927421f9337e0d8b
SOURCE_CI=15_SUCCESS_0_FAILURE_0_PENDING

T1_MUTATION_DURING_SOURCE_REPAIR=false
BOARD_ACCESS=false
F4_AUTHORIZATION_GRANTED=false
MERGE=false
```

## 2. R2 live failure

The R2 live apply used the exact R2 artifact and a new one-shot authorization. Durable claim succeeded, proving
the KF-114 claim-marker repair on the real path. The run then stopped in `load_images`:

```text
R2_RESULT=STOP_PARTIAL
FAILED_STAGE=load_images
FAILURE_CODE=image_tar_binding_invalid
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false
CLEANUP_RESULT=PASS
REMOTE_PAYLOAD_PRESERVED=true
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

Post-failure read-only evidence showed a safe boundary:

```text
CONTAINERS=0
IMAGES=0
VOLUMES=0
NETWORKS=bridge,host,none
PRODUCT_LISTENERS=NONE
```

The preserved R2 Home Assistant tar was complete after the host-side transfer returned:

```text
HOMEASSISTANT_TAR_ACTUAL_SHA256=3cebb7b532237bb8841ae3f0a1ecb5d0b0a2bbd973ce6cb18c407229953efd1e
HOMEASSISTANT_TAR_MANIFEST_SHA256=3cebb7b532237bb8841ae3f0a1ecb5d0b0a2bbd973ce6cb18c407229953efd1e
R2_PAYLOAD_MANIFEST_SHA256=e2745281d37f675f6e769bc795c33a4dc766131ce44faa88ea9ffb4e87501fbf
ARTIFACT_OR_TRANSFER_CORRUPTION_PROVEN=false
```

## 3. Proven source root cause

The exact host wrapper transferred each image tar with `scp` directly to the final path under
`incoming/*.tar`. The remote installer treated final-path existence as the transfer-complete signal and
immediately checked size and SHA-256.

For a large image, `scp` creates the destination before all bytes have arrived. Therefore the remote installer
could observe the final pathname while the host was still writing it and fail the size/hash binding check.
The later forensic hash was correct because `scp` continued to completion after the remote installer had
already stopped.

```text
ROOT_CAUSE_CLASS=IMAGE_TRANSFER_COMPLETION_RACE
ROOT_CAUSE=SCP_WRITES_DIRECTLY_TO_FINAL_IMAGE_PATH_WHILE_REMOTE_INSTALLER_USES_FINAL_PATH_EXISTENCE_AS_COMPLETION_SIGNAL
```

## 4. Repair

The host wrapper now publishes an image only after full transfer and verification:

```text
SCP_TO_SIBLING_TEMP_PART
-> VERIFY_TEMP_SIZE_AND_SHA256
-> REQUIRE_TEMP_AND_FINAL_PARENT_ON_SAME_FILESYSTEM
-> ATOMIC_RENAME_TO_FINAL_INCOMING_PATH
-> REMOTE_INSTALLER_SEES_FINAL_PATH_ONLY_AFTER_COMPLETE_VERIFIED_TRANSFER
```

Additional guards:

- both the final image path and transfer-temp path must be absent before transfer;
- a transfer-temp residue is removed best-effort on host-side failure;
- the remote installer keeps its existing exact size/SHA-256 binding check;
- no sleep/timing heuristic and no validation relaxation were introduced;
- the regression test requires the order `scp(temp) -> verify(temp) -> atomic publish(final)`.

The consumed R2 authorization is not replayable. Source/artifact authority is rotated to:

```text
R3_AUTHORIZATION_ID=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R3_20261014_01
R3_AUTHORIZATION_GRANTED=false
R3_AUTHORIZATION_CLAIMED=false
R3_AUTHORIZATION_CONSUMED=false
```

## 5. CI and exact R3 artifact binding

The first repair commit exposed two bounded source-binding test updates: the bootstrap authorization assertion
still expected R2, and the F2 read-only execution package still pinned the previous staging-host blob. Both were
updated in the same source-repair gate.

Final exact source:

```text
SOURCE_HEAD=4887a76ef61d176b38e3656a9b04f7e0f13bce2f
SOURCE_TREE=8cdbd3ec5b83aa168d0559e2927421f9337e0d8b
SOURCE_CI=15_SUCCESS_0_FAILURE_0_PENDING
```

Exact deployable artifact:

```text
ARTIFACT_RUN_ID=38592674907
ARTIFACT_JOB_ID=115951322590
ARTIFACT_ID=11908830316
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-4887a76ef61d176b38e3656a9b04f7e0f13bce2f
ARTIFACT_SIZE_BYTES=2535581659
ARTIFACT_DIGEST=sha256:d10432c4c6caa8e7ce50ce4cf672ac966e3a190e3f0ddbd79866a1f26a878263
ARTIFACT_EXPIRES_AT=2026-11-13T15:53:08Z

RUNTIME_PAYLOAD_SHA256=c280c527debb6e47de202285867585f9eceb903e9da4d4598dd2301023cce68b
PAYLOAD_MANIFEST_SHA256=91088382aafc794bc90ecd8b3005d6eb148d080fb9fd14461faa936935c5c2c2
FRESH_CROSS_STORE_IMAGE_BINDING=PASS
FRESH_DOCKER_ARCHIVE_CONFIG_BINDING=PASS
FRESH_BOOTSTRAP_INNER_BINDING=PASS
FRESH_TRANSPORT_V2_POST_UPLOAD_BINDING=PASS
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS
```

## 6. KF status

```text
KF-114_STATUS=CLOSED_PASS_LIVE_REVALIDATED
KF-114_LIVE_PROOF=R2_DURABLE_CLAIM_SUCCEEDED_AND_REMOTE_APPLY_ADVANCED_TO_IMAGE_REQUESTED

KF-115_STATUS=GUARDED_SOURCE_LIVE_REVALIDATION_PENDING
KF-115_DOMAIN=PHYSICAL_HARNESS
KF-115_SYMPTOM=STOP_PARTIAL:load_images:image_tar_binding_invalid
KF-115_ROOT_CAUSE=SCP_DIRECT_FINAL_PATH_PUBLISH_RACED_REMOTE_FINAL_PATH_EXISTENCE_CHECK
KF-115_GUARD=TRANSFER_TO_TEMP_VERIFY_THEN_ATOMIC_RENAME_TO_FINAL
```

## 7. Next boundary

No R3 live authorization is granted by source/CI/artifact closure.

```text
NEXT_ONE_GATE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_R3_READONLY_PREAUTH_PREFLIGHT_20261015_01
AUTO_EXECUTE_NEXT_GATE=false

R2_AUTHORIZATION=CONSUMED_NO_REPLAY
R3_AUTHORIZATION_GRANTED=false
F4_AUTHORIZATION_GRANTED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

The next gate must fresh-rebind repository/PR/source/artifact and perform a minimum read-only target recheck.
Only after all preconditions pass may the user be asked to explicitly grant
`N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R3_20261014_01`.
