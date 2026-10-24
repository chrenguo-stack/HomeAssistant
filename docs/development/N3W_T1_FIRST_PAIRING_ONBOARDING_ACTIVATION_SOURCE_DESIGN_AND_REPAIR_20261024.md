# N3-W T1 First-Pairing Onboarding Activation — Source Design and Repair

Date: 2026-10-24  
Task: `N3W_T1_FIRST_PAIRING_ONBOARDING_ACTIVATION_SOURCE_DESIGN_AND_REPAIR_20261024_01`

## 1. Scope

```text
SOURCE_ONLY=true
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
PAIRING_EXECUTION=false
MERGE=false
```

This gate fills the product lifecycle gap between factory acceptance and user onboarding. It does not change the factory-accepted T1 defaults and does not itself authorize a live pairing window.

## 2. Frozen lifecycle boundary

The current production route remains:

```text
DEVICE_ACCEPTANCE_PASSED
→ USER_ONBOARDING / ACTIVE
```

The factory Compose remains intentionally fail-closed:

```text
GH_N3W_PRODUCT_PAIRING_ENABLED=false
GH_N3W_PAIRING_ADVERTISED_HOST=auto
GH_N3W_NODE_BROKER_HOST=gate-f-unbound.invalid
GH_N3W_NODE_BROKER_PORT=8883
GH_N3W_NODE_BROKER_TLS_SERVER_NAME=armbian
```

The onboarding tool must never rewrite those defaults in the repository or in the installed base Compose.

## 3. Source addition

New host tool:

```text
tools/n3w_t1_first_pairing_onboarding.py
```

Command surface:

```text
inspect
open
close
```

The tool is intentionally separate from F4 production activation. Factory production authorization does not implicitly authorize user onboarding.

## 4. Inspect contract

`inspect` is read-only. It verifies:

- installed base Compose and Compose environment are present;
- base Compose still renders the exact pairing-disabled factory contract;
- `FACTORY_ACCEPTED.json` is valid;
- the exact Broker, Manager and Home Assistant project services each resolve to one running container;
- Manager remains host-networked;
- the four first-registration tables can be read from the Manager state database;
- if an onboarding transaction exists, only public-safe hashes/state are emitted.

No raw peer address or Broker locator is printed.

## 5. Open contract

A live `open` will require a separately authorized ID with the `N3W_T1_FIRST_PAIRING_` prefix and exact confirmation text:

```text
OPEN FIRST PAIRING WINDOW: YES
```

Before claim, it requires:

```text
FACTORY_ACCEPTED=true
PAIRING_ENABLED=false
PAIRING_ADVERTISED_HOST=auto
NODE_BROKER_HOST=gate-f-unbound.invalid
PAIRING_UDP_47111=0
PAIRING_HTTP_47112=0
REGISTRATIONS=0
PAIRING_SESSIONS=0
REGISTRATION_EVENTS=0
NODE_ID_LEASES=0
```

The target Board peer IPv4 is runtime input only.

The exact deployed Manager image is used as the route-selection authority:

```text
pairing_discovery.is_local_source(peer)
n3w_simplified_discovery.resolve_route_selected_ipv4(peer)
```

The selected locator must be RFC1918 IPv4. The host then verifies TCP/8883 TLS using the installed CA while keeping:

```text
TLS_SERVER_NAME=armbian
```

No IP literal becomes a TLS identity.

The transaction is durably claimed before Manager recreation. Once claimed:

```text
authorization_consumed=true
replay_allowed=false
```

A private mode-0600 runtime override changes only:

```text
GH_N3W_PRODUCT_PAIRING_ENABLED=true
GH_N3W_NODE_BROKER_HOST=<route-selected current T1 LAN IPv4>
```

The base Compose is not edited.

Docker Compose is invoked only for:

```text
up -d --no-deps --force-recreate manager
```

Broker and Home Assistant container identities/restart counts must remain unchanged.

Post-recreate acceptance requires all of:

```text
MANAGER_RUNNING=true
PAIRING_ENABLED=true
PAIRING_BROKER_LOCATOR_MATCH=true
UDP_47111_LISTENER_COUNT=1
TCP_47112_LISTENER_COUNT=1
GET_127_0_0_1_47112_HEALTHZ=gh.pair.simple-health/1 + ok
PAIRING_SOCKET=/run/greenhouse-manager/pairing.sock
MANAGER_NAMESPACE_BROKER_TLS=PASS
BROKER_CONTAINER_UNCHANGED=true
HOMEASSISTANT_CONTAINER_UNCHANGED=true
```

If Manager recreation has started and post-recreate verification fails, the tool performs one safety rollback to the base Compose Manager configuration and verifies the pairing listeners are closed. This is a rollback of the authorized transition, not a retry of pairing.

A Compose timeout or lost return value is not interpreted as proof that recreation did not occur. Both open-failure rollback and normal close treat final observed state as authority: the tool attempts the factory Manager recreation, removes the runtime override, then requires the final pairing-disabled listeners/TLS/non-target-container invariants. A command error may therefore be recorded while a separately observed safe factory state still closes the transition.

## 6. Setup Secret boundary

This tool does not print, persist in Git, or accept a Setup Secret.

The existing product path remains authoritative:

```text
Board LCD QR
GHN3W2:<hardware_id>:<pairing_id>:<setup_secret>
→ private operator handoff
→ greenhouse-manager-pairing import
→ Manager-owned /run/greenhouse-manager/pairing.sock
```

The existing CLI reads the Setup Secret from stdin. The value must not be supplied as a command-line argument or public evidence.

The future live gate must separately define the operator-side QR/handoff step. This source gate does not treat serial capture as the normal product path.

## 7. Close contract

The same consumed onboarding transaction owns closure. Exact confirmation:

```text
CLOSE FIRST PAIRING WINDOW: YES
```

Two outcomes are supported:

```text
success
abort
```

`success` requires first-pair database evidence before closure:

```text
REGISTRATIONS=1
NODE_ID_LEASES=1
PAIRING_SESSIONS>=1
REGISTRATION_EVENTS>=1
```

This is necessary but not sufficient for final Board runtime acceptance. MQTT/Manager/HA telemetry remains a later live acceptance step.

Closure recreates only Manager from the original base Compose without the override, removes the private runtime override, and requires:

```text
PAIRING_ENABLED=false
NODE_BROKER_HOST=gate-f-unbound.invalid
UDP_47111_LISTENER_COUNT=0
TCP_47112_LISTENER_COUNT=0
MANAGER_NAMESPACE_BROKER_TLS=PASS
BROKER_CONTAINER_UNCHANGED=true
HOMEASSISTANT_CONTAINER_UNCHANGED=true
DATABASE_COUNTS_UNCHANGED_DURING_CLOSE=true
```

A successful transaction after the configured window deadline is classified fail-closed as `CLOSED_FAIL_WINDOW_EXPIRED`.

`abort` exists only to close a claimed/open window safely. It does not convert an incomplete pair into success.

## 8. Persistence and privacy

Private transaction:

```text
/var/lib/n3w-t1-provisioning/FIRST_PAIRING_ONBOARDING.json
```

Private runtime override:

```text
/run/n3w-first-pairing-onboarding/manager-pairing.override.yml
```

The transaction may contain the live peer and Broker locator because it is private target state. Public command output contains only the Broker locator SHA-256.

The runtime override is not persistent across reboot. A reboot therefore does not silently reopen pairing. The installed base Compose remains pairing-disabled.

## 9. No-replay and failure semantics

After the transaction claim:

```text
authorization_consumed=true
replay_allowed=false
```

An ambiguous post-claim result may be inspected but must not be rerun under the same authorization.

This first version intentionally refuses to overwrite an existing transaction record. A future successor/recovery path, if needed after an aborted or failed transaction, must preserve the old record and use a new explicit authorization rather than erasing evidence.

## 10. Regression coverage

New focused tests cover:

- factory Compose must stay pairing-disabled with the invalid placeholder;
- onboarding override must change only the pairing enable and Broker locator contract;
- Manager-only Compose recreation;
- route selection through the exact Manager runtime source;
- rejection of a non-local peer;
- clean first-pair database requirement;
- durable claim occurs before Manager recreation;
- public result does not reveal the live Broker locator;
- failed open performs factory Manager rollback;
- successful close requires approved registration plus committed MQTT credential and N3-W application-key evidence;
- credential generation/key epoch mismatch and incomplete credential state fail closed;
- Compose-return ambiguity is resolved only by final observed factory state;
- successful close returns to the factory pairing-disabled state;
- authorization naming is explicit and bounded.

Dedicated workflow:

```text
.github/workflows/n3w-t1-first-pairing-onboarding-ci.yml
```

## 11. Current gate state

```text
SOURCE_IMPLEMENTATION_CREATED=true
FACTORY_COMPOSE_CHANGED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
PAIRING_EXECUTION=false
MERGE=false

NEXT=EXACT_HEAD_SOURCE_REVIEW_AND_CI
```

## 12. Exact-head review findings repaired before live use

The source-only review found and repaired two blockers before any T1/Board execution:

1. an intermediate helper edit accidentally inserted the exact-success count check recursively inside `_security_state_counts()`; this was detected by exact-head source inspection and moved into `_first_pair_success_evidence()`;
2. the first Manager recreation implementation used successful command return as the oracle for whether rollback was needed. A timeout could have meant the recreate happened but the return was lost. The repaired path marks mutation as started before invoking Compose and always uses observed factory state as the safety oracle.

```text
LIVE_T1_IMPACT_FROM_REVIEW_FINDINGS=false
BOARD_IMPACT_FROM_REVIEW_FINDINGS=false
```
