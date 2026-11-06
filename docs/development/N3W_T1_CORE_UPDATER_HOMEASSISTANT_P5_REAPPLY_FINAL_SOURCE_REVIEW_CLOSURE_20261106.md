# N3W T1 Core Updater Home Assistant P5 Reapply Final Source Review Closure

DATE=2026-11-06

## Review target

REAPPLY_SOURCE_HEAD=6194b6ce8134191a7ad176f4fd86c8b2382891c5

GATE_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_REAPPLY_PREAUTHORIZATION_REVIEW_20261106_01

PROPOSED_AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_REAPPLY_P5_20261106_01

POSTCLEANUP_PREFLIGHT_CLOSURE_BLOB_SHA=5151dd8a63de7132e169068356674db001daec76

## CI

CI_RESULT=16_OF_16_SUCCESS

HA_TARGET_BINDING_CI=PASS

MANAGER_A_TO_B_CI=PASS

CORE_STACK_AUTHORITY_CI=PASS

PUBLIC_REPOSITORY_SAFETY_CI=PASS

FAST_SOURCE_EXACT_CLOSURE_CI=PASS

## Independent final source review

SOURCE_REPAIR_REQUIRED=false

NEW_BLOCKER_COUNT=0

REAPPLY_SOURCE_READY_FOR_AUTHORIZATION=true

LIVE_REAPPLY_AUTHORIZED=false

MERGE=false

BOARD_ACCESS=false

### Pre-claim chain

The executor validates exact source authority and requires live_reapply_authorized=true before creating its evidence root or opening the T1 SSH transport.

After authorization, the executor still performs a fresh live preflight before writing authorization-claim.json.

The fresh preflight requires:
- the previous Home Assistant transaction to remain ROLLED_BACK;
- recovery_required=false;
- PREDECESSOR_BOUND_RUNNING / HEALTHY;
- current predecessor bindings and peer health unchanged;
- current baseline double-read stable;
- current baseline canonical SHA256 equal to the frozen P4 baseline;
- target plan prestate PRESENT_AND_EXACT;
- exact frozen archive verified;
- rollback_available=true.

The authorization claim is written only after that fresh preflight passes.

### Preexisting target / no reload path

Generic V2 plan verifies the frozen archive SHA256.

When the target image already exists, plan and apply verify archive-to-runtime portable image identity.

Generic V2 apply records candidate_image_preexisting=true.

Because target_prestate is non-null, docker load is skipped.

The successor post gate requires candidate_image_preexisting=true, so a successful closure proves the preexisting-image path was used.

The exact archive is still staged and verified. The successor does not weaken artifact identity to tag-only matching.

### Activation readiness

LocalHost.activate_component(homeassistant) calls start_services with HOMEASSISTANT_SERVICES_READINESS_TIMEOUT_SECONDS=600.

The widened 600-second readiness budget is therefore on the actual Home Assistant activation and automatic rollback path.

The outer remote apply timeout remains 3600 seconds.

### Automatic rollback

Generic V2 apply remains wrapped by automatic rollback.

Failure before quiesce produces a terminal ROLLED_BACK transaction with predecessor still running.

Failure after quiesce restores the predecessor binding, activates the predecessor, verifies peer continuity and A1 policy, and writes ROLLED_BACK.

If automatic rollback itself fails, the updater records FAILED_EMERGENCY rather than claiming PASS.

There is no explicit blind rollback route in the successor execution package.

### Existing transaction lifecycle

V2StateStore TERMINAL_TX_V2 includes COMMITTED and ROLLED_BACK.

prepare_new() accepts the existing Attempt 03 ROLLED_BACK transaction, archives it into transaction history, then permits the new transaction.

The successor therefore preserves Attempt 03 history instead of deleting or resetting it.

### Capacity model

The exact target image is already resident and must remain PRESENT_AND_EXACT at fresh preflight.

The successor still stages the 835309535-byte exact archive for identity verification.

The successor does not reserve a second image-unpack/import peak because docker load is not expected.

The capacity gate therefore requires staged exact archive bytes plus the existing 1.5 GiB post-peak reserve.

### Authorization boundary

No live mutation authority is granted by this source review.

A new explicit user authorization is required before live_reapply_authorized may be changed to true.

The consumed Attempt 03 authorization and consumed cleanup authorization remain non-replayable and are not reused.

## Final classification

POSTCLEANUP_READONLY_PREFLIGHT=CLOSED_PASS

REAPPLY_SOURCE_REVIEW=CLOSED_PASS

SOURCE_REPAIR_REQUIRED=false

NEW_BLOCKER_COUNT=0

REAPPLY_SOURCE_READY_FOR_AUTHORIZATION=true

LIVE_REAPPLY_AUTHORIZED=false

AUTHORIZATION_CLAIMED=false

AUTHORIZATION_CONSUMED=false

BOARD_ACCESS=false

MERGE=false
