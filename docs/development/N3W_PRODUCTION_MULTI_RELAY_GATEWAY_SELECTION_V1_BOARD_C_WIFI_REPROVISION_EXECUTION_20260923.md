# N3-W Production Multi-Relay Gateway Selection V1 — Board C Wi-Fi reprovision execution

Status: `AUTHORIZED_IN_PROGRESS`

The operator confirmed Board C power stability has been corrected and authorized continuation
of the planned recovery.

Current evidence before this gate:

```text
BOARD_C_WIFI_CONNECTED=false
BOARD_C_FALLBACK_AP_ACTIVE=true
BOARD_C_N3W_PROVISIONING_STATE=UNPROVISIONED
BOARD_C_POWER_STABILITY_FIX=CONFIRMED_BY_OPERATOR
EXACT_ARTIFACT_REFLASH_REQUIRED=false
```

This gate restores only Board C's saved Wi-Fi STA configuration through the existing captive
portal. It does not erase flash, rewrite the application image, factory-reset the board, or
yet import/re-authorize N3-W pairing material.

```text
GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_WIFI_REPROVISION_20260923_01
BOARD_TARGET=C
WIFI_NVS_MUTATION=true
N3W_PAIRING_MUTATION=false
FLASH_WRITE=false
FULL_NVS_ERASE=false
FACTORY_RESET=false
T1_RUNTIME_MUTATION=false
AUTO_EXECUTE_NEXT_GATE=false
```

Acceptance requires Board C to leave fallback-AP-only state and establish STA connectivity to
the intended AP. N3-W may remain unprovisioned after this gate; that is expected and is handled
by a separate bounded successor gate.

Proposed successor after PASS:

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_N3W_REPROVISION_20260923_01
```
