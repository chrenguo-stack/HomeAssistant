# N3W KF-089 A/B relay data-path end-to-end physical authorization — ID11 — 2026-09-12

User explicitly authorized the complete bounded physical experiment:

```text
AUTHORIZATION_ID=N3W_KF089_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL_20260912_11
AUTHORIZATION_GRANTED=true
REPLAY_PERMITTED=false
TARGETS=BOARD_A,BOARD_B,T1_READONLY
PURPOSE=VERIFY_B_TO_A_RELAY_DATA_PATH_AND_A_TO_T1_DOWNSTREAM_DELIVERY
```

Authorized scope, as one indivisible physical gate:

1. Board A fresh normal boot and Direct baseline verification.
2. Board B power-off move to the already-qualified selective-RF location.
3. Board B cold boot at that location.
4. One 90-second RF observation window only.
5. During that window, Board A remains Direct; Board B must have no Direct ingress and may enter Relay_ACTIVE.
6. Board B remains powered for an additional 6 seconds after the main window so Schema-v5 diagnostics can persist.
7. Board B is powered off.
8. Board A remains powered for an additional 10 seconds so receive/decode/forward counters can persist, then is powered off.
9. Board B is returned to the Mac and enters ROM without running the application; one read-only NVS diagnostic snapshot is read using the already validated default stub / no-reset path.
10. Board A is read the same way exactly once.
11. T1/Broker/Manager may be observed read-only for the exact test window and downstream correlation.

Forbidden:

```text
FLASH_WRITE=false
NVS_WRITE=false
OTADATA_WRITE=false
PAIRING_CHANGE=false
FIRMWARE_REFLASH=false
PROTOCOL_CHANGE=false
RETRY_POLICY_CHANGE=false
SECOND_RF_CAPTURE=false
AUTO_RETRY=false
LOCATION_SEARCH=false
T1_MUTATION=false
BROKER_MUTATION=false
MANAGER_MUTATION=false
```

The authorization is consumed at the first deliberate physical action on Board A or Board B under ID11. If a required identity, baseline, observer, or readback precondition fails, stop without starting a second RF capture.

Expected decisive evidence:

- Board B: relay telemetry attempts and asynchronous unicast completion counters.
- Board A: compact receive/decode/forward counters and rejection/failure counters.
- T1/Broker/Manager: downstream relay ingress / canonical accept for end-to-end closure.

`esp_now_send(...) == ESP_OK` alone is not delivery proof.
