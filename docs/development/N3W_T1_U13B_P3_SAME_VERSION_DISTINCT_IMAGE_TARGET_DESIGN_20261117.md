# N3-W T1 U13B P3 same-version distinct-image acceptance target design — 2026-11-17

## Decision

The previous physical-acceptance candidate Home Assistant 2026.10.3 is superseded.

It remains retained as historical research/artifact evidence, but it must not be
used for the real P3 physical-acceptance transaction because that would require
running a lower Home Assistant application version against a data directory
already used by 2026.10.4.

The replacement target is a metadata-only derivative of the exact predecessor:

```text
PREDECESSOR_APPLICATION_VERSION=2026.10.4
PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR_RUNTIME_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365

ACCEPTANCE_APPLICATION_VERSION=2026.10.4
ACCEPTANCE_IMAGE=local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1
DERIVATION=LABEL_ONLY_FROM_FROZEN_PREDECESSOR_ARTIFACT
```

## Frozen base authority

The acceptance target is not rebuilt from GHCR.

It starts from the exact artifact that produced the real predecessor currently
running on T1:

```text
BASE_ARTIFACT_RUN=41976542377
BASE_ARTIFACT_ID=13391983948
BASE_ARTIFACT_DIGEST_SHA256=df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2
BASE_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
BASE_ARCHIVE_SIZE_BYTES=835309535
BASE_UPSTREAM_MANIFEST_DIGEST=sha256:5881590fca108a6e6b5eb9fff1718baeddda9d6dd5b52d1594e3386fe33b4d66
```

## Allowed transformation

Only one fixed Docker config label is added:

```text
org.hahub.n3w.u13b.acceptance=p3-same-version-distinct-image-v1
```

The transformation rewrites the Docker image config JSON and manifest tag,
which changes the Docker config digest / image ID, but it does not alter any
filesystem layer.

CI must prove:

- base and target application version are both 2026.10.4;
- base artifact is the frozen artifact above;
- no registry pull is used to derive the target;
- rootfs diff IDs are byte-for-byte identical;
- runtime Config is identical after removing Labels;
- target Labels equal predecessor Labels plus exactly the acceptance label;
- target Docker image ID differs from predecessor Docker image ID;
- the derived docker-save archive reloads and passes portable identity;
- T1 access/mutation remains false.

## Why this is a valid rollback-mechanics fixture

P3 is intended to test the N3-W OTA and U13B mechanics, not Home Assistant
downgrade compatibility.

With this target:

```text
Home Assistant application: 2026.10.4 -> 2026.10.4
persistent data schema: unchanged by version
Docker image identity: predecessor A -> acceptance target B
```

The product can still exercise:

- U6 exact predecessor export to fresh recovery USB;
- U7 consistent HA data backup;
- U10 predecessor removal;
- U11 loading/starting a distinct target image;
- U13B target cleanup;
- U13B exact predecessor image restore from USB;
- HA data restore and predecessor runtime restart.

## Superseded 2026.10.3 work

The following remain historical evidence only:

- 2026.10.3 compatibility review;
- exact 2026.10.3 GitHub Actions artifact;
- 2026.10.3 target binding;
- the prior non-live/live source packages that bind that target.

They are not current physical-acceptance authority and must not be granted live
execution authority.

A new exact same-version artifact must be produced and then separately bound
into replacement P3 target/live manifests.

## Current boundary

```text
P3_2026_10_3_PHYSICAL_TARGET_SUPERSEDED=true
P3_SAME_VERSION_ARTIFACT_READY=false
REAL_T1_ACCESS=false
T1_MUTATION=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```
