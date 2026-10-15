# N3W T1 F3 R4 live apply closure — 2026-10-15

```text
TASK=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R4_20261015_01
RESULT=CLOSED_PASS

R4_EXECUTABLE_SOURCE_HEAD=6ac82ae0872b05644e59470ffef7307dad14d359
R4_SOURCE_CI=15_SUCCESS_0_FAILURE_0_PENDING
R4_ARTIFACT_ID=11942497052
R4_ARTIFACT_DIGEST=sha256:1a8813b788fc4d597acfaafee417daa4bf6fc4bd3ea547d22dd1d689c462c4af

R4_AUTHORIZATION=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R4_20261015_01
R4_AUTHORIZATION_CLAIMED=true
R4_AUTHORIZATION_CONSUMED=true
R4_REPLAY_PERMITTED=false

HOMEASSISTANT_IMAGE_REQUESTED=true
HOMEASSISTANT_IMAGE_LOADED=true
HOMEASSISTANT_STAGED_TAR_DELETED=true
MANAGER_IMAGE_REQUESTED=true
MANAGER_IMAGE_LOADED=true
MANAGER_STAGED_TAR_DELETED=true
BROKER_IMAGE_REQUESTED=true
BROKER_IMAGE_LOADED=true
BROKER_STAGED_TAR_DELETED=true

PUBLIC_PRODUCT_STAGED=true
INSTANCE_MATERIAL_ABSENT=true
EXPLICIT_PROVISIONING_REQUIRED=true
ACTIVATION_AUTHORIZED=false
PRODUCTION_SERVICE_START=false
REMOTE_PAYLOAD_REMOVED=true
BOARD_ACCESS=false

KF_116=CLOSED_PASS_LIVE_REVALIDATED

EXPLICIT_DEVICE_PROVISIONING_EXECUTED=false
F4_ENTERED=false
BOARD_GATE_ENTERED=false
MERGE=false

NEXT_ONE_GATE=NONE:R4_CLOSURE_STOP
AUTO_EXECUTE_NEXT_GATE=false
```

The first operator invocation in this chat stopped before durable claim because the initial password-authenticated
SSH read-only check exceeded its timeout while waiting at the password prompt. That attempt reported
`STOP_PRECLAIM`, `authorization_claimed=false`, `authorization_consumed=false`, no payload transfer,
no Docker mutation and no production service start. It therefore did not consume the R4 one-shot authorization.

The subsequent exact frozen R4 execution passed. All three exact ARM64 images reached
`image_requested -> image_loaded`, and every staged image tar was deleted after load. The bootstrap then
reported `public_product_staged=true`, `instance_material_absent=true`,
`explicit_provisioning_required=true`, `activation_authorized=false`, and
`production_service_start=false`.

The host wrapper independently closed with `status=PASS`,
`authorization_claimed=true`, `authorization_consumed=true`, `replay_allowed=false`, and
`remote_payload_removed=true`. The R4 authorization is therefore permanently consumed and must not be replayed.

This live result closes KF-116: the repaired public-only candidate-root path completed successfully on the real
T1 and no longer failed at `public_runtime`.

R4 stops at the public product staging boundary. Explicit per-device provisioning, F4 production service
activation/end-to-end acceptance, board/USB/serial/Flash/NVS/RF work, and PR #544 merge were not entered and
remain separate future decisions.
