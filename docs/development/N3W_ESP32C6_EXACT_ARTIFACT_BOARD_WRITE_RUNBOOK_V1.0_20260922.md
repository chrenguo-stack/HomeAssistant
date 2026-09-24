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

For an **already provisioned board whose bootloader and partition table have been freshly proven compatible with the exact artifact**, only these two partitions are written:

```text
0x9000  <- ota_data_initial.bin
0x10000 <- firmware.bin
```

For that existing-board physical-validation route:

```text
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

This preserves board-specific provisioned identity and credentials stored outside the application/OTA-data write scope.

This two-region route is **not** a generic fresh-silicon rule. A replacement/new board must first prove that its bootloader and partition table are already compatible before inheriting the existing-board delta-write method.

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

## macOS esptool invocation and serial-open guard — 2026-09-24

A standalone `esptool` executable and `python3 -m esptool` are not assumed to use the same Python/`pyserial` environment.

The 2026-09-24 replacement-board preflight observed the following exact host-side sequence:

```text
STANDALONE_ESPTOOL_RESOURCE_BUSY=OBSERVED_REPEATEDLY
LSOF_VISIBLE_OWNER=false
CU_POSIX_OPEN=PASS
TTY_POSIX_OPEN=PASS
PYTHON_MODULE_ESPTOOL_VERSION=5.3.1
PYTHON_MODULE_PYSERIAL_VERSION=3.5
PYTHON_MODULE_ROM_READ_MAC=PASS
PYTHON_MODULE_GET_SECURITY_INFO=PASS
PYTHON_MODULE_FLASH_ID=PASS
```

Therefore, for operator-facing macOS ESP32-C6 work:

- prefer the verified interpreter/module form `python3 -m esptool`;
- record the actual `esptool` and `pyserial` versions when host-tool ambiguity matters;
- treat `Resource busy` that occurs before the serial port is successfully opened as a host/toolchain access failure, not proof of an ESP32-C6, ROM, Flash or application failure;
- check both `/dev/cu.usbmodem*` and `/dev/tty.usbmodem*`;
- if `lsof` shows no owner, a no-data POSIX open/close probe can distinguish a generally openable serial node from an `esptool`/`pyserial` path problem;
- do not repeatedly retry `esptool` against a persistent open failure before classifying the host-side failure;
- on interactive zsh, do not use a bare unmatched wildcard as the sole USB-target count oracle because zero matches can terminate the command with `no matches found`; use a zero-match-safe enumeration method.

The USB device path remains a temporary locator only. Fresh ROM silicon evidence, not the path, is the board-identity authority.

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

## ESP32-C6 post-write readback state guard — 2026-09-24

A successful `write-flash` followed by failed `read-flash` commands is not automatically a failed write.

The replacement Board C first-write run produced:

```text
FLASH_WRITE_COMMAND=PASS
POSTWRITE_READBACK_COMMAND_COUNT=4
POSTWRITE_READBACK_COMMAND_SUCCESS_COUNT=0
READBACK_HASH_MISMATCH_PROVEN=false
```

Every failed readback still connected to the ESP32-C6 over USB-Serial/JTAG, then stopped with:

```text
Failed to configure SPI flash pins
C000: Bad data length
```

The failed readback shape used `--no-stub --before no-reset` immediately after a write session that had run the flasher stub. This proves a readback-procedure failure, not a content mismatch.

Operational guard:

```text
READBACK_COMMAND_FAILURE_IS_NOT_HASH_MISMATCH=true
AUTO_REWRITE_AFTER_READBACK_COMMAND_FAILURE=false
AUTO_ERASE_AFTER_READBACK_COMMAND_FAILURE=false
FRESH_STUB_READBACK_RECOVERY_REQUIRED=true
```

For ESP32-C6 post-write verification, prefer a fresh connection with the normal esptool flasher stub for `read-flash`. Do not carry a `--no-stub --before no-reset` readback sequence forward from a prior stub-backed write session without a separately proven reason.

When several adjacent written regions together form the exact factory image, one contiguous readback may be used and compared against the frozen factory-image hash. This reduces reconnect/state transitions and still verifies every byte in the written range.

If the readback command itself fails, preserve the successful write as an unverified mutation and stop. Do not replay the write authorization.

## Validated fresh-stub readback recovery — 2026-09-24

The replacement Board C readback recovery physically validated the preceding guard.

Observed result:

```text
READBACK_COMMAND=PASS
READBACK_SIZE=1458496
FACTORY_RANGE_EXACT_MATCH=true
BOOTLOADER_READBACK_MATCH=true
PARTITION_TABLE_READBACK_MATCH=true
OTADATA_INITIAL_READBACK_MATCH=true
APPLICATION_READBACK_MATCH=true
RESULT=PASS_NEW_BOARD_C_POSTWRITE_EXACT_READBACK
```

The contiguous factory-range SHA-256 matched the frozen `firmware.factory.bin`:

```text
d8aa60082eca0482fe14806d8f4445223d3ccd4f87ba05d433b3ef31c187d304
```

This proves the earlier four post-write failures were readback-procedure failures, not write-content failures.

```text
FIRST_WRITE_CONTENT_VERIFIED=true
REWRITE_REQUIRED=false
AUTO_ERASE_REQUIRED=false
```

## Validated replacement-board first boot — 2026-09-24

The replacement Board C first normal boot after the verified exact first-write produced a fresh unprovisioned N3-W state:

```text
HARDWARE_ID_SHA256=f972633ca16463c8324a6921b60a2916c71bc9cab102333049d56449005b636b
POSTBOOT_NVS_CHANGED_FROM_BLANK=true
POSTBOOT_NVS_NON_FF_BYTE_COUNT=5242
N3W_NAMESPACE_PRESENT=true
SETUP_SECRET_KEY_PRESENT=true
PAIRING_INTENT_KEY_PRESENT=true
PROVISIONED_PEER_KEY_PRESENT=false
PROVISIONED_BROKER_KEY_PRESENT=false
OLD_BOARD_C_IDENTITY_REUSE=false
RESULT=PASS_NEW_BOARD_C_UNPROVISIONED_FIRST_BOOT
```

This validates the intended fresh-silicon transition:

```text
EXACT_FIRST_WRITE
-> VERIFIED_FACTORY_RANGE
-> NORMAL_APPLICATION_BOOT
-> NEW_SETUP_SECRET_AND_PAIRING_INTENT
-> UNPROVISIONED
```

No old logical node identity or broker credentials were inherited.

### Fresh-board onboarding display boundary

For the frozen Production Gateway Selection V1 target, the LCD provisioning QR is the ESPHome Wi-Fi fallback-AP QR generated from `App.get_name()`. It is not the N3-W `GHN3W2` pairing payload.

The product component exposes `pairing_qr_payload()` internally and logs the unprovisioned hardware/pairing identifiers, but the production target does not wire the secret-bearing N3-W pairing payload to the LCD or a public log.

```text
LCD_QR_PURPOSE=WIFI_PROVISIONING_ONLY
LCD_QR_IS_N3W_SETUP_SECRET_PAYLOAD=false
RAW_SETUP_SECRET_PUBLIC_LOG_ALLOWED=false
```

Therefore fresh-board onboarding must keep Wi-Fi provisioning and N3-W Setup-Secret transfer as separate steps and preserve the private-secret boundary.

## Validated fresh-board private pairing handoff materialization — 2026-09-24

For the replacement Board C, the first-boot private NVS readback was parsed offline and the exact fresh pairing handoff was materialized without reopening the board or contacting T1.

Observed public-safe result:

```text
SOURCE_NVS_SHA256=5619374bab10ad2b942e1315a006331b588eaa6daec256f0d92ed82b9f1cb28f
HARDWARE_ID_SHA256=f972633ca16463c8324a6921b60a2916c71bc9cab102333049d56449005b636b
PAIRING_ID_SHA256=d9f6431ff0e81a21f10d87271244d6727cbe1c8dc24c6f542018131b32c53e72
SETUP_SECRET_ENCODED_LENGTH=43
PRIVATE_HANDOFF_SHA256=2ea35936f075de5d919b60009b977f43df66a3739b52b1fbf5068e532fa35b03
PRIVATE_HANDOFF_MODE=0600
PAIRING_ID_RAW_EXPOSED=false
SETUP_SECRET_EXPOSED=false
BOARD_ACCESS=false
T1_ACCESS=false
RESULT=PASS_NEW_BOARD_C_PRIVATE_PAIRING_HANDOFF_MATERIALIZATION
```

Operational ordering guard for fresh-board first registration:

```text
CAPTURE_PRIVATE_HANDOFF_BEFORE_WIFI_PAIRING_WINDOW=true
RAW_SETUP_SECRET_PUBLIC_OUTPUT=false
PAIRING_ID_PUBLIC_OUTPUT_HASH_ONLY=true
PRIVATE_HANDOFF_MODE_REQUIRED=0600
```

Reason: the Manager pending/session lifetime is bounded. When possible, materialize and bind the private handoff before the board is placed on the production LAN so operator time is not consumed extracting the secret inside the live pairing window.

The private handoff must remain local/private until the exact fresh Manager registration for the same hardware and pairing identity is observed as pending and the delivery TTL/precondition gate is ready. Do not deliver a secret merely because the board obtained Wi-Fi.

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

## Fresh-silicon first-write artifact-layout guard — 2026-09-24

A new/replacement ESP32-C6 must not inherit the historical existing-board `0x9000 + 0x10000` write route merely because the chip family and Flash size match.

The frozen Production Gateway Selection V1 R2 artifact was independently inspected on 2026-09-24:

```text
SOURCE_HEAD=8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c
ARTIFACT_ID=10693728323
OUTER_ARTIFACT_SHA256=e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814
RELEASE_BUNDLE_SHA256=f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

FLASH_MODE=dio
FLASH_FREQ=80m
FLASH_SIZE=8MB

0x00000000 bootloader.bin
0x00008000 partitions.bin
0x00009000 ota_data_initial.bin
0x00010000 firmware.bin
```

Bound hashes:

```text
BOOTLOADER_SHA256=de9616925b2a868feb7c616762d9173899e5b947d0de5da7117268872c8297d1
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTADATA_INITIAL_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
APPLICATION_SHA256=c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a
FACTORY_IMAGE_SHA256=d8aa60082eca0482fe14806d8f4445223d3ccd4f87ba05d433b3ef31c187d304
```

The bundled `firmware.factory.bin` was checked byte-for-byte at the four required offsets and matches the corresponding release files:

```text
FACTORY_BOOTLOADER_0x0_MATCH=true
FACTORY_PARTITION_TABLE_0x8000_MATCH=true
FACTORY_OTADATA_0x9000_MATCH=true
FACTORY_APPLICATION_0x10000_MATCH=true
```

Operational rule:

```text
EXISTING_BOARD_DELTA_WRITE_POLICY_TRANSFER_TO_FRESH_SILICON=false
FRESH_SILICON_FULL_ERASE_DEFAULT=false
FRESH_SILICON_BOOTLOADER_PARTITION_COMPATIBILITY_REQUIRED=true
EXACT_ARTIFACT_LAYOUT_REQUIRED_BEFORE_FIRST_WRITE=true
```

For a fresh/replacement board, the write gate must choose one of two proven routes:

1. **Delta write allowed** only after read-only evidence proves the existing bootloader and partition table are already compatible with the frozen artifact and the current security state permits the route.
2. **First-write/factory layout** when compatibility is absent or unproven, using the exact artifact-defined bootloader/partition/OTA/application layout after explicit review and authorization.

Do not perform a whole-chip erase merely because the board is new or assumed blank. Do not write bootloader or partition table speculatively. The first-write route must be derived from the exact artifact and the target's fresh security/Flash evidence.

The artifact's bundled `flash_args` records build-layout authority, but it uses build-directory filenames. It must not be blindly pasted as an operator command; release-file names and hashes must be rebound explicitly.

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


## Validated controlled-reset runtime binding pattern

The 2026-09-22 Board A post-write Direct baseline physically validated the current-cursor binding method.

Observed result:

```text
CONTROLLED_RESET=PASS
PERSISTENT_MUTATION=false
UNIQUE_CANONICAL_BOOT_CHANGE=PASS
BOUND_NODE_PUBLIC_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5

DIRECT_SEQ_BEFORE=0
DIRECT_SEQ_AFTER=19
DIRECT_SEQ_DELTA=19
OBSERVATION_SECONDS=90
SAME_BOOT=true
FINAL_SOURCE=direct

MANAGER_RESTART_COUNT_UNCHANGED=true
DIRECT_BASELINE=PASS
```

Operational lesson:

```text
PREFERRED_ALREADY_PROVISIONED_RUNTIME_BINDING=
MANAGER_PRE_SNAPSHOT + ONE_CONTROLLED_BOARD_RESET + UNIQUE_FRESH_CANONICAL_BOOT_CHANGE

APPLICATION_HASH_NOT_REQUIRED=true
ROM_HASH_TO_REGISTRATION_JOIN_NOT_REQUIRED=true
PRE_RESET_BOOT_HISTORY_NOT_REQUIRED=true
```

Once a physical-acceptance same-boot baseline has been established through this method, later role-transition gates must preserve that boot session. Any reset or power cycle invalidates the baseline and requires a new baseline before claiming same-boot transition evidence.


## Fresh-peer discovery before role assignment

When one board is already runtime-bound, do not assume that exactly one other fresh Direct canonical node will already be visible and then interpret zero matches as a board failure.

Use a two-stage observer:

1. enumerate the complete current canonical inventory with public-safe node hashes, source, boot hash, sequence and cursor age;
2. classify presence/freshness/path before assigning a physical role.

```text
ZERO_OTHER_FRESH_DIRECT_IS_NOT_PRODUCT_FAILURE=true
CANONICAL_INVENTORY_FIRST=true
ROLE_ASSIGNMENT_AFTER_INVENTORY=true
RAW_NODE_ID_PUBLIC=false
RAW_BOOT_ID_PUBLIC=false
```

A missing fresh peer can mean the peer is powered off, stale, currently Relay, outside network coverage, not yet canonical after a recent boot, or otherwise not visible to the current Manager observer. The observer must classify these states before requesting physical intervention.

Do not reset a peer merely to make identification easier when the physical gate is intended to preserve an existing same-boot session on another board.


## Fresh/stale canonical inventory classification

A Manager canonical inventory can legitimately contain stale historical nodes alongside currently active nodes. Role assignment must therefore separate "present in the table" from "currently live".

Validated 2026-09-22 example:

```text
CANONICAL_NODE_COUNT=3
ACTIVE_BOARD_A_COUNT=1
ACTIVE_BOARD_B_COUNT=1
STALE_OTHER_NODE_COUNT=1
```

The Board B live binding was established by combining:

1. a repository-frozen public-safe Board-B node hash;
2. fresh current canonical source=direct;
3. current cursor age within the live threshold;
4. exclusion of a separate stale node.

```text
TABLE_PRESENCE_IS_LIVENESS=false
FRESHNESS_REQUIRED_FOR_LIVE_ROLE_ASSIGNMENT=true
STALE_CANONICAL_ROWS_MUST_NOT_CAUSE_ROLE_AMBIGUITY=true
FROZEN_PUBLIC_NODE_HASH_MAY_DISAMBIGUATE_RUNTIME_ROLE=true
RAW_NODE_ID_PUBLIC=false
```

If a frozen public-safe node hash is available and matches one fresh canonical row exactly, it is a stronger runtime-role discriminator than "unique other row" counting alone.


## Dual-Direct role-swap baseline pattern

Before moving one board into a Relay-child location, prove both the future Child and the future Gateway are concurrently healthy Direct nodes on stable boot sessions.

Validated 2026-09-22 pattern:

```text
OBSERVATION_SECONDS=90

FUTURE_CHILD_SOURCE_BEFORE=direct
FUTURE_CHILD_SOURCE_AFTER=direct
FUTURE_CHILD_SEQ_DELTA=18
FUTURE_CHILD_SAME_BOOT=true

FUTURE_GATEWAY_SOURCE_BEFORE=direct
FUTURE_GATEWAY_SOURCE_AFTER=direct
FUTURE_GATEWAY_SEQ_DELTA=19
FUTURE_GATEWAY_SAME_BOOT=true

MANAGER_RESTART_COUNT_UNCHANGED=true
DUAL_DIRECT_BASELINE=PASS
```

This separates later movement-induced path changes from pre-existing liveness problems. After a dual-Direct baseline passes, any reset or power cycle of either participant invalidates the same-boot role-swap starting condition and requires re-baselining.


## Power-source changes and same-boot acceptance

A same-boot physical transition claim cannot span an intentional power-source change that reboots the board.

If a board must switch from USB power to battery power before movement:

```text
POWER_SOURCE_CHANGE_REBOOTS_BOARD=true
OLD_SAME_BOOT_BASELINE_INVALID_AFTER_POWER_CHANGE=true
NEW_BASELINE_REQUIRED=true
```

The accepted pattern is:

1. complete the power-source change before physical path movement;
2. allow exactly the expected reboot;
3. keep the board in the Direct/Wi-Fi location;
4. bind the new boot from Manager canonical durable state;
5. prove Direct advancement on that new boot;
6. only then begin the movement gate;
7. require no further reboot or power cycle during Direct -> Relay.

The same-boot interval begins at the post-power-change Direct baseline, not at an earlier USB-powered baseline.


## Validated battery-power rebaseline pattern

The 2026-09-22 Board A battery-power transition physically validated the rule that a planned power-source reboot must occur before the same-boot movement window begins.

```text
BATTERY_POWER_REBOOT=EXPECTED
OLD_USB_BOOT_INVALIDATED=true
POST_REBOOT_DIRECT_REBASELINE_SECONDS=90
BATTERY_BOOT_DIRECT_SEQ_DELTA=19
GATEWAY_BOARD_DIRECT_SEQ_DELTA=19
BATTERY_BOOT_STABLE=true
GATEWAY_BOOT_STABLE=true
MANAGER_RESTART_COUNT_UNCHANGED=true
BATTERY_DIRECT_REBASELINE=PASS
```

Operationally, the new battery boot becomes the sole same-boot authority for the subsequent Direct -> Relay movement. Any further reboot or power cycle of the moving board invalidates that transition gate and requires another Direct rebaseline.


## Validated reversed-role Direct -> Relay transition pattern

The 2026-09-22 reversed-role physical run validated Board B as Direct/Gateway and Board A as Relay Child on one continuous Board A battery boot.

```text
MOVING_CHILD=BOARD_A
STATIONARY_GATEWAY=BOARD_B
SAME_BOOT_DIRECT_TO_RELAY=true
RELAY_GATEWAY_MATCH=true
POST_RELAY_SEQ_ADVANCEMENT=2
MOVE_START_TO_FIRST_OBSERVED_RELAY_MS=47144
MANAGER_VISIBLE_GAP_MS=27652
TRANSITION_MISSING_SEQUENCE_COUNT=2
TRANSITION_MISSING_SEQUENCE_RANGE=179-180
BOARD_B_DIRECT_REMAINS_HEALTHY=true
ROLE_SWAP_FUNCTIONAL_RESULT=PASS
```

This adds opposite-direction role-symmetry evidence to the historical Board-B-as-Child runs. It does not change the frozen Option-B reliability boundary: Direct -> Relay transition loss can occur, while Relay steady-state zero-loss continuity is a separate gate.


## Validated reversed-role Relay steady-state pattern

The 2026-09-22 Board-A-as-Child / Board-B-as-Gateway run completed a 600-second Relay continuity window with zero missing replay sequence.

```text
OBSERVATION_SECONDS=600
RELAY_START_SEQ=258
RELAY_END_SEQ=378
EXPECTED_ROW_COUNT=121
ACCEPTED_ROW_COUNT=121
MISSING_SEQUENCE_COUNT=0
SOURCE_NON_RELAY_OBSERVED=false
GATEWAY_MISMATCH_OBSERVED=false
MAX_MANAGER_INTERARRIVAL_SECONDS=31.542
RELAY_DATA_CONTINUITY_600S=PASS
```

A long Manager-visible interarrival can coexist with complete ordered delivery. Treat replay tuple completeness as the loss oracle and the interarrival maximum as a separate latency/buffering metric.


## Validated reversed-role Relay -> Direct failback pattern

The 2026-09-22 reversed-role failback completed on the same Board A battery boot:

```text
LAST_RELAY_SEQ=483
FIRST_DIRECT_SEQ=484
POST_DIRECT_LAST_SEQ=486
POST_DIRECT_SEQ_DELTA=2
MOVE_START_TO_FIRST_OBSERVED_DIRECT_MS=65835
MANAGER_VISIBLE_FAILBACK_GAP_MS=17252
MISSING_SEQUENCE_COUNT=0
RELAY_AFTER_FIRST_DIRECT_OBSERVED=false
SAME_BOOT_RELAY_TO_DIRECT=true
FAILBACK_RESULT=PASS
```

Combined with the preceding Direct -> Relay and 600-second Relay continuity gates, this proves the reverse A/B role assignment completes the full same-boot Direct -> Relay -> Direct physical round trip.
