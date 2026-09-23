# N3-W Production Gateway Selection V1
## Board Identity Parser Source Repair Closure — 2026-09-23

Status: `CLOSED_PASS`

## Gate

```text
TASK=N3W_PRODUCTION_GWSEL_V1_BOARD_IDENTITY_PARSER_SOURCE_REPAIR_20260923_01
BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
```

## Exact repair authority

```text
BRANCH=fix/n3w-gwsel-v1-board-identity-parser-repair-20260923
HEAD=b1587ea9ffb0a14b4c784bcfa8f1cb5f919faf18
TREE=4a672ec20ca0ac45879e4d3aea5fffb34b2c4129

CI_RUN_ID=35815218810
CI_RESULT=SUCCESS
```

CI passed:

```text
Compile Board A and Board B executors=PASS
Board A / Board B / RUNBOOK tests=PASS
Parser repair contract=PASS
Public repository safety=PASS
```

## Root cause

The original production preflight parser captured only six bytes after a generic
`MAC:` label. ESP32-C6/esptool may expose an eight-byte EUI-64 identity with an
inserted `ff:fe` extension. Truncating that value to its first six bytes discarded
board-specific tail bytes and could make distinct physical boards produce the same
derived hardware identity.

The earlier Board B identity conflict was therefore a software-generated false
positive. Equal OTA-data digests were also incorrectly treated as supporting
identity evidence; OTA-data is mutable boot-selection state and is not silicon
identity.

## Corrected identity contract

The reusable parser now follows this order:

```text
1. prefer explicit BASE MAC (6 bytes)
2. otherwise parse the complete 8-byte MAC/EUI-64
3. require inserted ff:fe in the ESP32-C6 EUI-64 form
4. remove ff:fe to recover the canonical 6-byte base MAC
5. allow a legacy 6-byte MAC fallback
6. fail closed for malformed or unsupported forms
```

The existing project hardware-ID normalization remains unchanged:

```text
compact = lowercase base MAC with ":" removed
hardware_id = "ghw-c6-" + compact
hardware_id_sha256 = SHA256(UTF-8 hardware_id)
```

No new identity namespace or digest contract was introduced.

## RUNBOOK authority

The correction is frozen in:

```text
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md
```

The RUNBOOK additionally freezes:

```text
DO_NOT_TRUNCATE_EUI64=true
OTADATA_IS_NOT_SILICON_IDENTITY=true
OPERATOR_LABEL_AND_SILICON_IDENTITY_ARE_SEPARATE=true
SEQUENTIAL_BOARD_PREFLIGHT=A_STOP_B_STOP_C_STOP
READONLY_PREFLIGHT_IS_NOT_WRITE_AUTHORIZATION=true
```

## Evidence correction

The Board A closure now marks the original identity digest as invalid as silicon
identity evidence while preserving its independently valid chip, flash-size,
security, partition-table and artifact-binding results.

The Board B identity-conflict document is superseded as a false positive. Operator
Board B labeling doubt is withdrawn. The independently valid Board B chip,
flash-size, security, partition-table and artifact-binding results remain usable.

## Regression coverage

```text
EUI64_WITH_FF_FE_TO_BASE_MAC=PASS
EXPLICIT_BASE_MAC_PREFERRED=PASS
LEGACY_MAC48_FALLBACK=PASS
MALFORMED_EUI64_FAILS_CLOSED=PASS
SAME_PREFIX_DIFFERENT_TAIL_DISTINCT_IDENTITY=PASS
RAW_MAC_NOT_PUBLISHED=PASS
PUBLIC_REPOSITORY_SAFETY=PASS
```

## Closure

```text
IDENTITY_PARSER_SOURCE_REPAIR=CLOSED_PASS
BOARD_A_IDENTITY_RECHECK=PENDING
BOARD_B_IDENTITY_RECHECK=PENDING
BOARD_C_ACCESS=false

PERSISTENT_BOARD_MUTATION=false
FLASH_WRITE=false
NVS_WRITE=false
STOP=true
```

Proposed next ONE gate:

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_B_MINIMAL_ROM_IDENTITY_RECHECK_20260923_01

BOARD_LABEL=B
BOARD_ACCESS_REQUIRED=true
READ_ONLY=true
TEMPORARY_RESET_ROM_ENTRY=true
ARTIFACT_REDOWNLOAD_NOT_REQUIRED=true
PARTITION_REREAD_NOT_REQUIRED=true
FLASH_WRITE=false
NVS_WRITE=false
BOARD_C_ACCESS=false
EXPLICIT_AUTHORIZATION_REQUIRED=true
```
