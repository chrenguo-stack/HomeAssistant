# N3-W ESP32-C6 exact-artifact board-write runbook V1.0 — 2026-09-22

Status: `CURRENT_OPERATIONAL_RUNBOOK`

## Purpose

This document freezes the board-write method that should be reused for N3-W physical validation instead of rebuilding ad-hoc terminal commands in chat.

It is derived from the repository-versioned PR #437 Board-B writer and the physical evidence archived on 2026-09-20/21.

## Historical Board B method

The successful Board-B route was not "compile locally and run an arbitrary esptool command". It used four bound stages:

1. build one exact GitHub artifact from an exact source head/tree/config;
2. independently verify artifact member set, manifest and hashes;
3. run a repository-versioned target-specific preflight;
4. consume a one-shot preflight and perform a minimal application + OTA-data write.

For the final PR #437 physical artifact:

```text
SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_BLOB=37654481747b21ca51ccecc246bf84ca437ab7a9

WORKFLOW_RUN_ID=35553142523
ARTIFACT_ID=10619047221
ARTIFACT_NAME=n3w-pr437-4270f24-boardb-exact-source
ARTIFACT_ZIP_SIZE=731019
ARTIFACT_ZIP_SHA256=33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895

APPLICATION_OFFSET=0x10000
APPLICATION_SIZE=1145984
APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843

OTADATA_OFFSET=0x9000
OTADATA_SIZE=8192
OTADATA_INITIAL_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

PARTITION_TABLE_OFFSET=0x8000
PARTITION_TABLE_SIZE=0xC00
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

Historical Board-B writer authority:

```text
tools/execution_packages/n3w/kf096/pr437_board_b_write/executor.py
tests/execution_packages/n3w/kf096/pr437_board_b_write/test_executor.py
```

## Canonical write scope

Only these two partitions are written:

```text
0x9000  <- ota_data_initial.bin
0x10000 <- firmware.bin
```

The following are never part of this physical-validation write:

```text
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

This preserves board-specific provisioned identity and credentials stored outside the application/OTA-data write scope.

## Canonical preflight

Before any write, the target-specific executor must prove:

- artifact ZIP size/hash and exact member set;
- manifest source/tree/config/toolchain/hash binding;
- firmware image is for ESP32-C6;
- exact intended board identity or an explicit fail-closed board discriminator;
- 8 MB flash;
- Secure Boot state expected by the route;
- Flash Encryption state expected by the route;
- partition-table hash;
- current serial-port binding.

The preflight closure is single-use and currently expires after 900 seconds.

No write is permitted from a stale, consumed, replayed or target-mismatched preflight.

## Canonical mutation sequence

Immediately before mutation:

1. reload and validate the preflight;
2. revalidate artifact bytes;
3. fresh-read target identity and partition table;
4. consume the one-shot authorization/preflight;
5. issue the reviewed esptool write;
6. never broaden the write to bootloader, partition table, product NVS or full erase.

The reviewed write shape is:

```text
esptool --chip esp32c6 --port <PORT> --baud 460800 \
  --before default-reset --after hard-reset \
  write-flash \
  0x9000  ota_data_initial.bin \
  0x10000 firmware.bin
```

Operators should invoke the repository-versioned executor rather than retyping this low-level command directly.

## Correct post-write verification

Valid post-write oracles:

```text
APPLICATION_READBACK_SHA256 == frozen APPLICATION_SHA256
PARTITION_TABLE_READBACK_SHA256 == frozen PARTITION_TABLE_SHA256
BOARD_TARGET_IDENTITY == preflight identity
PRODUCT_NVS_WRITE == false by bounded write scope
POSTBOOT_DIRECT_RUNTIME_BASELINE == separately observed
```

Invalid oracle:

```text
POSTBOOT_OTADATA_SHA256 == OTADATA_INITIAL_SHA256
```

The OTA-data partition is expected to change after boot. Historical Board-B evidence already proved that comparing post-boot OTA-data byte-for-byte with `ota_data_initial.bin` creates a false failure.

This exact regression must not be reintroduced.

## Artifact acquisition on the physical Mac

The historical repository records prove independent artifact download/binding, but they do not preserve one canonical Mac-side download command.

For current operations the frozen host rule is therefore:

- use the GitHub CLI for GitHub API/authenticated artifact transport;
- do not use system `curl` as the primary artifact transport;
- verify downloaded ZIP size and SHA-256 before any board access;
- if the download fails, STOP before preflight; do not improvise alternate unverified artifact sources.

Preferred transport shape:

```text
gh api repos/<owner>/<repo>/actions/artifacts/<artifact-id>/zip > exact-artifact.zip
```

Then verify exact size and SHA-256 against the bound artifact authority.

## Host working-directory rule

Do not assume the terminal starts inside the repository.

A physical command package must either:

- use an explicit absolute repository path; or
- fetch the exact versioned executor by commit/ref without requiring the current directory to be a Git checkout.

A bare `git fetch` without first proving the working directory is a repository is forbidden in future physical instructions.

## Stop policy

Stop before board mutation on any of:

- artifact download failure;
- artifact size/hash mismatch;
- executor/ref mismatch;
- more/fewer USB targets than expected;
- target identity ambiguity;
- partition mismatch;
- stale preflight;
- authorization mismatch;
- serial port drift.

Do not "try another command" after such a stop until the failure class is understood.

## Current Board A adaptation

PR #471 adapts the same method to Board A while reusing the exact Board-B physical artifact.

The Board-A writer adds:

- hard rejection of the frozen Board-B identity;
- explicit operator confirmation that the connected target is Board A;
- exact application readback after write;
- partition-table readback after write;
- post-boot OTA-data observation for evidence only, never equality-gated.

```text
HISTORICAL_BOARD_B_METHOD_REUSED=true
AD_HOC_FLASH_COMMANDS_FORBIDDEN=true
SYSTEM_CURL_PRIMARY_ARTIFACT_TRANSPORT=false
POSTBOOT_OTADATA_BYTE_EQUALITY_ORACLE=false
```
