# N3-W Production Multi-Relay Gateway Selection V1
## Board B Identity Conflict — 2026-09-23

Status: `STOP_IDENTITY_CONFLICT`

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
