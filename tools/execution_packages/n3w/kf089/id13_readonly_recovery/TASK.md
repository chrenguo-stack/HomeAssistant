# N3W KF-089 ID13 READONLY RECOVERY

Status: `REVIEW_ONLY` until the exact package head passes host CI and the high-level model marks it ready for a new physical authorization.

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_TO_COMMAND_COMPILATION=false
EXECUTION_PACKAGE_STORAGE_MODEL=STAGE_AND_GATE_SCOPED
```

## 1. Purpose

Recover the persisted Schema-v5 diagnostic counters from Board B and Board A after the already-consumed ID11 RF window, without repeating RF capture and without writing target Flash, NVS, otadata, or product state.

This package does **not** adjudicate the product path. It only recovers exact A/B diagnostic evidence needed by the high-level model to adjudicate:

```text
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

## 2. Frozen predecessor facts

```text
ID11_CLAIMED=true
ID11_CONSUMED=true
ID11_REPLAY_PERMITTED=false
RF_WINDOW_COMPLETED=true
RF_WINDOW_SECONDS=90
SECOND_RF_CAPTURE=false

ID12_CLAIMED=true
ID12_CONSUMED=true
ID12_REPLAY_PERMITTED=false
ID12_RESULT=STOP_BEFORE_BOARD_ACCESS
ID12_READ_MAC_EXECUTED=false
ID12_BOARD_B_ACCESSED=false
```

Only the following ID12 host failure facts are treated as OBSERVED:

```text
OBSERVED_ESPTOOL_WRAPPER_EXECUTION_PERMISSION_ERROR=true
OBSERVED_COMMAND_FAILED_BEFORE_READ_MAC=true
OBSERVED_BOARD_B_ACCESS=false
```

The following remain explicitly NOT PROVEN and are not used as root-cause assumptions by ID13:

```text
WRAPPER_IS_PYTHON_SCRIPT=NOT_PROVEN
DIRECT_WRAPPER_EXECUTION_USED=NOT_PROVEN
MISSING_EXECUTABLE_BIT_IS_ROOT_CAUSE=NOT_PROVEN
CORRECT_FIX_IS_PYTHON_PLUS_WRAPPER=NOT_PROVEN
```

ID13 deliberately uses an explicit `python -m esptool` invocation so command authority is unambiguous and recorded before launch. This is an ID13 design choice, not a retrospective claim about ID12.

## 3. Exact source/tool bindings

```text
BASE_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5

DIAG_PARSER_PATH=tools/n3w_read_diag_snapshot.py
DIAG_PARSER_GIT_BLOB=de6951daf6cfd20035243b85c32957eb6108308a

PYTHON_MAJOR_MINOR=3.11
ESPTOOL_VERSION=5.3.1
CHIP=esp32c6
FLASH_SIZE=8MB
NVS_OFFSET=0x790000
NVS_SIZE=0x70000
```

The execution package itself is bound externally by the exact commit passed as `--expected-package-commit`. The executor verifies `git rev-parse HEAD` before any board access.

## 4. Target identity contract

USB/serial path is a locator only. It is never identity authority.

Canonical identity evidence is the `read-mac` stdout using these rules:

1. accept only complete `BASE MAC:` lines;
2. ignore generic `MAC:` and `EUI64:` lines;
3. repeated identical `BASE MAC:` values are allowed;
4. require exactly one distinct `BASE MAC:` value;
5. require trusted expected suffix match before NVS read.

Public-safe suffix bindings:

```text
BOARD_B_EXPECTED_BASE_MAC_SUFFIX=F4:5C
BOARD_A_EXPECTED_BASE_MAC_SUFFIX=F3:50
FULL_BASE_MAC_PUBLIC_COMMIT=false
```

Full BASE MAC values remain only inside the private evidence root.

## 5. Exact physical sequence after a future new authorization

No physical authorization is granted by this file.

After package readiness and explicit new ID13 authorization, Codex executes exactly one committed executor invocation.

Sequence implemented by `executor.py`:

```text
HOST PREFLIGHT
  -> exact package commit check
  -> tracked worktree clean check
  -> diagnostic parser Git blob check
  -> esptool version 5.3.1 check
  -> only then claim/consume new ID13 authorization

BOARD B
  -> read-mac, ROM/no-reset/no-stub
  -> canonical BASE MAC validation
  -> one read-flash of NVS partition, ROM/no-reset/no-stub
  -> offline Schema-v5 decode from captured NVS file
  -> required Board B counters validation

BOARD A
  -> read-mac, ROM/no-reset/no-stub
  -> canonical BASE MAC validation
  -> one read-flash of NVS partition, ROM/no-reset/no-stub
  -> offline Schema-v5 decode from captured NVS file
  -> required Board A counters validation

CLOSURE
  -> evidence manifest with SHA-256
  -> selected counters
  -> PASS or STOP
```

Board B and Board A must be simultaneously available through two distinct port locators for this package revision. If the physical arrangement later requires sequential reconnect on one locator, STOP before authorization and return to the high-level model for a new package revision. Codex must not improvise around this contract.

### 5.1 Manual ROM-only preparation contract

The current executor intentionally uses `--before no-reset --after no-reset --no-stub`. It therefore does **not** force either target into Download Boot mode. The operator must prepare both boards in ROM Download mode only after explicit ID13 physical authorization and before the executor is invoked.

Both boards must begin fully unpowered. Disconnect battery, solar, Boost, bench supply, or any other non-USB power path before preparation. Normal USB power-on without the BOOT strap is forbidden because that may start the product application and alter the persisted diagnostic state being recovered.

The board design binds BOOT to GPIO9 and holds GPIO8 high. The authorized preparation sequence is:

```text
BOARD B
  -> with Board B unpowered, hold BOOT so GPIO9 is low
  -> while BOOT remains held, connect Board B USB-C to the Mac and apply USB power
  -> keep BOOT held through power-on/reset and USB enumeration
  -> release BOOT only after enumeration

BOARD A
  -> with Board A unpowered, hold BOOT so GPIO9 is low
  -> while BOOT remains held, connect Board A USB-C to the Mac and apply USB power
  -> keep BOOT held through power-on/reset and USB enumeration
  -> release BOOT only after enumeration
```

Expected strap state at the sampled power-on reset boundary:

```text
GPIO9=0
GPIO8=1
EXPECTED_BOOT_MODE=ROM_DOWNLOAD
```

After both boards are prepared, do not press RESET, do not power-cycle, do not disconnect/reconnect, and do not allow a reset retry before the executor completes or STOPs.

If either board was already powered, normal application boot is observed or suspected, BOOT was not held through the relevant power-on reset, the device fails to enumerate, or any reset/reconnect would be required, STOP before executor use and return to the high-level model. Do not improvise a retry under the same execution record.

Manual ROM preparation is within the future explicit ID13 physical authorization scope; it is not authorized during package authoring. The executor's persisted `authorization.json` records claim/consume immediately before the first software board-target command. If manual preparation itself deviates from this contract, treat ID13 conservatively as non-replayable and return for adjudication rather than attempting to continue.

## 6. Read-only esptool contract

The executor constructs explicit commands equivalent to:

```text
python -m esptool
  --chip esp32c6
  --port <PORT>
  --before no-reset
  --after no-reset
  --no-stub
  read-mac
```

and:

```text
python -m esptool
  --chip esp32c6
  --port <PORT>
  --before no-reset
  --after no-reset
  --no-stub
  read-flash
  --flash-size 8MB
  0x790000
  0x70000
  <PRIVATE_EVIDENCE_PATH>/nvs_partition.bin
```

`--no-stub` is intentional so the operation stays on the ROM loader and does not upload a flasher stub to target RAM.

Forbidden esptool operations are guarded in code/tests, including:

```text
write-flash
erase-flash
erase-region
write-mem
write-flash-status
```

## 7. Required Schema-v5 counters

Board B:

```text
schema_version
boot_session
snapshot_uptime_ms
path_state
relay_active_count
relay_telemetry_attempts
relay_telemetry_success
unicast_completion_count
unicast_completion_success
unicast_completion_failure
```

Board A:

```text
schema_version
boot_session
snapshot_uptime_ms
path_state
compact_rx_count
compact_state_reject_count
compact_child_binding_failure
compact_decode_success
compact_decode_failure
compact_wrap_failure
compact_forward_attempts
compact_forward_submit_success
compact_forward_submit_failure
```

Missing fields or any schema other than v5 cause STOP.

## 8. Raw evidence contract

Private evidence root must be outside the Git repository and absent or empty at start.

Permissions:

```text
DIRECTORY_MODE=0700
FILE_MODE=0600
RAW_EVIDENCE_PUBLIC_COMMIT=false
```

For every external command:

```text
persist command.json
-> launch command
-> persist stdout.txt
-> persist stderr.txt
-> persist result.json
```

Per-operation evidence:

```text
op_NN_<label>/
  command.json
  stdout.txt
  stderr.txt
  result.json
```

Per board:

```text
board_b|board_a/
  identity_private.json
  nvs_partition.bin
  snapshot_private.json
  selected_counters.json
  capture_manifest.json
```

Final:

```text
session.json
authorization.json
closure.json
evidence_manifest.json
```

`evidence_manifest.json` contains file SHA-256 and size, but raw private contents remain outside GitHub.

## 9. Authorization semantics

Before host preflight completes:

```text
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
```

Immediately before the first deliberate Board B target command:

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
```

This is conservative: after that boundary any STOP consumes the one-shot ID13 authorization.

No ID13 authorization exists during package authoring/testing.

## 10. Hard forbidden scope

```text
APPLICATION_BOOT=false
SECOND_RF_CAPTURE=false
RESET_RETRY=false
AUTO_RETRY=false
FLASH_WRITE=false
NVS_WRITE=false
OTADATA_WRITE=false
PAIRING_CHANGE=false
FIRMWARE_REFLASH=false
T1_ACCESS=false
T1_MUTATION=false
PRODUCT_SOURCE_CHANGE=false
```

No execution of this package is authorized by its presence in GitHub.

## 11. PASS

Package execution PASS requires:

```text
BOARD_B_IDENTITY_MATCH=true
BOARD_B_NVS_READ_PASS=true
BOARD_B_SCHEMA_V5_DECODE_PASS=true
BOARD_B_REQUIRED_COUNTERS_PRESENT=true

BOARD_A_IDENTITY_MATCH=true
BOARD_A_NVS_READ_PASS=true
BOARD_A_SCHEMA_V5_DECODE_PASS=true
BOARD_A_REQUIRED_COUNTERS_PRESENT=true

RAW_EVIDENCE_COMPLETE=true
READONLY_RECOVERY_RESULT=PASS
```

PASS only makes the evidence ready for high-level-model adjudication. It does not automatically enter another physical gate.

## 12. STOP

Fail closed on any:

```text
package commit mismatch
dirty tracked worktree
diagnostic parser blob mismatch
esptool version mismatch
process launch failure
read-mac failure
missing/ambiguous BASE MAC
identity suffix mismatch
NVS read failure
NVS size mismatch
Schema-v5 decode failure
missing required counter
evidence persistence failure
```

On package/executor defect:

```text
STOP
-> RETURN_TO_HIGH_LEVEL_MODEL
-> HIGH_LEVEL_MODEL_MODIFIES_GITHUB_CODE
-> NEW_COMMIT
-> HOST_TESTS
-> EXACT_REBIND
```

Codex must not patch or replace commands locally.

## 13. Future exact invocation template

Only after a new explicit physical authorization:

```text
python tools/execution_packages/n3w/kf089/id13_readonly_recovery/executor.py \
  --expected-package-commit <EXACT_ID13_PACKAGE_COMMIT> \
  --authorization-id <NEW_ID13_AUTHORIZATION_ID> \
  --execution-id <ID13_EXECUTION_ID> \
  --board-b-port <BOARD_B_PORT_LOCATOR> \
  --board-a-port <BOARD_A_PORT_LOCATOR> \
  --evidence-root <PRIVATE_PATH_OUTSIDE_REPOSITORY>
```

During the current authoring gate:

```text
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
RF_EXECUTION=false
NEW_PHYSICAL_AUTHORIZATION=false
```
