# N3W T1 F5 V2 post-reboot SSH boot-epoch race source repair

Date: 2026-10-21

## 0. Gate and safety boundary

~~~text
TASK=N3W_T1_F5_V2_POST_REBOOT_SSH_BOOT_EPOCH_RACE_SOURCE_REPAIR_20261021_01
BASE_MAIN=f3934f9c41790208d77e20a39b2f6e577394d3f8

REAL_T1_FAILED_RUN=TERMINAL_NO_REPLAY
RUN_ID_RAW_PUBLICATION=false
RUN_ID_SHA256=67fc973c09c1d7335197c64291454ff636643e4507dc3e177484b6c8b77a2569

T1_PRODUCTION_READY=false
TARGET_DISPOSITION=REFLASH_REQUIRED
IMMEDIATE_REFLASH=false

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_EXECUTION=false
WORKFLOW_DISPATCH=false
MERGE=false
~~~

The repair is source-only. The failed T1 remains reflash-required and must not be
used for another production attempt until repaired source is reviewed, merged,
rebuilt into a fresh exact release and locally validated.

## 1. New real-T1 failure evidence

The fresh exact-main production run reached the repaired operator-presence and
post-reboot path, then terminated as:

~~~text
STATUS=FAIL
TERMINAL_STAGE=POST_REBOOT_READINESS
ERROR_CLASS=POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
ERROR_CODE=reboot_not_observed
TARGET_FAILURE_CLASS=VERIFY_FAILED
MARKER_STATE=STARTED
T1_PRODUCTION_READY=false
REFLASH_REQUIRED=true
AUTOMATIC_RETRY=false
OPERATOR_SESSION_CLOSED=true
EVIDENCE_COMPLETE=true
~~~

Frozen forensics are complete and read-only:

~~~text
FORENSIC_MANIFEST=PASS
FORENSIC_UNAVAILABLE_COUNT=0
PRODUCTION_MARKER=OBSERVED
F4_TRANSACTION=OBSERVED
REBOOT_CLAIM=OBSERVED
SYSTEM_STATE=OBSERVED
SYSTEMD_STATE_AT_FORENSIC=stopping
~~~

The exact failure code is decisive. The installed reboot verifier raises
`reboot_not_observed` only when the current boot-id hash equals the
`pre_boot_id_sha256` stored in the consumed reboot claim, or that claim is
structurally invalid. The claim itself was observed and the failure class was
`VERIFY_FAILED`; therefore the current evidence supports the same-old-boot
case.

## 2. Root cause

The live executor currently proves only that the old SSH ControlMaster stopped
working before returning `REBOOT_PENDING`. Its next `wait_for_ssh()` step
treats a successful raw TCP connection to port 22 as post-reboot SSH readiness.

That leaves this race:

~~~text
systemctl reboot
-> old ControlMaster disconnects
-> old boot is still in systemd stopping
-> TCP/22 is still briefly reachable
-> WAIT_FOR_SSH returns PASS
-> SSH epoch #2 is opened against the old boot
-> POST_REBOOT_READINESS runs
-> reboot verifier sees current_boot == pre_boot
-> reboot_not_observed
~~~

Frozen real-T1 evidence matches this exact sequence because the failure occurred
with `systemd=stopping` and an unchanged boot identity.

~~~text
KF_126=F5_V2_POST_REBOOT_SSH_BOOT_EPOCH_RACE
ROOT_CAUSE_CONFIDENCE=HIGH
PERSISTENT_T1_RUNTIME_FAILURE_EVIDENCE=false
SSH_PASSWORD_FAILURE=false
SSH_HOST_KEY_DRIFT=false
KF_125_REGRESSION=false
SOURCE_REPAIR_REQUIRED=true
~~~

KF-125 remains a separate product-readiness race after a genuine new boot.
KF-126 occurs earlier: the executor can misclassify the shutdown tail of the old
boot as the beginning of the new SSH epoch.

## 3. Frozen repair invariant

A planned reboot must not enter post-reboot SSH waiting until the executor has
observed both:

~~~text
OLD_CONTROL_MASTER_DISCONNECTED=true
OLD_BOOT_TCP_22_DOWN_OBSERVED=true
~~~

The repaired sequence is:

~~~text
systemctl reboot
-> observe old ControlMaster disconnect
-> observe TCP/22 unreachable at least once
-> REBOOT_PENDING
-> close pre-reboot SSH epoch
-> WAIT_FOR_SSH
-> observe TCP/22 reachable
-> SSH epoch #2
-> POST_REBOOT_READINESS
-> boot identity must differ from pre-reboot claim
-> strict post-reboot acceptance
-> five external probes
-> existing 90-second stability observation
-> MARKER_ACCEPTED
~~~

The target-side `reboot_not_observed` guard remains unchanged. It is the final
fail-closed authority and must not be weakened into WAIT.

## 4. Source implementation

The repair is intentionally narrow and confined to the Mac live executor.

`tools/n3w_t1_production_v2_executor.py`:

- adds a raw TCP reachability helper;
- adds bounded polling constants for old-boot TCP/22 down observation;
- replaces the previous ControlMaster-only reboot-disconnect decision with
  `_wait_for_old_boot_ssh_down()`;
- requires both ControlMaster disconnect and a TCP/22 down observation before
  emitting `OLD_BOOT_SSH_DOWN` and `REBOOT_PENDING`;
- preserves the existing 45-second reboot-disconnect bound;
- preserves the existing 180-second post-reboot SSH-up bound;
- does not open another SSH epoch and does not request another password.

No change is required in the target-side reboot verifier or R3 orchestrator for
this defect. The existing `POST_REBOOT_READINESS` boot-identity check remains
the final guard against an unchanged boot.

## 5. Fail-closed behavior

~~~text
CONTROL_MASTER_DOWN_BUT_TCP_22_STILL_UP=WAIT
TCP_22_DOWN_OBSERVED_BUT_CONTROL_MASTER_STILL_UP=WAIT
BOTH_OBSERVED=ALLOW_REBOOT_PENDING
NO_TCP_22_DOWN_WITHIN_45S=FAIL:reboot_disconnect_not_observed
POST_REBOOT_TCP_22_NEVER_RETURNS=FAIL:post_reboot_ssh_timeout
POST_REBOOT_BOOT_ID_UNCHANGED=FAIL:reboot_not_observed
~~~

A transient network error cannot create a false production PASS because the
target-side boot-id comparison still runs before strict acceptance. The new
gate exists to prevent the known old-boot shutdown tail from being mistaken for
the new SSH epoch.

## 6. Preserved contracts

~~~text
ONE_PRODUCTION_APPROVAL=true
ONE_REBOOT_ARMING_BOUNDARY=true
SSH_PASSWORD_EPOCHS=2
THIRD_SSH_EPOCH=false
SECOND_PRODUCTION_APPROVAL=false

POST_REBOOT_READINESS_TIMEOUT_SECONDS=300
POST_REBOOT_READINESS_POLL_SECONDS=2
STRICT_TARGET_VERIFY_UNCHANGED=true
FIVE_EXTERNAL_PROBES_UNCHANGED=true
RUNTIME_STABILITY_OBSERVATION_SECONDS=90
BOARD_ACCESS=false
~~~

No fixed blind sleep is introduced.

## 7. Focused regression tests

The implementation adds focused tests proving:

1. ControlMaster disconnect alone is insufficient while TCP/22 remains up.
2. The gate succeeds only after TCP/22 is observed down.
3. If old TCP/22 never goes down within the bound, the executor fails closed.
4. `OLD_BOOT_SSH_DOWN` is emitted before `REBOOT_PENDING`.
5. The existing reboot arming remains before reboot actuation.
6. The existing readiness, strict acceptance, external probes and 90-second
   observation remain downstream and unchanged.

## 8. Release consequence

Any merged repair changes `v2_mac_tools`, so the current exact release is
historical and cannot be reused for another T1 production run.

Required route after source closure:

~~~text
SOURCE_REPAIR
-> INDEPENDENT_SOURCE_REVIEW
-> CI PASS
-> MERGE
-> F3/F4 EXACT ARTIFACT REBUILD
-> RELEASE_INPUTS REBUILD
-> FINAL EXACT RELEASE REBUILD
-> MAC LOCAL EXACT-RELEASE VALIDATION
-> REFLASH FAILED T1
-> STANDARD FRESH ARMBIAN READ-ONLY QUALIFICATION
-> NEW RUN_ID
-> NEW EXPLICIT PRODUCTION AUTHORIZATION
-> REAL T1 PRODUCTION
~~~

The failed run is never replayed.

## 9. Current source-repair gate

~~~text
BRANCH=fix/n3w-t1-f5-v2-post-reboot-ssh-boot-epoch-race-20261021
SOURCE_REPAIR_IMPLEMENTED=true
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
REFLASH=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F5_V2_POST_REBOOT_SSH_BOOT_EPOCH_RACE_SOURCE_REPAIR_REVIEW_20261021_01
~~~
