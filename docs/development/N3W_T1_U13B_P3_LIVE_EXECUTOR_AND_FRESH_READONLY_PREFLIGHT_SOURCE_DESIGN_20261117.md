# N3-W T1 U13B P3 live executor + fresh real-T1 read-only preflight source design — 2026-11-18

## Current authority

```text
PR=807
SAME_VERSION_ARTIFACT_SOURCE_HEAD=d8446485557eb8e02bdb1460e84fe23984047f5b
SAME_VERSION_EXACT_ARTIFACT_RUN=44199389702
SAME_VERSION_EXACT_ARTIFACT_ID=14381710716
SAME_VERSION_GITHUB_ARTIFACT_DIGEST_SHA256=22b36b6141eb5b50f976341725c7d56f46eccd9817b241844a22a4a276df6092
TARGET_ARCHIVE_SHA256=be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d
TARGET_ARCHIVE_SIZE_BYTES=835299595
TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1
TARGET_CI_RUNTIME_IMAGE_ID=sha256:59b51fc720f83eac91881937337e439e2a2a1a8bb58c9e760cbdf95ce8653fbc
LIVE_PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
LIVE_PREDECESSOR_RUNTIME_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
T1_ACCESS=false
T1_MUTATION=false
```

The previous Home Assistant 2026.10.3 physical-acceptance target is superseded.
P3 now uses the same application version as the live predecessor (2026.10.4)
while deriving a distinct Docker image identity by adding exactly one acceptance
label to the frozen predecessor artifact.

## Exact artifact proof

Run 44199389702 completed SUCCESS and re-downloaded the produced artifact before
closing its byte binding. CI proved:

- application version remains 2026.10.4;
- RootFS diff IDs are identical to the frozen predecessor;
- runtime config is identical except for the acceptance label;
- target CI-side image identity is distinct;
- no registry pull was used to derive the target;
- no real T1 access or mutation occurred.

The exact target archive is
`local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1`,
SHA-256 `be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d`,
size 835299595 bytes.

## Docker 29 cross-store identity contract

The CI-side target runtime ID
`sha256:59b51fc720f83eac91881937337e439e2a2a1a8bb58c9e760cbdf95ce8653fbc`
is provenance only. It is not a portable oracle for the future T1 Docker store.

The live path loads the exact archive on T1, verifies portable RootFS + config
semantics, obtains the T1-local runtime image ID, and uses that local ID for U11
runtime binding. P3 additionally requires the rebound T1-local target runtime ID
to differ from the predecessor T1-local runtime ID
`sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365`.

## Package A — fresh real-T1 read-only preflight

Path:
`tools/execution_packages/n3w/r7a/u13b_p3_fresh_readonly_preflight/`

It verifies the exact terminal U13A predecessor state and requires exactly one
different eligible fresh USB candidate. It does not format/mount/write USB,
change transactions, services, images or HA data, or claim authorization.

```text
REAL_T1_READONLY_EXECUTION_AUTHORIZED=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
```

## Package B — acceptance source adapter

Path:
`tools/execution_packages/n3w/r7a/u13b_p3_acceptance_clean_ota_source/`

The package is rebound to
`infra/n3w-t1/upgrades/homeassistant-2026.10.4-u13b-same-version-acceptance.json`.
It preserves the production updater contracts and supplies only the exact staged
acceptance artifact. Manager version rules remain unchanged.

## Package C — P3 live executor to U11

Path:
`tools/execution_packages/n3w/r7a/u13b_p3_live_to_u11/`

```text
LIVE_EXECUTION_AUTHORIZED=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
```

Future separately authorized sequence:

```text
fresh real-T1 read-only preflight
-> verify exact same-version acceptance artifact
-> revalidate same fresh USB before claim
-> one-shot P3 outer authorization claim
-> stage exact source bundle + exact target archive
-> fresh U1 transaction / USB preparation
-> U5 install request
-> U6 predecessor recovery
-> U7 HA-data backup
-> U8 recovery admission
-> separate product U9 claim
-> U10 predecessor capacity release
-> U11 load exact target and verify portable identity
-> rebind T1-local target runtime image ID
-> require target runtime ID != predecessor runtime ID
-> start target owner and verify runtime
-> STOP before U12
```

`record_target_accepted()` and `record_commit()` remain outside P3.

## Current safety truth

```text
P3_SAME_VERSION_EXACT_ARTIFACT_READY=true
REAL_T1_READONLY_PREFLIGHT_EXECUTED=false
REAL_T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_MUTATION=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

Next boundary after source/simulation CI is a separately authorized fresh real-T1
read-only preflight. This source rebind grants no real-T1 authority.


## Single-USB hardware constraint and controlled reuse reset

Physical T1 hardware has one USB host interface and the operator currently has no second USB storage device. Therefore P3 cannot require the historical U13A recovery USB and a different fresh USB to be online simultaneously.

The historical medium currently bound to U13A is:

```text
MODEL=Extreme
CAPACITY_BYTES=32017047552
PUBLIC_FINGERPRINT=4014f1fb36f2c2bdff9d1af4f918a8324506c3df4e7d0720977ad9421a9de021
FILESYSTEM_UUID=967cf065-abe5-49ee-8499-7c3f50d2c48f
MOUNT_TARGET=/run/n3w-t1-ota/media/ca89774eb4254d0f
```

The operator explicitly authorized destruction/reuse of this historical USB on 2026-11-18. A dedicated gate is introduced at:

`tools/execution_packages/n3w/r7a/u13b_p3_single_usb_reuse_reset/`

This gate is intentionally narrower than the later product prepare flow. It must verify the exact terminal U13A transaction, exact running predecessor image, exactly one USB device, exact current media fingerprint/model/capacity, exact historical filesystem UUID and exact product-owned mount. Only after all checks pass may it:

```text
unmount exact historical product mount
-> remove filesystem signatures from the historical partition
-> verify old filesystem UUID is absent
-> verify the same USB disk is now unmounted and eligible
-> STOP
```

It does **not** repartition, run mkfs, create a new OTA transaction, mutate services/images/HA data, claim P3 live authorization, or enter U13B. Standard GPT recreation and ext4 formatting remain owned by the production `confirm_and_prepare()` path in the later separately authorized P3 live stage.

Safety rationale: destroying the old recovery medium occurs while the currently running predecessor remains unchanged. No production service/image/HA-data mutation is allowed until the later flow rebuilds target, predecessor recovery and HA-data backup on the reused USB and passes recovery admission. The reset gate therefore closes the single-USB hardware gap without weakening the ordering of U6/U7/U8 before U9+ production mutation.


## Downstream closure for post-reset single-USB reuse

Before the destructive reset executes, the reset package delegates the exact historical U13A status-only binding probe. This preserves evidence that the historical transaction, runtime and USB mirror were exact immediately before the old filesystem identity is destroyed.

After the reset removes the historical filesystem UUID, the historical USB mirror can no longer be re-read. The post-reset P3 preflight therefore switches to an explicit single-USB reuse contract: it revalidates the exact host terminal transaction and current Home Assistant runtime, requires the same diagnosed USB public fingerprint, requires the old U13A filesystem UUID to be absent, requires the device to be unmounted and otherwise eligible, and returns `single_usb_reuse_after_reset=true`.

The live executor must fail closed unless that exact preflight result reports `single_usb_reuse_after_reset=true`. It still creates a fresh U1 transaction and uses the normal production `confirm_and_prepare()` path for partition-table recreation, ext4 formatting and target preparation. Reuse without the destructive reset remains forbidden.
