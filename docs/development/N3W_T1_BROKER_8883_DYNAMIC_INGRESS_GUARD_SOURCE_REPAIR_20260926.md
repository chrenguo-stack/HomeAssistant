# N3-W T1 Broker 8883 Dynamic Ingress Guard — Source Repair

Status: `SOURCE_REVIEW_R5_FAIL_REGRESSION_COVERAGE_INCOMPLETE`  
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
SOURCE_BLOCKER_COUNT=1
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

## Live R3 blocker discovered

The first guarded Broker activation on T1 invalidated the R3 source closure for the activation lifecycle.

```text
R3_REVIEWED_SOURCE_HEAD=1a2d1d27602ef9f9deeb590eb4847ce6780da4c9
LIVE_GUARD_APPLY=PASS
LIVE_COMPOSE_CUTOVER=PASS
BROKER_ACTIVATION=FAIL_SOURCE_CONTRACT
ROOT_CAUSE=COMPOSE_PROJECT_IDENTITY_NOT_FROZEN
EXPECTED_RUNTIME_PROJECT=n3wfc4
OBSERVED_ACTIVATION_PROJECT=recipes
OBSERVED_SECOND_BROKER_CONTAINER=recipes-broker-1
R3_SOURCE_CLOSURE=REOPENED
R4_SOURCE_REPAIR_REQUIRED=true
```

The activation unit passed `--env-file` and `-f` but did not pass an explicit Compose project name. Docker Compose therefore derived the project identity from the Compose working-directory basename. The live activation created a second Broker under a different Compose project instead of recreating the existing `n3wfc4` Broker. This is a source/deployment-contract defect, not a T1 operator error.

R4 freezes `N3WFC4_COMPOSE_PROJECT_NAME=n3wfc4`, passes it explicitly to activation `ExecStart` and `ExecStop`, and makes the rendered-Compose deployment gate reject any project identity other than `n3wfc4`.

## R4 independent source review

The R4 review is bound to the exact source authority below. Later documentation-only commits do not change this reviewed source.

```text
R4_SOURCE_REVIEW_HEAD=54342e8807308582f0a61454386645821ce5ef2b
R4_SOURCE_REVIEW_TREE=f1b420e53b40cc05921cf15b0bab9da74a386c27
R4_SOURCE_REVIEW_CI=13_OF_13_PASS
R4_SOURCE_REVIEW=PASS
R4_SOURCE_BLOCKER_COUNT=0
```

Focused review scope was limited to the live blocker discovered during the first guarded activation. The review confirmed:

- Broker activation start and stop both pass an explicit Compose project identity;
- the source package defines the frozen project identity as `n3wfc4`;
- the deployment gate rejects missing, empty, `recipes`, and other project identities;
- the positive deployment contract reports project identity verification;
- lifecycle regression requires the explicit project option on both start and stop;
- R4 does not change the already-reviewed firewall guard, NetworkManager trusted-subnet logic, Broker wildcard publication contract, or B2/B3 scope.

The live finding that created `recipes-broker-1` is therefore closed at source level. It is not yet closed at T1 runtime level. T1 must materialize this exact R4 source, update the installed activation unit/environment authority, and repeat guarded Broker activation before live acceptance can continue.

## Live R5 ingress-coverage blocker discovered

The trusted-LAN positive ingress probe passed, but the non-trusted negative probe exposed a separate packet-path gap after the R4 Compose-project fix.

```text
TRUSTED_LAN_ETH0_TLS=PASS
TRUSTED_ALLOW_COUNTER_ADVANCED=true
NONTRUSTED_SOURCE=DOCKER_BRIDGE_NAMESPACE
NONTRUSTED_SOURCE_IN_TRUSTED_SUBNET=false
NONTRUSTED_TCP_8883_CONNECT=SUCCESS
DOCKER_USER_ANCHOR_COUNTER_CHANGED=false
CUSTOM_CHAIN_DROP_COUNTER_CHANGED=false
DOCKER_NAT_8883_COUNTER_CHANGED=false
HOST_8883_LISTENER=docker-proxy
PACKET_PATH_CLASS=HOST_LOCAL_DOCKER_PROXY_PATH
R4_PROJECT_IDENTITY_RUNTIME_FIX=PASS
R5_INGRESS_COVERAGE_REPAIR_REQUIRED=true
T1_LIVE_GATE=PAUSED_GUARD_PARTIAL_COVERAGE_R5_SOURCE_REPAIR_PENDING
```

The observed Docker-bridge namespace connection to the host LAN address did not traverse the current `DOCKER-USER` original-destination anchor. The host listener is `docker-proxy`, so the current guard proves the forwarded/DNAT path but does not cover this host-local listener path. External untrusted `eth0` ingress is not proven to bypass the guard by this evidence; the newly proven blocker is the uncovered host-local Docker-origin path.

R5 must close this coverage gap or explicitly redefine the accepted threat model before live ingress acceptance can close. Dispatcher installation remains blocked until that decision is implemented and reviewed.

## R5 design frozen

R5 design is frozen in:

`docs/development/N3W_T1_BROKER_8883_HOST_LOCAL_INGRESS_COVERAGE_R5_DESIGN_20260927.md`

The design keeps the R4 `DOCKER-USER` original-destination TCP/8883 guard and adds one exact TCP/8883 anchor at the filter `INPUT` hook for host-local `docker-proxy` traffic. Both hooks use the same project-owned policy chain.

The R5 chain contract is:

```text
trusted state:
  lo + 127.0.0.0/8 -> RETURN
  eth0 + current unique subnet -> RETURN
  everything else -> DROP

zero/ambiguous subnet:
  lo + 127.0.0.0/8 -> RETURN
  everything else -> DROP
```

R5 source repair must support an exact R4 -> R5 migration without deleting the working R4 guard first. Dispatcher installation remains blocked until R5 source review and live acceptance pass.

```text
R5_DESIGN=COMPLETE
R5_SOURCE_REPAIR=IMPLEMENTED
R5_SOURCE_REPAIR_HEAD=6b48104d13f77e4866f02b0825515472b8853cb4
R5_SOURCE_REPAIR_TREE=ffc32e1b97e522670dccb4a97336eaefd2d87d25
R5_GUARD_BLOB=795903b06c7ee93a0602649e478bc070723ab8c0
R5_TEST_BLOB=6f9509463225f15c0e6697327d9183206be8f2ba
R5_CI=13_OF_13_PASS
R5_SOURCE_REVIEW=FAIL
R5_T1_MUTATION=false
NEXT_REQUIRED_STAGE=R5_SOURCE_REVIEW
```

## R5 focused source review

The focused R5 review is bound to the exact source authority below:

```text
R5_SOURCE_REVIEW_BASE=268c2e89b4d491fa442d59b383a7dfd4e56781f6
R5_SOURCE_REVIEW_HEAD=6b48104d13f77e4866f02b0825515472b8853cb4
R5_SOURCE_REVIEW_TREE=ffc32e1b97e522670dccb4a97336eaefd2d87d25
R5_SOURCE_REVIEW_CI=13_OF_13_PASS
R5_SOURCE_REVIEW=FAIL
R5_SOURCE_BLOCKER_COUNT=1
```

The implementation logic is directionally consistent with the frozen R5 design: it adds an exact INPUT TCP/8883 anchor, keeps the DOCKER-USER original-destination anchor, uses one shared policy chain, preserves the loopback-before-trusted-before-DROP order, accepts exact R4 state as migration input, and installs the R5 chain before inserting the new INPUT anchor.

The review found one closure blocker in regression coverage rather than a proven runtime/source-logic defect.

```text
R5-B1=IDEMPOTENT_RELOAD_AND_FOREIGN_STATE_REGRESSION_MISSING
SEVERITY=SOURCE_CLOSURE_BLOCKER
RUNTIME_DEFECT_PROVEN=false
```

The frozen design requires regression proof that idempotent reload preserves normalized foreign INPUT/DOCKER-USER firewall state. The current tests only prove that foreign rules are parsed/preserved in the inventory representation; they do not execute an R5 apply/reload twice against a state containing foreign INPUT and DOCKER-USER rules and verify that those rules are unchanged and no duplicate owned anchor is created.

A focused repair must add an apply/reload state-machine regression covering at least:

- exact R4 -> R5 migration with foreign INPUT and DOCKER-USER rules present;
- second R5 apply/reload idempotence;
- foreign-rule content/order preserved after both passes;
- exactly one first-position DOCKER-USER owned anchor;
- exactly one first-position INPUT owned anchor;
- exact final R5 policy chain after both passes;
- no global INPUT/DOCKER-USER flush or foreign delete/rewrite.

T1 deployment remains blocked. This review does not invalidate the already-proven R4 project-identity runtime fix, Broker recreate, Manager loopback TLS, or trusted-LAN positive ingress evidence.

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

SOURCE_REPAIR_RESULT=R5_REPAIR_R2_REQUIRED
SOURCE_REVIEW_R3=SUPERSEDED_BY_LIVE_BLOCKER
SOURCE_REVIEW_R4=PASS
SOURCE_REVIEW_R4_HEAD=54342e8807308582f0a61454386645821ce5ef2b
R5_SOURCE_REPAIR_HEAD=6b48104d13f77e4866f02b0825515472b8853cb4
R5_SOURCE_REVIEW=NOT_YET_EXECUTED
SOURCE_BLOCKER_COUNT=0
T1_LIVE_GATE=PAUSED_GUARD_PARTIAL_COVERAGE_R5_REPAIR_R2_PENDING
KF097=OPEN
AUTO_EXECUTE_LIVE=false
STOP_AFTER_R4_SOURCE_REVIEW_CLOSURE=true
```
