# N3-W T1 Core Updater — Home Assistant P2B exact target binding closure

Date: 2026-11-05

## Result

```text
TASK=N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_EXACT_ARM64_ARTIFACT_BUILD_AND_COMPONENT_TARGET_20261105_01
STAGE=P2B_COMPONENT_TARGET_BINDING
RESULT=CLOSED_PASS

EXECUTABLE_SOURCE_HEAD=f43e3600a017af04cb253d10ec0c86b47d24b5e3
PR=784
PR_STATE=OPEN_DRAFT
PR_MERGEABLE=true
MERGE=false

T1_ACCESS=false
T1_MUTATION=false
SERVICE_RESTART=false
BOARD_ACCESS=false
```

## Fresh exact-head CI closure

PR #784 exact executable head `f43e3600a017af04cb253d10ec0c86b47d24b5e3` completed all observed workflows successfully:

```text
WORKFLOW_COUNT=16
SUCCESS_COUNT=16
FAILURE_COUNT=0
PENDING_COUNT=0

TARGET_BINDING_RUN_ID=41977897463
TARGET_BINDING_SOURCE=SUCCESS
TARGET_BINDING_EXACT_BINDING=SUCCESS

POST_TARGET_EXACT_ARTIFACT_RUN_ID=41977897376
POST_TARGET_EXACT_ARTIFACT_SOURCE=SUCCESS
POST_TARGET_EXACT_ARTIFACT_JOB=SKIPPED
POST_TARGET_EXACT_ARTIFACT_COUNT=0
```

The skipped exact-artifact job is intentional. Once the frozen Home Assistant target exists, P2A artifact production is no longer allowed. This proves P2B did not silently create a replacement P2A artifact.

## Frozen P2A authority

```text
P2A_RUN_ID=41976542377
P2A_SOURCE_HEAD=fb7cfc857003ace3d368521d76ca2320ba399736

ARTIFACT_ID=13391983948
ARTIFACT_NAME=n3w-t1-core-updater-homeassistant-2026.10.4-arm64-fb7cfc857003ace3d368521d76ca2320ba399736
ARTIFACT_DIGEST_SHA256=df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2

ARCHIVE_NAME=homeassistant-arm64.tar.gz
ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
ARCHIVE_SIZE_BYTES=835309535

TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

UPSTREAM_INDEX_DIGEST=sha256:23f4dfbb69ce76315dbc4de7915504f1c2dcecd7ca2648113a493a385972e133
UPSTREAM_LINUX_ARM64_MANIFEST_DIGEST=sha256:5881590fca108a6e6b5eb9fff1718baeddda9d6dd5b52d1594e3386fe33b4d66
```

P2A independently proved compressed Docker-load compatibility, portable image identity and post-upload re-download byte binding.

## Frozen updater target

Repository authority:

```text
TARGET_PATH=infra/n3w-t1/upgrades/homeassistant-2026.10.4.json
TARGET_SCHEMA=gh.n3w-t1-core-updater-target/2
COMPONENT=homeassistant
MUTATION_PROFILE=IMAGE_ONLY_V1
TARGET_PLATFORM=linux/arm64
ROLLBACK_COMPATIBLE=true

COMPATIBILITY_REVIEW_SHA256=8b02e9bb0143fc4fc7900c4c0e4c52b27f92725cd41f1f03b82ba67ffb9e0267
A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7
```

The exact-binding CI re-downloaded the frozen P2A artifact and proved:

```text
HA_TARGET_UPSTREAM_GITHUB_ARTIFACT_IDENTITY=PASS
HA_2026_10_4_TARGET_V2_BINDING=PASS
HA_TARGET_ARTIFACT_ID=13391983948
HA_TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
HA_TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
HA_TARGET_UPSTREAM_MANIFEST_DIGEST=sha256:5881590fca108a6e6b5eb9fff1718baeddda9d6dd5b52d1594e3386fe33b4d66
T1_ACCESS=false
T1_MUTATION=false
```

## Runtime-template predecessor proof

The preceding real-T1 read-only gate is already `CLOSED_PASS`:

```text
CURRENT_BINDING_MODE=legacy_static
CANDIDATE_BINDING_MODE=dynamic
DOUBLE_READ_STABLE=true
RENDER_SEMANTICALLY_EQUAL=true
CURRENT_RENDER_SHA256=1705f3a87f058f68a4846865ebd52270d5ddd812ad4138ef37eff5cbbc077e7c
CANDIDATE_RENDER_SHA256=1705f3a87f058f68a4846865ebd52270d5ddd812ad4138ef37eff5cbbc077e7c
```

This is proof that the minimal runtime-template binding convergence is semantically neutral for the accepted predecessor. It is not authorization to mutate the T1 template.

## Source repairs made during P2

Two bounded source/CI issues were repaired without expanding product scope:

1. OCI portable-image parsing now accepts a single-manifest OCI archive whose descriptor omits platform metadata, while the image config still has to prove the expected platform. ARM64 `v8` and unspecified ARM64 variant are treated as equivalent. Explicit wrong architecture and ambiguous multi-manifest cases remain fail-closed.
2. CI policy/self-trigger coverage was repaired for the Stack semantic workflow, HA readonly workflow, HA exact-artifact workflow and HA target-binding workflow. P2A now also contains the post-target artifact freeze gate.

No new product known-failure entry is required; regression tests directly guard the repaired paths.

## PR chain at closure

```text
MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774

PR779=OPEN_DRAFT
PR780=OPEN_DRAFT
PR781=OPEN_DRAFT
PR782=OPEN_DRAFT
PR783=CLOSED_SUPERSEDED_UNMERGED
PR784=OPEN_DRAFT

MERGE_AUTHORIZATION=false
```

## Closure meaning

P2 is now complete:

```text
HA_P0_SOURCE_AND_COMPATIBILITY_PREPARATION=CLOSED_PASS
HA_P1_RUNTIME_TEMPLATE_CONVERGENCE_READONLY_PREFLIGHT=CLOSED_PASS
HA_P2_EXACT_2026_10_4_PACKAGE_AND_COMPONENT_TARGET=CLOSED_PASS

LIVE_HA_UPGRADE_READY=false
STACK_1_1_0_PUBLICATION=false
```

No Home Assistant live apply, runtime-template mutation, service restart, rollback, current-authority promotion, or Stack 1.1.0 publication has occurred.

## Next one gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_HOMEASSISTANT_P3_UPDATER_SOURCE_SIMULATION_AND_READONLY_PLAN_20261105_01

NEXT_GATE_T1_ACCESS=false
NEXT_GATE_T1_MUTATION=false
NEXT_GATE_BOARD_ACCESS=false
NEXT_GATE_MERGE=false
```

P3 must prove that the existing generic V2 updater can consume the frozen Home Assistant target, model the updater-owned runtime-template convergence plus Home Assistant image mutation as one bounded transaction, simulate apply/rollback behavior, and produce a read-only plan without entering the live T1 mutation boundary.
