# N3W Board D R4 warm/cold boot and LCD acceptance redesign — 2026-10-23

## Decision

~~~text
TASK=N3W_BOARD_D_R4_FIRST_BOOT_LCD_WARM_COLD_REASSESSMENT
STATUS=DESIGN_READY_PHYSICAL_AUTHORIZATION_REQUIRED

PRIOR_GATE=N3W_BOARD_D_R4_POSTWRITE_FIRST_BOOT_RUNTIME_ACCEPTANCE_20261023_01
PRIOR_90S_BASIC_RUNTIME_EVIDENCE=VALID_SCOPED_ONLY
PRIOR_PRODUCT_LEVEL_CLOSED_PASS=WITHDRAWN

KF130=OPEN
ROOT_CAUSE=TBD
REFLASH_FIRST=false

NEXT_ONE_GATE=N3W_BOARD_D_R4_WARM_COLD_BOOT_LCD_ACCEPTANCE_20261023_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

## Why the previous acceptance is insufficient

The previous gate proved exactly one application boot, 90.4 seconds of stable USB presence, a continuously-on status LED, no observed reset/sleep, and unchanged NVS. Those facts remain valid.

However, the LCD was not a required oracle. The operator subsequently reported that the LCD stayed frozen after the firmware-write/reset path and recovered after unplugging/replugging USB for a true cold power cycle. Prior soft-reboot failure has also been observed. Because LCD12864 local display is a frozen product-baseline capability, the product-level first-boot acceptance cannot remain closed.

## Exact source and hardware observations

~~~text
PRODUCT_SOURCE=ec5f6d68e33db7757d91c807fff708ca81b075dc
DISPLAY_CONFIG_BLOB=0551c13a7c0c751d08723547fc60cdac37a6cd58

LCD_PLATFORM=st7920
LCD_SPI_CLK=GPIO2
LCD_SPI_MOSI=GPIO3
LCD_CS=GPIO16
LCD_CS_INVERTED=true
LCD_DATA_RATE=1MHz
LCD_UPDATE_INTERVAL=1s
LCD_PAGE_COUNT=5
LCD_PAGE_PERIOD=4s
LCD_FULL_PAGE_CYCLE_SECONDS=20

LCD_MCU_RESET_PIN_CONFIGURED=false
~~~

The SMR12864-15A module has a dedicated active-low /RST pin and its datasheet requires the LCD to be reset during power-on. The frozen Board-D GPIO plan and exact R4 display configuration enumerate CLK/MOSI/CS only; no MCU-controlled LCD reset line is documented/configured.

This makes LCD reset-state discontinuity a strong hypothesis: the ESP32 can restart while the externally powered LCD controller remains in an old state. A cold power cycle resets both domains. This is not yet a proven root cause because the actual PCB /RST net/wiring has not yet been independently verified.

The exact R4 product source also contains legitimate restart paths, including the ESPHome restart button and an `esp_restart()` low-battery recovery path. Therefore warm-reset correctness is a normal product requirement, not a laboratory-only edge case.

## New acceptance strategy

Do not reflash first. Reflashing would add mutation while failing to distinguish a reset-lifecycle problem from a firmware-image problem.

### Stage A — true cold boot baseline

Precondition: Board D must have no alternate power source that keeps the LCD powered.

1. Remove USB power completely.
2. Keep the board unpowered long enough for the LCD rail to collapse.
3. Reconnect USB and allow a normal application boot.
4. Observe at least 30 seconds.
5. Mandatory LCD oracle:
   - LCD becomes readable;
   - page content visibly changes;
   - five-page sequence completes at least one full cycle;
   - no frozen frame, corrupt frame, blank-stuck state or permanent partial page.
6. Status LED and USB presence remain secondary corroborating oracles.

If cold boot fails, STOP. Do not proceed to warm reset.

### Stage B — MCU-only warm reset

Without removing power from the LCD rail, trigger one bounded MCU reset path that does not write Flash/NVS.

Observe at least 30 seconds using the same mandatory LCD oracle.

If LCD freezes while the cold boot baseline passed, classify:

~~~text
WARM_COLD_DIVERGENCE=true
BOARD_D_R4_LCD_RESET_ACCEPTANCE=FAIL
ROOT_CAUSE_DOMAIN=LCD_RESET_OR_WARM_INIT_PATH
AUTO_REFLASH=false
~~~

Stop and repair source/hardware; do not repeat reset until the failure is documented.

### Stage C — repeatability only after A+B both pass

Only if one cold boot and one warm reset both pass, perform a small repeatability matrix:

~~~text
COLD_BOOT_TOTAL=3
WARM_RESET_TOTAL=3
LCD_FULL_PAGE_CYCLE_REQUIRED_EACH_RUN=true
~~~

Any failure stops the matrix. No “majority pass” rule.

### Stage D — software restart path

If an exact, non-pairing, non-T1 method can invoke the product's normal software restart without changing credentials or configuration, validate it separately. This stage must not be emulated by claiming that a hardware reset proves `esp_restart()`.

If no clean software-restart trigger is available within current scope, record it as NOT_EXECUTED rather than inventing equivalence.

## PASS criteria

~~~text
COLD_BOOT_PASS_COUNT=3
WARM_RESET_PASS_COUNT=3
LCD_READABLE_EACH_RUN=true
LCD_FULL_5_PAGE_CYCLE_EACH_RUN=true
LCD_FREEZE_COUNT=0
LCD_BLANK_STUCK_COUNT=0
UNEXPECTED_RESET_LOOP_COUNT=0
REFLASH_EXECUTED=false
PAIRING_EXECUTED=false
T1_MUTATION=false
RF_EXECUTION=false
~~~

Software-restart acceptance is reported independently as PASS / FAIL / NOT_EXECUTED.

## Failure and repair boundary

A reproduced cold-pass/warm-fail result is sufficient to reject the current product reset lifecycle. It should trigger a focused design review covering:

- actual Board D LCD /RST schematic/net;
- whether /RST is tied to power-on reset, ESP32 EN, another reset source, or left passive;
- whether a spare GPIO/control path exists;
- ST7920 initialization timing and command sequence on warm start;
- whether firmware can safely force a full LCD reinitialization without hardware reset;
- whether a PCB revision is required if reliable warm-reset recovery cannot be guaranteed in software.

Do not select a hardware or software fix before the actual /RST wiring and failure reproduction are both known.

## Scope

~~~text
FLASH_WRITE=false
DIRECT_NVS_WRITE=false
PAIRING=false
T1_RUNTIME_MUTATION=false
DIRECT_RELAY_RF_ACCEPTANCE=false

PHYSICAL_BOARD_ACCESS_REQUIRES_NEW_AUTHORIZATION=true
AUTO_EXECUTE=false
~~~


## 2026-10-23 execution result

~~~text
EXECUTION_GATE=N3W_BOARD_D_R4_WARM_COLD_BOOT_LCD_ACCEPTANCE_20261023_01
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false

COLD_BOOT_1=PASS
WARM_EN_RESET_1=PASS
COLD_BOOT_2=PASS
WARM_EN_RESET_2=PASS
COLD_BOOT_3=PASS
WARM_EN_RESET_3=PASS

COLD_BOOT_PASS_COUNT=3
PHYSICAL_EN_WARM_RESET_PASS_COUNT=3
LCD_FREEZE_COUNT=0
LCD_CORRUPTION_COUNT=0
LCD_FULL_5_PAGE_CYCLE_EACH_RUN=true

SOFTWARE_RESTART_EXECUTED=false
SOFTWARE_RESTART_RESULT=NOT_EXECUTED
BOARD_D_NETWORK_STATE=UNPROVISIONED
LCD_PAGE5_STATE=配置节点网络
ESPHOME_MDNS_DISCOVERY_COUNT=0
NATIVE_API_EXACT_TARGET_MATCH_COUNT=0

FLASH_WRITE=false
DIRECT_NVS_WRITE=false
PAIRING=false
T1_RUNTIME_MUTATION=false
RF_EXECUTION=false

SCOPED_WARM_COLD_MATRIX=CLOSED_PASS
KF130=OPEN
BOARD_D_FIRST_BOOT_RUNTIME_ACCEPTANCE=REOPENED
~~~

### Interpretation

The focused warm/cold matrix passed completely. Three true power-off cold boots and three physical EN warm resets all restored the LCD in about one second and completed the five-page cycle with no freeze or corruption. USB presence remained stable in every observation.

Therefore, the simple failure model “ESP32 warm reset while LCD stays powered always leaves the ST7920 stuck” is not supported by this run.

The original post-flash freeze remains valid operator evidence and is not erased by this matrix. It occurred on a different lifecycle boundary and still requires explanation.

### Software restart disposition

A software-restart validation was prepared through ESPHome Native API but deliberately not executed. The host ESPHome runtime contains `aioesphomeapi`, but Board D is unprovisioned: LCD page 5 displays “配置节点网络”, no `_esphomelib._tcp` mDNS service was discovered, and no exact Native API target could be bound.

Because pairing/network configuration is outside this gate, the test did not modify Board D merely to obtain a restart transport. Software restart is therefore `NOT_EXECUTED`, not PASS and not FAIL.

### Next boundary

KF-130 remains OPEN. A later gate must independently address at least one of:

1. exact post-flash reset-path reproduction/acceptance under a fresh write authorization;
2. software `esp_restart()` after a legitimate provisioning/network stage;
3. actual PCB LCD `/RST` net and reset timing verification.

No automatic reflash or additional board action is authorized by this result.
