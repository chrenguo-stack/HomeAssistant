# N3-W Board D Software esp_restart LCD Acceptance Design — 2026-10-24

```text
TASK=N3W_BOARD_D_SOFTWARE_ESP_RESTART_LCD_ACCEPTANCE_20261024_01
PHASE=DESIGN_AND_READONLY_PREFLIGHT
EXECUTION_AUTHORIZATION_GRANTED=false

CURRENT_BOARD_D_APPLICATION=DEV_LOW_BATTERY_BYPASS
CURRENT_BOARD_D_APPLICATION_IS_PRODUCTION_EXACT_R4=false
FIRST_WIFI_PROVISIONING_ACCEPTANCE=CLOSED_PASS
PRECHANGE_NVS_SHA256=d0c4bacc28291348669bf56ec25386685778eb2380c993dbd63583efcd548ab9

KF130=OPEN
SOFTWARE_ESP_RESTART_EXECUTED=false
```

## Goal

Validate exactly one software-triggered ESPHome restart on Board D after first Wi-Fi provisioning. The acceptance must prove that the software restart path independently restores the LCD five-page cycle and the local network API path.

This gate must not inherit PASS from physical EN reset, cold boot, or the earlier exact-R4 post-flash reproduction.

## Frozen source contract

DEV product source: `a15daad779adde74cdead4702f017553118321f8`.

`firmware/esphome_rc/f1_0_rc2/packages/core.yml` blob `b35ca36bcabbe4e1e0a55725738a4c1c52b0ba01` defines:

- Native API enabled with `reboot_timeout: 0s`;
- mDNS enabled;
- Wi-Fi `reboot_timeout: 0s`;
- one ESPHome restart button named `Reboot`, id `sys_reboot`.

ESPHome's restart button invokes the software safe-reboot path. The test trigger must use the Native API button entity and must not use EN/RESET, USB power removal, firmware write, factory reset, or triple reset.

## Scope

Allowed after explicit execution authorization:

1. read-only Native API discovery and exact `Reboot` button identification;
2. exactly one Native API press of the `Reboot` button;
3. passive LCD observation;
4. read-only mDNS / TCP Native API reachability checks after restart.

Forbidden:

- firmware write or OTA;
- raw NVS write or restore;
- repeated software restart;
- physical EN/RESET as recovery inside the acceptance;
- USB power-cycle as recovery inside the acceptance;
- factory reset / triple reset;
- T1 pairing;
- MQTT / Manager acceptance;
- Direct / Relay / RF acceptance;
- PR #663 merge;
- any merge.

## Preconditions

Immediately before mutation:

```text
BOARD_D_WIFI_JOINED=true
MDNS_DISCOVERY=PASS
NATIVE_API_NETWORK_PATH=PASS
LCD_5_PAGE_CYCLE_PRE_RESTART=PASS
LCD_FREEZE_OR_CORRUPTION_PRE_RESTART=false
LCD_PAGE5_PRE_RESTART=正在查找主机
EXACT_REBOOT_BUTTON_COUNT=1
```

No ROM/NVS read is required immediately before this gate because entering ROM and returning to the application would introduce an extra hardware reset directly before the software-reset experiment. The already frozen pre-provisioning NVS image remains private rollback evidence; this gate is about reset/LCD/network behavior, not byte-level NVS invariance.

## One-shot execution

The mutation consists of exactly one Native API `button_command` for the entity named `Reboot`.

After command submission:

- do not send a second command;
- do not press EN;
- do not remove USB power;
- observe the LCD from the restart event through at least one complete five-page cycle;
- allow up to 90 seconds for Wi-Fi/mDNS/Native API network reachability to return.

## PASS criteria

```text
SOFTWARE_RESTART_COMMAND_COUNT=1
SOFTWARE_RESTART_TRIGGER=NATIVE_API_REBOOT_BUTTON
PHYSICAL_EN_RESET_COUNT=0
USB_POWER_CYCLE_COUNT=0

LCD_RECOVERS_AFTER_SOFTWARE_RESTART=true
LCD_5_PAGE_CYCLE_AFTER_SOFTWARE_RESTART=PASS
LCD_FREEZE_OR_CORRUPTION=false

BOARD_D_REJOINS_TARGET_WIFI=true
MDNS_DISCOVERY_AFTER_RESTART=PASS
NATIVE_API_NETWORK_PATH_AFTER_RESTART=PASS

SECOND_SOFTWARE_RESTART_EXECUTED=false
T1_PAIRING_EXECUTED=false
MQTT_ACCEPTANCE_EXECUTED=false
DIRECT_RELAY_ACCEPTANCE_EXECUTED=false
```

## Failure handling

Any LCD freeze/corruption, failure to recover network within the bounded observation, ambiguous reboot-button identity, or inability to prove the command was sent exactly once is a STOP.

Do not retry the software restart in the same authorization. Preserve the board in the observed state and perform read-only forensics first.

## Classification boundary

A PASS closes only the DEV-image software restart/LCD acceptance path. It does not make the DEV low-battery-bypass image production eligible and does not by itself close KF-130 for production exact R4. KF-130 requires separate classification after this evidence and the later production-exact revalidation boundary.
