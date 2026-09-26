# N3-W T1 Broker TCP/8883 Dynamic Ingress Guard
# Source Design — 2026-09-26

Status: `SOURCE_DESIGN_CANDIDATE`

```text
TASK=N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01
REPOSITORY=chrenguo-stack/HomeAssistant
DESIGN_BASE_PR475=c070cc50c72cbbd261e8e8ba6e70d00aa4ef5fd6
CONTEXT_PR476=b5ae9ef55a0d8ab3cb453dee5243afcd31e3c6e1
LIVE_MUTATION=false
BOARD_ACCESS=false
PR474_MERGE=false
PR475_MERGE=false
```

## 1. Purpose

This design closes the remaining A6 live-safety prerequisite for PR #475 B1.

PR #475 already removes the customer-specific Docker host-IP dependency from the source contract by requiring one explicit IPv4 wildcard Broker publication on TCP/8883. The remaining problem is that wildcard publication must not expose Broker TCP/8883 beyond the current trusted wired LAN.

The guard must therefore:

- use Docker's `DOCKER-USER` hook;
- identify Docker-DNAT traffic by its original destination TCP port 8883;
- derive the trusted IPv4 subnet from the current NetworkManager-managed `eth0` runtime state;
- refresh automatically after DHCP or network changes;
- be fail-closed when the trusted subnet is absent or ambiguous;
- be idempotent and preserve unrelated Docker/firewall rules;
- remain safe across boot and Docker restarts;
- have explicit rollback and later live-acceptance oracles.

This gate is design-only. It does not mutate T1.

## 2. Frozen boundaries

```text
BROKER_PUBLICATION=0.0.0.0:8883->8883/tcp
BROKER_MOSQUITTO_LISTENER=8883/0.0.0.0
DOCKER_FIREWALL_BACKEND=iptables
NETWORK_AUTHORITY=NetworkManager
TRUSTED_INTERFACE=eth0
DOCKER_FILTER_HOOK=DOCKER-USER
CUSTOM_CHAIN=N3WFC4-BROKER-INGRESS
SERVICE_PORT=8883
```

Out of scope:

- B2 stable T1 hostname/TLS identity lifecycle;
- B3 migration of already-provisioned nodes using historical literal Broker IPs;
- PR #474 physical validation;
- changing Docker firewall backend;
- nftables-service deployment;
- changing Mosquitto listener, TLS, DynSec, ACLs, credentials or Manager application configuration.

## 3. Design decisions

### 3.1 One source of truth for the trusted subnet

The trusted subnet authority is the fresh NetworkManager runtime state of `eth0`.

The dispatcher event environment is only a trigger. It is not the subnet authority.

Every apply/reconcile run must freshly query NetworkManager and derive the subnet again. This is required because NetworkManager dispatcher events may be queued and may run after a later network event.

The helper must not read or persist:

- a customer LAN IP;
- a customer subnet constant;
- a gateway-specific address;
- an old DHCP lease file as authority;
- a hand-maintained allowlist.

### 3.2 Trusted-subnet derivation algorithm

The helper performs this logic:

```text
1. Query fresh NetworkManager state for eth0.
2. Require eth0 to be managed and currently connected.
3. Read all current IPv4 address/prefix values owned by that NetworkManager device.
4. Reject unusable addresses such as unspecified, loopback, multicast and link-local.
5. Convert each usable address/prefix into its IPv4 network.
6. Deduplicate identical networks.
7. Exactly one resulting network => TRUSTED_SUBNET_VALID.
8. Zero or more than one distinct network => TRUSTED_SUBNET_AMBIGUOUS_OR_ABSENT.
9. Ambiguous or absent => install DENY_ALL_8883 guard.
```

Multiple addresses that normalize to the same connected subnet are not ambiguous.

The runtime subnet may appear in the live iptables rule because it is dynamically derived. It must not appear as a source-code or product configuration constant.

Public evidence must not archive the raw customer subnet. Public evidence may record a digest or boolean equality result.

### 3.3 Why conntrack original-destination matching is required

At `DOCKER-USER`, Docker-published traffic has already passed destination NAT. Normal destination-port matching therefore sees the container-side destination, not the host-side original publication.

The guard must use the conntrack extension to match the original flow.

The target flow selector is:

```text
IPv4
TCP
conntrack direction ORIGINAL
conntrack state DNAT
original destination port 8883
```

The `DNAT` condition prevents the product guard from accidentally filtering unrelated routed TCP/8883 traffic that was never a Docker-published connection.

### 3.4 Rule semantics

The custom chain owns only Broker publication traffic. It must return immediately for unrelated traffic.

Trusted state conceptually contains:

```text
if DNAT + ORIGINAL + TCP + original-dst-port 8883
and input-interface eth0
and source in dynamically-derived trusted subnet
then RETURN to DOCKER-USER

if DNAT + ORIGINAL + TCP + original-dst-port 8883
then DROP

otherwise RETURN
```

`RETURN`, rather than unconditional `ACCEPT`, is used for the permitted path so later independent rules in `DOCKER-USER` are still able to evaluate the packet.

Fail-closed state contains:

```text
if DNAT + ORIGINAL + TCP + original-dst-port 8883
then DROP

otherwise RETURN
```

The guard does not modify Docker's `DOCKER`, `DOCKER-FORWARD`, NAT, bridge or automatically maintained chains.

### 3.5 Local Manager loopback path

The Manager remains `network_mode=host` and continues to use its independent loopback Broker endpoint.

The ingress guard is a forwarded Docker-publication filter in `DOCKER-USER`; it must not add a broad source allow for `127.0.0.0/8` to external ingress.

The exact Manager-runtime TCP+TLS probe required by KF-035/KF-097 remains mandatory after live recreate. If the actual Docker/netfilter behavior on T1 causes the loopback flow to traverse the guard unexpectedly, live acceptance fails and the source design must be corrected before rollout.

No assumption that "local traffic is automatically safe" can replace that exact runtime probe.

## 4. Rule ownership and idempotence

### 4.1 Dedicated chain

The product owns exactly one chain:

```text
N3WFC4-BROKER-INGRESS
```

The product owns exactly one tagged jump from `DOCKER-USER` into that chain.

The jump is inserted before Docker's terminal return behavior. The guard must not flush or rebuild `DOCKER-USER`.

### 4.2 Bounded chain replacement

The custom chain is rebuilt with `iptables-restore --noflush`.

The restore input declares only the product-owned user chain. With `--noflush`, declaring that user-defined chain flushes and rebuilds that chain while retaining unrelated table/chain contents.

The implementation must:

```text
1. render the next custom-chain rules in memory;
2. validate them with iptables-restore --test;
3. apply them with iptables-restore --noflush --wait;
4. verify the resulting chain;
5. verify exactly one owned jump exists in DOCKER-USER.
```

On first install, the chain is populated before its jump is inserted, so there is no moment where an empty owned chain is treated as an active security boundary.

Repeated apply with the same NetworkManager state must produce the same effective rules and must not add duplicate jumps.

If multiple exact tagged jumps are found, the helper may remove only its own exact duplicate jump rules and must leave every unrelated `DOCKER-USER` rule untouched.

## 5. Runtime helper contract

Proposed source component:

```text
tools/n3w_t1_broker_ingress_guard.py
```

The helper should support bounded host operations rather than embedding private deployment paths.

Required modes:

```text
check
apply
remove
```

Expected behavior:

- `check`: read-only inspection, derive expected state, compare installed guard, emit public-safe structured result;
- `apply`: derive fresh NetworkManager state and converge to trusted-subnet or deny-all state;
- `remove`: remove only the exact owned jump and owned chain; refuse broad/global cleanup.

The helper must serialize concurrent apply/remove activity with a bounded lock under `/run`.

A lock timeout is a failure. It must not silently skip reconciliation.

Default logs must not print the raw current customer IP/subnet.

## 6. NetworkManager refresh model

Proposed dispatcher:

```text
/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
```

Relevant `eth0` actions:

```text
up
dhcp4-change
reapply
down
```

The dispatcher must ignore other interfaces and unrelated actions.

The dispatcher invokes the same helper used by boot-time reconciliation. It does not directly edit iptables rules.

The helper re-queries current NetworkManager state on every run, so stale queued dispatcher events cannot re-install a historical subnet merely because the event environment is old.

The helper must be fast and bounded because NetworkManager dispatcher scripts are time-limited.

## 7. Boot and Docker restart ordering

### 7.1 Security invariant

The mandatory invariant is:

```text
BROKER_WILDCARD_PUBLICATION_MUST_NOT_START_BEFORE_GUARD_READY=true
BROKER_DOCKER_AUTOSTART_OUTSIDE_GUARD_FORBIDDEN=true
```

A guard that is installed only after a Broker container has already auto-started is not fail-closed.

### 7.2 Why a new Broker lifecycle owner is required

`DOCKER-USER` is a Docker-created hook. Pre-creating it before Docker startup is not used as the design because that relies on Docker-version-specific behavior and can interfere with Docker's own installation of the FORWARD jump.

The safe order is therefore:

```text
NetworkManager service starts
Docker service starts and creates its firewall hooks
guard service runs and verifies DOCKER-USER
guard installs trusted-subnet or deny-all rules
Broker service is then allowed to start
NetworkManager dispatcher refreshes the guard on later eth0 changes
```

### 7.3 systemd units

The source-repair stage must add a dedicated oneshot guard unit:

```text
n3wfc4-broker-ingress-guard.service
```

Required ordering:

```text
After=docker.service NetworkManager.service
PartOf=docker.service
```

The helper may succeed in `DENY_ALL_8883` state when NetworkManager has no unique trusted subnet. Safe-closed is a valid boot state.

The source-repair stage must also add a Broker lifecycle unit:

```text
n3wfc4-broker.service
```

Required ordering:

```text
Requires=docker.service n3wfc4-broker-ingress-guard.service
After=docker.service n3wfc4-broker-ingress-guard.service
PartOf=docker.service
```

The exact private Compose locator is an install-time/private runtime input and is not committed to public GitHub.

The Broker container must not retain a Docker restart policy that can auto-start it before the systemd guard dependency has run.

The later source repair must define one runtime owner for Broker restart. It must not leave both Docker restart policy and systemd independently racing to start the same Broker.

### 7.4 Docker restart

A Docker service restart must cause:

```text
Broker stop
Docker firewall recreation
guard re-apply
Broker start only after guard success
```

The source/host regression must prove the systemd dependency graph produces this order.

## 8. Fail-closed behavior

The guard enters `DENY_ALL_8883` when any of these conditions occur:

- NetworkManager unavailable;
- `eth0` missing, unmanaged or not connected;
- no usable IPv4 address;
- more than one distinct current connected IPv4 subnet;
- malformed NetworkManager address/prefix data;
- conntrack matcher/rule parse unavailable;
- custom-chain apply verification fails;
- exact owned jump cannot be installed or verified;
- Docker `DOCKER-USER` hook is absent.

If `DOCKER-USER` is absent, the helper cannot prove enforcement and returns failure. The Broker lifecycle unit must not start wildcard publication.

If the trusted subnet cannot be derived but `DOCKER-USER` is available, the helper installs the deny-all 8883 state and may report safe-closed success.

## 9. Non-target invariants

The implementation must not:

- flush the filter table;
- flush `FORWARD`;
- flush `DOCKER-USER`;
- modify Docker-generated chains;
- change Docker firewall backend;
- enable or configure nftables service;
- modify non-8883 traffic policy;
- weaken TLS, DynSec or Broker authentication;
- persist a customer subnet;
- change Manager network mode;
- change PR #474 radio/product source.

Before and after a source/host integration test, unrelated iptables-save content must compare equal except for the exact owned chain and one exact owned jump.

## 10. Source regression plan

Required deterministic tests:

### 10.1 Trusted-subnet derivation

- one valid connected IPv4 subnet -> trusted state;
- multiple addresses in same subnet -> trusted state;
- no address -> deny-all;
- disconnected `eth0` -> deny-all;
- unmanaged `eth0` -> deny-all;
- multiple distinct IPv4 subnets -> deny-all;
- invalid CIDR -> deny-all;
- loopback/link-local/multicast/unspecified only -> deny-all.

### 10.2 Rule rendering

Tests must prove:

- TCP only;
- `--ctdir ORIGINAL`;
- DNAT state;
- original destination port 8883;
- trusted allow is bound to `eth0` and the derived subnet;
- deny rule follows trusted allow;
- unrelated traffic returns;
- deny-all state has no trusted allow;
- no current customer IP/subnet literal exists in source fixtures intended as production constants.

### 10.3 Idempotence

Applying the same desired state twice must keep:

```text
OWNED_JUMP_COUNT=1
OWNED_CHAIN_COUNT=1
OWNED_RULESET_DUPLICATION=0
```

### 10.4 Non-destructive behavior

Tests must reject any generated operation containing broad/global flushes or mutations of Docker-owned chains.

### 10.5 Startup contract

Tests must prove:

- Broker lifecycle depends on guard;
- Broker cannot use an independent Docker auto-restart path;
- guard runs after Docker;
- Docker restart propagates through guard before Broker restart.

### 10.6 Existing deployment gate integration

PR #475 deployment-gate v2 remains authoritative for:

- one explicit `0.0.0.0:8883->8883/tcp` Broker publication;
- Manager host network with no ports;
- exact Broker dual-network mapping.

The new guard source tests are additive. They must not weaken KF-034/KF-035/KF-097 checks.

## 11. Host regression plan

A Linux host regression, separate from pure unit tests, must prove the real iptables frontend supports the generated conntrack rules.

It must verify:

```text
IPTABLES_RESTORE_TEST=PASS
CUSTOM_CHAIN_REBUILD=PASS
OWNED_JUMP_EXACTLY_ONE=PASS
UNRELATED_RULE_PRESERVATION=PASS
SECOND_APPLY_IDEMPOTENT=PASS
DENY_ALL_RECONCILIATION=PASS
TRUSTED_SUBNET_RECONCILIATION=PASS
```

A host regression may use synthetic non-customer subnets. It must not archive the live customer subnet.

## 12. Rollback model

Rollback is fail-closed.

Required later live rollback order:

```text
1. stop or prove absent the wildcard-published Broker;
2. restore the exact prechange Broker/deployment lifecycle authority;
3. remove the exact owned DOCKER-USER jump;
4. delete only N3WFC4-BROKER-INGRESS;
5. remove/disable the guard dispatcher and systemd units;
6. verify unrelated firewall state is unchanged;
7. verify Broker is not left wildcard-published without the guard.
```

If the Broker cannot be stopped or its prechange deployment authority cannot be restored, the guard must remain installed and rollback is `ROLLBACK_INCOMPLETE`.

The source-repair/live gate must take fresh prechange hashes and runtime snapshots before mutation.

## 13. Later live acceptance oracle

The later live gate is not authorized by this document. When authorized, PASS requires all applicable oracles below.

### 13.1 Pre-activation

```text
PR475_STATIC_DEPLOYMENT_GATE=PASS
GUARD_SOURCE_HEAD_BOUND=true
FRESH_PRECHANGE_SNAPSHOT=PASS
DOCKER_USER_PRESENT=true
OWNED_JUMP_COUNT=1
GUARD_EFFECTIVE_STATE=TRUSTED_SUBNET_OR_DENY_ALL
BROKER_WILDCARD_NOT_ACTIVE_BEFORE_GUARD=true
```

### 13.2 Trusted LAN ingress

From a client genuinely located on the currently derived trusted wired LAN:

```text
TCP_8883_CONNECT=PASS
TLS_SERVER_NAME_HANDSHAKE=PASS
BROKER_AUTH_BOUNDARY_UNCHANGED=true
```

### 13.3 Untrusted ingress

From a source genuinely outside the trusted subnet/interface:

```text
TCP_8883_UNTRUSTED=BLOCKED
GUARD_DROP_COUNTER_ADVANCES=true
```

If no genuine untrusted path can be produced, this part is `INCONCLUSIVE`; it must not be converted to PASS from source inspection alone.

### 13.4 Manager loopback continuity

From the exact Manager image with host networking:

```text
MANAGER_GETADDRINFO_EXPECTED_LOOPBACK=PASS
MANAGER_TO_BROKER_TCP_8883=PASS
MANAGER_TO_BROKER_TLS_SERVER_NAME=PASS
MANAGER_STABLE_AFTER_BROKER_RECOVERY=PASS
```

This remains an independent KF-035/KF-097 proof.

### 13.5 DHCP / network change

After an authorized change that produces a different connected IPv4 subnet:

```text
NETWORKMANAGER_EVENT_OBSERVED=true
GUARD_AUTO_REFRESH=PASS
OLD_SUBNET_RULE_REMOVED=true
NEW_DERIVED_SUBNET_RULE_PRESENT=true
OWNED_JUMP_COUNT=1
BROKER_PUBLICATION_REMAINS_CUSTOMER_IP_INDEPENDENT=true
```

Raw subnets stay private.

### 13.6 Reboot and Docker restart

After separately authorized restart tests:

```text
GUARD_BEFORE_BROKER_START=PASS
BROKER_NEVER_AUTOSTARTS_OUTSIDE_GUARD=PASS
POST_REBOOT_GUARD=PASS
POST_DOCKER_RESTART_GUARD=PASS
POST_RESTART_MANAGER_TLS=PASS
```

### 13.7 Fail-closed oracle

Where a safe test method exists:

```text
NO_UNIQUE_TRUSTED_SUBNET=>DENY_ALL_8883
BROKER_START_BLOCKED_IF_GUARD_ENFORCEMENT_UNPROVEN=true
```

## 14. Security and privacy evidence

Public GitHub evidence may contain:

- exact source SHA;
- rule-template hashes;
- booleans proving runtime subnet/rule equality;
- prefix length where non-identifying;
- service/unit state;
- sanitized iptables diffs;
- acceptance results.

Public GitHub evidence must not contain:

- current customer T1 IPv4;
- current customer subnet;
- private host locator;
- credentials;
- private Compose path.

## 15. External technical basis

The design relies on these upstream behaviors:

- Docker documents `DOCKER-USER` as the user hook evaluated before Docker forwarding rules and states that packets there have already been DNATed; matching original destination requires conntrack.
- NetworkManager dispatcher documents `up`, `down`, `dhcp4-change` and `reapply` events and warns that queued scripts may run after later network events; therefore the helper re-queries live state.
- `iptables-restore --noflush` documents that declaring a user-defined chain flushes/rebuilds that chain while retaining unrelated chains in the table.

## 16. Design closure criteria

```text
DESIGN_AUTHORITY=this document
DOCKER_FILTER_HOOK=DOCKER-USER
TRUSTED_SUBNET_AUTHORITY=fresh NetworkManager eth0 runtime state
NETWORK_CHANGE_REFRESH_AUTHORITY=NetworkManager dispatcher -> fresh helper reconcile
BOOT_ORDERING=Docker -> guard -> Broker
FAIL_CLOSED_BEHAVIOR=deny all DNAT original TCP/8883 when subnet unavailable/ambiguous; block Broker start when enforcement itself is unproven
RULE_IDEMPOTENCE=one owned chain + one owned tagged jump + atomic custom-chain rebuild
ROLLBACK_MODEL=stop wildcard Broker before guard removal; restore exact prechange authority
SOURCE_TEST_PLAN=defined
LIVE_ACCEPTANCE_PLAN=defined
```

Design PASS requires source review to confirm no narrower issue remains in the packet selector, lifecycle ordering, rollback model or test oracle.

No source implementation or T1 mutation is authorized by this document.
