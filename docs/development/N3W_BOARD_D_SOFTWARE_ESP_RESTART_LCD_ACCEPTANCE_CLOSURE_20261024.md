# N3-W Board D Software Restart + LCD Recovery Acceptance Closure — 2026-10-24

## 1. Gate

```text
TASK=N3W_BOARD_D_SOFTWARE_ESP_RESTART_LCD_ACCEPTANCE_20261024_01
RESULT=CLOSED_PASS
CURRENT_BOARD_D_APPLICATION=DEV_LOW_BATTERY_BYPASS
CURRENT_BOARD_D_APPLICATION_IS_PRODUCTION_EXACT_R4=false
```

This gate validates exactly one software-triggered ESPHome restart on the currently deployed DEV-only low-battery-bypass image after first Wi-Fi provisioning.

It does not promote the DEV image to production eligibility and does not independently prove the production exact-R4 software-restart path.

## 2. Frozen pre-restart baseline

```text
FIRST_WIFI_PROVISIONING_ACCEPTANCE=CLOSED_PASS
SOFTWARE_RESTART_PREFLIGHT=PASS
BOARD_D_NETWORK_ENDPOINT_BINDING=PASS
API_DEVICE_NAME_MATCH=true
API_MAC_SUFFIX_MATCH=true
NETWORK_ENDPOINT_BINDING_SHA256=6e39106d8cbc6fa27b0ad3c3b9af4622b31f4850e7ae7bc16eedd11c448cdcdf
NATIVE_API_CONNECTIVITY_PRE_RESTART=PASS
EXACT_REBOOT_BUTTON_COUNT=1
ROM_HARDWARE_ID_REDERIVATION=NOT_APPLICABLE_VIA_NATIVE_API
SOFTWARE_RESTART_COMMAND_COUNT=0

LCD_5_PAGE_CYCLE_PRE_RESTART=PASS
LCD_FREEZE_OR_CORRUPTION_PRE_RESTART=false
LCD_PAGE5_PRE_RESTART=正在查找主机
```

The previously frozen Board D ROM/product identity chain remained authoritative. Native API endpoint checks were deliberately not used to rederive the ROM hardware identity.

An earlier preflight stopped on `BOARD_D_IDENTITY_MISMATCH`; source review classified that as a checker-design false stop caused by mixing the product STA-MAC identity path with ESPHome's Native API/eFuse MAC path. No restart command or board mutation occurred during that false stop.

## 3. Authorized one-shot mutation

Explicit authorization was granted for this gate only.

```text
SOFTWARE_RESTART_COMMAND_COUNT=1
SOFTWARE_RESTART_TRIGGER=NATIVE_API_REBOOT_BUTTON
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false
SECOND_SOFTWARE_RESTART_EXECUTED=false
```

The command selected the exact single Native API button entity named `Reboot` after rechecking the frozen network endpoint binding.

No second software restart, physical EN/RESET recovery, USB power-cycle recovery, firmware/OTA write, raw NVS write/restore, T1 pairing, MQTT acceptance, Direct/Relay acceptance, RF execution, or merge occurred.

## 4. LCD recovery evidence

```text
LCD_RECOVERS_AFTER_SOFTWARE_RESTART=true
LCD_5_PAGE_CYCLE_AFTER_SOFTWARE_RESTART=PASS
LCD_FREEZE_OR_CORRUPTION=false
LCD_PAGE5_AFTER_SOFTWARE_RESTART=正在查找主机
```

The LCD recovered after the one software restart and completed the full five-page cycle without freeze, corruption, or manual recovery.

## 5. Post-restart network recovery evidence

A read-only bounded post-restart check produced:

```text
BOARD_D_REJOINS_TARGET_WIFI=true
MDNS_DISCOVERY_AFTER_RESTART=PASS
NATIVE_API_NETWORK_PATH_AFTER_RESTART=PASS
NATIVE_API_ENDPOINT_BINDING_AFTER_RESTART=PASS
SECOND_SOFTWARE_RESTART_EXECUTED=false
POST_RESTART_NETWORK_RECOVERY=PASS
```

No retry or second restart was required.

## 6. Acceptance classification

```text
N3W_BOARD_D_SOFTWARE_ESP_RESTART_LCD_ACCEPTANCE_20261024_01=CLOSED_PASS

DEV_SOFTWARE_RESTART_LCD_PATH=PASS
DEV_SOFTWARE_RESTART_NETWORK_RECOVERY=PASS
DEV_SOFTWARE_RESTART_MANUAL_RECOVERY_REQUIRED=false

PRODUCTION_EXACT_R4_SOFTWARE_RESTART_VALIDATED=false
DEV_IMAGE_PRODUCTION_ELIGIBLE=false
KF130=OPEN
```

This closes the scoped software-restart/LCD/network-recovery acceptance for the currently deployed DEV-only image.

KF-130 remains OPEN because the historical production exact-R4 LCD freeze is not root-caused and the exact-R4 software-restart path has not been revalidated with this same one-shot acceptance. The present result narrows the issue: a generic software-restart failure is not reproduced on the current DEV image.

## 7. STOP boundary

```text
REPEAT_SOFTWARE_RESTART_UNDER_CONSUMED_AUTHORIZATION=FORBIDDEN
AUTOMATIC_T1_PAIRING=false
AUTOMATIC_MQTT_ACCEPTANCE=false
AUTOMATIC_DIRECT_RELAY_ACCEPTANCE=false
AUTOMATIC_PRODUCTION_R4_REFLASH=false
MERGE=false
```

Any next live stage requires its own scope and authorization.
