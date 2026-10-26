# N3-W Board D physical identity authority source repair — 2026-10-26

## Status

```text
TASK=N3W_BOARD_D_PHYSICAL_IDENTITY_AUTHORITY_SOURCE_REPAIR_20261026_01
BASE_MAIN=507dbd49495c558b1344f7d713938b733b3bad18
BRANCH=fix/n3w-board-d-physical-identity-authority-20261026

SOURCE_REPAIR=true
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_MUTATION=false
PAIRING_WINDOW_OPEN=false
SECOND_FIRST_PAIR_ATTEMPT=false
RECOVERY_EXECUTION=false
MERGE=false
```

## 1. Root cause being repaired

The previous physical Board D identity path parsed generic `MAC:` output from esptool with a six-octet regex.

For ESP32-C6 in esptool v5.3.1, the normal chip banner prints:

```text
MAC:      <8-byte EUI-64>
BASE MAC: <6-byte factory/base MAC>
MAC_EXT:  <2-byte extension>
```

The old regex matched the first six octets of the 8-byte EUI-64. That produced the invalid historical public-safe identity:

```text
INVALID_FROZEN_HARDWARE_ID_SHA256=
3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
```

Live runtime evidence independently cross-bound the correct Board D product identity through Wi-Fi/ARP, LCD QR and T1 registration/session:

```text
CORRECTED_BOARD_D_HARDWARE_ID_SHA256=
3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55
```

## 2. Parser repair

Both Board D physical identity observers now accept only an exact, line-anchored six-byte `BASE MAC:` line:

- `tools/execution_packages/n3w/board_d/post_r4_write_target_preflight/executor.py`
- `tools/execution_packages/n3w/board_d/r4_dual_slot_normalization_write/executor.py`

The parser:

- ignores the generic 8-byte `MAC:` EUI-64 line;
- requires exactly one `BASE MAC:`;
- rejects missing base MAC;
- rejects duplicate/ambiguous base MAC output;
- derives `ghw-c6-<12 hex>` only from the six-byte base MAC.

## 3. Identity authority update

Future Board D source authority is corrected to:

```text
EXPECTED_HARDWARE_ID_SHA256=
3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55
```

Updated downstream executable contracts:

- dual-slot normalization write executor;
- scoped pairing NVS-reset executor.

This source update does not replay any historical write or erase and does not authorize either executor.

## 4. Evidence schema hardening

Old evidence was created under the faulty parser. New code must never accept it as if it had the corrected semantics.

Schema changes:

```text
post-r4-write-target-preflight: /1 -> /2
r4-dual-slot-normalization-write-preflight: /2 -> /3
r4-dual-slot-normalization-write: /2 -> /3
```

The scoped NVS-reset executor now requires the corrected post-R4 preflight schema `/2`.

Old evidence remains historical evidence only.

## 5. Regression coverage

The repaired tests model the real ESP32-C6/esptool shape with:

```text
MAC:      <8-byte EUI-64>
BASE MAC: <6-byte base MAC>
MAC_EXT:  <2-byte extension>
```

They prove:

- identity is derived from `BASE MAC:`;
- the first six octets of EUI-64 are not accepted as identity;
- missing `BASE MAC:` fails;
- duplicate `BASE MAC:` fails;
- old evidence schemas fail closed;
- corrected Board D identity hash is frozen in downstream Board D contracts.

## 6. Historical evidence boundary

Historical documents and consumed live evidence are not rewritten.

In particular:

```text
HISTORICAL_3991_RECORDS_DELETED=false
HISTORICAL_WRITE_REPLAY=false
HISTORICAL_NVS_RESET_REPLAY=false
```

The repair changes future interpretation and future machine-verifiable Board D identity authority only.

## 7. Collateral scope

Historical Board B write executors contain the same generic `MAC:` parser pattern.

This repair does not change Board B source because the authorized gate is Board D only.

```text
BOARD_B_SOURCE_MUTATION=false
BOARD_B_RUNTIME_ACCEPTANCE_REOPENED=false
BOARD_B_IDENTITY_AUDIT_REQUIRED=true
```

## 8. Remaining closure requirement

Source repair alone is not enough to close the live identity blocker.

After exact-head source review and CI pass, a separate read-only physical gate must re-observe Board D through the corrected `BASE MAC:` parser and prove:

```text
CORRECTED_PHYSICAL_BASE_MAC_SHA256=
3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55
```

That future gate may reset the board as an unavoidable ROM/esptool side effect, but must not write Flash/NVS and requires separate explicit physical authorization.

## 9. Current boundary

```text
SOURCE_REPAIR_IMPLEMENTED=true
CI_STATUS=PENDING
INDEPENDENT_SOURCE_REVIEW=PENDING
BOARD_PHYSICAL_REVALIDATION=PENDING

SECOND_FIRST_PAIR_ATTEMPT_AUTHORIZED=false
SAME_RELEASE_PAIRING_RECOVERY_AUTHORIZED=false
OLD_QR_REUSE_ALLOWED=false
OLD_SETUP_SECRET_REUSE_ALLOWED=false
MERGE=false
```
