# N3-W PR #437 Board B post-write disconnect-context T1 read-only forensic

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Trigger

The exact Board B MQTT client disconnected from the authoritative Broker at:

    2026-09-20T14:35:30.732623821Z

The last Manager canonical acceptance was:

    seq=49
    source=direct
    updated_at=2026-09-20T14:35:06.070Z

The exact-client disconnect followed the last canonical acceptance by about 24.66 seconds.

Current Broker/DynSec evidence already proves:

    Broker running / restart_count=0
    exact Board B DynSec client exists
    expected role present and assigned
    Direct ingress publish ACL present
    no exact-client auth/ACL error in the available post-anchor logs

## Goal

Inspect a bounded Broker window around the exact Board B disconnect and determine whether the event was:

- isolated to Board B;
- accompanied by Manager session loss;
- part of wider MQTT client churn;
- adjacent to a Broker error cluster;
- followed by a logged Board B reconnect.

This gate also samples the Manager process's own currently established MQTT socket by matching socket inodes owned by PID 1 inside the Manager container against its configured MQTT remote port. This is current-state continuity evidence only; it is not retroactive proof of the historical socket state at 14:35.

## Bounded window

    center = 2026-09-20T14:35:30.732623821Z
    before = 90 seconds
    after  = 180 seconds

No raw client IDs are emitted in public-safe stdout or result fields.

## Broker logging limitation

The current Broker log configuration is:

    log_type error
    log_type notice
    log_type warning

Therefore absence of PUBLISH/PUBACK lines is not a usable packet-level oracle. The executor reports:

    BROKER_PUBLISH_VISIBILITY=NOT_AVAILABLE_AT_NOTICE_WARNING_ERROR_LOG_LEVEL

and does not interpret zero packet lines as zero traffic.

## Output

Important fields include:

    MANAGER_MQTT_SOCKET_SAMPLE_COUNTS
    MANAGER_MQTT_SOCKET_STABLE_NOW

    BOARD_B_DISCONNECT_COUNT
    BOARD_B_CONNECTION_BEFORE_DISCONNECT_COUNT
    BOARD_B_CONNECTION_AFTER_DISCONNECT_COUNT
    BOARD_B_RECONNECT_CLASSIFICATION

    MANAGER_DISCONNECT_COUNT_IN_WINDOW
    MANAGER_CONNECTION_COUNT_IN_WINDOW
    MANAGER_WINDOW_CLASSIFICATION

    OTHER_UNIQUE_DISCONNECT_CLIENT_COUNT
    OTHER_DISCONNECT_COUNT_WITHIN_5S
    OTHER_DISCONNECT_COUNT_WITHIN_30S
    MASS_DISCONNECT_NEAR_EVENT

    GENERIC_ERROR_CATEGORIES
    GENERIC_ERROR_COUNT_WITHIN_5S
    GENERIC_ERROR_COUNT_WITHIN_30S
    BROKER_ERROR_CLUSTER_NEAR_EVENT

    DISCONNECT_CONTEXT_CLASSIFICATION

## Execution

    python3 /tmp/n3w-pr437-177468e-disconnect-context-t1-forensic.py       --t1-target <PRIVATE_T1_SSH_TARGET>       --output /tmp/n3w-pr437-177468e-disconnect-context-t1-forensic.json

## Boundary

    BOARD_ACCESS=false
    BOARD_RESET=false
    BOARD_FLASH_WRITE=false
    PRODUCT_NVS_WRITE=false
    APPLICATION_SERIAL_OPEN=false

    MQTT_TEST_PUBLISH=false
    MQTT_EXTRA_SUBSCRIBER=false

    T1_ACCESS=SSH_READ_ONLY
    T1_MUTATION=false

    PR437_MERGE=false
    KF096_STATUS=OPEN
