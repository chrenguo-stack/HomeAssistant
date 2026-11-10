# N3-W T1 KF-147 fresh rebind and capacity preflight entry — 2026-11-10

## 1. Result

```text
TASK=N3W_T1_KF147_FRESH_REBIND_AND_CAPACITY_PREFLIGHT_ENTRY_20261110_01

PROJECT_PREREQUISITE_AUDIT=PASS
KF147_REPOSITORY_FRESH_REBIND=PASS
KF147_CAPACITY_PREFLIGHT_SOURCE=PASS
KF147_FRESH_T1_CAPACITY_EVIDENCE=PENDING_READONLY_EXECUTION
KF147_CAPACITY_GATE_FINAL_RESULT=PENDING

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
REMOTE_STAGING=false
MANAGER_TAR_STREAMED_TO_T1=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This record enters the fresh KF-147 recovery route after the 2026-11-10
readiness/Core-Updater/storage prerequisite queue closed. It does not reuse the
2026-11-09 live package or authorization and does not claim live capacity PASS
without a new T1 read-only observation.

## 2. Project milestone / prerequisite audit

The current project authority and the V0.7 dependency model were reviewed
together.

Public N3-W phase closure remains:

```text
N3W_PHASE_CLASSIFICATION=N3W_COMPLETE_WITH_RECORDED_DEVIATIONS
N3W_EXIT_BLOCKER_COUNT=0
N3L_ENTRY_ELIGIBLE=true
N3L_AUTHORIZED=false
```

The normal-product Pre-U1 acceptance remains CLOSED_PASS through G0-G5.

The immediate T1 repair queue is now:

```text
NEXT_1_READINESS_DESIGN=CLOSED_PASS
NEXT_1_READINESS_IMPLEMENTATION=NOT_EXECUTED_NONBLOCKING
NEXT_2_CORE_UPDATER_DEPLOYED_ASSET_INTEGRITY=CLOSED_PASS
NEXT_3_STORAGE_HEADROOM_IMAGE_LIFECYCLE=CLOSED_PASS
```

The readiness implementation debt is not promoted to complete. It remains a
separate later source repair. KF-147 preflight must not use the authenticated
readiness helper as a runtime health probe because that helper opens a real MQTT
connection with the production Home Assistant service identity.

Other OPEN/guarded historical KFs remain tracked in
`KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`, but current-state authority does not
place them in the KF-147 prerequisite chain. Relevant execution guards remain
applicable, especially the versioned-executor / SSH-stdin ownership rules from
KF-078.

## 3. Fresh repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
PR=800
PR_STATE=OPEN_DRAFT_UNMERGED
CANDIDATE_REF=feat/n3w-ha-usb-r7a-prepare-pipeline-20261107

KF147_REBIND_EXECUTABLE_HEAD=fb63707edc1ab063ddc97de8475303df8daecfb1
PRIOR_HA_READONLY_COMPAT_REPAIR_HEAD=3691704bbf28eeb3ec6a85326480ab13a74f93b6
```

From the Manager V3 product source authority
`44e7d74727147975de88e85c4b18ba3f7493fd76` to the fresh rebind candidate,
there is no diff under:

```text
host/greenhouse-manager/src/*
infra/n3w-t1/production/*
```

Current differences are updater/control-plane work, so the already-built Manager
V3 product image remains the candidate image material. This does not make the old
live package reusable.

## 4. Historical package / authorization status

```text
KF147_OLD_LIVE_PACKAGE_REUSABLE=false
KF147_OLD_LIVE_AUTHORIZATION_REUSABLE=false
KF147_OLD_AUTHORIZATION_CLAIM_ALLOWED=false
```

The old package CI now correctly rejects current-source drift. That is evidence
that a new live package/manifest binding is required, not a reason to replay the
old package.

The historical Manager-only artifact was re-downloaded only to recover and verify
the immutable Manager tar as capacity-planning input. No old execution manifest or
authorization is consumed.

Verified candidate material:

```text
MANAGER_PRODUCT_SOURCE_HEAD=44e7d74727147975de88e85c4b18ba3f7493fd76
MANAGER_TARGET_IMAGE=local/greenhouse-manager:fresh-44e7d7472714
MANAGER_TARGET_IMAGE_ID=sha256:fd5104d610645347fe47137dbb24121851fa8a48530df3e3c905704607c5e3d4

CANDIDATE_MATERIAL_ARTIFACT_ID=13681899131
CANDIDATE_MATERIAL_ARTIFACT_EXPIRED=false
MANAGER_TAR_SHA256=9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5
MANAGER_TAR_SIZE_BYTES=62957568
MANAGER_DOCKER_SAVE_REGULAR_MEMBER_BYTES=62945412
```

## 5. Fresh capacity policy

Authority:

`infra/n3w-t1/updater-releases/storage-image-lifecycle-policy.json`

The gate uses:

```text
FREE_BYTES
>=
EXACT_STAGED_TRANSPORT_BYTES
+ EXACT_IMAGE_IMPORT_WORST_CASE_BYTES
+ DERIVED_POST_PEAK_RESERVE_BYTES
```

For this Manager-only candidate:

```text
EXACT_STAGED_TRANSPORT_BYTES=62957568
EXACT_IMAGE_IMPORT_WORST_CASE_BYTES=62945412
PERSISTENT_CONTROL_SOURCE_STAGED=false
```

The successor live route must preserve
`PERSISTENT_CONTROL_SOURCE_STAGED=false`; if a later package design stages any
additional persistent control file, capacity must be recalculated before that
package can be bound.

The reserve remains fresh-evidence-derived:

```text
max(
  1 GiB,
  10 percent of measured filesystem total,
  8 * measured mutable allocated bytes
)
rounded upward to 256 MiB
```

Using the prior accepted 1.5 GiB maintenance reserve only as a reference
calculation gives:

```text
REFERENCE_REQUIRED_FREE_BYTES=1736515716
REFERENCE_REQUIRED_FREE_GIB=1.6173
LAST_PROVEN_POST_ENOSPC_FREE_BYTES=592859136
LAST_PROVEN_POST_ENOSPC_FREE_GIB=0.5521
REFERENCE_DEFICIT_VS_LAST_PROVEN_BYTES=1143656580
```

These old numbers are not a fresh capacity verdict. They show why fresh T1
measurement is mandatory and why no large payload may be staged first.

## 6. Fresh read-only capacity preflight source

New tool:

`tools/n3w_t1_kf147_fresh_capacity.py`

Regression coverage:

`tests/tools/test_n3w_t1_kf147_fresh_capacity.py`

The tool:

- verifies the exact Manager tar SHA-256 and byte size locally;
- computes Docker-save import worst case from regular members;
- reads the actual staging / Docker / image-store topology;
- requires staging, Docker and image store to resolve to one device;
- reads fresh filesystem total/free bytes;
- measures selected persistent/maintenance allocated bytes plus container writable layers;
- requires Manager/Home Assistant/Broker to remain running at the expected live identities;
- reads the preserved U1/Extreme confirmation state without mutating it;
- computes the current capacity result;
- does not create a remote staging directory;
- does not send the Manager tar to T1;
- does not start/stop/restart services;
- does not mutate Docker, USB, credentials, boards or transaction state.

## 7. Source validation

At the executable rebind head:

```text
FAST_SOURCE_RUN=42739941332
FAST_SOURCE_RESULT=SUCCESS

STORAGE_IMAGE_LIFECYCLE_RUN=42739941127
STORAGE_IMAGE_LIFECYCLE_SOURCE_AND_POLICY=SUCCESS

HA_TARGET_BINDING_RUN=42739941238
HA_TARGET_BINDING_SOURCE=SUCCESS
HA_TARGET_BINDING_EXACT_BINDING=IN_PROGRESS_AT_POLL_STOP

CORE_UPDATER_MANAGER_A_TO_B_RUN=42739941185
CORE_UPDATER_SOURCE=SUCCESS
CORE_UPDATER_EXACT_MANAGER_SLICE=IN_PROGRESS_AT_POLL_STOP
```

The earlier Home Assistant target-binding source failure was a real local
integration regression: historical P4 read-only bundles imported the new
finalize-only module transitively. It was repaired at
`3691704bbf28eeb3ec6a85326480ab13a74f93b6` by making finalize imports lazy;
the subsequent HA target-binding source job passed.

The two still-running exact jobs are not used as substitutes for the fresh KF-147
capacity evidence. Active polling stopped at the project polling limit.

## 8. Next ONE gate

```text
NEXT_ONE_GATE=N3W_T1_KF147_FRESH_CAPACITY_READONLY_EXECUTION_20261110_01

ALLOWED=
fresh exact candidate tar materialization;
fresh T1 read-only SSH epoch;
storage topology/free-space observation;
mutable allocation observation;
core-service identity/running observation;
preserved U1/Extreme/confirmation observation;
local capacity calculation;
private evidence capture;
public-safe GitHub closure

FORBIDDEN=
remote manager-tar staging;
Manager image load/recreate;
old authorization claim/replay;
PREPARE replay;
CONFIRM_USB_ERASE;
USB mutation;
U2+;
broad Docker prune;
board access;
merge
```

PASS advances to:

```text
NEW_PACKAGE_MANIFEST_BINDING
```

STOP on insufficient capacity or any authority/runtime/U1 drift. A capacity STOP
does not authorize automatic cleanup or live repair.
