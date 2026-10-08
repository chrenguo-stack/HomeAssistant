# N3-W Auto Safe Fallback Gate F R2 Broker Session Reconciliation — 2026-10-04

Status: `R2_PHYSICAL_ACCEPTANCE_FAIL_BROKER_SESSION_NOT_PROVEN`

## Confirmed physical evidence

- R2 exact-source application write/readback: PASS.
- Runtime otadata stable after boot: PASS.
- Historical durable Broker host remained preserved as the stale-address oracle.
- Controlled-reset acceptance did not recover Manager-visible MQTT/telemetry within the 120 s budget.
- Manager canonical cursor did not advance and Manager restart count did not increase.
- A later passive T1 capture observed one Board-to-current-T1 TCP/8883 flow using one source port for the full observation window, with repeated ACK and ACK+PSH packets carrying payload.
- No UDP/47111 discovery packets were observed during that later capture, so discovery may have occurred before the capture window.
- A subsequent read showed no currently established Board TCP/8883 socket and no canonical telemetry advance.
- Broker stdout/stderr logs did not provide connection/authentication evidence for the Board during the inspected window. Absence of logs is not treated as proof that the connection never existed.

## Current interpretation

The 120 s product acceptance remains FAIL. The later TCP evidence is strong enough that the investigation must not assume Broker relocation never reached the current T1 address. However, a stable MQTT-connected state and Manager-visible telemetry were not established.

The next forensic step is an end-to-end network timeline captured on T1 beginning before a controlled Board reboot. The capture must distinguish:

1. UDP discovery request/response timing.
2. TCP SYN/SYN-ACK/ACK timing to current T1:8883.
3. TLS record progression where observable from record headers.
4. TCP close/reset behavior.
5. Whether any sustained established session appears before the 120 s acceptance deadline.

No T1 configuration mutation, Board NVS erase, or Broker-host correction is authorized as part of this forensic step.

```text
R2_RECOVERY_WITHIN_120S=FAIL
R2_STABLE_MQTT_SESSION_PROVEN=false
R2_MANAGER_TELEMETRY_RECOVERY_PROVEN=false
BROKER_LOG_ABSENCE_NOT_TREATED_AS_PRODUCT_FAILURE=true
NEXT=END_TO_END_NETWORK_TIMELINE_FROM_PRE_RESET_CAPTURE
MERGE=false
```
