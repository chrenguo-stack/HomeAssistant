# N3-W Auto Safe Fallback Gate F — Board B Reboot Suspect — 2026-10-04

Status: `REBOOT_SUSPECT_CLOSED_NOT_REPRODUCED_LOW_BATTERY_LED_OFF_CONFIRMED`

## User observation

During the current Gate F stale-Broker physical failure state, Board B's normal runtime status LED was observed to extinguish irregularly. The visual pattern appeared similar to a reboot, but LED behavior alone was not sufficient to classify the event as a reboot.

## Relevant exact-product behavior

The F1.0-RC2 product configuration sets the status LED output to `restore_mode: ALWAYS_OFF` and turns it ON at the final local boot stage. Therefore a real reboot can produce a temporary LED-off interval until boot reaches the final local initialization step.

The same product source also turns the status LED OFF for non-reboot reasons:

- entering low-battery protection;
- preparing to restart after low-battery recovery;
- OTA start.

Low-battery protection is evaluated from the battery ADC every 30 seconds. After the startup grace period, three consecutive low-voltage samples enter low-battery mode and turn the status LED off without immediately rebooting.

The N3-W product core also contains explicit fail-safe reboot paths which log a fail-safe reboot reason before using the ESPHome safe reboot path.

## Continuous forensic observation

A single serial session was kept open continuously. The first 20 seconds were treated as an arming window and discarded so that any boot event associated with initial serial attachment would not be counted. The following 600 seconds were observed without Board, flash, or T1 mutation.

Result:

```text
OBSERVATION_SECONDS=600
REBOOT_SIGNATURE_COUNT=0
N3W_SAFE_REBOOT_COUNT=0
LOW_BATTERY_ENTRY_COUNT=1
LOW_BATTERY_RECOVERY_RESTART_COUNT=0
BROWNOUT_COUNT=0
WATCHDOG_COUNT=0
PANIC_COUNT=0
BOARD_B_UNEXPECTED_REBOOT_OBSERVED=false
BOARD_FLASH_WRITE=false
T1_MUTATION=false
```

The battery path produced three consecutive low readings at approximately 30-second spacing after the startup grace period:

```text
Low sample 1/3: 0.00 V
Low sample 2/3: 0.00 V
Low sample 3/3: 0.00 V
Entering low-battery protection mode
```

This exactly matches the product's low-battery protection behavior and explains the observed status-LED extinction without requiring a reboot.

## Classification

```text
BOARD_B_STATUS_LED_IRREGULAR_OFF_OBSERVED=true
BOARD_B_UNEXPECTED_REBOOT_SUSPECT=false
BOARD_B_UNEXPECTED_REBOOT_CONFIRMED=false
BOARD_B_UNEXPECTED_REBOOT_NOT_REPRODUCED_600S=true
LOW_BATTERY_LED_OFF_CONFIRMED=true
LOW_BATTERY_ADC_READING_ZERO=true
LOW_BATTERY_RECOVERY_RESTART_OBSERVED=false
N3W_FAIL_SAFE_REBOOT_OBSERVED=false
BROWNOUT_OBSERVED=false
WATCHDOG_OBSERVED=false
PANIC_OBSERVED=false
GATE_F_PHYSICAL_ACCEPTANCE_COMPLETE=false
MERGE=false
```

## Interpretation boundary

The reboot suspicion is closed for this observation window. The LED-off behavior is explained by low-battery protection, not by a spontaneous reboot.

The `0.00 V` battery reading remains a separate condition that must not be confused with N3-W Broker-relocation behavior. If Board B is intentionally USB-powered without a battery connected, this reading is compatible with the present bench setup but causes the production low-battery policy to enter protection after the startup grace period. If a battery is physically connected, the zero reading is abnormal and requires a separate battery/ADC path investigation.

Low-battery mode can also suppress the soil-read workflow, so formal physical acceptance should not use the status LED as a liveness oracle and should avoid allowing this bench-only low-battery condition to contaminate sensor-path acceptance results.

The stale-Broker physical oracle remains unchanged. Do not modify the T1 Broker-host condition as part of this closure.
