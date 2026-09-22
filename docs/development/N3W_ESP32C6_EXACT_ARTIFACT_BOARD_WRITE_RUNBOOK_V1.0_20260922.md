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
- fresh ROM-silicon identity capture bound to the operator-confirmed physical target;
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


## Terminal command formatting rule

All terminal command blocks supplied for physical execution must be directly pasteable into the user's shell.

Requirements:

```text
INLINE_SHELL_COMMENT_LINES=false
HASH_COMMENT_LINES_IN_COMMAND_BLOCKS=false
PASTE_READY_COMMAND_BLOCKS=true
```

Do not place `# ...` comment lines inside terminal command blocks. Explanations must be written outside the code block.

This rule exists because the user's current shell execution path treated an inline `#` comment line as a command and stopped with:

```text
zsh: command not found: #
```

A command block that is intended for direct execution must therefore contain executable shell syntax only.

Shell options must not leak into the user's interactive zsh after the command finishes. In particular, `set -u` can break macOS shell-session save hooks when they reference unset parameters.

```text
SHELL_OPTION_SIDE_EFFECTS_SCOPED=true
INTERACTIVE_SHELL_GLOBAL_SET_U=false
OPERATOR_FACING_SET_U_FORBIDDEN=true
PASTE_READY_COMMANDS_USE_EXPLICIT_CHECKS=true
```

For operator-facing macOS/zsh command blocks, do not use `set -u` at all, even inside a subshell. Use explicit variable checks and command-result checks instead. A cleanup line such as `unsetopt nounset 2>/dev/null || true` may be given separately when an earlier command already contaminated the interactive shell.

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

The Board-A writer uses:

- fresh ROM-silicon identity capture;
- explicit operator confirmation that the connected physical target is Board A;
- binding of the write to the exact fresh silicon hash, exact serial-port locator and a single-use 15-minute preflight;
- exact application readback after write;
- partition-table readback after write;
- post-boot OTA-data observation for evidence only, never equality-gated.

The current contents of the application partition are not an identity authority and are not a preflight admission requirement.

```text
HISTORICAL_BOARD_B_METHOD_REUSED=true
PREWRITE_APPLICATION_HASH_REQUIRED=false
PREWRITE_APPLICATION_HASH_USED_FOR_IDENTITY=false
FRESH_ROM_SILICON_IDENTITY_REQUIRED=true
OPERATOR_PHYSICAL_TARGET_CONFIRMATION_REQUIRED=true
AD_HOC_FLASH_COMMANDS_FORBIDDEN=true
SYSTEM_CURL_PRIMARY_ARTIFACT_TRANSPORT=false
POSTBOOT_OTADATA_BYTE_EQUALITY_ORACLE=false
```


## Board identity and unknown prewrite firmware rule

Board identity and existing application contents are separate concerns.

A board may be new, blank, factory-programmed, running an older test image, or running an unknown application. None of those states should prevent an application refresh merely because the pre-write application hash is not known.

```text
APPLICATION_HASH_IS_BOARD_IDENTITY=false
PREWRITE_APPLICATION_HASH_REQUIRED=false
UNKNOWN_PREWRITE_APPLICATION_ALLOWED=true
FRESH_ROM_SILICON_IDENTITY_CAPTURE=true
WRITE_BOUND_TO_FRESH_SILICON_HASH=true
USB_PORT_IS_LOCATOR_ONLY=true
```

For a board that does not yet have a trusted logical A/B inventory entry, the safe binding is established at preflight time:

1. the operator identifies the physical target;
2. the executor reads the ROM-silicon identity;
3. the preflight records the public-safe silicon hash and serial-port hash;
4. the write command must repeat that exact silicon hash explicitly;
5. the executor re-reads the silicon immediately before mutation and requires equality with the preflight.

An old application hash may be collected for diagnostics, but it must never be required to distinguish Board A from Board B or to admit a new board into the write path.

A truly blank/new board may still require a different factory-provisioning route if its bootloader, partition table, or product provisioning state is absent or incompatible. That is a separate concern from application identity.

### 2026-09-22 correction

The first Board-A preflight stopped because the executor treated a historical Board-B silicon hash as a permanent exclusion rule. That was too strict for a project whose A/B labels had previously been corrected and is not a general solution for new boards.

The replacement contract is:

```text
HISTORICAL_OTHER_BOARD_HASH_AS_HARD_EXCLUSION=false
FRESH_SILICON_HASH_AS_CURRENT_WRITE_BINDING=true
EXISTING_APPLICATION_HASH_AS_DISCRIMINATOR=false
OPERATOR_TARGET_CONFIRMATION=true
WRITE_REQUIRES_PREFLIGHT_HASH_ECHO=true
WRITE_REQUIRES_FRESH_SILICON_REREAD=true
```

The earlier STOP remains valid as a fail-closed event, but its hard-exclusion rule is superseded by this corrected binding model.


## Runtime observer identity rule

Do not assume that the fresh ROM-silicon-derived hardware hash can always be joined directly to the Manager registration table to identify an already-provisioned runtime node.

The product runtime derives a hardware ID from the current STA MAC during pairing, but an already-provisioned runtime loads its persisted peer/broker state and operates under the persisted `node_id`. Historical provisioning, board-label correction, or copied/restored NVS can therefore make a direct silicon-hash -> current Manager-registration join an invalid observation oracle.

```text
ROM_SILICON_HASH_IS_WRITE_TARGET_BINDING=true
ROM_SILICON_HASH_IS_ALWAYS_RUNTIME_NODE_LOOKUP_KEY=false
PREWRITE_APPLICATION_HASH_IS_RUNTIME_NODE_LOOKUP_KEY=false
PROVISIONED_NODE_ID_IS_RUNTIME_IDENTITY_AUTHORITY=true
MANAGER_CANONICAL_CURSOR_IS_RUNTIME_LIVENESS_AUTHORITY=true
```

For physical runtime acceptance, bind the connected board to Manager canonical state through a runtime identity that the board actually uses. Preferred public-safe methods are:

1. exact persisted `node_id` from a read-only product-state authority, emitted only as a hash; or
2. an exact boot-session correlation between the board's read-only lab diagnostic snapshot and Manager `n3w_canonical_cursors`.

A zero-row Manager registration lookup by fresh ROM hardware hash is an observer mismatch until proven otherwise; it is not by itself a product Direct-path failure.


## Current-only canonical cursor / reset-race rule

Do not try to identify a running board by reading a pre-reset lab-diagnostic boot session and then looking for that same boot session in Manager `n3w_canonical_cursors` after the read operation has reset the board.

The Manager canonical table is current-state storage, not historical boot-session storage:

```text
n3w_canonical_cursors.node_id=PRIMARY_KEY
ONE_CURRENT_CURSOR_PER_NODE=true
OLD_BOOT_CURSOR_RETAINED=false
```

When a new boot for the same `node_id` advances canonical state, the row is updated in place to the new `boot_session_hex`. The replay registry similarly advances its highest session and removes old-session replay rows. Therefore an esptool/NVS read that causes a reset can erase the very old-session lookup key that an observer intended to use.

```text
PRE_RESET_DIAG_BOOT_TO_POST_RESET_CURRENT_CURSOR_JOIN=INVALID_RACY_ORACLE
ZERO_MATCH_AFTER_RESET_IS_NOT_PRODUCT_FAILURE=true
CURRENT_CURSOR_IS_LIVENESS_AUTHORITY_NOT_BOOT_HISTORY=true
```

Correct runtime identity binding for an already-provisioned live board should use a controlled transition observed from both sides:

1. take a read-only Manager canonical snapshot before touching the board;
2. issue one bounded, non-persistent reset to the operator-confirmed board;
3. observe which current canonical node changes to a new boot session and resumes fresh Direct telemetry;
4. require exactly one matching node transition;
5. bind that public-safe node hash for the remainder of the physical gate;
6. start the same-boot acceptance window only after that post-reset Direct baseline is established.

This method does not depend on current application bytes, historical A/B labels, or a ROM-hardware-hash-to-registration join.

```text
RUNTIME_IDENTITY_BINDING_METHOD=PRE_SNAPSHOT_PLUS_CONTROLLED_RESET_PLUS_CANONICAL_BOOT_CHANGE
EXACT_ONE_NODE_BOOT_CHANGE_REQUIRED=true
PERSISTENT_MUTATION=false
SAME_BOOT_WINDOW_STARTS_AFTER_CONTROLLED_RESET=true
```
