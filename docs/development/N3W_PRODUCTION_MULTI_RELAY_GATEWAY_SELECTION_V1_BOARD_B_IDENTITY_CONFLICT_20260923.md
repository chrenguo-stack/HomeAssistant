# N3-W Production Multi-Relay Gateway Selection V1
## Board B Identity Conflict — 2026-09-23

Status: `SUPERSEDED_FALSE_POSITIVE_IDENTITY_CONFLICT`

```text
TASK=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_THREE_BOARD_WRITE_TARGET_PREFLIGHT_20260923_01
BOARD_STAGE=B

BOARD_A_PREFLIGHT=PASS
BOARD_B_EXECUTOR_RESULT=PASS
BOARD_B_DISTINCT_PHYSICAL_IDENTITY=NOT_PROVEN
BOARD_C_ACCESS=false

BOARD_A_PUBLIC_IDENTITY_EQUALS_BOARD_B_ATTEMPT=true
BOARD_A_OTADATA_HASH_EQUALS_BOARD_B_ATTEMPT=true

CHIP_CHECK=PASS
FLASH_SIZE_CHECK=PASS
SECURITY_STATE_CHECK=PASS
PARTITION_TABLE_CHECK=PASS
ARTIFACT_BINDING=PASS

PERSISTENT_MUTATION=false
FLASH_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false
```

The second-board run cannot be closed as Board B because its fresh public ROM-derived
identity equals the already accepted Board A identity. The OTA-data region digest is
also identical. The evidence therefore does not establish a distinct physical target.

Recovery is read-only and sequential:

```text
1. disconnect the currently attached board
2. connect the operator-identified Board B only
3. require exactly one USB modem target
4. perform an independent ROM built-in-address read
5. convert it locally to the existing public identity digest without publishing the raw value
6. require the digest to differ from Board A before rerunning full Board B preflight

AUTO_PROCEED=false
BOARD_C_ACCESS=false
STOP=true
```


## 2026-09-23 supersession

This stop was caused by an executor parser defect, not by proof that the operator
connected the same physical board twice.

The affected parser captured only six bytes after a generic `MAC:` label. For the
ESP32-C6 EUI-64 form this retained the common prefix and discarded the
board-specific tail. The resulting equal public identity digests were therefore a
false collision produced by software.

The equal OTA-data digests were also not valid supporting identity evidence.
OTA-data is mutable boot-selection state and may legitimately be byte-identical on
different boards.

```text
BOARD_B_IDENTITY_CONFLICT=FALSE_POSITIVE
OPERATOR_BOARD_B_LABEL_DOUBT=WITHDRAWN
OTADATA_AS_IDENTITY_EVIDENCE=FORBIDDEN

CHIP_CHECK=PASS
FLASH_SIZE_CHECK=PASS
SECURITY_STATE_CHECK=PASS
PARTITION_TABLE_CHECK=PASS
ARTIFACT_BINDING=PASS

ORIGINAL_BOARD_B_HARDWARE_ID_SHA256=INVALID_AS_SILICON_IDENTITY
```

The corrected reusable authority is:

```text
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md
```

The Board B identity should be re-read with the repaired parser. The other
independent read-only preflight evidence above does not need to be repeated solely
because of this identity-parser defect.
