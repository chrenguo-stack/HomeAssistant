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
