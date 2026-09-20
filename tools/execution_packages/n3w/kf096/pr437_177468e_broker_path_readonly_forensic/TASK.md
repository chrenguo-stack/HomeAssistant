# N3-W PR #437 177468e Board B post-write Broker-path read-only forensic

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Trigger

Board B's Manager canonical/replay cursor is frozen at:

    seq=49
    source=direct
    updated_at=2026-09-20T14:35:06.070Z

Manager remains running with restart count 0. Pairing is approved and the node lease is active. No fresh Manager Direct acceptance or rejection after the seq=49 anchor is proven.

The exact application image was independently read back byte-for-byte equal to artifact 10607030747.

## Goal

Use only T1 read-only evidence to determine whether, after the seq=49 anchor:

1. the exact Board B MQTT client reconnected/disconnected at the Broker;
2. the Broker logged any exact-client authentication/ACL/protocol/socket failure;
3. the Broker debug log observed any exact-client PUBLISH or PUBACK;
4. Dynamic Security still contains the exact Board B client, expected role, and Direct ingress publish ACL.

A log absence is not proof that Board B never transmitted. The executor reports Broker logging configuration and container continuity so evidence strength can be judged separately.

## Runtime authority

The executor:

- resolves Board B's raw node ID privately from Manager canonical SQLite using the frozen node-ID SHA-256;
- derives the expected MQTT username/client ID using the repository contract;
- identifies the authoritative running Broker by Docker Compose labels:
  - service=broker
  - project=n3wfc4
- reads active mosquitto.conf and Dynamic Security JSON from the running Broker container;
- reads Broker logs from the exact canonical anchor timestamp.

No raw node ID, username, credential, MAC, or T1 locator is emitted into public-safe stdout.

## Output classifications

One of:

    BROKER_RECEIVED_DIRECT_PUBLISH_AFTER_ANCHOR
    EXACT_CLIENT_AUTH_OR_ACL_FAILURE_OBSERVED
    EXACT_CLIENT_BROKER_SESSION_ACTIVITY_OBSERVED
    NO_EXACT_CLIENT_BROKER_LOG_EVIDENCE

The last result means only that the Broker log did not contain exact-client evidence in the available log window.

## Execution

    python3 /tmp/n3w-pr437-177468e-broker-path-readonly-forensic.py       --t1-target <PRIVATE_T1_SSH_TARGET>       --output /tmp/n3w-pr437-177468e-broker-path-readonly-forensic.json

## Boundary

    BOARD_ACCESS=false
    BOARD_RESET=false
    BOARD_FLASH_WRITE=false
    PRODUCT_NVS_WRITE=false
    APPLICATION_SERIAL_OPEN=false

    T1_ACCESS=SSH_READ_ONLY
    T1_MUTATION=false
    MQTT_TEST_PUBLISH=false
    MQTT_EXTRA_SUBSCRIBER=false

    PR437_MERGE=false
    KF096_STATUS=OPEN
