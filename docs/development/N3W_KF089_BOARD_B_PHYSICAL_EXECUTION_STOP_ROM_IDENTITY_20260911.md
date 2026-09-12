# N3-W KF-089 Board B Physical Execution STOP — ROM Identity Binding — 2026-09-11

Status: `STOP_FAIL_CLOSED_NO_FLASH_ACCESS_NO_MUTATION`

## 1. Authorization disposition

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
```

The authorization is consumed and must never be reused. Any later physical workflow requires a fresh explicit authorization.

## 2. Fresh pre-execution bindings

```text
FRESH_SOURCE_REBIND=PASS
FRESH_LOCAL_TOOLCHAIN_REBIND=PASS
FRESH_FIRMWARE_BINDING=PASS
FRESH_PRIVATE_TARGET_IDENTITY_BINDING=PASS
```

## 3. Physical execution result

```text
PORT_DISCOVERY=PASS
ROM_IDENTITY_BINDING=FAIL

APP0_READBACK_SIZE=NOT_EXECUTED
APP0_READBACK_SHA256=NOT_EXECUTED
APP0_BINDING=NOT_EXECUTED
APP0_WRITE_EXECUTED=false
SECOND_APP0_FLASH_EXECUTED=false

OTADATA_PRE_READ=NOT_EXECUTED
OTADATA_PRE_SELECTED_SLOT=NOT_EXECUTED
SAME_CONNECTION_IDENTITY_RECHECK=NOT_EXECUTED
SAME_CONNECTION_APP0_FRESHNESS=NOT_EXECUTED
SAME_CONNECTION_OTADATA_FRESHNESS=NOT_EXECUTED
OTADATA_MUTATION_EXECUTED=false
OTADATA_MUTATION_COUNT=0
OTADATA_POST_READ=NOT_EXECUTED
OTADATA_POST_VERIFY=NOT_EXECUTED
OTADATA_POST_SELECTED_SLOT=NOT_EXECUTED

MUTATION_RETRY_EXECUTED=false
AUTO_ROLLBACK_EXECUTED=false
NORMAL_BOOT_EXECUTED=false
SCHEMA_V5_RUNTIME_OBSERVATION=NOT_EXECUTED
```

## 4. STOP reason

```text
RESULT=STOP
FIRST_FAILED_STAGE=ROM_IDENTITY_BINDING
STOP_REASON=Guard ROM identity output did not contain exactly one BASE_MAC; authorization consumed, no retry performed.
```

This closure proves only that the reviewed Guard rejected the first ROM identity observation. It does **not** prove that the connected silicon identity mismatched the expected Board B identity. The current public evidence does not distinguish among:

- ROM/esptool output formatting or stream-placement differences;
- zero MAC candidates reaching the parser;
- multiple MAC-like candidates reaching the parser;
- command/result plumbing around the identity read;
- a genuine identity mismatch occurring before or during parser evaluation.

No root cause is assigned until the private evidence from the consumed attempt is reviewed host-only.

## 5. Safety result

```text
FLASH_READ=false
FLASH_WRITE=false
OTADATA_MUTATION=false
APP0_WRITE=false
SECOND_APP0_FLASH=false
MUTATION_RETRY=false
AUTO_ROLLBACK=false
NORMAL_BOOT=false
```

The physical workflow stopped before app0 readback and before all mutation boundaries.

## 6. Next gate

```text
NEXT_ONE_GATE=HOST_ONLY_ROM_IDENTITY_EVIDENCE_FORENSIC
BOARD_ACCESS_ALLOWED=false
USB_OR_SERIAL_REOPEN_ALLOWED=false
OLD_AUTHORIZATION_REUSE_ALLOWED=false
```

The next gate may inspect only already-created private evidence from the consumed attempt plus reviewed source/toolchain material. It must not reconnect to Board B.
