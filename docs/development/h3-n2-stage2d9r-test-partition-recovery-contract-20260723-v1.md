# H3/N2 Stage 2D-9R test-partition recovery contract V1

## 1. Purpose

The current dedicated test board contains the historical Stage 2D-9 V69 state:

```text
active_generation=0
candidate_generation=1
candidate_state=PREPARED
```

That result remains valid within the V69 no-network PREPARE scope, but the candidate is not a TLS-usable input. Stage 2D-9R therefore requires a future destructive reset of only the dedicated test NVS partition before a new candidate can be prepared.

This document is a source/review contract. It does not authorize a board, serial, Flash, NVS or recovery operation.

## 2. Exact recovery region

```text
partition_label=gh2d8_p2d9
partition_type=data
partition_subtype=nvs
address=0x00400000
size=0x00010000
size_bytes=65536
expected_erased_byte=0xff
expected_erased_sha256=71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063
```

No other Flash address range is writable under this recovery contract.

Explicitly prohibited:

- whole-chip erase;
- bootloader, partition table, OTA slot or production NVS mutation;
- modification of eFuse, Secure Boot or Flash Encryption state;
- use of `CLEANUP_TEST_STATE` as a substitute for the exact partition reset;
- recovery of a different board or a board whose pre-state does not match the authorized evidence.

## 3. Future authorized recovery sequence

A later exact D2 may authorize this sequence once and only once:

```text
read chip identity and flash ID
→ read 0x00400000..0x0040ffff
→ verify exact expected pre-recovery partition SHA-256
→ verify current V69 active=0 / candidate=1 / PREPARED evidence
→ erase exactly 0x00400000..0x0040ffff
→ read back exactly 65536 bytes
→ verify every byte is 0xff
→ verify SHA-256 equals 71189f7f...9063
→ stop
```

The recovery-only operation does not flash Stage 2D-9R firmware, send PREPARE or VERIFY, start a Broker or connect to Wi-Fi/MQTT. Those actions are separate later gates, even when an eventual combined execution package sequences them after a successfully proven recovery boundary.

## 4. Fail-closed preconditions

Recovery must not begin unless all of the following match the future authorization:

- source SHA;
- recovery manifest SHA-256;
- recovery tool SHA-256;
- Python/esptool environment digest;
- exact serial path and USB/chip identity;
- current firmware/Artifact binding;
- exact current test-partition SHA-256;
- exact current V69 candidate digest and state evidence;
- authorization ID, issuance time, expiry time and one-shot status;
- consumed marker absent.

A mismatch stops before the erase command.

## 5. Allowed counts

```text
pre_read=1
erase_region=1
post_read=1
firmware_flash=0
full_chip_erase=0
prepare_command=0
verify_command=0
activate_command=0
cleanup_command=0
physical_reset=0
physical_boot_button=0
```

The erase boundary is destructive. After it is crossed, any failure stops and preserves evidence; no unreviewed retry is allowed. A locked recovery retry requires an explicit count and procedure in the same future D2 or a fresh D2.

## 6. Evidence

Public evidence may record:

- source/tool/manifest/environment hashes;
- redacted board identity digest;
- pre/post partition SHA-256;
- exact address and length;
- erase/readback results;
- authorization consumed state;
- confirmation that no other address or operation was attempted.

Private evidence may additionally contain the serial path and raw partition readbacks. Raw private paths and board identifiers must not be committed to the repository or public Artifact.

## 7. Successful recovery postcondition

```text
test_partition_erased=true
post_readback_all_ff=true
post_partition_sha256=71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063
namespace_present=false
active_generation=0
candidate_generation=0
candidate_state=EMPTY
firmware_flash_attempted=false
network_operation_attempted=false
```

The logical EMPTY state is not inferred solely from the erase command return code. It requires exact readback proof and, after the future Stage 2D-9R firmware is flashed, a separate read-only startup inspection.
