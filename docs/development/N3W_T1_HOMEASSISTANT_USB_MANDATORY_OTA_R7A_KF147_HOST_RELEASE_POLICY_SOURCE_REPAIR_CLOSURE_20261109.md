# N3-W T1 Home Assistant mandatory-USB OTA R7A
# KF-147 host release-policy source repair closure — 2026-11-09

## 1. Gate and result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_SOURCE_REPAIR_FINAL_CLOSURE_REVIEW_AND_ARCHIVE_20261109_01
RESULT=CLOSED_PASS
KF=KF-147

HOMEASSISTANT_REPOSITORY=chrenguo-stack/HomeAssistant
HOMEASSISTANT_PR=800
SOURCE_VALIDATION_HEAD=988e8052b08f8c65bf6c313ef232e11ee78a8e87
PRODUCTION_SOURCE_LAST_CHANGED_HEAD=26a25537cdefa83d47c62b3ecc867a2cc37e8b8d
PRODUCTION_SOURCE_CHANGED_AFTER_QUALIFICATION=false

OTA_ORIGIN_REPOSITORY=chrenguo-stack/hahub.top
OTA_ORIGIN_PR=4
OTA_ORIGIN_SOURCE_HEAD=a4aa7ff3011c945555f7df77165bb5bee0f58d94
OTA_ORIGIN_ROUTE_CI=SUCCESS

KF147_SOURCE_REPAIR=CLOSED_PASS
KF147_OVERALL_STATUS=SOURCE_CLOSED_LIVE_REPAIR_PENDING
NEW_BLOCKER_COUNT=0

LIVE_T1_MUTATION=false
LIVE_OTA_SERVER_MUTATION=false
USB_MUTATION=false
CONFIRM_USB_ERASE=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

This closure completes the repository/source/CI work authorized for KF-147. It does not
perform the later live OTA-origin publication, T1 source/policy repair, destructive USB
confirmation, U2+ advancement, or merge.

## 2. Root cause and repaired contract

KF-147 was opened after the real Boundary B destructive preflight proved that
`/etc/n3w-t1-ota/homeassistant-release-source.json` was absent even though
`FixedHostReleasePolicyProvider` required it.

The source review also found that the old policy model incorrectly treated all non-target
capacity inputs as globally fixed constants. The repair therefore closed both parts of the
defect:

1. freeze and deploy a repository-owned exact host release-policy authority;
2. replace the fixed-capacity model with the frozen hybrid dynamic capacity model.

The selected OTA release origin remains:

```text
https://ota.hahub.top
```

with immutable versioned Home Assistant release paths outside Git and outside the website
deployment tree.

## 3. Frozen release authority

Repository policy:

`infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json`

```text
POLICY_SCHEMA=gh.n3w-t1-ha-ota-host-release-policy/2
RELEASE_IDENTITY=homeassistant-2026.10.4
ARTIFACT_URL=https://ota.hahub.top/n3w/homeassistant/releases/homeassistant-2026.10.4/homeassistant-arm64.tar.gz
TARGET_ARCHIVE_SIZE_BYTES=835309535
TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
EXPECTED_PREDECESSOR_IMAGE_REF=local/n3w-homeassistant:2026.10.0-0c73235a
PREDECESSOR_RECOVERY_BUDGET_BYTES=1342177280
USB_MEASURED_USABLE_FLOOR_BYTES=15032385536
```

The downloader is fail-closed to the exact HTTPS `ota.hahub.top` origin and exact versioned
path. Redirect/final-URL drift, target byte-count drift, target SHA drift and portable-image
identity drift are rejected.

## 4. Shared predecessor recovery qualification

The final qualification authority intentionally binds the last production-source-changing
head, not later evidence/test-only closure commits:

```text
QUALIFICATION_SOURCE_HEAD=26a25537cdefa83d47c62b3ecc867a2cc37e8b8d
QUALIFICATION_RUN_ID=42562214305
QUALIFICATION_JOB_ID=128980900831
QUALIFICATION_ARTIFACT_ID=13650277244
QUALIFICATION_ARTIFACT_DIGEST=sha256:79f2ede4a6e654e88857edde02caf52c495c3486fe706ac927098ff72bf987d9
EVIDENCE_JSON_SHA256=26b03c028e11ee335d12185eee835a3d5294094d4e45dd56a379894e9a5a044f
EVIDENCE_CANONICAL_SHA256=02d457caf39a3112b225b372c8eb38d15b749d759d09765c3c9ad4d385b64010

SAMPLE_1_SIZE_BYTES=835454828
SAMPLE_2_SIZE_BYTES=835454838
MEASURED_EXPORT_BYTES=835454838
PREDECESSOR_RECOVERY_BUDGET_BYTES=1342177280
```

The qualification workflow uses the same production
`export_predecessor_archive()` implementation installed by the A1 source package.
The qualification workflow no longer contains an independent `subprocess.Popen` encoding
implementation.

The current closure head also reran
`N3W T1 Home Assistant predecessor recovery qualification CI` as run
`42564218158` and passed. That later rerun is additional regression evidence; it does not
replace the record authority because no production source changed after the bound qualification.

Independent budget recomputation:

```text
ratio_bound=ceil(835454838 * 110 / 100)=919000322
additive_bound=835454838 + 268435456=1103890294
raw_bound=max(919000322,1103890294)=1103890294
round_up_256MiB(raw_bound)=1342177280
BUDGET_RECOMPUTE=PASS
```

## 5. Hybrid dynamic capacity closure

The frozen capacity model is implemented and regression-tested:

```text
TARGET_ARTIFACT_INPUT=RELEASE_FIXED
PREDECESSOR_RECOVERY_INPUT=RELEASE_TRANSITION_BOUND
HA_DATA_BACKUP_INPUT=RUNTIME_DYNAMIC
TRANSACTION_WORKING_INPUT=FIXED_FORMULA
REMOVABLE_RESERVE_INPUT=FIXED_FORMULA

ROUND_UP_QUANTUM_BYTES=268435456
HA_DATA_BACKUP_MIN_BYTES=1073741824
HA_DATA_GROWTH_MARGIN=max(512MiB,ceil(measured*25%))
TRANSACTION_WORKING=max(512MiB,ceil(target*10%))
REMOVABLE_RESERVE=max(1GiB,ceil(base*10%))
RECOMMENDED_NOMINAL_USB_GB=32,64,128,256,512,1024
NOMINAL_USABLE_GUARD=90%
```

Required admission/revalidation points are all present:

- PREPARE capacity snapshot;
- candidate raw-capacity plausibility;
- one-time additive backfill for the existing U1 transaction;
- immediate pre-format recomputation before any destructive operation;
- post-format measured-usable verification;
- U5/install-capacity revalidation;
- U8 recovery-admission free-space verification before later authorization/U9.

The current live U1 transaction is not reset or replayed by this source closure.

## 6. HA persistent-data measurement boundary

Production HA persistent data is measured from the production HA state root in a read-only
walk. The implementation fails closed for unsupported external persistent symlinks, special
files and overflow conditions.

No raw host path, USB serial, WWN, backup path or detailed private capacity evidence is added
to public MQTT/Home Assistant state.

## 7. IPC / Manager / Home Assistant projection

The host IPC response advances to schema V3 while retaining V1/V2 compatibility and exposes
only the bounded capacity projection:

```text
usb_required_bytes_or_null
usb_recommended_nominal_gb_or_null
usb_capacity_check_state
user_message_code_or_null
```

The projection is fail-closed. Manager validation and HA presentation tests bind these exact
fields and preserve the privacy boundary.

## 8. A1 deployment source closure

The R7A host A1 source package now exact-binds and installs:

- the Policy V2 repository asset to
  `/etc/n3w-t1-ota/homeassistant-release-source.json`;
- the shared predecessor recovery encoder module;
- the capacity module and repaired updater source.

The package requires the policy to be a regular root:root 0644 file and verifies installed
source hashes byte-exactly.

Current manifest evidence:

```text
host_release_policy_install=true
host_release_policy_exact_hash_verify=true
predecessor_recovery_encoder_install=true
predecessor_recovery_encoder_shared_with_qualification=true
live_execution_authorized=false
```

The old repaired-Manager A1R live package is historical consumed authority and was not rebound
to current source. Its tests now verify the immutable historical live-authorized head
`70aaa4070641dd73c1a97738e6332be31403d45e`.

## 9. OTA origin source closure

Repository `chrenguo-stack/hahub.top`, PR #4:

```text
HEAD=a4aa7ff3011c945555f7df77165bb5bee0f58d94
CI_RUN=42561679317
CI_RESULT=SUCCESS
```

The source contract provides an exact `ota.hahub.top` TLS vhost before wildcard FRP routing,
routes only the immutable Home Assistant release subtree to the independent static OTA server,
permits GET/HEAD only, disables autoindex and does not proxy the release route through FRP.

No Home Assistant OTA binary is committed to Git and no live server deployment occurred in
this gate.

## 10. Exact-head CI closure

PR #800 exact source-validation head:

`988e8052b08f8c65bf6c313ef232e11ee78a8e87`

All 28 workflows returned `SUCCESS`, including:

- N3W T1 Core Updater Home Assistant 2026.10.4 target binding CI;
- N3W T1 Home Assistant predecessor recovery qualification CI;
- N3W T1 Core Updater Manager A-to-B CI;
- greenhouse-manager CI;
- N3W CI fast source and exact closure contract;
- Public repository safety CI;
- N3W T1 deployment gate CI;
- N3W T1 production Manager state binding CI;
- existing Manager/Broker/HA and identity regression suites.

The earlier closure-head target-binding failure was a single stale test fixture containing the
historical qualification artifact-name HEAD. The bounded repair changed only that test
expectation; production source was unchanged.

## 11. Final independent closure review

```text
SOURCE_DESIGN_SATISFIED=PASS
PREDECESSOR_EVIDENCE_COMPLETE=PASS
PRODUCTION_ENCODER_QUALIFICATION_SHARED=PASS
POLICY_AND_EVIDENCE_CROSS_BOUND=PASS
CAPACITY_CHECKPOINTS_COMPLETE=PASS
A1_DEPLOYMENT_SOURCE_COMPLETE=PASS
OTA_ORIGIN_SOURCE_COMPLETE=PASS
HISTORICAL_LIVE_AUTHORITY_PRESERVED=PASS
PUBLIC_PRIVACY_BOUNDARY=PASS
NEW_FALSE_PASS_PATH_FOUND=false
NEW_BLOCKER_COUNT=0
SOURCE_REPAIR_CLOSED_PASS=true
```

## 12. KF-147 disposition and remaining authorization boundaries

```text
KF147_SOURCE_DESIGN=CLOSED
KF147_SOURCE_REPAIR=CLOSED_PASS
KF147_OTA_ORIGIN_SOURCE=CLOSED_PASS
KF147_OVERALL_STATUS=SOURCE_CLOSED_LIVE_REPAIR_PENDING

OLD_CONFIRM_USB_ERASE_AUTHORIZATION=SUPERSEDED_UNCLAIMED
PREPARE_REPLAY=false
CONFIRM_USB_ERASE=false
WIPEFS=false
PARTITION_WRITE=false
MKFS=false
MOUNT=false
TARGET_DOWNLOAD=false
U2_PLUS=false
MERGE=false
```

The remaining product sequence is intentionally outside this closure and requires later
authorization at the corresponding live/merge boundaries:

```text
A. OTA_ORIGIN_LIVE_PUBLICATION
   deploy exact ota.hahub.top route + exact 2026.10.4 artifact
   verify external HTTPS size/SHA

B. T1_KF147_LIVE_POLICY_REPAIR
   install exact Policy V2 + repaired source
   preserve current U1/candidate
   additive capacity snapshot backfill
   fresh read-only destructive preflight

C. NEW_CONFIRM_USB_ERASE_AUTHORIZATION
   only after A+B PASS

D. U2_PLUS_EXECUTION
   separately authorized

E. MERGE
   separately authorized
```

No old destructive authorization may be replayed.

## 13. Closure

```text
CURRENT_MODE=SOURCE_FREEZE_AND_CLOSURE
SOURCE_FREEZE_AND_CLOSURE=COMPLETE

KF147_SOURCE_REPAIR=CLOSED_PASS
SOURCE_REPAIR_COMPLETE=true
LIVE_REPAIR_COMPLETE=false
MERGE_COMPLETE=false

NEXT_STAGE=KF147_LIVE_REPAIR_AUTHORIZATION_DECISION
AUTO_EXECUTE_NEXT_STAGE=false
```
