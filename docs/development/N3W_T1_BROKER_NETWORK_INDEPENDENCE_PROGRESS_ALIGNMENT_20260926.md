# N3-W T1 Broker Network-Independence Progress Alignment — 2026-09-26

Status: `CURRENT_PROGRESS_ALIGNMENT`

This document aligns the current local-chat progress with GitHub before a new-chat handoff. Architecture decisions already made for B1/B2/B3 are archived separately in `docs/development/N3W_T1_BROKER_NETWORK_INDEPENDENCE_ARCHITECTURE_DECISIONS_20260926.md`. It is public-safe: private T1 locators, private LAN addresses, raw credentials, and raw board identities are intentionally omitted.

## 1. Repository and active PR authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=b32878682ab4981fd38b8982caefed95ba3e204d

PR474_STATE=OPEN_DRAFT
PR474_HEAD=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PR474_SOURCE_REVIEW=PASS
PR474_IMPLEMENTATION_REVIEW_COMPLETE=true
PR474_PHYSICAL_VALIDATION=PENDING
PR474_MERGE=false

PR475_STATE=OPEN_DRAFT
PR475_BASE=b32878682ab4981fd38b8982caefed95ba3e204d
PR475_HEAD=c070cc50c72cbbd261e8e8ba6e70d00aa4ef5fd6
PR475_MERGEABLE=true
PR475_SOURCE_REVIEW_R3=PASS
PR475_MERGE_BLOCKER_COUNT=0
PR475_CI=12_OF_12_PASS
PR475_MERGE=false
```

PR #474 remains the bounded full-channel Relay discovery fallback source route. Its source review is closed, but its physical validation has not resumed.

PR #475 is the B1 source/deployment-contract repair for customer-LAN-independent Broker TLS publication. It does not solve stable T1 naming/TLS-identity lifecycle or migration of already-provisioned nodes.

## 2. PR #475 closure through R3

Initial independent review found three blockers:

1. implicit Docker host binding was too broad for an IPv4-only contract;
2. TCP port ranges could bypass 8883 publication counting;
3. the known-required Broker two-network topology was not fully protected.

The current exact PR #475 head closes them:

```text
A1_IPV4_WILDCARD_SEMANTICS=CLOSED_PASS
A2_TLS_PUBLICATION_COUNTING=CLOSED_PASS
A3_KF035_SUCCESSOR=PASS
A4_KF034_PRESERVED=PASS
A5_BROKER_DUAL_NETWORK_GUARD=CLOSED_PASS
A6_WILDCARD_INGRESS_SECURITY=LIVE_GATE_REQUIRED
A7_B2_B3_SCOPE_BOUNDARY=PASS
A8_UNRELATED_REGRESSION=NONE
```

The static deployment contract now requires:

```text
Broker TLS publication:
  exactly one explicit host_ip=0.0.0.0
  target=8883
  published=8883
  protocol=tcp

Broker network mapping:
  n3wfc4-private  -> n3wfc4-private
  n3wfc4-services -> n3wfc4-services

Manager:
  network_mode=host
  ports absent
```

TCP port ranges overlapping 8883 and malformed TCP publication forms fail closed.

## 3. Fresh T1 read-only rebind

No T1 mutation occurred during the rebind.

Fresh evidence confirms:

```text
LIVE_PRIVATE_COMPOSE_BOUND=true
LIVE_PRIVATE_COMPOSE_SHA256=d3a2bb681db523d4414e64fd26d49074d76c90ac5265493f18ec760494472f

BROKER_STATE=EXITED
BROKER_EXIT_CODE=255
BROKER_OOM=false
BROKER_ROOT_CAUSE=STALE_CONCRETE_LAN_HOST_PUBLICATION
BROKER_8883_LISTENER_PRESENT=false

MANAGER_NETWORK_MODE=host
MANAGER_STATE=RESTARTING
MANAGER_INTERNAL_MQTT_HOST=armbian
MANAGER_EXACT_GETADDRINFO_IPV4=127.0.1.1
MANAGER_EXACT_GETADDRINFO_IPV6=::1
BROKER_CERT_SAN=DNS:armbian
KF035_PREBIND=PASS
POST_RECREATE_TCP_TLS=NOT_YET_PROVEN

BROKER_EXPECTED_NETWORKS=n3wfc4-private,n3wfc4-services
BROKER_RENDERED_EFFECTIVE_NETWORK_MAPPING=PASS
BROKER_FAILED_RUNTIME_ATTACHMENT=PARTIAL_AS_EXPECTED_DURING_FAILED_CREATE

BROKER_MOSQUITTO_LISTENER=8883/0.0.0.0
BROKER_ALLOW_ANONYMOUS=false
BROKER_DYNSEC_ENABLED=true
```

The Mosquitto listener is already wildcard inside the container. B1 does not require changing Mosquitto listener configuration; the defect is the Docker host publication lifecycle.

## 4. Fresh host-network and firewall facts

```text
NETWORK_AUTHORITY=NetworkManager
PRIMARY_WIRED_INTERFACE=eth0
WIRED_IPV4_ASSIGNMENT=DHCP
STATIC_CUSTOMER_SUBNET_AS_PRODUCT_AUTHORITY=false

DOCKER_FIREWALL_BACKEND=iptables
DOCKER_USER_CHAIN_PRESENT=true
DOCKER_USER_CUSTOM_RULE_COUNT=0
HOST_INPUT_POLICY=ACCEPT
HOST_FORWARD_POLICY=ACCEPT
NFTABLES_SERVICE=disabled/inactive
FC4_SYSTEMD_DEPLOYMENT_UNIT=ABSENT

CURRENT_8883_INGRESS_GUARD=ABSENT
A6_INGRESS_POLICY=BLOCKER_FOR_LIVE_WILDCARD_ACTIVATION
```

The current customer subnet is deliberately not archived here. Future policy must derive the current connected IPv4 subnet from the managed wired interface instead of persisting a site-specific subnet.

## 5. Current repair boundary

B1 source repair is complete, but live recovery is not ready because publishing `0.0.0.0:8883` without an ingress guard would broaden exposure to every applicable host IPv4 interface.

The next design direction is intentionally narrow:

```text
COMPONENT=n3wfc4-broker-ingress-guard
INTERFACE_AUTHORITY=eth0
SERVICE_PORT=8883
NETWORK_EVENT_AUTHORITY=NetworkManager
DOCKER_FILTER_HOOK=DOCKER-USER
CUSTOM_CHAIN=N3WFC4-BROKER-INGRESS

TRUSTED_SOURCE_RULE=current eth0 connected IPv4 subnet, derived at runtime
UNTRUSTED_8883_RULE=DROP
UNKNOWN_OR_AMBIGUOUS_SUBNET=FAIL_CLOSED
```

A persistent implementation must cover both boot/restart and DHCP/network changes, without switching Docker firewall backend and without hard-coding the current LAN.

This is a design direction, not yet an implemented or live-tested product contract.

## 6. Explicitly separate unresolved work

```text
B1_BROKER_FIXED_LAN_BINDING_SOURCE=PASS
B1_LIVE_RECOVERY=BLOCKED_ON_INGRESS_GUARD

B2_STABLE_T1_NAME_AND_TLS_IDENTITY=OPEN_OUT_OF_SCOPE
B3_EXISTING_NODE_LITERAL_IP_MIGRATION=OPEN_OUT_OF_SCOPE

PR474_PHYSICAL_VALIDATION=DEFERRED_UNTIL_T1_ROUTE_RECOVERS
BOARD_ACCESS=false
T1_RUNTIME_MUTATION=false
```

Do not treat PR #475 source PASS as proof that nodes can already resolve a canonical hostname or that already-paired nodes have migrated away from historical literal addresses.

## 7. Next bounded task

```text
NEXT_ONE_GATE=N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
PR475_MERGE=false
PR474_MERGE=false
```

The next gate designs the durable ingress guard: ownership, iptables/conntrack semantics, NetworkManager refresh, systemd boot ordering, idempotence, fail-closed behavior, tests, rollout, and rollback. It does not mutate T1, recreate Broker, touch boards, solve B2/B3, or merge PR #474/#475.
