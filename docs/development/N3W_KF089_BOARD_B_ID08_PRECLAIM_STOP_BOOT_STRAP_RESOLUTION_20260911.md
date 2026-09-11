# N3W KF-089 Board B ID08 preclaim STOP — BOOT strap resolution

## Observed preclaim result

```text
ID08_CLAIMED=false
OBSERVER_READY_BEFORE_BOOT=false
ROM_DOWNLOAD_STRAP_RELEASED=NOT_PROVEN
NORMAL_BOOT_RESET_EXECUTED=false
RESULT=STOP
STOP_REASON=Existing host evidence could not prove GPIO9/BOOT had been released from ROM download-mode condition.
```

Because ID08 was not claimed and Board B was not accessed/reset, the existing ID08 authorization remains unused and may continue after resolving the precondition. No new authorization is required.

## Hardware authority

Project PCB guidance defines:

- GPIO9 / BOOT: momentary switch to GND plus 10 kΩ pull-up to 3.3 V.
- GPIO8: 10 kΩ pull-up to 3.3 V.

ESP32-C6 boot contract:

- SPI boot when GPIO9=1 (GPIO8 don't-care).
- Download boot when GPIO9=0 and GPIO8=1.

Therefore, on the designed board, releasing the BOOT switch and ensuring there is no external short from GPIO9 to GND establishes the normal hardware strap condition for SPI boot.

## Next physical gate under the same ID08 authorization

Do not use esptool hard-reset as the primary proof of normal boot. Instead:

1. Start the fixed USB re-enumeration observer first and confirm READY.
2. Operator confirms BOOT/GPIO9 is not pressed or shorted to GND.
3. Operator performs one brief RESET/EN press only, without touching BOOT.
4. Observe up to 60 seconds with the fixed observer.
5. Stop after classification.

No Flash, otadata, NVS, rollback, second reset, or automatic retry is allowed.
