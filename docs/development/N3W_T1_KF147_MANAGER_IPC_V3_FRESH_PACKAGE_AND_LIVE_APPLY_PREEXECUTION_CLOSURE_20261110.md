# N3-W T1 KF-147 Manager IPC V3 fresh package + live-apply preexecution closure — 2026-11-10

## 1. Result

```text
TASK=N3W_T1_KF147_MANAGER_IPC_V3_FRESH_PACKAGE_AND_LIVE_APPLY_PREEXECUTION_20261110_01
TASK_RESULT=CLOSED_PASS
PR=800

KF147_CAPACITY_BLOCKER=CLOSED_PASS
FRESH_MANAGER_PACKAGE_BINDING=CLOSED_PASS
LIVE_APPLY_PREEXECUTION=CLOSED_PASS

EXECUTABLE_SOURCE_HEAD=b85b98593fe4caaa7b5a4be63f344a85e815baa8
LATEST_DOCS_ALIGNED_HEAD=d2ddc1396ab072d6c1273ebea61b5b21fc9fdd3e
EXECUTABLE_TO_LATEST_DRIFT=DOCS_ONLY

LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

T1_ACCESS=false
T1_MUTATION=false
MANAGER_LIVE_APPLY=false
USB_MUTATION=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

The KF-147 disk-capacity blocker is already closed by measured post-cleanup capacity
evidence. This closure proves that the successor Manager-only live package is bound,
the current executable path has been independently reviewed, and the required
latest-head CI evidence is successful. It does not grant live execution authority.

## 2. Frozen Manager product input

```text
MANAGER_PRODUCT_SOURCE_HEAD=44e7d74727147975de88e85c4b18ba3f7493fd76
TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-44e7d7472714
TARGET_MANAGER_IMAGE_ID=sha256:fd5104d610645347fe47137dbb24121851fa8a48530df3e3c905704607c5e3d4

MANAGER_TAR_SHA256=9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5
MANAGER_TAR_SIZE_BYTES=62957568
```

The fresh package workflow independently re-materializes only the exact Manager
slice from the frozen exact ARM64 artifact, loads the image, verifies image identity,
recomputes the tar SHA-256 and size, emits a Manager-only binding, re-downloads the
uploaded package and verifies it again.

## 3. Bound package authority

Repository-owned live manifest:

`tools/execution_packages/n3w/r7a/kf147_manager_v3_live_apply/manifest.json`

Bound authority:

```text
BINDING_STATE=FRESH_ARTIFACT_BOUND

PACKAGE_WORKFLOW_RUN_ID=42761736604
PACKAGE_ARTIFACT_ID=13738561063
PACKAGE_ARTIFACT_NAME=n3w-kf147-manager-v3-live-44e7d7472714-20261110
PACKAGE_ARTIFACT_DIGEST=sha256:69af4054e993398c25bd7788773c76cc80f54524787d1f5972a894adef22bcfc

LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_STATE_GRANTED=false
AUTHORIZATION_STATE_CLAIMED=false
AUTHORIZATION_STATE_CONSUMED=false
REPLAY_PERMITTED=false
```

The package contains only:

```text
greenhouse-manager-arm64.tar
manager-live-binding.json
```

It does not carry a Home Assistant image, Broker image, host policy payload or USB
mutation payload.

## 4. Latest-head revalidation

At latest docs-aligned PR head
`d2ddc1396ab072d6c1273ebea61b5b21fc9fdd3e`, the Manager package workflow
completed successfully again:

```text
LATEST_HEAD_PACKAGE_RUN=42767681381
LATEST_HEAD_PACKAGE_RESULT=SUCCESS
LATEST_HEAD_PACKAGE_ARTIFACT_ID=13740492257
LATEST_HEAD_PACKAGE_ARTIFACT_DIGEST=sha256:b6de68d85fccda0c54336acce14a9c0a6e8567ce76ffdb5f887e7cbeb91267d9
```

This later artifact is revalidation evidence, not a silent replacement of the
repository-bound package authority. The bound artifact remains the exact authority
recorded in the manifest.

## 5. Required latest-head CI

The CI set required for this KF-147 package/preexecution gate is closed PASS:

```text
KF147_MANAGER_PACKAGE_RUN=42767681381
KF147_MANAGER_PACKAGE_RESULT=SUCCESS

CORE_STACK_CURRENT_AUTHORITY_RUN=42767681193
CORE_STACK_CURRENT_AUTHORITY_RESULT=SUCCESS

MANAGER_A_TO_B_RUN=42767681380
MANAGER_A_TO_B_RESULT=SUCCESS

FAST_SOURCE_EXACT_CLOSURE_RUN=42767681474
FAST_SOURCE_EXACT_CLOSURE_RESULT=SUCCESS

STORAGE_IMAGE_LIFECYCLE_RUN=42767681579
STORAGE_IMAGE_LIFECYCLE_RESULT=SUCCESS

PUBLIC_REPOSITORY_SAFETY_RUN=42767681280
PUBLIC_REPOSITORY_SAFETY_RESULT=SUCCESS
```

Therefore the KF-147 gate-required CI result is PASS.

## 6. PR-wide legacy artifact failures are isolated

Two PR-wide workflows remain red, but both fail only when attempting to download the
same historical artifact:

```text
HISTORICAL_MANAGER_ARTIFACT_RUN_ID=38040433177
HISTORICAL_MANAGER_ARTIFACT_ID=11665219740
GITHUB_ARTIFACT_LOOKUP=FOUND_0_ARTIFACTS
FAILURE=HISTORICAL_ARTIFACT_NOT_FOUND
```

Affected workflows:

```text
N3W_T1_PRODUCTION_STACK_STAGING_PAYLOAD_RUN=42767681505
N3W_T1_PRODUCTION_MANAGER_STATE_BINDING_RUN=42767681557
```

For the Manager-state-binding workflow, focused source tests and production Compose
validation pass before the historical artifact download step. The staging-payload
workflow fails at the same historical artifact lookup.

These failures are not treated as KF-147 Manager-only package failures. Repairing
them would broaden this gate into generic production staging/state-binding artifact
authority and is intentionally deferred. Consequently:

```text
KF147_GATE_REQUIRED_CI=PASS
PR_WIDE_ALL_GREEN=false
PR_MERGE_READY=false
```

## 7. Exact U1 / USB anti-drift repair

Independent preexecution review found that the earlier executor validated U1
semantics but did not bind the already accepted exact U1 file identity or exact USB
candidate fingerprint. The executable was repaired at:

```text
EXECUTABLE_SOURCE_HEAD=b85b98593fe4caaa7b5a4be63f344a85e815baa8

EXPECTED_U1_TRANSACTION_SHA256=6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49
EXPECTED_USB_CANDIDATE_FINGERPRINT=e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93
```

Any mismatch now stops before Manager image load, service stop, Compose environment
rewrite or other Manager/service mutation.

The executor also still requires:

- exact predecessor Manager ref and accepted T1 runtime image ID;
- exact Home Assistant ref/runtime image ID;
- exact Broker ref/runtime image ID;
- U1 phase `U1_PREPARE_REQUESTED`, ACTIVE transaction and exact target archive identity;
- confirmation unconsumed;
- exactly one eligible unmounted writable `Extreme` USB candidate of 32017047552 bytes;
- required services active;
- Manager V3 absent before the upgrade;
- exact Manager tar identity;
- pre-transfer free-space admission.

## 8. Mutation and rollback boundary

The execution contract remains Manager-only:

```text
MANAGER_IMAGE_MUTATION=true
APPLICATION_OWNER_RESTART_REQUIRED=true

HOMEASSISTANT_IMAGE_MUTATION=false
HOMEASSISTANT_CONTAINER_RECREATE=false
BROKER_MUTATION=false
HOST_POLICY_MUTATION=false
HOST_SOURCE_MUTATION=false

U1_TRANSACTION_RESET=false
PREPARE_REPLAY=false
CONFIRM_USB_ERASE=false
USB_MUTATION=false
U2_PLUS=false
AUTOMATIC_RETRY=false

REMOTE_LOCAL_ROLLBACK=true
BOARD_ACCESS=false
MERGE=false
```

The remote executor snapshots the Compose environment before mutation. Once the
application-owner quiesce boundary is crossed, a failure attempts a local rollback
to the exact predecessor Manager and revalidates Home Assistant, Broker and U1
continuity. Authorization is one-shot and is not replayable after claim.

## 9. Preserved live state from capacity closure

The latest accepted live evidence before this preexecution closure remains:

```text
FREE_BYTES=5811048448
REQUIRED_FREE_BYTES=1736515716
POST_PEAK_FREE_BYTES=5685145468
CAPACITY_PASS=true

U1_PHASE=U1_PREPARE_REQUESTED
TRANSACTION_SHA256=6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49
CONFIRMATION_REQUIRED=true
CONFIRMATION_CONSUMED=false
USB_CANDIDATE_MODEL=Extreme
USB_CANDIDATE_CAPACITY_BYTES=32017047552
USB_CANDIDATE_PUBLIC_FINGERPRINT=e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93
```

The live executor is fail-closed if this state has drifted by execution time.

## 10. Authorization boundary

```text
PROPOSED_LIVE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_20261110_01
REQUIRED_CONFIRMATION=EXECUTE KF147 MANAGER IPC V3 IMAGE ONLY LIVE APPLY: YES

LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

EXPLICIT_USER_AUTHORIZATION_REQUIRED=true
AUTO_EXECUTE=false
```

A future explicit authorization may permit the bounded Manager-only live apply.
It does not authorize USB erase, PREPARE replay, U2+, broad Docker cleanup, board
access, merge or unrelated production-staging repair.

## 11. Final state

```text
KF147_EXACT_HA_CLEANUP=CLOSED_PASS
KF147_FRESH_CAPACITY=CLOSED_PASS
KF147_CAPACITY_BLOCKER=CLOSED_PASS

KF147_FRESH_MANAGER_PACKAGE=CLOSED_PASS
KF147_MANAGER_LIVE_APPLY_PREEXECUTION=CLOSED_PASS

NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_20261110_01
NEXT_GATE_REQUIRES_EXPLICIT_USER_AUTHORIZATION=true

T1_ACCESS=false
T1_MUTATION=false
MANAGER_LIVE_APPLY=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```
