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

## 9. First live attempt false STOP and source repair

The first live read-only execution reached T1 successfully and stopped before
capacity evaluation:

```text
STATUS=STOP
REASON=live_image_id_drift:manager
REMOTE_STAGING=false
MANAGER_TAR_STREAMED_TO_T1=false
MUTATION=false
```

Private evidence remains local and is publicly represented only by this sanitized
binding:

```text
PRIVATE_EVIDENCE_PRESENT=true
PRIVATE_EVIDENCE_PATH_CLASS=LOCAL_PRIVATE_N3W_KF147_CAPACITY_EVIDENCE
PRIVATE_EVIDENCE_SHA256=7e2dd8e7473068bb2e4c3ccdc28e6622b676c34fab6e69ec5823503908e49247
PRIVATE_EVIDENCE_SIZE=260
PRIVATE_EVIDENCE_CREATED_AT=2026-11-10T10:22:46+0800
PRIVATE_EVIDENCE_PURPOSE=KF147_FIRST_FRESH_CAPACITY_READONLY_FALSE_STOP
SECRET_VALUES_INCLUDED=false
```

The cause was a source-side oracle error. `EXPECTED_LIVE_IMAGE_IDS` used the
historical build-side image IDs while the accepted A1R, Boundary-B and 2026-11-09
live evidence binds the running T1 images to:

```text
MANAGER_RUNTIME_IMAGE_ID=sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b
HOMEASSISTANT_RUNTIME_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
BROKER_RUNTIME_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
```

The issue affects all three components even though fail-fast ordering exposed
Manager first. Source repair:

```text
KF111_REGRESSION_FIX_HEAD=0ca17193a39f9b9f96da33b4ae9a5a4cc574e27d
FOCUSED_CAPACITY_TESTS=10_PASS
FOCUSED_STORAGE_AND_CAPACITY_TESTS=21_PASS
RUFF=PASS
PY_COMPILE=PASS
GITHUB_CI=PENDING
FRESH_POST_FIX_T1_READONLY_EXECUTION=PENDING
```

This is a recurrence of the existing KF-098/KF-111 cross-image-store identity
guard, not a new independent failure class. The regression suite now asserts the
accepted runtime IDs as literal evidence and
separately proves that a real runtime-ID drift still fails closed. Capacity PASS,
new package/manifest binding and live retry remain unclaimed.

## 10. Post-fix fresh capacity result

After the live-image oracle repair passed the Storage/Image Lifecycle and Fast
Source CI, a new read-only execution reached the capacity calculation:

```text
STATUS=STOP
NEXT_ACTION=STOP_CAPACITY_INSUFFICIENT
FILESYSTEM_TOTAL_BYTES=14453903360
FREE_BYTES=589799424
STAGED_TRANSPORT_BYTES=62957568
IMAGE_IMPORT_WORST_CASE_BYTES=62945412
DERIVED_POST_PEAK_RESERVE_BYTES=1610612736
REQUIRED_FREE_BYTES=1736515716
CAPACITY_DEFICIT_BYTES=1146716292
POST_PEAK_FREE_BYTES=463896444
OBSERVED_MUTABLE_ALLOCATED_BYTES=172249088
REMOTE_STAGING=false
MANAGER_TAR_STREAMED_TO_T1=false
MUTATION=false
```

Runtime identity and stability passed for all three services. The U1 transaction
remains at `U1_PREPARE_REQUESTED`; the Extreme candidate remains bound;
confirmation remains required and unconsumed. Staging, Docker and the containerd
image store resolve to the same ext4 device.

Private evidence remains local and is represented by these sanitized bindings:

```text
CAPACITY_RESULT_SHA256=afb439315885cad0e5306c0a30dd6ad0ff0e53d683654c70eeffd83fa9b84fa8
CAPACITY_RESULT_SIZE=1974
RUNTIME_MUTABLE_REPORT_SHA256=c7e8250df8321ca9df09f95c318180d92087b3845a7006ec1dc917aba70430da
RUNTIME_MUTABLE_REPORT_SIZE=2371
STORAGE_REPORT_SHA256=8b44e3fc094b8c15af75cab87dc08accd6a8d38dbd686caa1d0244aef4c5cf36
STORAGE_REPORT_SIZE=617
PRIVATE_EVIDENCE_CREATED_AT=2026-11-10T10:34:05+0800
PRIVATE_EVIDENCE_PATH_CLASS=LOCAL_PRIVATE_N3W_KF147_CAPACITY_EVIDENCE
PRIVATE_EVIDENCE_PURPOSE=KF147_POST_FIX_FRESH_CAPACITY_STOP
SECRET_VALUES_INCLUDED=false
```

The selected mutable-data report totals 172,249,088 bytes. `/var/cache/apt` is
107,876,352 bytes and therefore cannot by itself close the 1,146,716,292-byte
deficit. No deletion is authorized from this observation. The next bounded gate is
an exact read-only storage/reclaim audit covering image/container references and
other large filesystem allocations before any targeted cleanup proposal.

## 11. Exact read-only reclaim audit source

The next diagnostic is implemented in the existing capacity entry point:

```text
SOURCE_HEAD=c14674b9fa4f17570d7f629e47563acffe296436
ENTRY=tools/n3w_t1_kf147_fresh_capacity.py
MODE=--reclaim-audit-on-stop
NEW_PARALLEL_MODULE=false
FOCUSED_TESTS=23_PASS
RUFF=PASS
PY_COMPILE=PASS
EMBEDDED_REMOTE_SCRIPT_COMPILE=PASS
GITHUB_CI=PENDING
LIVE_READONLY_EXECUTION=PENDING
```

The private audit captures:

- every running or stopped container's exact image ID and image reference;
- image IDs, tags, digests, total sizes and RootFS layer identities;
- Docker verbose disk accounting;
- Docker volume allocation;
- containerd namespace visibility;
- major root-filesystem path and child allocation;
- journal disk usage;
- files at least 16 MiB on the root filesystem;
- stable container/service state before and after collection.

The remote script contains no deletion, prune, cache-clean, journal-vacuum or
service-control operation. Evidence is written only to the Mac private evidence
root. Collection does not classify any item as safe to delete and creates no
cleanup authorization.

## 12. First reclaim-audit live STOP and collector repair

The first live read-only audit invocation ended before producing the audit JSON:

```text
LIVE_RESULT=STOP
REASON=command_failed:ssh:1
AUDIT_FILE_CREATED=false
MANAGER_TAR_STREAMED_TO_T1=false
REMOTE_STAGING=false
MUTATION=false

CAPACITY_STOP_SHA256=3c2367c94aa64937858b94ad575cb334decf0d86539e3941b98f79bcbfc31ec0
CAPACITY_STOP_SIZE=253
PRIVATE_EVIDENCE_CREATED_AT=2026-11-10T10:46:32+0800
```

The SSH transport deliberately exposes only the remote command return code, so the
private failure result cannot prove which individual child command failed. Source
review did prove three collector reliability defects: a child `TimeoutExpired`
escaped the remote program, a transient directory-enumeration error could also
escape, and the before/after Docker comparison used time-varying human-readable
`Status` text.

Repair head `b43d47f4a5fa06192ca5df513de186aed9ea9654` converts per-command
timeout/unavailability into structured audit records, tolerates directory snapshot
races and compares stable Docker `State`. The repair does not weaken the final
runtime stability requirement and adds no mutating command.

```text
SOURCE_REPAIR_LOCAL_FOCUSED_TESTS=12_PASS
PY_COMPILE=PASS
EMBEDDED_REMOTE_SCRIPT_COMPILE=PASS
GITHUB_CI=PENDING
LIVE_READONLY_RETRY=PENDING
```

## 13. Repaired reclaim-audit live PASS and exact HA cleanup candidate

The repaired read-only audit completed without changing T1:

```text
AUDIT_SCHEMA=gh.n3w-t1-kf147-storage-reclaim-audit/1
AUDIT_READ_ONLY=true
AUDIT_MUTATION=false
AUDIT_RUNTIME_STABLE=true

FREE_BYTES=589463552
REQUIRED_FREE_BYTES=1736515716
CAPACITY_DEFICIT_BYTES=1147052164

MANAGER_TAR_STREAMED_TO_T1=false
REMOTE_STAGING=false
```

The exact Home Assistant image inventory is:

```text
RUNNING_PREDECESSOR=local/n3w-homeassistant:2026.10.0-0c73235a
RUNNING_PREDECESSOR_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306

RECLAIM_CANDIDATE=local/n3w-homeassistant:2026.10.4-5881590f
RECLAIM_CANDIDATE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
RECLAIM_CANDIDATE_RUNNING=false
RECLAIM_CANDIDATE_CONTAINER_REFERENCES=0
RECLAIM_CANDIDATE_INSPECT_SIZE_BYTES=2447072066
RECLAIM_CANDIDATE_DOCKER_SHARED_SIZE=0B
RECLAIM_CANDIDATE_DOCKER_UNIQUE_SIZE=5.221GB
```

The current mandatory-USB transaction stores target image reference, manifest
identity and archive SHA/size. It does not require the target image to be present
in the internal image store at U1. The accepted architecture explicitly retired
the earlier P5 assumptions `target_image_prestate=PRESENT_AND_EXACT` and
`preexisting_exact_target_required=true`; pre-U9 recovery authority is the running
predecessor plus durable USB recovery material.

The 2026.10.4 image is therefore a valid exact cleanup candidate. This conclusion
does not itself authorize deletion. Any cleanup must revalidate exact ref/ID, zero
references, three-service runtime stability and unchanged U1 state immediately
before deletion; delete only the exact image ID; then prove runtime/U1 continuity
and rerun the fresh capacity gate.

Private evidence bindings:

```text
CAPACITY_RESULT_SHA256=18a9fd87eee45fe36cca5f5715fca338e110cf24ed6da24d22494de7f8ac764a
CAPACITY_RESULT_SIZE=1974
RUNTIME_MUTABLE_REPORT_SHA256=d569bc372ecdcef5a27ce06c664c8f3903daac07e7df2ef7d98f390215b23c1c
RUNTIME_MUTABLE_REPORT_SIZE=2371
STORAGE_REPORT_SHA256=32e48742de6c03c6beb05fc759836c381d28012d721286b5a058ac115d737e06
STORAGE_REPORT_SIZE=617
STORAGE_RECLAIM_AUDIT_SHA256=d15a55ae125f046ba7eaad3b63fc15a483cce95e9a5837fd6555cac904ff152c
STORAGE_RECLAIM_AUDIT_SIZE=30024
PRIVATE_EVIDENCE_CREATED_AT=2026-11-10T11:00:00+0800
SECRET_VALUES_INCLUDED=false
```
