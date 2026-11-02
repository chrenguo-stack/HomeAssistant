# N3-W T1_Core_Stack Clean Reference — R0H T1_B download-only cache acquisition and Mac archive preflight

Date: 2026-11-01

## 0. Gate

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_T1B_DOWNLOAD_ONLY_CACHE_ACQUISITION_AND_MAC_ARCHIVE_20261101_01

SOURCE_AUTHORITY_HEAD=c4984baf274d74d1459175153b62bed9a2b7626e
SOURCE_CLOSURE=CLOSED_PASS

TARGET=T1_B
T1_A_MUTATION=false
BOARD_ACCESS=false
T1_CORE_STACK_DEPLOYMENT=false

APT_METADATA_REFRESH_ALLOWED=true
PACKAGE_PAYLOAD_DOWNLOAD_ALLOWED=true
DOCKER_INSTALL_ALLOWED=false
DOCKER_SERVICE_START_ALLOWED=false
COMPOSE_INSTALL_ALLOWED=false
PRODUCT_SERVICE_START_ALLOWED=false
```

## 1. Required order

```text
T1_B fresh preflight
-> exact tool transfer
-> tool self-check
-> acquire/download-only
-> T1-side verify
-> derive bundle ID
-> copy exact bundle T1_B -> durable Mac cache
-> Mac verify-archive
-> STOP
```

No Docker/Compose installation is permitted in this gate.

## 2. Preflight requirements

Before acquisition, T1_B must still satisfy the R0 host assumptions relevant to this gate:

- Armbian 26.05.0 / board S912-Phicomm-T1;
- Ubuntu resolute / arm64;
- Docker command absent;
- `docker.io` and `docker-compose-v2` packages absent;
- no Docker/containerd runtime data residue;
- no product deployment or product-service activation.

If any of these no longer hold, STOP rather than adapting the host.

## 3. Exact source transfer

Transfer only these repository-owned files from exact source authority
`c4984baf274d74d1459175153b62bed9a2b7626e`:

```text
tools/n3w_t1_fresh_host_baseline.py
tools/n3w_t1_host_runtime_cache.py
```

The operator must verify transfer byte identity before execution.

## 4. Acquisition boundary

Run only:

```text
python3 n3w_t1_host_runtime_cache.py --phase self-check
python3 n3w_t1_host_runtime_cache.py --phase acquire --cache-dir <empty T1 staging path>
python3 n3w_t1_host_runtime_cache.py --phase verify --cache-dir <same T1 staging path>
```

The acquire phase may:

- run `apt-get update`;
- resolve exact Ubuntu candidates;
- download the exact Docker/Compose dependency closure.

It must not install packages.

## 5. Durable Mac archive

After T1 verification passes:

1. read `manifest.sha256` as the bundle ID;
2. copy the entire staging directory into:
   `~/Documents/N3W/host-runtime-cache/<bundle-id>/`;
3. verify the copied bundle on macOS using:
   `--phase verify-archive`.

The Mac archive must be verified before any future install gate.

## 6. Evidence to preserve

Capture at least:

```text
SOURCE_AUTHORITY_HEAD
T1_TOOL_TRANSFER_SHA256_MATCH
SELF_CHECK_STATUS
ACQUIRE_STATUS
BUNDLE_ID
PACKAGE_COUNT
TOTAL_BYTES
REQUESTED_DOCKER_IO_VERSION
REQUESTED_DOCKER_COMPOSE_V2_VERSION
T1_VERIFY_STATUS
MAC_ARCHIVE_PATH_CLASS
MAC_VERIFY_ARCHIVE_STATUS
DOCKER_INSTALL_PERFORMED=false
DOCKER_SERVICE_STARTED=false
T1_CORE_STACK_DEPLOYED=false
T1_A_MUTATION=false
BOARD_ACCESS=false
```

Do not publish the T1 IP address, local Mac username/path expansion, SSH host key or any
credential/secret in the public repository.

## 7. Stop point

```text
STOP_AFTER=MAC_VERIFY_ARCHIVE_PASS
AUTO_INSTALL=false
```

The next gate after successful archive verification is a separate cache-only
Docker/Compose installation and R0H post-install acceptance gate.
