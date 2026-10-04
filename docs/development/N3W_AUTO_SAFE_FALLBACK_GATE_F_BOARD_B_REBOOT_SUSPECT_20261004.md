# N3-W Auto Safe Fallback Gate F — Board B Reboot Suspect — 2026-10-04

Status: `REBOOT_SUSPECT_UNCONFIRMED`

## User observation

During the current Gate F stale-Broker physical failure state, Board B's normal runtime status LED has been observed to extinguish irregularly. The visual pattern appears similar to a reboot, but LED behavior alone is not sufficient to classify the event as a reboot.

## Relevant exact-product behavior

The F1.0-RC2 product configuration sets the status LED output to `restore_mode: ALWAYS_OFF` and turns it ON at the final local boot stage. Therefore a real reboot can produce a temporary LED-off interval until boot reaches the final local initialization step.

The same product source also turns the status LED OFF for non-reboot reasons:

- entering low-battery protection;
- preparing to restart after low-battery recovery;
- OTA start.

Low-battery protection is evaluated from the battery ADC every 30 seconds. After the startup grace period, three consecutive low-voltage samples can enter low-battery mode and turn the status LED off without immediately rebooting.

The N3-W product core also contains explicit fail-safe reboot paths. These log:

```text
N3-W fail-safe reboot requested reason=...
```

and call the ESPHome safe reboot path.

## Existing related evidence

A previous serial capture contained a reboot signature, but because opening/attaching the serial observation itself can disturb the board or capture a boot already in progress, that single signature is not sufficient to prove spontaneous reboot.

Combined with the independent visual LED observation, unexpected reboot is now a valid separate forensic hypothesis and must be resolved before Gate F physical closure.

## Classification

```text
BOARD_B_STATUS_LED_IRREGULAR_OFF_OBSERVED=true
BOARD_B_UNEXPECTED_REBOOT_SUSPECT=true
BOARD_B_UNEXPECTED_REBOOT_CONFIRMED=false
LOW_BATTERY_LED_OFF_ALTERNATIVE=true
OTA_LED_OFF_ALTERNATIVE=true
N3W_FAIL_SAFE_REBOOT_ALTERNATIVE=true
GATE_F_PHYSICAL_ACCEPTANCE_COMPLETE=false
MERGE=false
```

## Required forensic gate

Before writing a repaired artifact or using LED behavior as a reboot oracle, keep one serial session open continuously and ignore any boot event during an initial arming interval. Any subsequent boot ROM / boot initialization signature while the same serial session remains open is strong evidence of a spontaneous reboot.

The capture must also retain battery and N3-W fail-safe lines so the event can be classified among:

1. low-battery protection without reboot;
2. low-battery recovery followed by intentional reboot;
3. N3-W fail-safe reboot;
4. watchdog/panic/brownout/reset outside the N3-W safe-reboot path;
5. no reboot, LED-only behavior.

Do not modify the T1 Broker-host failure oracle during this forensic step.
