# N3-W Production Board Write-Target Preflight RUNBOOK

Status: `ACTIVE`

Purpose: reusable authority for production ESP32-C6 board identity binding and
read-only write-target preflight before any N3-W firmware mutation.

## 1. Scope

This RUNBOOK applies to production-board preflight for Board A, Board B, Board C,
and later replacement boards when the operator must prove which physical ESP32-C6
is connected before a firmware write.

The operator-visible board label and the silicon identity are separate facts:

```text
OPERATOR_BOARD_LABEL != SILICON_IDENTITY
```

A label is established by the operator. Silicon identity is established by a fresh
ROM read. A USB device path is only a temporary locator and must not be treated as
persistent identity.

## 2. Sequential-board rule

When several physical boards must be checked, inspect them one at a time:

```text
A -> STOP -> B -> STOP -> C -> STOP -> SUMMARY
```

At each board boundary:

- disconnect the previous board;
- connect only the operator-selected target;
- require exactly one eligible USB modem target;
- obtain explicit authorization before any reset or ROM bootloader entry;
- stop after the current board is adjudicated.

A successful board preflight is not permission to flash.

## 3. Reset and mutation boundary

ROM/esptool inspection may temporarily reset the target or enter the ROM bootloader.

```text
ROM_RESET_OR_BOOTLOADER_ENTRY=EPHEMERAL_PHYSICAL_STATE_CHANGE
PERSISTENT_BOARD_MUTATION=false
```

Read-only preflight may use ROM/esptool commands such as security information,
flash identification and flash readback.

The following remain forbidden until a separate write gate is explicitly authorized:

```text
write-flash
erase-flash
erase-region
NVS mutation
partition-table write
bootloader write
full-flash erase
```

## 4. ESP32-C6 silicon identity parsing

Do not derive identity by taking the first six bytes from a generic `MAC:` line.

ESP32-C6/esptool can expose an 8-byte EUI-64 value and a 6-byte base MAC. The
correct parser order is:

1. If an explicit `BASE MAC:` value exists, use that 6-byte value.
2. Otherwise, if `MAC:` contains eight bytes, consume all eight bytes.
3. For the ESP32-C6 EUI-64 form, require bytes 4-5 to be `ff:fe`, remove those
   two bytes, and use the remaining six bytes as the base MAC.
4. Otherwise, a legacy six-byte `MAC:` value may be accepted as the base MAC.
5. Any unsupported length or malformed EUI-64 must fail closed.

Never truncate an eight-byte value to its first six bytes. Such truncation can make
different physical boards appear identical because their board-specific tail bytes
are discarded.

## 5. Hardware-ID contract

The project hardware-ID contract remains unchanged:

```text
base_mac = lowercase 6-byte base MAC
compact = base_mac with ":" removed
hardware_id = "ghw-c6-" + compact
hardware_id_sha256 = SHA256(UTF-8 hardware_id)
```

Do not silently replace this with a hash of the raw EUI-64, a hash of the
colon-separated base MAC, or a new prefix.

Raw MAC/base-MAC values are private physical identifiers. Public GitHub evidence may
store only the derived public-safe digest unless a separate private-evidence process
explicitly requires the raw value.

## 6. Identity-conflict handling

If two operator-labeled boards produce the same public hardware-identity digest:

- do not immediately conclude that the operator connected the wrong board;
- first verify that the parser consumed the complete ROM identity;
- verify that no EUI-64 truncation occurred;
- verify that the same hardware-ID normalization contract was used;
- only after parser correctness is proven should a repeated digest be treated as
  evidence requiring a physical-target recheck.

A parser defect invalidates only the identity result produced by that parser. Other
independently read facts such as chip type, flash size, security state and partition
table remain usable if their own read paths were unaffected.

## 7. OTA-data is not board identity

The OTA-data region is mutable boot-selection state.

```text
OTADATA_EQUAL => DOES_NOT_PROVE_SAME_BOARD
OTADATA_DIFFERENT => DOES_NOT_PROVE_DISTINCT_BOARD_IDENTITY
```

Two different boards may have byte-identical OTA-data when they share the same OTA
state. Therefore an OTA-data SHA-256 must never be used as a silicon-identity
oracle or as supporting evidence that two reads came from the same board.

OTA-data readback may still be retained for boot-selection/write-route planning.

## 8. Write-target compatibility checks

A production write-target preflight should independently prove, as applicable:

```text
OPERATOR_TARGET_CONFIRMATION
FRESH_ROM_SILICON_IDENTITY
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT_STATE
FLASH_ENCRYPTION_STATE
PARTITION_TABLE_BINDING
CURRENT_OTA_STATE_OR_OTADATA_READBACK
EXACT_CANDIDATE_ARTIFACT_BINDING
```

A partition mismatch, incompatible security state, artifact mismatch or unresolved
identity parser error is a hard stop.

Do not automatically erase, migrate partitions, rewrite NVS, write a bootloader or
switch to a factory/full-flash path as a recovery action.

## 9. Evidence publication

Public evidence must not include:

- raw ROM MAC/base MAC;
- private USB device path;
- raw NVS contents;
- credentials or secrets;
- private local closure paths when those paths expose identifying host information.

Prefer:

```text
operator board label
public hardware identity SHA-256
chip type
flash size
security-state booleans
partition-table SHA-256
OTA-data SHA-256
artifact ID / artifact SHA-256
executor exact HEAD
CI run ID
mutation booleans
```

## 10. 2026-09-23 parser defect guard

A production preflight implementation must include regression coverage for all of
the following:

```text
EUI64_WITH_FF_FE_TO_BASE_MAC=TESTED
EXPLICIT_BASE_MAC_PREFERRED=TESTED
LEGACY_MAC48_FALLBACK=TESTED
MALFORMED_EUI64_FAILS_CLOSED=TESTED
TWO_EUI64_VALUES_WITH_SAME_PREFIX_AND_DIFFERENT_TAILS_PRODUCE_DISTINCT_IDENTITIES=TESTED
RAW_MAC_NOT_PUBLISHED=TESTED
OTADATA_NOT_USED_AS_IDENTITY=REQUIRED
```

The historical first-six-byte parser is forbidden for new production-board
preflight executors and must not be copied into future Board C or replacement-board
execution packages.


## 11. Paste-ready operator shell command safety

When an instruction is intended to be copied directly into the operator's interactive
shell, the executable code block must be paste-safe for that shell.

For interactive zsh execution:

- do not place shell comment lines beginning with `#` inside a paste-ready command block;
- do not assume `INTERACTIVE_COMMENTS` is enabled;
- keep explanatory comments outside the executable block;
- if inline shell comments are operationally necessary, explicitly wrap the script
  in a non-interactive shell invocation whose parsing behavior is controlled;
- a command-generation error must fail before ROM access or persistent mutation
  whenever possible.

This rule applies to all future A/B/C preflight, identity-check and write-gate
operator commands.


## 12. Exact firmware-write gate

A successful static or fresh preflight is not a write authorization.

For an exact production firmware mutation:

- require a board-specific explicit write authorization after the fresh read-only
  preflight has passed;
- the preflight used by the write executor must be no older than 900 seconds;
- immediately before mutation, revalidate the exact artifact, ROM silicon identity,
  chip type, flash size, security state and partition-table binding;
- consume the preflight authorization before the first `write-flash` command;
- once authorization is claimed, any command failure, disconnect, readback mismatch,
  or unexpected reset is a hard stop and must not be retried automatically;
- do not reinterpret a failed or partial write as permission to erase, migrate
  partitions, rewrite NVS, write a bootloader, use a factory image, or full-erase;
- after a successful write command, read back every intentionally written region
  and the partition table and verify their frozen SHA-256 values;
- stop after the current board is adjudicated.

For Production Gateway Selection V1 artifact `10693728323`, the exact minimal
route is frozen as:

```text
WRITE 0x9000  ota_data_initial.bin
WRITE 0x10000 firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FACTORY_IMAGE_WRITE=false
FULL_FLASH_ERASE=false
```

This route is valid only while fresh target checks prove the expected 8 MiB
ESP32-C6 security state and the exact partition-table SHA-256:

```text
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

The artifact's bundled `flash_args` is evidence for the build layout, not an
operator command. It contains build-directory filenames that are not the flat
release filenames, so blind execution of that file is forbidden.

Post-write acceptance requires:

```text
OTADATA_READBACK_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

APPLICATION_READBACK_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

PARTITION_TABLE_READBACK_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

For the three-board Gateway Selection V1 deployment, mutation remains sequential:

```text
A -> STOP -> B -> STOP -> C -> STOP
```

No board inherits another board's reset, preflight or write authorization.
