# N3W T1 U9+ bounded recovery — source implemented / physical acceptance pending

DATE=2026-11-19
GATE=N3W_T1_U9_PLUS_BOUNDED_RECOVERY_SOURCE_REVIEW_AND_ACCEPTANCE_DESIGN
PR=807
DEFAULT_MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
SOURCE_IMPLEMENTATION_HEAD=22f8da382ef50af3f2133b3027b0d2e49236cdef
LIVE_STAGE=U9_LIVE_AUTHORIZATION_CLAIMED
U9_TRANSACTION_SHA256=2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b
U9_AUTHORIZATION=CONSUMED_NO_REPLAY

## Result

KF-168's product source gap is implemented. The HA OTA daemon now owns a
phase-gated U9+ bounded-recovery coordinator and composes the existing U13B
reconciliation/rollback stack. No parallel recovery implementation was added.

On daemon/host re-entry in U9-U12, the product chooses rollback rather than
guessing that an interrupted forward mutation completed. Recovery never claims
or replays U9 authorization. Bound recovery media absence/mismatch becomes
RECOVERY_MEDIA_REQUIRED rather than automatic formatting or substitution.

## Customer-visible completion contract

ROLLED_BACK is exposed only after all of the following are true:

1. exact predecessor runtime is healthy;
2. Home Assistant HTTP is ready;
3. Manager is ready;
4. Broker continuity is healthy;
5. fresh greenhouse telemetry after recovery is accepted by Manager and
   produces a new Home Assistant Recorder state;
6. the durable U13B3 exact pre-upgrade data-restore proof is retained and the
   Recorder history database remains readable;
7. Host and the bound USB terminal transaction authorities are exact;
8. the consumed U9 authorization identity is unchanged.

The exact backup/tree comparison remains before service restart. It is not
re-run against the live Recorder after new telemetry, because legitimate
post-recovery database writes would otherwise create a false failure.

## Validation status

CI_FINAL_ALLOWED_POLL=18_SUCCESS_0_FAILURE_4_RUNNING
CI_P3_LIVE_READONLY_SOURCE=44428121767_SUCCESS
CI_P3_ACCEPTANCE_CLEAN_OTA_SOURCE=44428121744_SUCCESS
CI_FAST_SOURCE_EXACT_CLOSURE=44428121732_SUCCESS
CI_CORE_STACK_CURRENT_AUTHORITY=44428121703_SUCCESS
CI_PUBLIC_REPOSITORY_SAFETY=44428121662_SUCCESS

CI_PENDING_MANAGER_A_TO_B=44428121642
CI_PENDING_HA_2026_10_3_TARGET_BINDING=44428121787
CI_PENDING_HA_2026_10_4_TARGET_BINDING=44428121752
CI_PENDING_HA_2026_10_4_SAME_VERSION_ARTIFACT=44428121785

Polling stopped by repository rule after the permitted cadence. The remote
runs were not cancelled or retriggered.

## Physical boundary

REAL_T1_ACCESS=false
REAL_T1_MUTATION=false
SERVICE_WRITE=false
SERVICE_RESTART=false
DESTRUCTIVE_U10=false
TARGET_LOAD=false
U11_PLUS=false
MERGE=false

The current live T1 is still at durable U9. Installing or restarting this new
daemon there would immediately enter product recovery, so that operation is
itself outside this source gate.

KF168_STATUS=OPEN_SOURCE_IMPLEMENTED_KEY_CI_PASS_FULL_CI_AND_PHYSICAL_ACCEPTANCE_PENDING
NEXT_ONE_GATE=N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE
NEXT_GATE_REQUIRES_EXPLICIT_AUTHORIZATION=true

Physical closure must measure the full customer outage from the real service
stop through the customer-visible completion oracle. Source CI alone does not
prove the physical <=15-minute post-cutover engineering objective.
