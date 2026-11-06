# N3-W T1 Core Updater — Home Assistant 2026.10.4 exact ARM64 artifact design

Date: 2026-11-05

## Gate

```text
TASK=N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_EXACT_ARM64_ARTIFACT_BUILD_AND_COMPONENT_TARGET_20261105_01
STAGE=P2A_EXACT_ARTIFACT_BUILD

PARENT_READONLY_GATE=CLOSED_PASS
PARENT_EXECUTION_HEAD=60af31fc661434c9b5ae3166a3f9ebafcde7ce63

T1_ACCESS=false
T1_MUTATION=false
SERVICE_RESTART=false
IMAGE_LOAD_ON_T1=false
BOARD_ACCESS=false
MERGE=false
```

## Input authority

```text
UPSTREAM_REPOSITORY=ghcr.io/home-assistant/home-assistant
UPSTREAM_TAG=2026.10.4
TARGET_PLATFORM=linux/arm64
PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

COMPATIBILITY_REVIEW=infra/n3w-t1/upgrades/homeassistant-2026.10.4-compatibility-review.json
COMPATIBILITY_REVIEW_CANONICAL_SHA256=8b02e9bb0143fc4fc7900c4c0e4c52b27f92725cd41f1f03b82ba67ffb9e0267
```

## Exact upstream resolution

The workflow does not accept a tag-only pull as final authority.

It first reads the raw multi-platform manifest/index for `2026.10.4`, requires exactly one
`linux/arm64` descriptor, records that descriptor digest, and then pulls the image by that exact
digest.

The local product reference is derived from the selected manifest digest:

```text
local/n3w-homeassistant:2026.10.4-<manifest-digest-prefix>
```

The tag therefore cannot silently select different bytes after artifact construction.

## Exact archive

The pulled ARM64 image is saved with Docker and gzip-compressed:

```text
homeassistant-arm64.tar.gz
```

The exact compressed archive itself is the transport authority. Its SHA256 and size are recorded.

This format is accepted by both relevant paths:

- Python `tarfile` parsing through `n3w_t1_portable_image_identity.py`;
- Docker `load -i`, which is smoke-tested in CI after removing the original local image.

CI does not run the ARM64 Home Assistant container on the x86 runner.

## Portable identity

The workflow parses the archive with the existing portable-image-identity contract and verifies
the loaded Docker image against:

- platform;
- normalized config semantics;
- rootfs diff IDs.

The artifact contains:

```text
homeassistant-arm64.tar.gz
portable-image-identity.json
upstream-binding.json
```

No credential or device-specific data is included.

## Artifact/target split

The exact GitHub artifact ID and artifact digest do not exist until upload completes.

Therefore P2 is intentionally split:

```text
P2A exact ARM64 artifact build
  -> immutable workflow run + artifact ID/digest

P2B component target binding
  -> infra/n3w-t1/upgrades/homeassistant-2026.10.4.json
  -> gh.n3w-t1-core-updater-target/2
```

P2B must bind the exact P2A workflow run, artifact ID, artifact digest, archive SHA256, selected
upstream manifest digest, local image reference, compatibility review and A1 authority.

P2B must not trigger a replacement P2A artifact and then silently bind the newer bytes.

## Governance

The new exact workflow must be registered in `N3W_CI_POLICY_MANIFEST_V1.json` and included in the
fast-source self-trigger path in the same source change.

This is a direct regression guard for KF-134.

## Stop boundary

```text
LIVE_HA_UPGRADE_READY=false
HA_TARGET_MANIFEST_READY=false
HA_EXACT_ARTIFACT_READY=false

NEXT_AFTER_P2A=P2B_COMPONENT_TARGET_BINDING
NEXT_T1_ACCESS=false
NEXT_T1_MUTATION=false
```
