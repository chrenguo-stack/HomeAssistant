# N3-W Board D development low-battery bypass runtime acceptance — 2026-10-24

## Result

~~~text
TASK=N3W_BOARD_D_DEVELOPMENT_LOW_BATTERY_BYPASS_RUNTIME_ACCEPTANCE_20261024_01
RESULT=CLOSED_PASS

BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

DEV_SOURCE_HEAD=a15daad779adde74cdead4702f017553118321f8
DEV_ARTIFACT_RUN_ID=40039280572
DEV_ARTIFACT_ID=12538399121
DEV_FIRMWARE_SHA256=da17489dd1ba4fdc13d52b88c03812cbc5a26d23ac2a57e2da5ab1c59a014e95
DEV_NORMALIZED_SLOT_SHA256=c50e71ad3842bb2aa041896442ec4fb64f8326826086c06ba6d09a6a9aedef6d

LOW_BATTERY_PROTECTION_BYPASSED=true
DEVELOPMENT_ONLY=true
PRODUCTION_ELIGIBLE=false

RUNTIME_OBSERVATION_SECONDS=480
USB_SAMPLES=475
USB_MISSING_SAMPLES=2
USB_PRESENCE_TRANSITIONS=2

LCD_5_PAGE_CYCLE_CONTINUED_THROUGH_480S=true
LCD_FREEZE_OR_CORRUPTION_OBSERVED=false
STATUS_LED_ON_AT_390S=true
STATUS_LED_ON_AT_480S=true

FLASH_WRITE_DURING_RUNTIME=false
DIRECT_NVS_WRITE=false
LOW_BATTERY_PROTECTION_ENTRY_OBSERVED=false
LOW_BATTERY_RECOVERY_RESTART_OBSERVED=false
~~~

## Interpretation

The development-only low-battery-bypass image remained running for 480 seconds after a single normal EN/RESET application start. This interval crosses the former low-battery grace/counting window.

The LCD continued its full five-page cycle through the complete observation. No freeze or corruption was observed. The status LED was still on at both 390 seconds and 480 seconds, so the former low-battery protection behavior that would turn the status LED off was not observed.

Two USB locator samples were absent during the 480-second observation and the locator returned, producing two presence transitions. Since LCD progression and the status LED remained normal and no low-battery behavior or restart was observed, these are retained as USB enumeration/transient observations rather than classified as a product failure.

This acceptance proves the development bypass is operational for bench work. It does not modify or validate the production low-battery policy. The development artifact remains explicitly non-production and PR #663 must not be merged.

## Closure

~~~text
LOW_BATTERY_BYPASS_SOURCE=PASS
LOW_BATTERY_BYPASS_ARTIFACT=PASS
LOW_BATTERY_BYPASS_PHYSICAL_WRITE=PASS
LOW_BATTERY_BYPASS_RUNTIME_480S=PASS

BOARD_D_DEVELOPMENT_LOW_BATTERY_BYPASS=CLOSED_PASS
PRODUCTION_LOW_BATTERY_LOGIC_CHANGED=false
PR663_MERGE_ALLOWED=false
~~~
