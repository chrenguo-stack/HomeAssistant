# N3-W Production Multi-Relay Gateway Selection V1 — P1B pre-reboot Relay log forensic closure

Status: `CLOSED_PASS_AS_FORENSIC`

The read-only Manager log forensic found accepted Relay telemetry for Board C through both
Gateway A and Gateway B within the 45-minute evidence window.

```text
READ_ONLY=true
LOG_WINDOW_MINUTES=45
T1_MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
MANAGER_STARTED_AT=2026-09-14T02:46:17.376354998Z

C_ACCEPTED_DIRECT_COUNT=24
C_ACCEPTED_RELAY_ANY_GATEWAY_COUNT=9
C_ACCEPTED_RELAY_VIA_A_COUNT=5
C_ACCEPTED_RELAY_VIA_B_COUNT=4

C_RELAY_VIA_B_FIRST_ACCEPTED_AT=2026-09-23T13:35:07.591577138Z
C_RELAY_VIA_B_LAST_ACCEPTED_AT=2026-09-23T13:39:17.877971884Z
C_RELAY_VIA_B_MANAGER_ACCEPTED=true

C_ANY_RELAY_FIRST_ACCEPTED_AT=2026-09-23T13:14:32.892793776Z
C_ANY_RELAY_LAST_ACCEPTED_AT=2026-09-23T13:39:17.877971884Z

T1_RUNTIME_MUTATION=false
BOARD_ACCESS=false
RESULT=COMPLETE
STOP=true
```

Disposition:

- Gateway B relay path is proven capable of delivering Board C telemetry to Manager canonical ingress.
- The earlier P1B observer did not emit PASS because Board C changed boot session before its same-boot qualification could close.
- The reboot therefore invalidated same-boot P1B closure, but the evidence does not support classifying Gateway B relay delivery as nonfunctional.
- Board C power stability is now a primary physical-test confounder to isolate before repeating same-boot P1B qualification.

The log window alone does not bind every accepted Relay entry to the exact pre-reboot boot session because the first forensic parser did not retain the dedup-key boot ID. A further read-only timeline extraction can close that attribution if required.

```text
P1A_GATEWAY_A_QUALIFICATION=PASS
GATEWAY_B_RELAY_DELIVERY_TO_MANAGER=PROVEN
P1_GATEWAY_B_SAME_BOOT_QUALIFICATION=NOT_CLOSED
BOARD_C_POWER_STABILITY_REVIEW=REQUIRED

NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_POWER_STABILITY_AND_P1B_RETRY_PREP_20260923_01
```
