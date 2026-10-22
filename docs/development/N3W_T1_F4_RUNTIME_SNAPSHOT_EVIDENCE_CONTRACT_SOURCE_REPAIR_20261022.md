# N3W T1 F4/F5 runtime snapshot evidence contract source repair

Date: 2026-10-22

## 0. Gate and safety boundary

~~~text
TASK=N3W_T1_F4_RUNTIME_SNAPSHOT_EVIDENCE_CONTRACT_SOURCE_REPAIR_20261022_01
BASE_MAIN=84cdc4faeb1f5afd5eb5f5df276ac669f9fdf7e0
BRANCH=fix/n3w-t1-f4-runtime-snapshot-evidence-contract-20261022

T1_ACCESS=false
T1_MUTATION=false
T1_REFLASH=false
PRODUCTION_EXECUTION=false
PRODUCTION_RETRY=false
FAILED_RUN_REPLAY=false
MARKER_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

This gate is source-only. It does not alter the terminal production history or
the deployed T1-B.

## 1. Frozen runtime evidence

The already-deployed T1-B was checked read-only after the terminal production
failure. The complete F4 post-reboot verifier returned PASS and independently
proved a real reboot plus the persisted product runtime.

~~~text
FULL_F4_POST_REBOOT_VERIFY=PASS
T1_B_ACTUAL_DEPLOYMENT=PASS
T1_B_RUNTIME_HEALTH=PASS
PRODUCT_RUNTIME_FAILURE_PROVEN=false
SYSTEMD_STATE=running
CRITICAL_JOURNAL_RECORD_COUNT=0
BROKER_RESTART_COUNT=0
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
MANAGER_CURRENT_ESTABLISHED_8883_SOCKET_COUNT=1
HOMEASSISTANT_CURRENT_ESTABLISHED_1883_SOCKET_COUNT=1
~~~

The historical production run remains terminal FAIL. It is not replayed or
rewritten as PASS.

## 2. Confirmed snapshot false FAIL

The independent runtime snapshot returned:

~~~text
STATUS=FAIL
FAILURE_CLASS=VERIFY_FAILED
ERROR_CODE=broker_authenticated_connection_state_invalid
~~~

Exact source-boundary matching corrected an earlier broad substring grep.
Manager had two relevant exact-client Broker events. The first was the valid
authenticated CONNECT event. The second occurred about 124 microseconds later
and was not another authenticated CONNECT line. The current Manager 8883 socket
still existed and the full F4 verifier passed.

The old helper collected all exact-client events and required the final event to
be another authenticated CONNECT line. That made historical event ordering act
as the authority for current connection state and allowed it to fail before the
service-owned current socket probe.

## 3. Confirmed continuity defect

The old snapshot exported `broker_events_sha256`, a digest over the full
matching Broker event history. `require_continuity()` then required the whole
snapshot dictionary to be byte-for-byte equivalent to the baseline.

That couples harmless append-only history to the 90-second current-runtime
continuity contract. A new normal Broker event can therefore produce
`runtime_continuity_changed` even if boot, containers, identities, sockets,
systemd state and current product health are unchanged.

Both defects are one KF because both come from assigning current-state authority
to historical Broker log material.

## 4. KF-128 successor contract

~~~text
KF_128=F4_F5_RUNTIME_SNAPSHOT_EVIDENCE_CONTRACT
ROOT_CAUSE_CONFIDENCE=HIGH
~~~

The repaired contract separates four facts.

1. Historical Broker authentication proof:
   - an exact ClientID connection with the exact expected username must exist;
   - a same exact ClientID connection with a wrong username fails closed;
   - no authenticated historical evidence is evidence-insufficient and cannot PASS;
   - later disconnect, close, duplicate-client or other exact-client log lines do
     not by themselves describe the current connection.

2. Current service-owned socket proof:
   - Manager requires exactly one established service-owned socket to 8883;
   - Home Assistant requires at least one established service-owned socket to 1883;
   - missing Manager/Home Assistant current sockets are explicit verification failures;
   - Manager zero or multiple sockets are explicit verification failures.

3. Current runtime identity and service continuity:
   - container ID + StartedAt remain bound;
   - restart counts remain stable;
   - service identity digest remains stable;
   - current socket fingerprint remains stable.

4. Current host/runtime health:
   - boot/source/control bindings remain stable;
   - systemd stable-state digest remains stable;
   - critical journal digest remains stable;
   - Home Assistant HTTP readiness remains true.

No one signal substitutes for another. A valid current socket cannot replace
missing historical authentication evidence, and historical authentication
cannot replace a missing current socket.

## 5. Snapshot schema /2

The runtime snapshot schema advances from:

~~~text
gh.n3w-t1-runtime-snapshot/1
~~~

to:

~~~text
gh.n3w-t1-runtime-snapshot/2
~~~

Each service authentication record now carries:

~~~text
authenticated=true
endpoint_port
identity_sha256
owned_socket_count
owned_socket_sha256
authenticated_connection_sha256
~~~

`authenticated_connection_sha256` hashes only exact successful authenticated
connection lines for the expected ClientID and username. Other historical
Client events are not treated as current-state transitions.

## 6. 90-second continuity

`require_continuity()` no longer compares the complete snapshot document.
It compares an explicit continuity projection containing only fields that must
remain stable during the observation:

~~~text
schema
boot_id_sha256
source_head
control_manifest_sha256
containers
runtime_service_auth.authenticated
runtime_service_auth.endpoint_port
runtime_service_auth.identity_sha256
runtime_service_auth.owned_socket_count
runtime_service_auth.owned_socket_sha256
systemd_state_sha256
critical_errors_sha256
homeassistant_http_ready
~~~

The historical authentication digest remains valid public evidence, but its
growth is excluded from the continuity equality because historical log growth is
not itself a current runtime state change.

A real reconnect still changes the service-owned socket fingerprint and is
therefore detected.

## 7. Fail-closed behavior

~~~text
NO_AUTHENTICATED_HISTORY=EVIDENCE_INSUFFICIENT
EXACT_CLIENT_WRONG_USERNAME=VERIFY_FAILED
MANAGER_SOCKET_COUNT_0=VERIFY_FAILED
MANAGER_SOCKET_COUNT_GT_1=VERIFY_FAILED
HOMEASSISTANT_SOCKET_COUNT_0=VERIFY_FAILED
INVALID_SOCKET_EVIDENCE=EVIDENCE_INSUFFICIENT
CONTAINER_IDENTITY_CHANGE=VERIFY_FAILED_BY_CONTINUITY
CONTAINER_RESTART=VERIFY_FAILED_BY_CONTINUITY
SOCKET_RECONNECT_OR_REPLACEMENT=VERIFY_FAILED_BY_CONTINUITY
NEW_CRITICAL_JOURNAL_EVENT=VERIFY_FAILED_BY_CONTINUITY
BENIGN_BROKER_HISTORY_GROWTH=ALLOWED
~~~

## 8. Regression matrix

The source/tests cover the required cases:

1. exact authenticated connect only;
2. authenticated connect plus later exact-client event;
3. authenticated history plus valid current owned socket;
4. historical disconnect/close/duplicate-client lines do not replace current socket evidence;
5. current required socket missing;
6. wrong username for exact ClientID;
7. synthetic ClientID suffix does not contaminate exact identity proof;
8. duplicate-client/closing-old history does not become current-state authority;
9. Broker log truncation remains evidence-insufficient;
10. Manager non-unique current socket fails;
11. Home Assistant missing current socket fails;
12. container restart/identity change remains a continuity failure;
13. current socket without authenticated historical proof cannot PASS;
14. valid auth plus later log plus stable current socket can PASS;
15. 90-second observation ignores historical authentication digest growth while
    continuing to reject changes to boot/container/socket/systemd/current-health state.

## 9. PR #642 boundary

PR #642 remains the KF-127 readiness partial-unit repair only.

~~~text
PR642_SCOPE_EXPANSION=false
KF127_REOPEN=false
KF126_REOPEN=false
~~~

KF-128 is based independently on exact main. The changed source regions are
separate in purpose even where the same verifier file is touched.

## 10. Release consequence

If this repair is reviewed and merged, the current exact release becomes
historical because F4/F5 acceptance tool bytes changed. A new exact release and
local exact-release validation are required before any new production attempt.

The prior failed production run remains terminal/no-replay.

## 11. Current gate

~~~text
SOURCE_REPAIR_IMPLEMENTED=true
SOURCE_REVIEW_PENDING=true
CI_PENDING=true
T1_ACCESS=false
T1_MUTATION=false
PRODUCTION_EXECUTION=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F4_RUNTIME_SNAPSHOT_EVIDENCE_CONTRACT_SOURCE_REVIEW_20261022_01
~~~
