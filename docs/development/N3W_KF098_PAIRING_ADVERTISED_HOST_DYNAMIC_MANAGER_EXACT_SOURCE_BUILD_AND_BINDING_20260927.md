# N3W KF-098 Manager exact-source build and binding — 2026-09-27

## Gate

```text
TASK=N3W_KF098_PAIRING_ADVERTISED_HOST_DYNAMIC_MANAGER_EXACT_SOURCE_BUILD_AND_BINDING_20260927_01
RESULT=PASS
```

This gate binds the Manager live-candidate image for the KF-098 pairing
advertised-host dynamic repair. It is source/build-only. It does not deploy,
restart, recreate, or modify the live T1 Manager and does not access any board.

## Exact source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
SOURCE_SHA=575ce642e372961e21de14a36eba5877082de3cf
SOURCE_TREE=7f1641827b75668aa220832b7663bf81d98633ba
DOCKERFILE_BLOB=82ee1312905c2d289ef7d6e231333091030df212
PYPROJECT_BLOB=48c271cdeb7ba7a8b25f8fd2807d845f42c2c069
```

The repository `main` still resolved to the same SOURCE_SHA at final binding.

## Formal build

The first successful build run `36329118915` produced a technically valid
image but its standalone `manifest.sha256` referenced a runner-local absolute
path. That artifact is historical only and MUST NOT be used for T1 deployment.

The portable checksum packaging was repaired in workflow commit:

```text
WORKFLOW_COMMIT=4490a4f0530b04632717e98891e94d799be750b1
```

The authoritative replacement build is:

```text
RUN_ID=36329597775
RUN_RESULT=SUCCESS
ARTIFACT_ID=10935052471
ARTIFACT_NAME=n3w-kf098-manager-exact-source-575ce642
ARTIFACT_DIGEST=sha256:41dde2129aa64623746257814e7568f8a8d6948ad299766d7a1b1ea7f3bdf9a5
ARTIFACT_EXPIRES_AT=2026-10-27T15:29:17Z
```

Independent download verification reproduced the same ZIP SHA-256:

```text
DOWNLOADED_ARTIFACT_ZIP_SHA256=41dde2129aa64623746257814e7568f8a8d6948ad299766d7a1b1ea7f3bdf9a5
ARTIFACT_DIGEST_MATCH=PASS
```

## Manager image binding

```text
IMAGE_ID=sha256:49c9fcc0a17d47678b0667c48a06f9a9475609a757e510ca148983b53ed537e3
IMAGE_OS=linux
IMAGE_ARCHITECTURE=arm64
PRODUCT_ENTRYPOINT=greenhouse-manager
IMAGE_USER=greenhouse
RUNTIME_UID=999
RUNTIME_GID=999
```

The immutable image tar inside the artifact is:

```text
GREENHOUSE_MANAGER_ARM64_TAR_SIZE=59138560
GREENHOUSE_MANAGER_ARM64_TAR_SHA256=6392b8c9bb87d95404346583d6f44967bd4e20fcc092be393c45f75a4ca7a5b2
```

The later T1 live candidate MUST be loaded from this exact tar and rebound to
the exact IMAGE_ID above. A later rebuild from the same source is not an
equivalent authority.

## Exact source archive binding

```text
EXACT_SOURCE_TAR_GZ_SIZE=732232
EXACT_SOURCE_TAR_GZ_SHA256=6ba09753f067e32f8d1a9fc6486218c15143303dd4970aaa8e608c54a77f9be6
```

The artifact manifest independently binds:

```text
IMAGE_INSPECT_JSON_SHA256=bdd034dae2983be68d484f8eb41abc600e16772966ec2bef17db87d413581a97
RUNTIME_IDENTITY_SHA256=ee6c132ea6d8df63aa259bfcdd6b4f2557d8338244acbf0ed4b388fff6c9513c
SOURCE_CORE_HASHES_SHA256=23f1e00cf0185ccf09f2bbbe01cd5f1167b4c7ce8b38c7e8602569adea6da03f
IMAGE_CORE_HASHES_SHA256=23f1e00cf0185ccf09f2bbbe01cd5f1167b4c7ce8b38c7e8602569adea6da03f
CORE_SOURCE_BYTE_BINDING=PASS
```

The two exact KF-098 core files were compared byte-for-byte by SHA-256 between
the repository source and the installed image:

- `greenhouse_manager/runtime/config.py`
- `greenhouse_manager/runtime/n3w_simplified_discovery.py`

The source and image hash maps were identical.

## Portable manifest closure

The replacement artifact was downloaded independently after the workflow
completed. From the extracted directory:

```text
sha256sum -c manifest.sha256
manifest.json: OK
```

Every file record in `manifest.json` was then independently recomputed for
both byte size and SHA-256. All records matched.

```text
PORTABLE_MANIFEST_CHECK=PASS
ALL_MANIFEST_FILE_BINDINGS=PASS
```

## Scope boundaries

```text
T1_ACCESS=false
T1_MUTATION=false
LIVE_MANAGER_RECREATE=false
BROKER_MUTATION=false
BOARD_ACCESS=false
BOARD_MUTATION=false
PR474_SOURCE_CHANGE=false
```

This gate does not prove live T1 deployment behavior. It only establishes the
single exact Manager image/source artifact that may be used by the next
live-candidate preflight and cutover gate.

## Binding decision

```text
KF098_MANAGER_EXACT_SOURCE_BUILD=PASS
KF098_MANAGER_EXACT_ARTIFACT_BINDING=PASS
AUTHORITATIVE_ARTIFACT_ID=10935052471
AUTHORITATIVE_IMAGE_ID=sha256:49c9fcc0a17d47678b0667c48a06f9a9475609a757e510ca148983b53ed537e3
FIRST_BUILD_ARTIFACT=HISTORICAL_DO_NOT_DEPLOY
MERGE_BLOCKER_COUNT=0
```
