# N3-W Production Multi-Relay Gateway Selection V1 — Board C Wi-Fi reprovision closure

Status: `CLOSED_PASS`

## Evidence

The summary field `BOARD_C_WIFI_CONNECTED_OBSERVED=false` is contradicted by the authoritative
ESPHome serial state transition captured later in the same run:

```text
Loaded settings: <SITE_AP>
Found networks:
Connecting to '<SITE_AP>'...
Connected
Disabling AP
IP Address: <REDACTED>
```

Therefore the summary boolean is an observer/parser false negative, not a product failure.

The same capture reports:

```text
Unprovisioned N3-W node ready for local pairing
Simplified pairing waiting code=1
```

Wi-Fi recovery is complete while N3-W Manager pairing remains outstanding.

The boot lines in this capture are consistent with the immediately preceding APP1 erase gate's
intentional final hard reset. The supplied observation contains no evidence of a later spontaneous
reboot after Wi-Fi association.

## Closure

```text
BOARD_C_WIFI_SETTINGS_LOADED=true
BOARD_C_TARGET_AP_VISIBLE=true
BOARD_C_WIFI_ASSOCIATION=PASS
BOARD_C_WIFI_IP_ASSIGNED=true
BOARD_C_FALLBACK_AP_DISABLED_AFTER_STA_CONNECT=true
BOARD_C_WIFI_REPROVISION=PASS
BOARD_C_N3W_PROVISIONING_STATE=UNPROVISIONED
BOARD_C_N3W_REPROVISION_REQUIRED=true
FLASH_WRITE=false
FULL_NVS_ERASE=false
FACTORY_RESET=false
```

The diagnostic script's connected boolean is classified as an oracle defect because it did not
match ESPHome's exact `[I][wifi]: Connected` form.

## Next gate

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01
AUTO_EXECUTE_NEXT_GATE=false
```
