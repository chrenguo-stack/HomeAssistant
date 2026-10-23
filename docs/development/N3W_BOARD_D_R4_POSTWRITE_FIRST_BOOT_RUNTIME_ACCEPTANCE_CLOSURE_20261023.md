# N3W Board D R4 postwrite first-boot runtime acceptance closure — 2026-10-23

## Result

~~~text
TASK=N3W_BOARD_D_R4_POSTWRITE_FIRST_BOOT_RUNTIME_ACCEPTANCE_20261023_01
STATUS=CLOSED_PASS

EXECUTION_ID=N3W_BOARD_D_R4_POSTWRITE_FIRST_BOOT_RUNTIME_ACCEPTANCE_20261023_01
AUTHORIZATION=N3W_BOARD_D_R4_POSTWRITE_FIRST_BOOT_RUNTIME_ACCEPTANCE_20261023_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false

MAIN=dc596ad50eb2ea80ba55aa3af2413236321f1465
MAIN_TREE=c2bc948fada4c28db6bbb4b27e852181a5e90697
PR661_MERGED=true

PRODUCT_SOURCE=ec5f6d68e33db7757d91c807fff708ca81b075dc
PRODUCT_SOURCE_TREE=16740efa8ad24d423adc0b2de32b99d56e2d23d1
ARTIFACT_RUN_ID=39901919230
ARTIFACT_ID=12478974186
ARTIFACT_SHA256=898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f

BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
BOARD_D_IDENTITY_MATCH=true

PREBOOT_MODE=ROM_BOOTLOADER
PREBOOT_NVS_SHA256=a61948eaf640aa878d245ef9c95a6529f28a1b2d876618e187419309e89d21a6
PREBOOT_NVS_MATCH_LAST_POSTWRITE=true
PREBOOT_FLASH_WRITE=false
PREBOOT_DIRECT_NVS_WRITE=false

NORMAL_APPLICATION_BOOT_INITIATED=true
NORMAL_APPLICATION_BOOT_COUNT=1
SECOND_APPLICATION_BOOT_EXECUTED=false

R4_APPLICATION_START_DIRECT_EVIDENCE=PASS
R4_APPLICATION_IDENTITY_EVIDENCE=EXACT_ARTIFACT_BINDING_PLUS_FROZEN_BOARD_IDENTITY_PLUS_SOURCE_DEFINED_STATUS_LED
RUNTIME_OBSERVATION_SECONDS=90.4
USB_OBSERVATION_SAMPLES=90
USB_MISSING_SAMPLES=0
USB_MULTI_LOCATOR_SAMPLES=0
USB_LOCATOR_CHANGED_SAMPLES=0
USB_PRESENCE_TRANSITIONS=0
USB_RUNTIME_STABLE=true
STATUS_LED_90S_CONTINUOUS_ON=true
UNEXPECTED_RESET_COUNT=0
UNEXPECTED_RESET_OR_SLEEP_OBSERVED=false
LEGACY_LOW_BATTERY_SLEEP_SIGNATURE_OBSERVED=false

POSTBOOT_NVS_SHA256=a61948eaf640aa878d245ef9c95a6529f28a1b2d876618e187419309e89d21a6
POSTBOOT_NVS_MATCH_PREBOOT=true
NVS_CHANGED_DURING_RUNTIME=false
NVS_CHANGE_CLASSIFICATION=UNCHANGED

POST_ACCEPTANCE_MODE=ROM_BOOTLOADER

FLASH_WRITE=false
DIRECT_NVS_WRITE=false
PAIRING_EXECUTED=false
T1_RUNTIME_MUTATION=false
RF_EXECUTION=false
APPLICATION_SERIAL_OPEN=false

BOARD_D_FIRST_BOOT_RUNTIME_ACCEPTANCE=CLOSED_PASS
NEXT_ROUTE=SEPARATE_BOARD_D_R4_PRODUCT_PAIRING_OR_RUNTIME_COMMUNICATION_ACCEPTANCE_DESIGN
AUTO_EXECUTE_NEXT_ROUTE=false
NEW_AUTHORIZATION_REQUIRED=true
STOP=true
~~~

## Acceptance meaning

This gate proves only the Board D R4 postwrite first normal application boot and the bounded 90-second basic runtime window.

The exact Board D public-safe hardware identity matched before and after the runtime window. The preboot NVS SHA256 exactly matched the frozen postwrite value, and the postboot NVS SHA256 exactly matched the preboot value. No direct NVS write, Flash write, pairing, T1 mutation, Direct/Relay acceptance, movement or RF execution was performed.

The one allowed normal application boot reached the source-defined status-LED initialization state. The LED remained continuously on for the complete 90-second observation. USB enumeration remained present and stable for all 90 samples, with zero disappearance, locator change, multi-locator sample or presence transition. No unexpected reset/sleep or legacy low-battery sleep signature was observed.

PASS here does not claim pairing, telemetry, MQTT, Direct, Relay, failover, RF or product-communication acceptance.

## Observation-script incident

The first application-boot observation wrapper used a Python heredoc while also calling Python `input()`. After the boot trigger had already succeeded, `input()` encountered EOF because stdin belonged to the heredoc. The operator's subsequent `LED_ON` text therefore reached zsh instead of Python.

No retry or second application boot was performed. Passive process/history forensics plus the already-running source-defined status LED established that the one allowed boot had been consumed. A fresh 90-second passive observation was then performed on that same application runtime.

This is an execution-wrapper/stdin-ownership issue, not Board D product failure. It is consistent with the existing project stdin/TTY ownership guard family; it did not require a new product repair or a second boot.

## PR #661 known-failure rollup

The separate PR #661 postwrite-verifier defect is registered as KF-129 in `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`.

The defect was loader-state discontinuity plus missing explicit 8 MB ROM read-flash binding and a non-durable fresh-prewrite baseline. PR #661 schema v2 repaired those boundaries with stub continuity, explicit 8 MB ROM reads and durable execution journaling. The repair is merged in main and guarded by source tests.

The present first-boot runtime acceptance does not claim that the historical failed postwrite verifier run was replayed. The consumed write authorization remains non-replayable, and Board D was not reflashed merely to re-run the verifier.

## Stop boundary

~~~text
CURRENT_BOARD_D_MODE=ROM_BOOTLOADER
SECOND_APPLICATION_BOOT_ALLOWED=false
PAIRING_AUTHORIZED=false
T1_MUTATION_AUTHORIZED=false
RF_EXECUTION_AUTHORIZED=false
AUTO_EXECUTE_NEXT_GATE=false
~~~

Any product pairing/runtime communication work is a separate stage requiring fresh design/rebind and new physical authorization.
