# N3-W T1_Core_Stack Clean Reference — R0H local host package cache source closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_LOCAL_PACKAGE_CACHE_SOURCE_IMPLEMENTATION_20261101_01

SOURCE_AUTHORITY_HEAD=c4984baf274d74d1459175153b62bed9a2b7626e

SOURCE_IMPLEMENTATION=PASS
SOURCE_REVIEW=PASS
SOURCE_CI=PASS
SOURCE_CLOSURE=CLOSED_PASS

LIVE_R0H_APPLY_BLOCKED_UNTIL_SOURCE_CLOSURE=false
T1_ACCESS=false
T1_A_MUTATION=false
T1_B_MUTATION=false
BOARD_ACCESS=false
T1_CORE_STACK_DEPLOYMENT=false
PR745_MERGE=false
PR705_UPWARD_MERGE=false
```

The R0H host-runtime local package-cache source gate is closed at exact source
`c4984baf274d74d1459175153b62bed9a2b7626e`.

This closure authorizes only progression to the next bounded physical gate. It does not
claim that Docker/Compose have been downloaded or installed on T1_B.

## 1. Implemented source

Repository-owned tool:

```text
tools/n3w_t1_host_runtime_cache.py
```

Supported phases:

```text
self-check
acquire
verify-archive
verify
install
```

The phase responsibilities are intentionally separated:

- `acquire`: exact Ubuntu candidate resolution and download-only dependency closure capture;
- `verify-archive`: portable file-only verification suitable for the durable Mac cache;
- `verify`: stricter T1/Linux verification including host contract, APT policy and .deb metadata;
- `install`: verified cache-only installation with package download disabled;
- `self-check`: source-level no-network-fallback and no-product-activation guard.

The historical `tools/n3w_t1_fresh_host_baseline.py` direct-install path is left unchanged
for compatibility. The Clean Reference R0H route uses the new cache tool.

## 2. Bundle identity and archive verification

The bundle manifest binds:

- Armbian version and board;
- Ubuntu ID/version/codename;
- package architecture;
- APT source policy;
- exact `docker.io` package version;
- exact `docker-compose-v2` package version;
- every downloaded .deb filename, size, SHA-256, package name, version and architecture.

The bundle ID is the SHA-256 of the canonical manifest.

Portable `verify-archive` requires only Python and the bundle files. It does not inspect
the target host OS, Armbian state, APT sources or dpkg metadata. Therefore the exact bundle
can be copied from T1_B to macOS and byte-verified there before installation is allowed.

## 3. T1-side verification and cache-only installation

The T1-side `verify` phase first performs the portable archive verification and then adds:

- exact supported host contract validation;
- exact APT source-policy validation;
- `dpkg-deb` package/version/architecture metadata validation.

The `install` phase first calls the strict T1 verification and then installs only the local
bundle members with:

```text
apt-get --no-download --no-remove install -y <local .deb members>
```

The installation path contains no `apt-get update`, download-only action or network package
fallback.

Docker is enabled and started only after the verified local install transaction. No
T1_Core_Stack application service activation authority is present.

## 4. Negative coverage

Focused tests cover:

- missing package member -> fail closed;
- extra package member -> fail closed;
- package-size mismatch -> fail closed;
- equal-length package-content tamper / SHA-256 mismatch -> fail closed;
- host-contract drift -> fail closed;
- post-install requested Docker/Compose package-version drift -> fail closed;
- cache-only install command includes `--no-download`;
- install path contains no APT metadata refresh/download operation;
- portable archive verification performs no host/APT probe;
- self-check contains no product activation authority.

## 5. CI closure

Exact source head:

```text
c4984baf274d74d1459175153b62bed9a2b7626e
```

Required observed CI:

```text
N3W T1 fresh install host-only CI=SUCCESS
run=41271295622

greenhouse-manager CI=SUCCESS
run=41271295734

Public repository safety CI=SUCCESS
run=41271295641

N3W T1 fresh install exact ARM64 CI=SUCCESS
run=41271295780
```

Earlier failures in this gate were all closed before the authority head:

1. Ruff import/executable-bit style issues;
2. Ruff import-block spacing issues;
3. portable Mac archive-verification capability gap found by independent closure review;
4. a negative test that changed file size while expecting only a hash mismatch.

The final authority head contains the capability repair and corrected negative coverage.

## 6. Physical boundary remains closed

No physical state was changed during this source gate:

```text
T1_ACCESS=false
T1_A_MUTATION=false
T1_B_MUTATION=false
BOARD_ACCESS=false
DOCKER_DOWNLOAD_ON_T1_B=false
DOCKER_INSTALL_ON_T1_B=false
T1_CORE_STACK_DEPLOYMENT=false
```

T1_A remains the preserved legacy/dirty upgrade specimen.

T1_B remains the R0-qualified Clean Reference target.

## 7. Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_T1B_DOWNLOAD_ONLY_CACHE_ACQUISITION_AND_MAC_ARCHIVE_20261101_01
```

The next gate must remain bounded:

```text
TARGET=T1_B
APT_METADATA_REFRESH_ALLOWED=true
PACKAGE_PAYLOAD_DOWNLOAD_ALLOWED=true
DOCKER_INSTALL_ALLOWED=false
DOCKER_SERVICE_START_ALLOWED=false
T1_CORE_STACK_DEPLOYMENT=false
T1_A_MUTATION=false
BOARD_ACCESS=false
```

Required order:

```text
fresh preflight
-> acquire/download-only on T1_B
-> T1-side verify
-> copy exact bundle to durable Mac cache
-> Mac verify-archive
-> STOP
```

Cache-only Docker/Compose installation is a later step and must not be combined with the
first download/archive transaction.
