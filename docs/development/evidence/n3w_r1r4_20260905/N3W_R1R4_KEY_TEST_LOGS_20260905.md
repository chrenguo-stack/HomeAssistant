# N3-W R1/R2/R1R3/R1R4 Key Test Logs — 2026-09-05

This file archives decision-grade test evidence for the official off-channel ESP-NOW / ROC validation route. It is a curated evidence record, not a complete mirror of every raw host log.

No credentials or private setup material are included. Mac-local raw serial logs are not copied here because they are not accessible through the current GitHub connector session.

## Repository / authority binding

```text
CURRENT_MAIN=127c3f1e89baaaba7b7fd60d6d263632d30b2461
CURRENT_MAIN_TREE=32135508818124e848bc895073b3cb6aaa6b9af3
PRODUCT_SOURCE_AUTHORITY=bff94bc4922d7a984eb1363cc24a163ad466a166

R1R4_BRANCH=diag/n3w-r1r4-usb-console-evidence-20260905
R1R4_BRANCH_BASE=3d7bcf2f47892d8f6e5c0456d9681ebfe8549ea0
R1R4_COMMIT=1b89639f9454ea725da1fef32564f5cdfa006289
R1R4_TREE=b2b815283deb1cbc976eab74c38ca096dd23b90d

R1R4_DIAGNOSTIC_SOURCE_TREE_HASH=b5005829e83d48277dd0bc6369dd112912a1e58d
R1R4_DIAGNOSTIC_MAIN_SHA256=adc94730efb7a69c859b11571cf27dbb7889f2b40800e867731ec9863f85305f

ESPRESSIF_REF=735507283d5b2f9fb363a1901172dbd9e847945d
PIOARDUINO_REF=8de41af2dbb81bc443a8d7986ebd152f82e10bba
```

## R1 / R2 official off-channel baseline

```text
R1A_HOME_CHANNEL_BASELINE=PASS

R1B_ACTIVE_OFFCHANNEL_TX_PATH=PROVEN
R1B_CONNECTED_DUT_SWITCH_CHANNEL_TX=PASS
R1B_CONTROL_REMAIN_ON_CHANNEL=PASS
R1B_CHANNEL6_FRAME_DELIVERY=PASS

R1C_REVERSE_OFFCHANNEL_RX=NOT_PROVEN
R1C_DUT_REMAIN_ON_CHANNEL=NOT_EXECUTED_TO_ORACLE

HOME_CHANNEL_AUTO_RETURN=NOT_PROVEN
R1_HARNESS_STATE_TRANSITION_AMBIGUITY=true

OFFICIAL_OFFCHANNEL_API_INSUFFICIENCY=NOT_PROVEN
FULL_RADIO_OWNERSHIP_MODEL=NOT_JUSTIFIED
```

Interpretation boundary: R1/R2 did not prove that the official API is insufficient. R1C was not executed to its intended oracle after the R1B state transition became ambiguous.

## R1R3 host-only diagnostic build authority

```text
R1R3_SOURCE_COMMIT=56d0ec6dcc633f3966affc68a9342716490e370e
R1R3_CLOSEOUT_TIP=3d7bcf2f47892d8f6e5c0456d9681ebfe8549ea0
R1R3_SOURCE_TREE_HASH=cec569a3c2cd024759474aea144448bbbc6b0c15
R1R3_MAIN_SHA256=9cac785e0019dc5d07e641c1c92092455d4a80f6100f170f743765774db07f38

R1R3_ARTIFACT_ID=9964994892
R1R3_ARTIFACT_SHA256=89956c1d7d07e8a63c139d406ef394095ba6d6f20116b6c8e11e0a76771b2235

R1R3_OFFICIAL_ROC_API_AUTHORITY=PASS
R1R3_CONTROL_HOST_COMPILE=PASS
R1R3_DUT_HOST_COMPILE=PASS
READY_FOR_R1R3_SHORT_PHYSICAL_GATE=true
```

Core R1R3 lifecycle under test:

```text
HOME_CH1_BASELINE
→ DUT ROC_REQ CH6, wait=3000ms, op_id=77
→ CONTROL one esp_now_switch_channel_tx probe CH6, seq=55
→ DUT probe RX CH6
→ DUT ROC_CANCEL same op_id=77
→ HOME CH1 recovery
→ STA association recovery
→ HOME ESP-NOW ACK seq=66
```

## Board B flash-read transport detour

The historical full 8 MiB backup session failed at approximately 78.2%, around address `0x00641000`. Subsequent bounded read evidence closed the detour:

```text
TARGETED_READ_0x00630000_LEN_0x40000=PASS
TARGETED_SHA256=3b874d3ba46c638fc3094f8e92fb744ca974893873f8885f54e23760f9b6311b

FULL_8MB_RETRY=PASS
FULL_8MB_RETRY_SHA256=179e3adcb7fb9899571ebb3429858ea68979de912231010393bed330f7c5f601

BOARD_B_HARDWARE_DEFECT_PROVEN=false
BOARD_B_PREFLASH_BACKUP_DETOUR=CLOSED
```

## R1R3 physical evidence

Two R1R3 physical attempts were safely restored, but the functional ROC result was not adjudicable because the intended serial evidence was not captured.

Second evidence-hardened run:

```text
CONTROL_CAPTURE_PREFLIGHT=PASS
DUT_CAPTURE_PREFLIGHT=PASS
CONTROL_CAPTURE_PID_ALIVE=true
DUT_CAPTURE_PID_ALIVE=true
DUAL_CAPTURE_ALIVE_BEFORE_OBSERVATION=true

CONTROL_SERIAL_LOG_SIZE=0
DUT_SERIAL_LOG_SIZE=0

R1R3_RF_FUNCTIONAL_RESULT=NOT_ADJUDICABLE_CAPTURE_FAILURE
OFFICIAL_ROC_LIFECYCLE_HOME_RETURN=NOT_PROVEN
```

Fresh restore authority from that run:

```text
CONTROL_PREFLASH_SHA256=9f21b4b2b192f06cee186eefdbbcf5355446dadb2fe543706a4be16c056945da
DUT_PREFLASH_SHA256=dc318ee1d8566dbec8d1c162b2705be13609d08631b99995cc290a04de06950c

CONTROL_RESTORE_PREBOOT_EXACT=true
DUT_RESTORE_PREBOOT_EXACT=true
CONTROL_PRODUCT_BOOT_AFTER_RESTORE=PASS
DUT_PRODUCT_BOOT_AFTER_RESTORE=PASS
RESTORE_RESULT=PASS
```

No second RF rerun was performed after the capture failure.

## Serial capture evidence

```text
OLD_BACKGROUND_CAPTURE_FAILURE=OUTPUT_FILE_NOT_CREATED

CAPTURE_HELPER_SHA256=588db33d25fa85c702e2d23a597cf3bcbfa1537f1735ef3153432d1726925101
PTY_DUAL_CAPTURE_BYTE_EXACT=PASS
PTY_DUAL_CAPTURE_CONCURRENT=PASS
```

The real-board evidence-hardened run proved the capture processes/files were prepared and alive before observation, but the resulting serial files remained zero bytes.

R1R3 generated configuration showed UART0 as primary console and USB Serial/JTAG as secondary. This observation motivated the R1R4 host-only successor.

## R1R4 intended evidence hardening

```text
PRIMARY_CONSOLE=USB_SERIAL_JTAG
SECONDARY_CONSOLE=NONE
R1R4_CAPTURE_HEARTBEAT_INTERVAL_MS=250
R1R4_CAPTURE_ARM_DELAY_MS=5000
CAPTURE_READY_HANDSHAKE=true
```

## R1R4 host-only closure

```text
EXECUTION_ID=N3W-R1R4-HOST-ONLY-USB-CONSOLE-EVIDENCE-HARDENING-20260905-01
AUTHORIZATION=USER_APPROVED_R1R4_HOST_ONLY_USB_CONSOLE_EVIDENCE_HARDENING

CI_RUN_ID=33957392009
CI_JOB_ID=101283085978
CI_RESULT=FAILURE

R1R4_OFFICIAL_USB_CONSOLE_AUTHORITY=PASS
R1R4_EVIDENCE_HARDENING_SOURCE_CONTRACT=PASS
R1R4_CONTROL_USB_PRIMARY_CONSOLE=FAIL
R1R4_DUT_USB_PRIMARY_CONSOLE=NOT_EXECUTED

ARTIFACT_ID=NOT_PRODUCED
ARTIFACT_NAME=NOT_PRODUCED

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_READ=false
FLASH_WRITE=false
RF_EXECUTION=false
KF089_IMPLEMENTATION=false

R1R4_HOST_ONLY_USB_CONSOLE_EVIDENCE_HARDENING=FAIL
GATE_RESULT=STOP_R1R4_HOST_BUILD_OR_CONTRACT_FAILED
STOP=true
```

High-level interpretation frozen after the closure:

```text
R1R4_FAILURE_BOUNDARY=CONTROL_HOST_BUILD_OR_PRIMARY_USB_CONSOLE_ORACLE
R1R4_SOURCE_CONTRACT=PASS
R1R4_CONTROL_BUILD_OR_USB_PRIMARY_ORACLE=FAIL
R1R4_DUT_BUILD=NOT_EXECUTED
R1R4_BINARY_EVIDENCE=NOT_EXECUTED
R1R4_ARTIFACT=NOT_PRODUCED
R1R4_PHYSICAL_EXECUTION=false

OFFICIAL_ROC_API_CAUSAL=false
USB_SERIAL_JTAG_RUNTIME_RESULT=NOT_ADJUDICATED
KF089_CAUSAL=false

R1R3_CORE_RADIO_SOURCE_CONTRACT_PRESERVED=PASS
R1R3_CORE_RADIO_BUILD_PRESERVATION=NOT_PROVEN
READY_FOR_R1R4_PHYSICAL=false
```

The closure field that reported `R1R3_CORE_RADIO_CONTRACT_PRESERVED=false` must not be read as a proven source-contract violation. The R1R4 source-contract oracle passed; the build-preservation oracle was simply not reached because CONTROL compilation failed first.

## First R1R4 compiler failure

The exact curated CI excerpt is archived beside this file as:

`CI_JOB_101283085978_FAILURE_EXCERPT.log`

Narrow supported classification at archival time:

```text
FAILURE_CLASS=SOURCE_COMPILE_ERROR
FIRST_FAILURE=CONTROL_COMPILE_MISSING_ESP_APP_DESC_H_IN_FRAMEWORK_IDF_INCLUDE_RESOLUTION
SDKCONFIG_USB_PRIMARY_ORACLE_REACHED=false
DUT_BUILD_REACHED=false
```

This does not establish a Kconfig conflict, a USB Serial/JTAG runtime failure, an ESP-NOW API failure, or a KF-089 causal relationship.

## Raw-log custody note

Known Mac-local raw serial log paths from earlier stages are intentionally not represented as repository files here because their bytes were not available through this GitHub archival session. In particular, this archive must not be interpreted as claiming that the R0 or R1/R2 raw serial logs themselves were uploaded.
