# N3-W T1 fresh product bootstrap deployment readiness review（2026-10-12）

## 0. Gate

```text
TASK=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_DEPLOYMENT_READINESS_REVIEW_20261012_01
MODE=READ_ONLY_SOURCE_AND_ARTIFACT_REVIEW
LIVE_T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

## 1. Current host state

Minimal-baseline normalization has CLOSED_PASS:

```text
TARGET_T1_BASELINE=ARMBIAN + DOCKER + NETWORK ONLY
CONTAINERS=0
IMAGES=0
VOLUMES=0
DOCKER_NETWORKS=bridge,host,none
PRODUCT_PATHS_ABSENT=true
PRODUCT_UNIT_ABSENT=true
PRODUCT_FIREWALL_ABSENT=true
PRODUCTION_LISTENERS=0
```

## 2. Current exact fresh ARM64 artifact

The current exact fresh three-image CI at source authority `43207da98bc0e116af2845b690b3f0ee230637ab` is valid artifact evidence:

```text
RUN_ID=38189402655
ARTIFACT_ID=11721600979
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-43207da98bc0e116af2845b690b3f0ee230637ab
ARTIFACT_DIGEST=sha256:f8e3d716f70758e63d0926b0d7bc5fa185724e3e9c7e181f0d7d69ef5cf4b531
POST_UPLOAD_BINDING=PASS

MANAGER_IMAGE=local/greenhouse-manager:fresh-43207da98bc0
MANAGER_IMAGE_ID=sha256:e8472cd65eaec420cb265dfaac5c7dc074d5832cecfff91dcc8c200d4e3376ef
MANAGER_TAR_SHA256=dd04744c7582c7e6c475075df3073c51a81d8a98bf8f6b99269078cb724d48a1

HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
HOMEASSISTANT_TAR_SHA256=fc3bb08dc87986021714a0b1130245f06385d8fd853e05e99fc42f343fbd0433

BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
BROKER_TAR_SHA256=9f05e08a5087aee890458747ea6945a28ab5169f7db0b09b714d2a2081b11a59
```

This artifact contains only the three image tar files plus `binding.json`. It is exact image evidence, not a deployable host apply package.

## 3. Current production staging payload is not eligible

Run `38189402744` / artifact `11721250984` is source-head-current as a workflow artifact, but its payload content is still legacy staging lineage:

```text
ARTIFACT_DIGEST=sha256:d863bc9308f83ba7dbf26ab8f654ee8913d8d60f9350ff2720fc54e73b1da1be
PAYLOAD_ARCHIVE_SHA256=1b8e62d169a8b22836d1711cfb18ff2e3f274df9ae1d178e759b23a7f78a53bb
MANIFEST_AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03
MANAGER_IMAGE=local/greenhouse-manager:s20-511db028
MANAGER_TAR_SHA256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081
```

That authorization is superseded and the Manager image is the old S20 image, not the current fresh Manager image. Therefore:

```text
RUN114_ARTIFACT_BINDING=PASS_AS_LEGACY_ARTIFACT_EVIDENCE
RUN114_FRESH_BOOTSTRAP_DEPLOYMENT_ELIGIBILITY=FAIL
```

It must never be used to bootstrap the newly normalized T1.

## 4. Source blockers

### A1 — no live FreshInstallerAdapters implementation

`fresh_installer.run_fresh_staging()` defines the correct orchestration contract, but the repository currently has only host-model adapters in tests. There is no repository-owned live adapter that implements:

- exact minimal-host preflight;
- offline exact-image load;
- fresh identity/state/Broker/DynSec creation;
- runtime/source/network/unit/guard staging;
- commit;
- stopped postcheck;
- transaction-owned cleanup.

### A2 — host wrapper is preflight-only

`tools/n3w_t1_fresh_product_staging_host.py` explicitly exposes only:

```text
--phase preflight
```

It contains transport helper functions, but no authorized apply entry point.

### A3 — production Manager runtime remains bound to old S20 image

Current production Compose and image-lock still require:

```text
local/greenhouse-manager:s20-511db028
```

The current exact fresh Manager image is:

```text
local/greenhouse-manager:fresh-43207da98bc0
```

The R6 exact-image test proves fresh constructors exist in the new Manager image, but the production deployment contract still points to the old Manager image. This must be repaired before live bootstrap.

### A4 — current staging payload workflow is legacy-coupled

The current payload workflow still:

- downloads the old S20 Manager artifact;
- packages `n3w_t1_production_stack_staging.py`;
- embeds superseded authorization `..._03`;
- creates a payload for the old precreated-product-state staging executor.

It cannot be repurposed by merely changing the authorization ID.

### A5 — remote tar extraction needs hardening

The fresh host wrapper checks member paths, but then uses `tarfile.extractall()` without rejecting symlink, hardlink, device, FIFO, or unsafe link-target members. A deployable apply path must accept only the exact allowed regular-file/directory payload structure and fail closed on all link/special-file members.

## 5. Review conclusion

```text
MINIMAL_BASELINE_NORMALIZATION=CLOSED_PASS
FRESH_EXACT_ARM64_IMAGE_ARTIFACT=PASS
FRESH_PRODUCT_BOOTSTRAP_LIVE_DEPLOYMENT=NOT_READY
LIVE_PRODUCT_BOOTSTRAP_AUTHORIZATION=NOT_REQUESTED
```

The correct next gate is source/CI only:

```text
NEXT_ONE_GATE=
N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_DEPLOYABLE_PATH_SOURCE_REPAIR_20261012_01

GATE_SCOPE=GITHUB_AND_HOST_ONLY
LIVE_T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

The source repair must create a new fresh-bootstrap-specific deployable payload and live adapter. It must not patch or reuse the obsolete `..._03` staging executor.
