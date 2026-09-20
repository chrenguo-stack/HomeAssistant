# PR437 Board B late reconnect + LAN reachability forensic

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Trigger

The exact Board B MQTT session is proven to have disconnected at:

    2026-09-20T14:35:30.732623821Z

No reconnect was logged in the first 180 seconds. Manager and Broker stayed up, Manager's own MQTT socket is currently stable, and no other-client disconnect cluster or Broker error cluster accompanied the event.

## Goal

Without touching Board B, distinguish:

1. Board B eventually reconnected to the Broker;
2. its previous LAN address is still currently reachable and L2 identity matches Board B, but MQTT never reconnected;
3. the previous Board B LAN address is unreachable/nonresponsive;
4. the historical source IP cannot be safely derived.

The executor first checks whether the canonical cursor has recovered since seq=49. It then searches Broker logs for late reconnects and derives the last pre-disconnect source IP from the exact Board B client connection line.

It never emits the raw node ID, hardware ID, IP address, or MAC address. The IP and interface are represented only by hashes in the private JSON/public-safe result.

When T1 has a direct L2 route to the prior source IP, the post-ping neighbor MAC is privately compared with the MAC suffix already bound in Board B's durable hardware_id. Only the boolean comparison result is emitted.

## Active-but-nondestructive probe

The only active network action is:

    ping -n -c 4 -W 1 <private prior Board B source IP>

No MQTT client is created, no MQTT publish/subscribe occurs, and no board reset/serial/flash operation occurs.

## Possible classifications

    CANONICAL_RECOVERY_OBSERVED
    LATE_MQTT_RECONNECT_CANONICAL_STILL_STALE
    BOARD_B_LAN_REACHABLE_MQTT_RECONNECT_NOT_OBSERVED
    SOURCE_IP_REACHABLE_BUT_BOARD_B_L2_IDENTITY_UNPROVEN
    BOARD_B_LAN_UNREACHABLE_OR_NONRESPONSIVE_MQTT_RECONNECT_NOT_OBSERVED
    NO_PRIOR_SOURCE_IP_AUTHORITY

## Execution

    python3 /tmp/n3w-pr437-177468e-boardb-lan-reachability-forensic.py       --t1-target <PRIVATE_T1_SSH_TARGET>       --output /tmp/n3w-pr437-177468e-boardb-lan-reachability-forensic.json

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
