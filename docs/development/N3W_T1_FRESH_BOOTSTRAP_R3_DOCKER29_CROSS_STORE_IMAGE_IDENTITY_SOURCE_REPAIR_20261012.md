# N3-W T1 fresh bootstrap R3 Docker 29 cross-store image identity source repair（2026-10-12）

## Live evidence and root cause

The R3 one-shot authorization was durably claimed and is permanently consumed.

```text
AUTHORIZATION_ID=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_03
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false
BOOTSTRAP_STATUS=STOP_PARTIAL
BOOTSTRAP_REASON=fresh_install_failed
HOST_STATUS=STOP_PARTIAL
REMOTE_PAYLOAD_PRESERVED=true
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

Post-failure minimal-host inventory proved transaction cleanup succeeded.

The retained payload kept all three image tars. Docker events then proved that the first Home Assistant image did load successfully:

```text
CLAIM_LOCAL=2026-10-12T15:10:48+08:00
HOMEASSISTANT_IMAGE_LOAD_LOCAL=2026-10-12T15:16:53+08:00
HOMEASSISTANT_RUNTIME_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
HOMEASSISTANT_UNTAG_DELETE_LOCAL=2026-10-12T15:17:17+08:00
EXPECTED_BUILD_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
```

The source unlinks an image tar only after `docker load`, `docker image inspect` and exact ID/platform binding succeed. The load event followed by cleanup untag/delete, combined with the differing runtime ID above, closes the failure to the single-store-ID assertion in the Home Assistant binding check.

This is not a timeout, storage-capacity or OOM failure. No relevant kernel storage/OOM evidence was observed and the image load completed.

The deployable workflow ran on GitHub `ubuntu-24.04` with Docker Server 28.0.4. The real T1 runs Docker 29.7.1. Docker upstream documents that the legacy graphdriver store identifies images by config digest while the containerd image store can identify them by manifest or index digest; a Docker maintainer states that this difference is expected.

The project had already captured the same rule in:

```text
tools/execution_packages/n3w/kf098/t1_live_cutover/TASK.md
```

That authority explicitly forbids assuming one `.Id` representation is universal across Docker image stores and binds the exact runtime with architecture/OS plus artifact-owned RootFS identity. The fresh bootstrap accidentally reintroduced the old single-`.Id` assumption.

The dockerd line `failed to validate image signature` is not classified as the primary failure because a successful image load event occurred afterwards and the exact loaded image was then removed by transaction cleanup.

## Source repair

The payload now freezes an artifact-owned SHA-256 fingerprint of each image's ordered `RootFS.Layers` list while building the exact artifact.

Runtime image validation now requires:

```text
exact artifact tar SHA binding
exact image tag
runtime ID syntax valid, but representation not assumed universal
Architecture=arm64
Os=linux
RootFS layer fingerprint exact
```

The CI-side `image_id` remains the immutable build/config identity used by the product image lock; it is no longer treated as a portable Docker runtime `.Id` oracle.

The stopped postcheck now requires exactly three runtime images and re-validates all three exact tags with the same RootFS/platform contract, including equality with the binding captured immediately after load.

Regression tests cover a Docker-containerd-style runtime ID that differs from the build/config digest while RootFS binding remains exact, and reject RootFS drift.

## Known failure state

```text
KF-110=GUARDED_SOURCE / LIVE_REVALIDATED
KF-111=OPEN_SOURCE_REPAIR_CI_PENDING
```

KF-110 is live-revalidated because R3 passed the repaired payload file-set gate, durably claimed authorization and entered image loading.

## Authorization rotation

```text
PREDECESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_03
PREDECESSOR_CLAIMED=true
PREDECESSOR_CONSUMED=true
PREDECESSOR_REPLAY_ALLOWED=false

SUCCESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_04
SUCCESSOR_GRANTED=false
SUCCESSOR_CLAIMED=false
SUCCESSOR_CONSUMED=false
```

No T1 mutation is part of this source repair. The retained R3 payload remains preserved until a separate exact cleanup gate.
