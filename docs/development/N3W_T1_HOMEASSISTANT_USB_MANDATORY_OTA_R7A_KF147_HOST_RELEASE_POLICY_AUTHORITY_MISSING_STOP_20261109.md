# N3-W T1 Home Assistant mandatory-USB OTA R7A
# KF-147 — host release policy authority missing — destructive gate STOP — 2026-11-09

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_BOUNDARY_B_CONFIRM_USB_ERASE_20261109_01
RESULT=STOP_BEFORE_CLAIM
KF=KF-147

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
DESTRUCTIVE_ACTION_EXECUTED=false
```

The destructive confirmation gate was authorized by the user, but the fresh live preflight failed
before claim because the privileged host release-policy authority file was absent:

```text
PREFLIGHT_FILE_INVALID=/etc/n3w-t1-ota/homeassistant-release-source.json
CONFIRM_USB_ERASE_PREFLIGHT=FAIL
```

No wipefs, partition write, mkfs, mount, target download, U2+ or runtime replacement occurred.

## 2. Live state preserved

The last accepted live Boundary-B state remains:

```text
TRANSACTION_PHASE=U1_PREPARE_REQUESTED
TRANSACTION_STATUS=ACTIVE
PUBLIC_PHASE=USB_REQUIRED_CONFIRMATION
USB_CONFIRMATION_REQUIRED=true
USB_CONFIRMATION_CONSUMED=false
USB_CANDIDATE_PRESENT=true
USB_CANDIDATE_MODEL=Extreme
USB_CANDIDATE_CAPACITY_BYTES=32017047552
SECOND_USB_CURRENTLY_INSERTED=true
```

The candidate must remain inserted and PREPARE must not be replayed.

## 3. Source contract

`tools/n3w_t1_core_updater_ha_prepare_host.py` defines:

```text
DEFAULT_HOST_RELEASE_POLICY=/etc/n3w-t1-ota/homeassistant-release-source.json
```

The policy is required by `FixedHostReleasePolicyProvider.load()` and must contain exactly:

```text
schema
release_identity
artifact_url
target_archive_sha256
target_archive_size_bytes
predecessor_recovery_worst_case_bytes
ha_data_backup_worst_case_bytes
transaction_metadata_and_working_bytes
removable_media_reserve_bytes
```

The document is root-owned authority for both:
- exact target download locator/binding; and
- full removable-media capacity admission.

`CONFIRM_USB_ERASE` starts the source-defined confirm worker. A successful worker does not stop
after erase; it proceeds through:

```text
candidate revalidation
-> wipefs
-> GPT repartition
-> ext4 mkfs
-> mount
-> media self-test
-> measured capacity check
-> U2 media bind
-> U3 target preparation
-> HTTPS target download / size / SHA / portable identity verification
-> U4 READY_TO_INSTALL
-> STOP
```

Therefore the policy must exist and be authoritative before destructive confirmation is claimed.

## 4. Deployment gap

The R7A host A1 activation package installs/activates:
- the exact host Python source set;
- `/etc/n3w-t1-ota/approved-homeassistant.json`;
- `n3w-t1-ha-ota.service`;
- the services-owner HA-OTA drop-in;
- `/etc/n3wfc4/ha-ota-activation.env`.

The A1 executor has an explicit `APPROVED_MANIFEST` authority and source destination, but no
`HOST_RELEASE_POLICY` / `homeassistant-release-source.json` installation authority.

The A1 design document likewise explicitly requires installation of the exact approved manifest,
but does not require installation of the host release-policy document.

Thus the live absence matches the source/deployment contract gap.

## 5. Why this is not a local copy-only repair

The missing policy cannot be safely synthesized from the approved manifest alone.

The approved manifest freezes:

```text
release_identity=homeassistant-2026.10.4
target_archive_size_bytes=835309535
target_archive_sha256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
target_image_ref=local/n3w-homeassistant:2026.10.4-5881590f
```

But the release-policy document additionally requires:
- an authoritative HTTPS `artifact_url`;
- predecessor recovery worst-case bytes;
- HA data-backup worst-case bytes;
- transaction metadata/working bytes;
- removable-media reserve bytes.

Current tests use synthetic policy providers and synthetic URLs such as
`https://updates.example.invalid/ha.tar.gz`; they do not freeze a production policy file.

The product architecture also explicitly states:

```text
GITHUB_ACTIONS_ARTIFACT_AS_FINAL_END_USER_CDN=false
PRODUCT_RELEASE_SOURCE=stable HTTPS release service
FINAL_RELEASE_SERVICE_DOMAIN=deferred
```

Therefore inventing a GitHub artifact URL or arbitrary capacity values at this gate would create a
new release-source design decision and would weaken the authority model.

## 6. Root cause

```text
ROOT_CAUSE=R7A_CONSUMER_IMPLEMENTED_BUT_PRODUCTION_HOST_RELEASE_POLICY_AUTHORITY_NOT_FROZEN_OR_DEPLOYED

SOURCE_CONSUMER_PRESENT=true
PRODUCTION_POLICY_FILE_PRESENT=false
A1_DEPLOYMENT_INSTALLS_POLICY=false
PRODUCTION_ARTIFACT_URL_AUTHORITY_FROZEN=false
EXACT_CAPACITY_BUDGET_AUTHORITY_FROZEN=false

TEST_COVERAGE_GAP=synthetic_policy_provider_does_not_assert_A1_deployment_of_real_policy
```

## 7. Classification

```text
KF147_STATUS=OPEN_SOURCE_DESIGN_REQUIRED
SOURCE_REPAIR_REQUIRED=true
LIVE_REPAIR_REQUIRED=true
DESTRUCTIVE_GATE_BLOCKED=true
PRODUCT_SOURCE_BLOCKER_PROVEN=true

USB_ENUMERATION_BLOCKER=false
R7A_CANDIDATE_DISCOVERY_BLOCKER=false
MANAGER_DYNSEC_BLOCKER=false
```

This is a source/deployment authority defect, not a SanDisk or T1 USB-path defect.

## 8. Required repair scope

A valid repair must, before any destructive live action:

1. freeze a repository-owned exact host release-policy schema instance for the approved HA target;
2. freeze the artifact distribution authority and exact HTTPS locator contract;
3. freeze all four non-target capacity budget values with evidence/rationale;
4. bind the release policy to the approved manifest / target archive identity;
5. update A1/deployment packaging so the policy is installed root-owned at the fixed path;
6. add source tests proving A1 cannot report PASS while the production policy asset is absent;
7. add policy/approved-manifest cross-binding tests;
8. add CI path coverage for the production policy asset;
9. perform a new live repair gate that installs only the frozen policy authority without replaying PREPARE;
10. rerun the destructive preflight against the still-live U1 candidate.

## 9. Frozen live safety boundary

```text
CURRENT_USB=SanDisk Extreme
CURRENT_USB_INSERTED=true
CURRENT_TRANSACTION_PRESERVE=true
PREPARE_REPLAY_AUTHORIZED=false

CONFIRM_USB_ERASE_AUTHORIZED_BY_USER=true
CONFIRM_USB_ERASE_AUTHORIZATION_CLAIMED=false
CONFIRM_USB_ERASE_EXECUTION_BLOCKED_BY_KF147=true

WIPEFS=false
PARTITION_WRITE=false
MKFS=false
MOUNT=false
TARGET_DOWNLOAD=false
U2_PLUS=false

AUTO_RETRY=false
AUTO_POLICY_SYNTHESIS=false
AUTO_LIVE_REPAIR=false
MERGE=false
STOP=true
```

The existing user authorization remains unclaimed and must not be consumed while KF-147 is open.

## 10. Next stage

```text
NEXT_STAGE=KF147_HOST_RELEASE_POLICY_SOURCE_DESIGN
NEXT_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_DESIGN_20261109_01
NEXT_GATE_LIVE_MUTATION=false
```

The source-design stage must resolve release-source and capacity authorities before a source/live repair
can be executed.
