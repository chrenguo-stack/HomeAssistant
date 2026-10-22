# N3W T1 F4/F5 runtime snapshot evidence contract source repair

Date: 2026-10-22

## 0. Gate and safety boundary

~~~text
TASK=N3W_T1_F4_RUNTIME_SNAPSHOT_EVIDENCE_CONTRACT_SOURCE_REPAIR_R2_20261022_01
BASE_MAIN=84cdc4faeb1f5afd5eb5f5df276ac669f9fdf7e0
BRANCH=fix/n3w-t1-f4-runtime-snapshot-evidence-contract-20261022
R1_REVIEW_HEAD=31e19984149b4227edc075ebd264e4ecdde57b6f
R1_REVIEW_COMMENT=6332619236
R1_REVIEW_RESULT=FAIL_R2_REQUIRED
R2_CODE_HEAD=e94ca47d971593e9f16a64ebd49a79b17e9e1ef2

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

1. Broker current-session authentication proof:
   - an exact ClientID connection with the exact expected username must exist;
   - a same exact ClientID connection with a wrong username fails closed;
   - benign exact-client log lines do not change session authentication state;
   - an explicit disconnect, close, duplicate-client old-session close or timeout
     transition after the latest successful CONNECT invalidates current-session
     authentication proof;
   - only a later exact successful authenticated CONNECT restores that proof;
   - no authenticated/current-session evidence is evidence-insufficient and cannot PASS.

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
missing current-session authentication evidence, and a historical authenticated
CONNECT cannot replace a stable current socket. R2 additionally brackets the
Broker lifecycle read with service-owned socket evidence before and after the
log read; socket count and fingerprint must be identical or the snapshot is
evidence-insufficient.

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
therefore detected. R2 also performs an intra-snapshot socket bracket:
socket-before -> Broker lifecycle evidence -> socket-after. The two socket
observations must have identical count and fingerprint before authenticated=true
can be emitted.

## 7. Fail-closed behavior

~~~text
NO_AUTHENTICATED_HISTORY=EVIDENCE_INSUFFICIENT
EXPLICIT_TERMINAL_AFTER_LATEST_AUTH=EVIDENCE_INSUFFICIENT
LATER_EXACT_AUTH_AFTER_TERMINAL=ALLOW_CURRENT_SESSION_PROOF
EXACT_CLIENT_WRONG_USERNAME=VERIFY_FAILED
MANAGER_SOCKET_COUNT_0=VERIFY_FAILED
MANAGER_SOCKET_COUNT_GT_1=VERIFY_FAILED
HOMEASSISTANT_SOCKET_COUNT_0=VERIFY_FAILED
INVALID_SOCKET_EVIDENCE=EVIDENCE_INSUFFICIENT
SOCKET_CHANGED_ACROSS_AUTH_EVIDENCE_READ=EVIDENCE_INSUFFICIENT
CONTAINER_IDENTITY_CHANGE=VERIFY_FAILED_BY_CONTINUITY
CONTAINER_RESTART=VERIFY_FAILED_BY_CONTINUITY
SOCKET_RECONNECT_OR_REPLACEMENT=VERIFY_FAILED_BY_CONTINUITY
NEW_CRITICAL_JOURNAL_EVENT=VERIFY_FAILED_BY_CONTINUITY
BENIGN_BROKER_HISTORY_GROWTH=ALLOWED
~~~

## 8. Regression matrix

The source/tests cover the required cases:

1. exact authenticated connect only;
2. authenticated connect plus benign later exact-client event;
3. authenticated CONNECT plus explicit disconnect/close/timeout with no later CONNECT cannot PASS;
4. authenticated CONNECT plus terminal event plus later exact authenticated CONNECT can PASS;
5. current required socket missing;
6. wrong username for exact ClientID;
7. synthetic ClientID suffix does not contaminate exact identity proof;
8. duplicate-client old-session close invalidates proof until the later exact CONNECT;
9. Broker log coverage truncation remains evidence-insufficient;
10. Manager non-unique current socket fails;
11. Home Assistant missing current socket fails;
12. container restart/identity change remains a continuity failure;
13. current socket without current-session authentication proof cannot PASS;
14. socket count/fingerprint change across the Broker evidence read cannot PASS;
15. valid auth plus benign later log plus stable current socket can PASS;
16. 90-second observation ignores historical authentication digest growth while
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
R1_SOURCE_REVIEW_RESULT=FAIL_R2_REQUIRED
R1_OPEN_SOURCE_BLOCKER_COUNT=1
R2_FINAL_HEAD=170dc15b7be0299da046045cbf5fa054d06affa4
R2_EXACT_HEAD_CI=14/14_PASS
R2_SOURCE_REVIEW_RESULT=FAIL_R3_REQUIRED
R2_OPEN_SOURCE_BLOCKER_COUNT=1
R2_BLOCKER=MOSQUITTO_2_1_2_TERMINAL_LOG_FORMAT_MISMATCH
R3_CODE_HEAD=07159cd750e7817dd7f6df23f47086a69812ebfe
R3_SOURCE_REPAIR_IMPLEMENTED=true
R3_SOURCE_REVIEW_RESULT=CLOSED_PASS_PENDING_EXACT_HEAD_CI
R3_OPEN_SOURCE_BLOCKER_COUNT=0
R3_CI_PENDING=true
T1_ACCESS=false
T1_MUTATION=false
PRODUCTION_EXECUTION=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F4_RUNTIME_SNAPSHOT_EVIDENCE_CONTRACT_SOURCE_REVIEW_R3_20261022_01
~~~


## 12. R1 independent review and R2 closure design

R1 exact-head review was performed against
`31e19984149b4227edc075ebd264e4ecdde57b6f` after 14/14 CI PASS.
The review did not accept CI as proof of the session-correlation contract.

It found one blocker:

~~~text
B1=CURRENT_AUTH_SESSION_CORRELATION_FALSE_PASS
OLD_AUTH_HISTORY_PLUS_NEW_TCP_SOCKET_COULD_PASS=true
SOURCE_REPAIR_R2_REQUIRED=true
~~~

The R2 implementation uses explicit lifecycle ordering rather than restoring the
old arbitrary last-event heuristic:

~~~text
SOCKET_BEFORE
-> BROKER_LIFECYCLE_LOGS_SINCE_SERVICE_STARTED_AT
-> REQUIRE_LATEST_EXPLICIT_LIFECYCLE_STATE_AUTHENTICATED
-> SOCKET_AFTER
-> REQUIRE_SOCKET_COUNT_AND_FINGERPRINT_UNCHANGED
-> EMIT_AUTHENTICATED=true
~~~

Benign log lines are ignored. Explicit session termination invalidates the
current-session authentication proof. A later exact authenticated CONNECT
restores it. The socket bracket prevents a log snapshot from being paired with a
socket that changed while the authentication evidence was read.

R2 adds repository-defined safe error codes:

~~~text
broker_current_session_authentication_evidence_missing
runtime_socket_auth_evidence_unstable
~~~

The prior failed production run remains terminal/no-replay. No T1 access is
required to review this source repair.


## 13. R2 independent review and R3 production-version parser repair

R2 exact-head source review used the production Broker version as an external
source authority instead of assuming older Mosquitto log wording.

Production image binding fixes Mosquitto 2.1.2. The upstream tag and source
authority are:

~~~text
MOSQUITTO_UPSTREAM_TAG=v2.1.2
MOSQUITTO_UPSTREAM_TAG_OBJECT=691eab38b43c16235251bf4a4c83b2b29195ba76
MOSQUITTO_UPSTREAM_COMMIT=99fa50f30e325609394c324c8ff71cfbbe95d8ab
CONNECT_SOURCE=src/handle_connect.c
DISCONNECT_SOURCE=src/loop.c
~~~

The upstream successful authenticated connection format remains compatible with
the existing exact CONNECT parser:

~~~text
New client connected from <addr>:<port> as <client-id> (p5, cX, kY, u'<username>').
~~~

The production disconnect format is different from the older test fixtures.
Mosquitto 2.1.2 emits:

~~~text
Client <client-id> [<addr>:<port>] disconnected.
Client <client-id> [<addr>:<port>] disconnected: malformed packet.
Client <client-id> [<addr>:<port>] disconnected: protocol error.
Client <client-id> [<addr>:<port>] disconnected: connection closed by client.
Client <client-id> [<addr>:<port>] disconnected: exceeded timeout.
Client <client-id> [<addr>:<port>] disconnected: session taken over.
Client <client-id> [<addr>:<port>] disconnected: <other reason>.
~~~

R2 did not match this bracketed-address form, so an actual production terminal
record could be ignored and an older authenticated CONNECT could remain the
state-machine authority. Green CI did not close this because its fixtures used
older log strings.

R3 keeps the R2 state model and changes only the terminal-record recognizer and
its focused tests:

~~~text
PRODUCTION_2_1_2_TERMINAL_RECORD=INVALIDATE_CURRENT_SESSION_AUTH
LEGACY_TERMINAL_RECORD=INVALIDATE_CURRENT_SESSION_AUTH
BENIGN_EXACT_CLIENT_EVENT=NO_STATE_CHANGE
LATER_EXACT_AUTHENTICATED_CONNECT=RESTORE_CURRENT_SESSION_AUTH
SOCKET_BRACKET_UNCHANGED=true
~~~

R3 code head before documentation alignment:
`77bd258fbab5403327921fb388221db4a24943c1`.

No runtime/T1 evidence collection is required for this parser closure because
the production-version log grammar is bound directly to the exact upstream
Mosquitto 2.1.2 source.


## 14. R3 independent source review

R3 independent review was performed after the production-version parser repair
and the regex escaping follow-up.

~~~text
R3_REVIEW_HEAD=07159cd750e7817dd7f6df23f47086a69812ebfe
R3_SOURCE_REVIEW_RESULT=CLOSED_PASS_PENDING_EXACT_HEAD_CI
R3_OPEN_SOURCE_BLOCKER_COUNT=0
~~~

The review independently checked:

1. production Broker config enables `connection_messages true`;
2. production logging includes `log_type notice`, which is the level used by
   Mosquitto connection lifecycle messages;
3. upstream Mosquitto `v2.1.2` successful CONNECT grammar matches the exact
   ClientID + username parser;
4. upstream `src/loop.c` graceful and reasoned disconnect records use the
   bracketed-address grammar now matched by R3;
5. synthetic ClientID suffixes do not match the exact lifecycle identity;
6. benign exact-client lines do not change authentication state;
7. every recognized terminal record after the latest authenticated CONNECT
   invalidates current-session authentication proof;
8. a later exact authenticated CONNECT restores that proof;
9. the R2 socket-before/log/socket-after bracket remains required and stable;
10. wrong exact-client username remains fail-closed and missing current-session
    proof remains evidence-insufficient;
11. Manager exact-one 8883 and Home Assistant at-least-one 1883 contracts remain
    unchanged;
12. historical authentication digest remains excluded from the 90-second
    continuity equality while current socket identity remains included.

No new false-PASS path was found within the KF-128 repair scope.

Final source closure is still conditional on the exact-head GitHub CI result.
