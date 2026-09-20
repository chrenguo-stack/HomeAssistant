# PR437 Board B Direct-recovery-window forensic

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Trigger

Current evidence proves:

    last Manager canonical Direct seq=49
    exact Board B MQTT disconnect at 2026-09-20T14:35:30.732623821Z
    no reconnect in the first 180 seconds
    Manager/Broker remained healthy
    Board B prior LAN address currently gave 0/4 ICMP replies
    neighbor state after the probe was INCOMPLETE

This does not by itself prove that the board never opens a short Direct-recovery Wi-Fi window.

## Source-derived timing oracle

At exact PR437 HEAD 177468e:

- DIRECT/no-MQTT is counted once per new 5-second business sample.
- LocalPathPolicy enters DISCOVERY after 3 Direct failures.
- claiming Relay radio disables ESPHome Wi-Fi.
- when no healthy Relay exists, full Direct verification is scheduled with the initial interval rather than exponential Relay backoff.
- initial no-Relay full-verify interval = 60 s.
- each no-Relay Direct attempt enables Wi-Fi and gives Wi-Fi recovery up to 20 s, MQTT recovery up to 25 s, with a 50 s absolute attempt bound.
- after a failed no-Relay full verification and successful Relay-radio restore, the next no-Relay full verification is again scheduled at 60 s.

Therefore a 150-second observation spans more than two nominal no-Relay scheduling intervals. A 5-second ICMP sample cadence should detect a Wi-Fi-associated window at the prior address if the address is still valid and the board responds to ICMP.

## Goal

Without touching Board B:

1. detect any canonical recovery;
2. detect any late exact-client Broker reconnect;
3. detect any periodic LAN reachability at the prior Board B source IP;
4. privately compare neighbor MAC with the durable Board B hardware identity when available.

No raw IP, MAC, node ID, or hardware ID is emitted.

## Execution

    python3 /tmp/n3w-pr437-177468e-direct-recovery-window-forensic.py       --t1-target <PRIVATE_T1_SSH_TARGET>       --output /tmp/n3w-pr437-177468e-direct-recovery-window-forensic.json

Expected duration: about 150 seconds.

## Boundary

    BOARD_ACCESS=false
    BOARD_RESET=false
    BOARD_FLASH_WRITE=false
    PRODUCT_NVS_WRITE=false
    APPLICATION_SERIAL_OPEN=false

    NETWORK_PROBE=ICMP_ONLY
    MQTT_TEST_PUBLISH=false
    MQTT_EXTRA_SUBSCRIBER=false
    T1_MUTATION=false

    PR437_MERGE=false
    KF096_STATUS=OPEN
