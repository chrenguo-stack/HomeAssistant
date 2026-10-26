# N3-W Board D physical-vs-runtime identity authority source review — 2026-10-26

## Status

```text
TASK=N3W_BOARD_D_PHYSICAL_VS_RUNTIME_IDENTITY_AUTHORITY_SOURCE_REVIEW_20261026_01
REPOSITORY_MAIN=507dbd49495c558b1344f7d713938b733b3bad18
PR=676
PR_STATE=OPEN_DRAFT
REVIEW_MODE=READ_ONLY_SOURCE_AND_PUBLIC_SAFE_LIVE_EVIDENCE

REPOSITORY_MUTATION=false
PRODUCT_SOURCE_MUTATION=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_MUTATION=false
PAIRING_WINDOW_OPEN=false
RECOVERY_EXECUTION=false
SECOND_FIRST_PAIR_ATTEMPT=false
MERGE=false
```

## 1. Live evidence being explained

The aborted Board D first-pair attempt produced one internally consistent live product identity:

```text
RUNTIME_PAIRING_HARDWARE_SHA256=3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55
PAIRING_ID_SHA256=9931c366d483abd3af6e1e3d903b82645542346dbd258975acd788998f0404dc

QR_VS_T1_CURRENT_HARDWARE_MATCH=true
QR_VS_T1_CURRENT_PAIRING_MATCH=true
QR_VS_T1_SESSION_HARDWARE_MATCH=true
QR_VS_T1_SESSION_PAIRING_MATCH=true

ARP_RUNTIME_HARDWARE_SHA256=3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55
ARP_VS_QR_RUNTIME_IDENTITY_MATCH=true
```

The historical physical Board D freeze instead used:

```text
FROZEN_PHYSICAL_BOARD_D_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
FROZEN_BOARD_D_VS_RUNTIME=false
```

## 2. Historical 3991... provenance

The original Board D read-only preflight source:

`tools/execution_packages/n3w/board_d/post_r4_write_target_preflight/executor.py`

runs:

```text
esptool --chip esp32c6 --port <PORT> --no-stub get-security-info
```

and parses the complete command output with:

```python
MAC_RE = re.compile(
    r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b"
)
mac_match = MAC_RE.search(security)
hardware_id_sha256 = public_identity_sha256(mac_match.group(1))
```

The historical preflight evidence explicitly states that the frozen public-safe hash was produced by this repository executor. Therefore `3991...` is source-bound to this parser.

## 3. Exact esptool v5.3.1 behavior for ESP32-C6

The live preflight recorded esptool 5.3.1.

In upstream `espressif/esptool` tag `v5.3.1`:

- `esptool/targets/esp32c6.py::ESP32C6ROM.read_mac()` reads the factory eFuse MAC and returns:
  - `BASE_MAC` as 6 bytes;
  - `EUI64` as 8 bytes, constructed as `base_mac[0:3] + ext_mac + base_mac[3:6]`.
- `esptool/cmds.py::read_mac()` prints the EUI-64 first as `MAC:`, then prints the 6-byte value as `BASE MAC:`.
- normal command preparation prints this MAC block before executing `get-security-info`.

For a representative C6 output shape:

```text
MAC:      aa:bb:cc:xx:yy:dd:ee:ff
BASE MAC: aa:bb:cc:dd:ee:ff
MAC_EXT:  xx:yy
```

the project regex does not require end-of-line after six octets. It therefore matches the first `MAC:` line and captures:

```text
aa:bb:cc:xx:yy:dd
```

That value is neither the 8-byte EUI-64 nor the 6-byte base MAC.

Therefore:

```text
ROOT_CAUSE=ESPTOOL_EUI64_TRUNCATED_TO_FAKE_6_BYTE_MAC
FROZEN_3991_IS_VALID_BASE_MAC_HASH=false
FROZEN_3991_IS_VALID_RUNTIME_STA_MAC_HASH=false
```

## 4. Why runtime 3a76... is the correct product identity chain

Current product firmware:

`firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp`

reads:

```cpp
esp_read_mac(local_mac_.data(), ESP_MAC_WIFI_STA)
```

and the pairing client converts those six bytes to:

```text
ghw-c6-<12 lowercase hex digits>
```

The same value is used in the QR and pairing protocol.

Repository-wide review found no product calls/configuration that override this authority:

```text
esp_base_mac_addr_set = absent
esp_iface_mac_addr_set = absent
esp_wifi_set_mac = absent
CONFIG_ESP_MAC_USE_CUSTOM_MAC_AS_BASE_MAC = absent
```

ESP-IDF's default ESP32-C6 MAC allocation maps Wi-Fi Station to the base MAC. The live ARP identity also hashes to the exact same `3a76...` value as QR and T1.

Therefore the runtime chain is independently cross-bound:

```text
BOARD_D_WIFI_STA
  -> PRODUCT_hardware_id
  -> LCD_QR
  -> T1_registration/session
  -> ARP
  -> SHA256 3a76...
```

## 5. False-PASS test path

The Board D preflight test:

`tests/execution_packages/n3w/board_d/post_r4_write_target_preflight/test_executor.py`

mocks esptool with only:

```text
MAC: 12:34:56:78:9A:BC
```

It does not model ESP32-C6/esptool v5.3.1 output containing an 8-byte `MAC:` EUI-64 followed by a 6-byte `BASE MAC:`.

The write executor test repeats the same simplified six-octet assumption.

Therefore existing tests prove only that a six-byte `MAC:` string can be hashed. They do not prove correct selection of the ESP32-C6 base MAC and allow the physical identity gate to false-PASS.

```text
IDENTITY_TEST_COVERAGE=false
FALSE_PASS_PATH=CONFIRMED
```

## 6. Board D propagation

The invalid `3991...` authority propagated into:

1. `docs/development/N3W_BOARD_D_IDENTITY_FREEZE_AND_WRITE_ROUTE_REVIEW_20261023.md`;
2. `tools/execution_packages/n3w/board_d/r4_dual_slot_normalization_write/executor.py`;
3. its focused tests and write/postwrite identity checks;
4. `tools/execution_packages/n3w/board_d/scoped_pairing_nvs_reset/executor.py`;
5. scoped-reset tests/design evidence;
6. later first-pair preparation/handoff assumptions.

The write executor uses the same faulty `MAC_RE`, so prewrite and postwrite checks repeatedly observed the same malformed EUI-64 projection. Their internal equality is therefore not independent proof of correct product hardware identity.

This does NOT prove that the firmware write or NVS-reset action targeted another physical board. The operator physical confirmation, same serial path and later Board D runtime evidence remain separate evidence. It does mean the machine-readable Board D identity attestation was wrong.

```text
BOARD_D_WRITE_TARGET_PROVEN_WRONG=false
BOARD_D_NVS_RESET_TARGET_PROVEN_WRONG=false
MACHINE_IDENTITY_ATTESTATION_VALID=false
WRITE_REDO_REQUIRED=false
NVS_RESET_REDO_REQUIRED=false
```

No write/reset replay is justified by this finding.

## 7. Collateral source exposure

The same vulnerable `MAC_RE` pattern also exists in historical/current Board B write executors:

- `tools/execution_packages/n3w/kf096/pr437_board_b_write/executor.py`
- `tools/execution_packages/n3w/kf099/board_b_write/executor.py`

This review does not reopen Board B radio/runtime acceptance. It does identify a separate identity-evidence audit requirement for those executors/hashes.

```text
BOARD_B_RUNTIME_ACCEPTANCE_REOPENED=false
BOARD_B_IDENTITY_EVIDENCE_AUDIT_REQUIRED=true
```

## 8. Required source repair

A later source-repair gate should:

1. replace generic `MAC:` parsing with an exact, line-anchored 6-byte `BASE MAC:` parser for ESP32-C6/esptool 5.x;
2. reject missing, duplicate or ambiguous base-MAC lines;
3. add a realistic esptool v5.3.1 ESP32-C6 transcript containing both 8-byte `MAC:` and 6-byte `BASE MAC:`;
4. prove the parser selects only `BASE MAC:`;
5. update Board D expected identity from invalid `3991...` to the runtime/product-bound `3a76...` only after exact source/test review;
6. update downstream Board D reset/preflight contracts and docs without replaying consumed physical mutations;
7. audit the same parser pattern in Board B executors separately.

A later read-only physical revalidation may re-observe the corrected `BASE MAC:` authority. It must not write flash or NVS.

## 9. Closure

```text
ROOT_CAUSE=CONFIRMED
ROOT_CLASS=PHYSICAL_IDENTITY_PARSER_FALSE_PASS
FROZEN_3991_AUTHORITY=INVALID_AS_PRODUCT_HARDWARE_ID
RUNTIME_3A76_CHAIN=INTERNALLY_AND_NETWORK_CROSS_BOUND
NEW_FALSE_PASS_PATH=true

SOURCE_REPAIR_REQUIRED=true
BOARD_PHYSICAL_REVALIDATION_REQUIRED_AFTER_REPAIR=true

SECOND_FIRST_PAIR_ATTEMPT_AUTHORIZED=false
SAME_RELEASE_PAIRING_RECOVERY_AUTHORIZED=false
OLD_QR_REUSE_ALLOWED=false
OLD_SETUP_SECRET_REUSE_ALLOWED=false
BOARD_WRITE_REDO_REQUIRED=false
NVS_RESET_REDO_REQUIRED=false
MERGE=false
```

Proposed next one gate:

```text
N3W_BOARD_D_PHYSICAL_IDENTITY_AUTHORITY_SOURCE_REPAIR_20261026_01
```
