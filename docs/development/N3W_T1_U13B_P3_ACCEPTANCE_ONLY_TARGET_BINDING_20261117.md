# N3-W T1 U13B P3 acceptance-only target binding — 2026-11-17

## Resulting target authority

The successful exact-artifact workflow produced:

```text
UPSTREAM_RUN_ID=44089585822
ARTIFACT_SOURCE_HEAD=fd00f66d646053ae1c7d4bcf85921ca6bc2b20e3
ARTIFACT_ID=14330409226
ARTIFACT_DIGEST_SHA256=a84ddb194ed72ddba6797a0141c1835ecdadfc369c84427303f02d3628d76200
ARCHIVE_SHA256=d26ac92ceed7baf689e1db9f11550c1e51d36f6dc81cac995a3eaf7a3d13912d
ARCHIVE_SIZE_BYTES=835151232
LOCAL_IMAGE=local/n3w-homeassistant:2026.10.3-c2bb99de
UPSTREAM_INDEX_DIGEST=sha256:407b89cd11a8cb67d388d21739a226c74acbbebe1ac59e3b83b11b43ce76b98f
UPSTREAM_MANIFEST_DIGEST=sha256:c2bb99de7179fe0c192757bc70a53db5f2ded6672a1ced0007accccd3f0de44c
```

The target manifest is frozen at:
`infra/n3w-t1/upgrades/homeassistant-2026.10.3-u13b-physical.json`.

## Control-plane boundary

This target is acceptance-only. It is intentionally **not** exposed as
`homeassistant-2026.10.3-approved.json`.

The normal Manager OTA control plane compares versions and correctly rejects
2026.10.3 as an update when 2026.10.4 is installed. P3 must not weaken or bypass
that field-product rule globally.

A later P3 physical executor may bypass only the *version discovery/control*
layer while still invoking the same lower-layer T1_Core_Updater prepare,
recovery, backup, U9 authorization, U10 and U11 product primitives. That
acceptance harness requires its own source review and explicit live mutation
authorization.

## No live authority

```text
T1_ACCESS=false
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
