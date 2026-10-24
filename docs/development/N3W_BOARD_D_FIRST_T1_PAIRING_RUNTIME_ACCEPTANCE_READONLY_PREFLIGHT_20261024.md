# N3-W Board D First T1 Pairing Runtime Acceptance — Read-only Preflight

Date: 2026-10-24

## Gate

```text
TASK=N3W_BOARD_D_FIRST_T1_PAIRING_RUNTIME_ACCEPTANCE_20261024_01
PHASE=READONLY_PREFLIGHT
RESULT=BLOCKED_BY_MISSING_ONBOARDING_ACTIVATION_PATH
T1_MUTATION=false
BOARD_D_MUTATION=false
PAIRING_EXECUTED=false
```

## Live public-safe baseline

The live T1 was inspected read-only through the established root SSH administration path. No password, private address, secret, raw pairing identifier, or Setup Secret is retained here.

```text
T1_ROOT_SSH_READONLY_PATH=PASS

MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
MANAGER_NETWORK_MODE=host
BROKER_RUNNING=true
BROKER_RESTART_COUNT=0
HOMEASSISTANT_RUNNING=true
HOMEASSISTANT_RESTART_COUNT=0

GH_N3W_RUNTIME_ENABLED=true
GH_N3W_PRODUCT_PAIRING_ENABLED=false
GH_N3W_PAIRING_ADVERTISED_HOST=auto
GH_N3W_NODE_BROKER_HOST=gate-f-unbound.invalid
GH_N3W_NODE_BROKER_PORT=8883
GH_N3W_NODE_BROKER_TLS_SERVER_NAME=armbian

UDP_47111_LISTENER_COUNT=0
TCP_47112_LISTENER_COUNT=0
TCP_8883_LISTENER_COUNT=1

REGISTRATIONS_COUNT=0
PAIRING_SESSIONS_COUNT=0
REGISTRATION_EVENTS_COUNT=0
NODE_ID_LEASES_COUNT=0

T1_PREPAIR_BASELINE=PASS_EXPECTED_PAIRING_DISABLED
PAIRING_ACTIVATION_REQUIRED=true
PAIRING_EXECUTION_ALLOWED_NOW=false
```

This is consistent with the factory-accepted T1 contract. Product pairing is intentionally disabled after device production acceptance and before user onboarding.

## Source review

Current main intentionally freezes the factory Compose baseline as:

```text
GH_N3W_PRODUCT_PAIRING_ENABLED=false
GH_N3W_PAIRING_ADVERTISED_HOST=auto
GH_N3W_NODE_BROKER_HOST=gate-f-unbound.invalid
GH_N3W_NODE_BROKER_TLS_SERVER_NAME=armbian
```

The current Manager source already contains the final-product simplified pairing composition and the Manager-owned private pairing socket. The product CLI `greenhouse-manager-pairing import` can import one Setup Secret over that local socket.

The current Board D firmware source exposes the product QR payload as:

```text
GHN3W2:<hardware_id>:<pairing_id>:<setup_secret>
```

and displays the pairing QR only after Manager discovery/handoff readiness.

The active Board D product core also contains the closed Auto Safe Fallback behavior: after provisioning, a stale Broker locator can be replaced in RAM through Manager rediscovery while TLS identity and credentials remain unchanged. Durable Broker NVS is not rewritten by that recovery path.

## Blocking gap

No repository-owned production onboarding tool was found that safely transitions a factory-accepted T1 from:

```text
pairing=false
node_broker_host=gate-f-unbound.invalid
```

to a bounded user-onboarding pairing window using the current route-selected T1 LAN IPv4 as the initial Broker locator.

Directly editing Compose or merely changing `GH_N3W_PRODUCT_PAIRING_ENABLED=true` is forbidden because the invalid placeholder Broker locator could be provisioned durably into Board D.

Therefore:

```text
BOARD_D_DEFECT_PROVEN=false
T1_RUNTIME_DEFECT_PROVEN=false
ONBOARDING_SOURCE_GAP_PROVEN=true
PAIRING_EXECUTION_ALLOWED_NOW=false
```

## Required successor source contract

The smallest safe successor should:

1. preserve the factory default Compose exactly as pairing-disabled with the invalid placeholder;
2. operate only after fresh factory/runtime binding checks;
3. derive a current route-selected private LAN IPv4 for the target board/network instead of committing any private IP to source;
4. verify Broker TCP/8883 and TLS identity using the existing CA and `armbian` server name before opening pairing;
5. recreate only the Manager for the onboarding window; Broker and Home Assistant identities must remain unchanged;
6. enable exactly the existing simplified product pairing composition;
7. verify one UDP/47111 listener and one TCP/47112 listener after opening;
8. keep the Setup Secret on the private product path and use the existing Manager-owned pairing socket / CLI, never public logs or GitHub;
9. bind the resulting registration back to the frozen Board D hardware identity authority without exposing raw identifiers publicly;
10. close the pairing window after the bounded first-pair transaction and recreate only Manager back to the factory-default pairing-disabled configuration;
11. verify Board D MQTT/Manager/HA runtime after closure;
12. remain fail-closed and non-replayable for ambiguous service recreation or credential-issuance results.

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_FIRST_PAIRING_ONBOARDING_ACTIVATION_SOURCE_DESIGN_AND_REPAIR_20261024_01

SOURCE_ONLY=true
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
PAIRING_EXECUTION=false
MERGE=false
```

No live pairing activation is authorized by this document.
