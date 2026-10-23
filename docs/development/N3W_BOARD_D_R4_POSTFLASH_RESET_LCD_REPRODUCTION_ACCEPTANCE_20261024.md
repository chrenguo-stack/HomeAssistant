# N3-W Board D R4 post-flash reset LCD reproduction acceptance — 2026-10-24

## Result

~~~text
TASK=N3W_BOARD_D_R4_POSTFLASH_RESET_LCD_REPRODUCTION_ACCEPTANCE_20261024_01
RESULT=CLOSED_PASS_NOT_REPRODUCED

EXACT_PRODUCT_SOURCE=ec5f6d68e33db7757d91c807fff708ca81b075dc
EXACT_ARTIFACT_RUN_ID=39901919230
EXACT_ARTIFACT_ID=12478974186
EXACT_RELEASE_BUNDLE_SHA256=b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5

BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

PREWRITE_NVS_SHA256=8384704e3fe6c6fe1a02ecea14faea0b609d8ca0508dba165aee31fca2672bb1
POSTWRITE_NVS_SHA256=8384704e3fe6c6fe1a02ecea14faea0b609d8ca0508dba165aee31fca2672bb1
NVS_UNCHANGED=true

PHY_INIT_SHA256_PREWRITE=f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6
PHY_INIT_SHA256_POSTWRITE=f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6
PHY_INIT_UNCHANGED=true

APP0_FULL_SLOT_SHA256=539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195
APP1_FULL_SLOT_SHA256=539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195
APP0_TAIL_ERASED=true
APP1_TAIL_ERASED=true
OLD_APPLICATION_CODE_REMAINS=false

POSTWRITE_HARDWARE_ID_MATCH=true
WRITE_AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

USB_POWER_REMOVED=false
POSTFLASH_EN_RESET_COUNT=1
OBSERVATION_SECONDS=35
USB_SAMPLES=34
USB_MISSING_SAMPLES=1
USB_PRESENCE_TRANSITIONS=2

LCD_FIRST_READABLE_SECONDS_APPROX=1
LCD_5_PAGE_CYCLE_OBSERVED=true
LCD_FREEZE_OR_CORRUPTION_OBSERVED=false
LCD_BEHAVIOR=正常

KF130_POSTFLASH_EXACT_R4_REPRODUCED=false
KF130=OPEN
ROOT_CAUSE=TBD
~~~

## Interpretation

The exact R4 artifact was written through the reviewed dual-slot padded-normalization route. Post-write verification passed for Board D identity, bootloader, partition table, OTA data, complete app0/app1 slot content, phy_init continuity and NVS continuity.

After the write and post-write verification completed, USB power remained applied. The operator performed exactly one physical EN/RESET and observed the LCD for 35 seconds.

The LCD became readable in about one second, completed the full five-page cycle, and showed no freeze or corruption. Therefore the original operator-observed post-flash LCD freeze was not reproduced in this controlled exact-R4 reproduction.

The USB serial locator was absent for one sample and returned, producing two presence transitions. Because the LCD and application-visible behavior remained normal, this is retained as a USB enumeration/transient observation and is not classified as a product failure from this evidence alone.

## NVS baseline note

The historical first-boot NVS hash was:

~~~text
a61948eaf640aa878d245ef9c95a6529f28a1b2d876618e187419309e89d21a6
~~~

The fresh prewrite hash in this gate was:

~~~text
8384704e3fe6c6fe1a02ecea14faea0b609d8ca0508dba165aee31fca2672bb1
~~~

The change occurred before this preflight/write gate. The read-only preflight performed no NVS write. This gate freezes the fresh prewrite value as its own continuity baseline and proves the exact-R4 write preserved it unchanged.

## KF-130 disposition

KF-130 remains OPEN.

This gate materially narrows the problem:

- 3/3 true cold boots PASS;
- 3/3 physical EN warm resets PASS;
- 1/1 controlled exact-R4 post-flash + EN reset PASS;
- the originally observed post-flash freeze remains historical evidence but was not reproduced;
- software `esp_restart()` remains independently unvalidated because Board D is unprovisioned and the Native API path was unavailable without out-of-scope pairing/configuration;
- actual LCD /RST wiring/timing remains unverified.

The next Board D image should be the development-only low-battery-bypass artifact so bench work can proceed without low-battery interruptions. That development image must not be treated as evidence for exact-R4 production behavior.
