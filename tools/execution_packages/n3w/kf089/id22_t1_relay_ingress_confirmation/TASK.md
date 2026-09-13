# KF-089 ID22 — T1 Relay Ingress Confirmation

Status: `HOST_ONLY_PACKAGE_PREPARATION`

This package is the next gate after ID21 PASS. It does not itself authorize Board A/Board B access, T1 access, application boot, controlled RF, or any mutation. A fresh explicit physical/T1 authorization bound to the final exact package commit is required before execution.

## Goal

Close the remaining KF-089 evidence gap in one fresh Schema-v5 Relay boot session:

```text
Board B RelayActive
-> B relay telemetry submit
-> B unicast TX completion
-> Board A compact RX/decode/forward submit
-> T1 Broker-mediated MQTT ingress
-> Manager accepted simplified N3-W telemetry source=relay
```

ID21 already proved the complete board-side chain in an independent session. ID22 repeats only one bounded Relay session because same-window T1 evidence is required; it does not repeat the ID21 Direct-baseline boot session.

A PASS proves Relay telemetry end-to-end through Manager ingress. Home Assistant entity/display propagation is not part of this gate.

## Frozen predecessor

```text
ID21_RESULT=PASS
ID21_EXECUTION_PACKAGE_COMMIT=9ebe5968e2f06f23a657abbeeb68c4094b445a66
BOARD_SIDE_RELAY_CHAIN=PROVEN
ID21_B_RELAY_TELEMETRY_ATTEMPTS=24
ID21_B_RELAY_TELEMETRY_SUBMIT_SUCCESS=24
ID21_B_UNICAST_COMPLETION_SUCCESS=22
ID21_A_COMPACT_RX=23
ID21_A_COMPACT_DECODE_SUCCESS=23
ID21_A_COMPACT_FORWARD_ATTEMPTS=23
ID21_A_COMPACT_FORWARD_SUBMIT_SUCCESS=23
```

Schema-v5 image authority remains:

```text
SOURCE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
FIRMWARE_SIZE=1115648
FIRMWARE_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
```

T1 runtime convergence is a frozen predecessor:

```text
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
AUTHORITATIVE_MANAGER_COUNT=1
LEGACY_MANAGER_COUNT=0
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_BROKER_COUNT=0
BROKER_HOST_PUBLICATION_RUNTIME=PASS
MANAGER_TO_BROKER_TLS_MQTT=PASS
T1_CONTROLLED_REBOOT_BOOT_RECOVERY=PASS
```

Fresh ID22 preclaim must re-observe the relevant runtime before any RF window.

The currently deployed Manager authority is not represented by a Compose service label. ID22 therefore binds the Manager using the public-safe frozen deployed authority tuple:

```text
CONTAINER_NAME=greenhouse-manager
IMAGE_PREFIX=greenhouse-manager:
SOURCE_REVISION=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
NETWORK_MODE=host
```

The Broker remains bound by its current Compose lineage:

```text
COMPOSE_SERVICE=broker
COMPOSE_PROJECT=n3wfc4
TLS_RUNTIME_PUBLICATION=8883/tcp
```

This reflects the observed post-convergence runtime and avoids treating absence of a Manager Compose label as absence of the Manager itself.

## Why Manager log acceptance is a valid T1 ingress oracle

The frozen Manager source subscribes to:

```text
gh/v1/<system_id>/ingress/gateway/+/+/frame
```

and the simplified MQTT service logs:

```text
Accepted simplified N3-W telemetry source=relay ...
```

only after its MQTT `_on_message` relay path has parsed and accepted the Relay ingress result. Therefore a positive `source=relay` acceptance inside the bounded T1 log window is positive evidence that the Board-A gateway publication reached the Broker-mediated Manager MQTT ingress path. Raw node/gateway IDs, dedup keys and full logs remain private evidence.

## Execution sequence after later authorization

### P0 — T1 read-only runtime preclaim

The executor SSHes to a user-supplied private T1 target and performs read-only Docker inspection only.

It requires exactly one authoritative Manager matching the frozen deployed Manager tuple above and exactly one Broker matching the current `n3wfc4` Compose `broker` lineage; both must be running. Manager must use host networking. Broker must expose a live `8883/tcp` runtime publication. Container IDs, images, labels, restart counts and port mappings are captured privately.

No container restart, exec, create, stop, network change, file write, MQTT publish/subscribe, or configuration mutation is permitted.

### P1 — fresh two-board ROM preclaim

Both boards begin fully unpowered and enter fresh ROM Download mode. The executor binds silicon identity using complete `BASE MAC:` values, then reads partition table, otadata, exact-size app0/app1 windows and NVS.

PASS requires both selected applications to remain the exact Schema-v5 image. Board A and Board B must both select slot 0 with `ota_seq=5`, state VALID. Diagnostic snapshots must be Schema v5. Historical ID21 counters may be nonzero at this preclaim and are not treated as the new window baseline; the next application boot creates a new diagnostic boot session.

### P2 — fresh Relay session staging

From ROM state:

1. fully power both boards off;
2. normal-boot A and B exactly once with BOOT/GPIO9 released;
3. keep both in normal AP coverage for at least 45 seconds;
4. keep all other lab N3-W compact senders powered off;
5. do not access T1 manually and do not open serial.

After the staging token, the executor reads a fresh UTC timestamp from T1. This timestamp becomes the start of the Manager log evidence window.

### P3 — bounded selective-RF window

1. keep Board A powered in normal AP coverage;
2. move/isolate only Board B into the previously qualified selective-RF condition, where B loses AP/Wi-Fi while A<->B ESP-NOW remains viable;
3. maintain the condition for at least 180 seconds;
4. power Board B off first;
5. keep Board A running at least 10 additional seconds for diagnostic persistence;
6. power Board A off;
7. re-enter fresh ROM Download on both boards;
8. confirm the final token.

The executor then captures a T1 end timestamp, Manager Docker logs bounded by the T1 start/end timestamps, fresh T1 runtime inventory, and the two board NVS snapshots.

## PASS criteria

Same fresh board boot session must prove:

```text
B path_state=RELAY_ACTIVE
B relay_active_count>=1
B accept_verify>=1
B peer_install_success>=1
B relay_telemetry_attempts>=1
B relay_telemetry_success>=1
B unicast_completion_success>=1

A path_state=DIRECT
A compact_rx_count>=1
A compact_decode_success>=1
A compact_forward_attempts>=1
A compact_forward_submit_success>=1
```

The bounded T1 Manager log window must prove:

```text
MANAGER_ACCEPTED_RELAY_COUNT>=1
```

and the authoritative Manager/Broker container IDs and restart counts must remain unchanged through the window.

PASS closure:

```text
BOARD_SIDE_RELAY_CHAIN=PROVEN_IN_ID22_SESSION
T1_BROKER_MEDIATED_RELAY_INGRESS=PROVEN
MANAGER_RELAY_INGRESS=PROVEN
MANAGER_RELAY_ACCEPTANCE=PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
HOME_ASSISTANT_ENTITY_UPDATE=NOT_IN_SCOPE
```

## Fail-closed localization order

```text
T1_RUNTIME_PRECLAIM
BOARD_PRECLAIM
B_RELAY_ACTIVE
B_AUTHENTICATED_RELAY_ACQUISITION
B_RELAY_TELEMETRY_SUBMISSION
B_UNICAST_TX_COMPLETION
A_COMPACT_RX
A_COMPACT_DECODE
A_COMPACT_FORWARD_SUBMIT
T1_MANAGER_RELAY_ACCEPTANCE
T1_RUNTIME_STABILITY_POSTCHECK
```

A STOP is final for that authorization. No automatic boot retry, SSH retry, board reconnect retry, second log window, mutation, or improvised recovery is allowed.

## Forbidden

```text
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE_BY_HOST=false
OTADATA_WRITE=false
APP_WRITE=false
PAIRING_CHANGE=false
CREDENTIAL_CHANGE=false
SERIAL_OPEN=false
T1_FILE_WRITE=false
T1_DOCKER_MUTATION=false
T1_NETWORK_MUTATION=false
MQTT_TEST_PUBLISH=false
MQTT_EXTRA_SUBSCRIBER=false
AUTO_RETRY=false
AUTO_ROLLBACK=false
SECOND_NORMAL_BOOT=false
```

Normal product diagnostic NVS persistence during the single authorized application boot is expected device behavior and is distinct from a host-side NVS mutation.

## Evidence boundary

The private evidence root may contain SSH target locators, Docker IDs/labels/images, complete board identities, raw NVS images and raw Manager logs. Public GitHub may contain only sanitized counts, hashes, public-safe board suffixes, package/source authority and adjudication summaries.
