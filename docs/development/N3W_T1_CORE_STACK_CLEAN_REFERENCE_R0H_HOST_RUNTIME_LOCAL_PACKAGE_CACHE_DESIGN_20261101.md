# N3-W T1_Core_Stack Clean Reference — R0H host-runtime local package cache design

Date: 2026-11-01

## 0. Decision

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_HOST_RUNTIME_LOCAL_PACKAGE_CACHE_DESIGN_20261101_01

PREVIOUS_R0H_DIRECT_ONLINE_INSTALL=SUPERSEDED_BEFORE_EXECUTION
PREVIOUS_R0H_LIVE_APPLY_EXECUTED=false

R0H_HOST_PACKAGE_CACHE=REQUIRED
FIRST_ACQUISITION_NETWORK_DOWNLOAD_COUNT_TARGET=ONE
FIRST_INSTALL_FROM_CACHE=true
REPEAT_INSTALL_FROM_CACHE=true
SILENT_NETWORK_FALLBACK=false

T1_CORE_STACK_DEPLOYMENT=false
T1_A_MUTATION=false
BOARD_ACCESS=false
```

R0H is revised before any T1_B host mutation. Docker Engine / Compose and the package
dependency closure are acquired once, archived on the Mac, and installed from the exact
local cache.

This advances only the Docker/Compose host-package caching part of the later O1 air-gapped
work. It does not claim that a completely fresh Armbian installation is fully air-gapped.

## 1. Why the route changes

The previous R0H design would run `apt-get update` and then install exact package versions
directly from Ubuntu repositories. That is safe but causes every fresh T1 to download the
same Docker/Compose package payload again.

The clean-reference project already uses durable exact-artifact caching for large product
artifacts. Host-runtime packages should follow the same operational principle:

```text
DOWNLOAD_ONCE
-> VERIFY
-> DURABLE_LOCAL_CACHE
-> CACHE_ONLY_INSTALL
-> REUSE_UNTIL_CACHE_IDENTITY_CHANGES
```

## 2. Cache is separate from T1_Core_Stack product identity

```text
CACHE_CLASS=R0H_HOST_RUNTIME_PACKAGE_BUNDLE
T1_CORE_STACK_ARTIFACT=false
PRODUCT_IDENTITY=false
```

The host bundle is bound to the environment that makes it safe to reuse:

- Armbian version;
- board;
- Ubuntu release/codename;
- architecture;
- APT source policy;
- exact `docker.io` package version;
- exact `docker-compose-v2` package version;
- every downloaded .deb filename, size and SHA-256.

A changed package set or changed supported host baseline produces a new cache identity.

## 3. Durable Mac cache root

Default durable path:

```text
~/Documents/N3W/host-runtime-cache/
```

Bundle layout:

```text
host-runtime-cache/
  <bundle-id>/
    manifest.json
    manifest.sha256
    packages/
      *.deb
```

The Mac cache is private operational storage and is not committed to GitHub.

GitHub stores only public-safe metadata such as:

- bundle ID;
- manifest SHA-256;
- package count;
- aggregate byte size;
- Docker/Compose exact package versions;
- OS/architecture binding.

## 4. First acquisition transaction

The first cache build runs only on an exact R0-qualified T1_B before Docker is installed.

```text
R0_READONLY_PASS
-> apt-get update
-> resolve exact docker.io candidate
-> resolve exact docker-compose-v2 candidate
-> apt-get --download-only exact package install request
-> collect downloaded dependency closure
-> generate manifest + per-file SHA256
-> archive/copy bundle to durable Mac cache
-> verify Mac copy byte-for-byte
-> only then allow installation
```

The first download may use the network. Installation must not.

The acquisition stage is a bounded host mutation only in the sense that APT metadata/cache
is populated; product state remains absent.

## 5. First installation must prove cache-only behavior

After durable Mac verification, the same exact package set is installed on T1_B using only
the downloaded package files.

The installer must enforce:

```text
APT_NO_DOWNLOAD=true
NETWORK_PACKAGE_FALLBACK=false
MISSING_PACKAGE=FAIL_STOP
HASH_MISMATCH=FAIL_STOP
```

The expected installation form is repository-owned automation equivalent to:

```text
apt-get --no-download install <exact local .deb set>
```

or another APT local-file form that is regression-tested to fail if the cached dependency
closure is incomplete.

Do not use `dpkg -i` plus an online `apt -f install` fallback.

## 6. Reuse on another fresh T1

For a later T1 with the same supported host contract:

```text
fresh R0 qualification
-> select exact compatible host-runtime bundle
-> copy bundle Mac -> T1 staging
-> verify manifest + every .deb SHA256
-> install with download disabled
-> verify exact package versions
-> verify Docker active/enabled
-> verify zero product state
```

No Docker/Compose package payload is downloaded again.

If the exact cached bundle is incompatible with the target host, STOP. Do not silently
download a replacement during a cache-only install. A new bundle must be explicitly acquired
and assigned a new bundle ID.

## 7. Bundle identity

The canonical bundle ID is the SHA-256 of a canonical manifest containing at least:

```text
schema
armbian_version
armbian_board
ubuntu_version_id
ubuntu_codename
architecture
apt_source_policy
docker_io_version
docker_compose_v2_version
package_members[
  filename,
  size_bytes,
  sha256
]
```

No machine identity, IP address, SSH host key, credential or secret is included.

## 8. Package closure requirements

The acquisition must include every package file APT needs beyond the exact fresh-Armbian
prestate to satisfy the Docker/Compose install transaction.

Acceptance requires:

```text
CACHE_ONLY_INSTALL_PROVEN=true
UNRESOLVED_DEPENDENCY_COUNT=0
NETWORK_DOWNLOAD_DURING_INSTALL=false
```

The cache is therefore tied to the supported fresh-Armbian host contract, not claimed to be
a universal Debian/Ubuntu Docker bundle.

## 9. Security and provenance

APT repository authentication remains the authority for the first acquisition.

After acquisition:

- every .deb is SHA-256 bound in the manifest;
- the manifest is SHA-256 bound as the bundle ID;
- all future transfers are verified before install;
- public GitHub evidence records hashes only;
- cache files remain on the operator Mac.

No `--allow-unauthenticated`, insecure repository option or unsigned local replacement is
allowed.

## 10. R0H post-install acceptance remains unchanged

After cache-only installation:

```text
DOCKER_PACKAGE_INSTALLED=true
COMPOSE_PACKAGE_INSTALLED=true
DOCKER_SERVICE_ACTIVE=true
DOCKER_SERVICE_ENABLED=true
TOTAL_CONTAINER_COUNT=0
TOTAL_IMAGE_COUNT=0
TOTAL_VOLUME_COUNT=0
ONLY_DEFAULT_DOCKER_NETWORKS=true
PRODUCT_PATH_RESIDUAL_COUNT=0
PRODUCT_UNIT_RESIDUAL_COUNT=0
PRODUCT_LISTENER_RESIDUAL_COUNT=0
T1_CORE_STACK_DEPLOYED=false
```

## 11. Relationship to O1

```text
R0H_DOCKER_COMPOSE_PACKAGE_CACHE=NOW
FULL_FRESH_ARMBIAN_AIRGAPPED_INSTALL=NOT_YET
O1_REMAINS_OPEN=true
```

R0H caching removes repeated Docker/Compose package downloads and creates reusable host
installation material. O1 later extends this into a complete factory/offline host installer,
including all package-index and host-dependency concerns required to operate without any
network dependency from a newly flashed machine.

## 12. Source work required before T1 mutation

The existing `tools/n3w_t1_fresh_host_baseline.py` does not currently implement durable
Mac cache acquisition/verification or cache-only install semantics.

Therefore:

```text
SOURCE_REPAIR_REQUIRED=true
LIVE_R0H_APPLY_BLOCKED_UNTIL_SOURCE_CLOSURE=true
```

Required bounded implementation:

1. add repository-owned host-runtime bundle manifest helpers;
2. add acquire/download-only mode;
3. add exact package-member hashing;
4. add cache-only local install mode with download disabled;
5. add missing-member/hash-mismatch/version-drift negative tests;
6. add no-network-fallback source guard;
7. keep all product activation operations forbidden.

## 13. Next one gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_LOCAL_PACKAGE_CACHE_SOURCE_IMPLEMENTATION_20261101_01

T1_ACCESS=false
T1_MUTATION=false
T1_CORE_STACK_DEPLOYMENT=false
BOARD_ACCESS=false
PR745_MERGE=false
PR705_UPWARD_MERGE=false
```
