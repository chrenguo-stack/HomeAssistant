# N3-W T1 Broker 8883 Dynamic Ingress Guard — Source Repair

Status: `SOURCE_REPAIR_CLOSED_PASS`  
Date: 2026-09-26  
Gate: `N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_REPAIR_20260926_01`

## Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR475_BASE_HEAD=c070cc50c72cbbd261e8e8ba6e70d00aa4ef5fd6
PR478=478
PR478_BRANCH=fix/n3w-t1-broker-8883-dynamic-ingress-guard-20260926
DESIGN_PR476_HEAD=290e27ad5dfb28d57f0c6504e5d3cd629d8f1927
DESIGN_PATH=docs/development/N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926.md
SOURCE_REVIEW_R3_HEAD=1a2d1d27602ef9f9deeb590eb4847ce6780da4c9
SOURCE_REVIEW_R3_CI=13_OF_13_PASS
SOURCE_REVIEW_R3=PASS
```

PR #478 is intentionally stacked on PR #475 because the ingress guard depends on the LAN-IP-independent wildcard publication contract in PR #475.

## Implemented source surface

```text
tools/n3w_broker_ingress_guard.py
tests/tools/test_n3w_broker_ingress_guard.py
tests/tools/test_n3w_broker_ingress_guard_lifecycle.py
tools/n3w_pairing_deployment_gate.py
tests/tools/test_n3w_pairing_deployment_gate.py
infra/n3w-t1/systemd/n3wfc4-broker-ingress-guard.service
infra/n3w-t1/systemd/n3wfc4-broker-activation.service
infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
infra/n3w-t1/broker-activation.env.example
infra/n3w-t1/README.md
.github/workflows/n3w-broker-ingress-guard-ci.yml
.github/workflows/n3w-t1-deployment-gate-ci.yml
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
```

## Frozen implementation behavior

```text
FILTER_HOOK=DOCKER-USER
PACKET_MATCH=conntrack ORIGINAL original-destination TCP/8883
CUSTOM_CHAIN=N3WFC4-BROKER-INGRESS
TRUSTED_SUBNET_AUTHORITY=NetworkManager current eth0 IPv4 state
ZERO_OR_AMBIGUOUS_SUBNET=DROP_ONLY
ALLOW=eth0 + current unique subnet -> RETURN
DEFAULT=DROP
GLOBAL_FLUSH=false
FOREIGN_RULE_MUTATION=false
REFRESH=atomic owned-chain replacement
BOOT_ORDER=Docker -> guard -> Broker activation
BROKER_RESTART_POLICY=no
NETWORK_CHANGE=NetworkManager dispatcher -> guard reload-or-restart -> fresh state reread
BROKER_RECOVERY=guard success -> ensure Broker activation owner started
RULE_MATCHING=option/value semantic pairs, not unordered token bag
FIRST_CHAIN_INSTALL=single iptables-restore --noflush transaction
HOST_TCP_8883_OWNER=Broker only across rendered Compose
```

## Regression coverage

Source/host tests cover:

- one valid subnet;
- multiple addresses in one subnet;
- no address/disconnected;
- different simultaneous subnets;
- invalid/link-local/loopback/multicast/IPv6/`/0`;
- no hardcoded RFC1918-only assumption;
- drop-only and allowed-chain generation;
- exact original-destination anchor ownership;
- foreign-rule preservation;
- ambiguous owned rule rejection;
- foreign custom-chain reference rejection;
- structured secret-safe output;
- systemd Docker→guard→Broker ordering;
- bounded NetworkManager dispatcher;
- guard failure stopping Broker activation owner;
- automatic Broker activation recovery after guard recovery;
- option/value-preserving firewall semantic matching;
- single-transaction first creation of the owned firewall chain;
- Broker `restart: no`;
- explicit IPv4 wildcard 8883 mapping;
- frozen two-network mapping;
- whole-Compose host TCP/8883 exclusive Broker ownership;
- rejection of another service exact/range TCP/8883 publication;
- UDP/8883 kept outside this TCP guard contract.

## Evidence boundary

The final independent source review is bound to the exact source HEAD below:

```text
SOURCE_REVIEW_R3_HEAD=1a2d1d27602ef9f9deeb590eb4847ce6780da4c9
SOURCE_REVIEW_R3_CI=13_OF_13_PASS
SOURCE_REVIEW_R3=PASS
SOURCE_BLOCKER_COUNT=0
```

This documentation closure is intentionally documentation-only. Its commit will advance the PR HEAD, but it does not change the reviewed source behavior above. Future live execution must keep the reviewed source authority separate from the documentation-only repository tip.

```text
T1_RUNTIME_MUTATION=false
FIREWALL_LIVE_MUTATION=false
BROKER_MUTATION=false
MANAGER_MUTATION=false
BOARD_ACCESS=false
PR474_MERGE=false
PR475_MERGE=false
PR478_MERGE=false
```

## Live acceptance remains separate

Source/CI success cannot prove:

- T1 iptables command/runtime semantics;
- actual DOCKER-USER packet path;
- current trusted-LAN positive ingress;
- non-trusted negative ingress;
- DHCP/subnet transition behavior;
- reboot/Docker restart ordering in the actual host;
- Broker recreate success;
- Manager exact-namespace TCP+TLS recovery;
- node hostname resolution;
- B2/B3;
- board telemetry.

Those remain for a separately authorized live gate after source review.

## Candidate closure

```text
SOURCE_REPAIR_IMPLEMENTATION_COMPLETE=true
SOURCE_REGRESSION_ARCHIVED=true
DEPLOYMENT_SOURCE_PACKAGE_ARCHIVED=true
KNOWN_FAILURES_ALIGNED=true
UNARCHIVED_CRITICAL_KNOWLEDGE=0

SOURCE_REPAIR_RESULT=CLOSED_PASS
SOURCE_REVIEW_R3=PASS
SOURCE_BLOCKER_COUNT=0
T1_LIVE_GATE=NOT_YET_EXECUTED
KF097=OPEN
AUTO_EXECUTE_LIVE=false
STOP_AFTER_DOCUMENTATION_CLOSURE=true
```
