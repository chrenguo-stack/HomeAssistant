# N3-W T1_Core_Stack Clean Reference — R0H T1_B download-only cache acquisition and Mac archive closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_T1B_DOWNLOAD_ONLY_CACHE_ACQUISITION_AND_MAC_ARCHIVE_20261101_01

SOURCE_AUTHORITY_HEAD=c4984baf274d74d1459175153b62bed9a2b7626e
TARGET=T1_B

T1_TOOL_TRANSFER_SHA256_MATCH=true
SELF_CHECK_STATUS=PASS
ACQUIRE_STATUS=PASS
T1_VERIFY_STATUS=PASS
MAC_VERIFY_ARCHIVE_STATUS=PASS

BUNDLE_ID=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
PACKAGE_COUNT=5
TOTAL_BYTES=79391752
REQUESTED_DOCKER_IO_VERSION=29.1.3-0ubuntu4.1
REQUESTED_DOCKER_COMPOSE_V2_VERSION=2.40.3+ds1-0ubuntu1

DOCKER_INSTALL_PERFORMED=false
DOCKER_SERVICE_STARTED=false
T1_CORE_STACK_DEPLOYED=false
T1_A_MUTATION=false
BOARD_ACCESS=false

GATE_RESULT=CLOSED_PASS
```

The first exact host-runtime package bundle was acquired on the R0-qualified T1_B using the
repository-owned download-only path. The bundle was verified on T1_B, copied to the durable
Mac cache, and independently verified there with the portable `verify-archive` phase.

No Docker/Compose package installation occurred in this gate.

## 1. Exact bundle identity

```text
BUNDLE_ID=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
PACKAGE_COUNT=5
TOTAL_BYTES=79391752
```

Requested package versions:

```text
docker.io=29.1.3-0ubuntu4.1
docker-compose-v2=2.40.3+ds1-0ubuntu1
```

Observed bundle members:

```text
docker.io_29.1.3-0ubuntu4.1_arm64.deb
docker-compose-v2_2.40.3+ds1-0ubuntu1_arm64.deb
containerd_2.2.2-0ubuntu1.2_arm64.deb
runc_1.4.0-0ubuntu1_arm64.deb
libnftables1_1.1.6-1_arm64.deb
```

The durable Mac cache uses the class path:

```text
~/Documents/N3W/host-runtime-cache/<bundle-id>
```

The exact local username/path expansion is private operational information and is not part
of public repository authority.

## 2. Acquisition evidence

The repository tool reported:

```text
phase=acquire
status=PASS
network_download_performed=true
cache_only_install=false
production_service_start=false
board_access=false
package_count=5
total_bytes=79391752
```

This proves the package payload was downloaded but not installed by the acquisition phase.

## 3. T1-side verification

The same bundle then passed strict T1 verification:

```text
phase=verify
status=PASS
network_download_performed=false
cache_only_install=false
production_service_start=false
board_access=false
```

This verification includes the exact supported host contract, APT source policy, manifest
integrity, exact package-member set and .deb package/version/architecture metadata.

## 4. Mac archive verification

After transfer to the durable Mac cache, portable archive verification reported:

```text
phase=verify-archive
status=PASS
bundle_id=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
package_count=5
total_bytes=79391752
network_download_performed=false
```

This establishes the Mac copy as a byte-verified reusable archive.

## 5. Installation boundary remains closed

Post-acquisition checks confirmed:

```text
DOCKER_INSTALL_PERFORMED=false
DOCKER_SERVICE_STARTED=false
T1_CORE_STACK_DEPLOYED=false
```

Therefore the download/archive gate did not cross into host-runtime installation or product
deployment.

## 6. Preflight false-negative note

An earlier ad-hoc shell preflight incorrectly matched unquoted lines in
`/etc/armbian-release`. The real file contains quoted values. Read-only diagnostics showed:

```text
VERSION="26.05.0"
BOARD="S912-Phicomm-T1"
DPKG_ARCH=arm64
DOCKER_COMMAND_PRESENT=false
DOCKER_IO_PACKAGE_PRESENT=false
DOCKER_COMPOSE_V2_PACKAGE_PRESENT=false
VAR_LIB_DOCKER_PRESENT=false
VAR_LIB_CONTAINERD_PRESENT=false
DOCKER_SOCKET_PRESENT=false
```

This was a shell-preflight bug only. The repository cache tool parses quoted assignment values
correctly and required no source repair.

## 7. Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_T1B_CACHE_ONLY_INSTALL_AND_POSTINSTALL_ACCEPTANCE_20261101_01
```

The next gate may install only this exact verified bundle and may start/enable Docker as a host
runtime prerequisite. It must not deploy or start any T1_Core_Stack application service.

Required post-install acceptance:

```text
BUNDLE_ID_EXACT_MATCH=true
CACHE_ONLY_INSTALL=true
NETWORK_DOWNLOAD_DURING_INSTALL=false
DOCKER_PACKAGE_VERSION_EXACT=true
COMPOSE_PACKAGE_VERSION_EXACT=true
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
T1_A_MUTATION=false
BOARD_ACCESS=false
```
