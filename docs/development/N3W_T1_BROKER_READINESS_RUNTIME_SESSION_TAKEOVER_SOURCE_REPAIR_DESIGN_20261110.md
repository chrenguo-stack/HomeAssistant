# N3-W T1 Broker readiness runtime-session-takeover source repair design

Date: 2026-11-10
Gate: BROKER_READINESS_RUNTIME_SESSION_TAKEOVER_SOURCE_REPAIR_DESIGN
Mode: source/design only; no T1 mutation; no board access; no merge

~~~text
SOURCE_REPAIR_DESIGN_RESULT=CLOSED_PASS
SOURCE_REPAIR_IMPLEMENTATION=NOT_EXECUTED
LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false

STARTUP_READINESS_CONTRACT=PRE_APPLICATION_ONLY_EXACT_PRODUCTION_SERVICE_IDENTITY
RUNTIME_HEALTH_CONTRACT=NONINVASIVE_EXISTING_SESSION_EVIDENCE
TOTAL_EXECUTION_CALL_SITE_COUNT=8
STARTUP_CALL_SITE_COUNT=5
RUNTIME_CALL_SITE_COUNT=3
RUNTIME_PHASE_COUNT=2
DYNSEC_IDENTITY_BINDING_PRESERVED=true
ALTERNATE_PROBE_CLIENT_ID=false
~~~

## 1. Fresh rebind

~~~text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
PR=800
PR_STATE=OPEN_DRAFT_UNMERGED
CANDIDATE_REF=feat/n3w-ha-usb-r7a-prepare-pipeline-20261107
FRESH_REBIND_HEAD_BEFORE_DESIGN_ARCHIVE=188e2885bf6cc1944db21aa4fc1f190271715582

READINESS_HELPER_BLOB=1361ae0f82ce8cc08be00efa565258954f03387a
R2B_BLOB=819db4767cce9dd1aeedeb8fe2500f2c0fd83b91
R2A_BLOB=e4c04df952ae73fae7995eb6e033b85b5ca2a260
F4_ACTIVATION_BLOB=08889200fe9663d223016a3cb3e1b4af0a9ffcd2
GENERIC_SERVICES_UNIT_BLOB=ee7c4151e79368e6daca5d6bd1359a846397fc95
F4_SERVICES_UNIT_BLOB=3485b6c2f9341fda2fcbd2c82c83077ad78cf42c
CLEAN_REFERENCE_SERVICES_UNIT_BLOB=8f614a57e4567ff0dba3cd1f36213c5243e2d1fb
READINESS_TEST_BLOB=fb65a805fd88e6a3e210d51a30fbf50271b33b39
R2B_TEST_BLOB=9e6f762d00a87b33c52714afca6640d2fa7bf255
~~~

All source/test/unit blobs above are identical between fresh main and the candidate branch. The current defect therefore predates the 2026-11-10 documentation handoff and is not new PR #800 source drift.

## 2. Root cause and non-negotiable boundary

The authenticated-readiness helper performs a real MQTT v5 CONNECT. It reads the production Home Assistant metadata and uses the exact production username, password and client ID. The helper is therefore a valid pre-application credential probe, but it is not a read-only runtime health probe.

When Home Assistant is already connected with the same client ID, a second successful CONNECT causes MQTT session takeover. S2G directly observed the sequence: live Home Assistant session -> session taken over -> short readiness session -> readiness disconnect -> Home Assistant reconnect.

The earlier idea of using an arbitrary alternate probe client ID is rejected. The DynSec service-identity plan creates Home Assistant with the fixed client ID gh-homeassistant-greenhouse and createClient binds that exact client ID to the service principal. Existing isolated tests also require a wrong client ID to be rejected.

~~~text
READINESS_HELPER_ROLE=PRE_APPLICATION_STARTUP_CREDENTIAL_PROBE
READINESS_HELPER_RUNTIME_USE=FORBIDDEN
RUNTIME_PROBE_MUST_NOT_READ_PASSWORD=true
RUNTIME_PROBE_MUST_NOT_OPEN_MQTT_CONNECTION=true
RUNTIME_PROBE_MUST_NOT_SEND_MQTT_CONNECT=true
~~~

## 3. Complete execution call-site classification

Install-map references, absent-file inventory references and documentation mentions are not counted as execution call sites.

| # | File / location | Phase | Classification |
|---|---|---|---|
| 1 | tools/n3w_t1_clean_reference_r2a.py direct readiness call after Broker start and before services start | pre-application | KEEP |
| 2 | tools/n3w_t1_f4_activation_host.py direct readiness call after Broker start and before services start | pre-application | KEEP |
| 3 | infra/n3w-t1/systemd/n3wfc4-services-activation.service ExecStartPre | pre-application | KEEP |
| 4 | infra/n3w-t1/f4/n3wfc4-services-activation.service ExecStartPre | pre-application | KEEP |
| 5 | infra/n3w-t1/clean-reference/n3wfc4-services-activation.service ExecStartPre | pre-application | KEEP |
| 6 | tools/n3w_t1_clean_reference_r2b.py _pre_reboot_state() | runtime / pre-reboot | REPAIR |
| 7 | tools/n3w_t1_clean_reference_r2b.py _wait_post_reboot() | runtime / post-reboot convergence | REPAIR |
| 8 | tools/n3w_t1_clean_reference_r2b.py verify() final post-reboot acceptance | runtime / post-reboot acceptance | REPAIR |

~~~text
TOTAL_EXECUTION_CALL_SITE_COUNT=8
STARTUP_CALL_SITE_COUNT=5
RUNTIME_CALL_SITE_COUNT=3
RUNTIME_PHASE_COUNT=2
~~~

This independently refines the handoff wording. The handoff correctly identified two unsafe runtime phases, but the post-reboot phase contains two literal helper invocations. A repair that removes only the final verify() call would still leave session takeover inside _wait_post_reboot().

## 4. Frozen startup readiness contract

The existing helper behavior is retained.

It must continue to prove, before Manager/Home Assistant start:

1. exact loopback endpoint 127.0.0.1:1883;
2. MQTT v5;
3. exact production service username;
4. exact production service client ID;
5. exact production service password;
6. successful CONNACK;
7. bounded retry/timeout.

No alternate client-ID derivation is allowed. No DynSec service identity is added for this repair.

Implementation regression must explicitly assert that wait_for_authenticated_broker passes metadata client_id through unchanged. This protects against reintroducing the superseded alternate-client-ID proposal.

## 5. Frozen non-invasive runtime health contract

Runtime/post-start checks must prove the already-existing Home Assistant session without creating a new MQTT session.

A runtime health sample is READY only when all of the following are true in one stable observation window:

1. identity.json and mqtt-bootstrap.json agree on Home Assistant username and client_id; no password value is read;
2. the Home Assistant container owns at least one ESTABLISHED TCP socket whose remote port is 1883;
3. Broker logs since the current Broker container start prove the current state of the exact Home Assistant client ID is authenticated by the exact expected username;
4. Home Assistant GET /api/ returns 200 or 401;
5. the Broker and Home Assistant container identities/start times/restart counts used by the observation remain unchanged across the sample;
6. the Home Assistant established socket is still present after Broker-log and HTTP evidence are collected.

The socket evidence must be container-local ownership evidence, using the already-proven /proc socket/inode method from the clean-reference observer/F4 verifier family. A host-wide 1883 connection count is not sufficient.

The Broker event state machine must preserve the already-live-revalidated KF-128 semantics for Mosquitto 2.1.2:

- exact successful CONNECT for expected client ID + username -> current authenticated;
- a connection event for the same client ID with a different username -> fail closed;
- disconnect, closed connection, old-session close/session takeover, or timeout after the latest successful CONNECT -> current authentication false;
- a later exact successful CONNECT restores current authentication;
- log coverage at the configured tail limit is evidence-insufficient and fails closed.

~~~text
HOMEASSISTANT_SOCKET_READY=COUNT_GE_1
HOMEASSISTANT_HTTP_READY=200_OR_401
BROKER_LOG_LIMIT=10000
PASSWORD_READ=false
NEW_MQTT_CONNECTION=false
MQTT_CONNECT_PACKET_SENT=false
~~~

## 6. Retry semantics

_pre_reboot_state() and final verify() are strict acceptance points: runtime health must be READY or the operation stops.

_wait_post_reboot() is a convergence loop. Only bounded not-yet-ready conditions may return WAIT and retry:

- Home Assistant established socket count is zero;
- exact current-auth event has not yet converged;
- Home Assistant HTTP is not yet ready.

The following are terminal/fail-closed and must not be converted into retry noise:

- identity.json / mqtt-bootstrap.json username or client-ID mismatch;
- malformed identity metadata;
- same client ID authenticated with unexpected username;
- Broker log coverage insufficient/truncated;
- invalid socket evidence;
- container identity/start/restart instability inside one sample;
- unexpected service/container set.

## 7. Implementation shape

The repair should be self-contained in tools/n3w_t1_clean_reference_r2b.py because its exact R2B package intentionally contains one executable file only. Do not add a runtime dependency on the clean-reference observer or F4 verifier.

Reuse their proven semantics by copying the minimum required socket and Broker-event logic into R2B, not by refactoring the already-live-revalidated verifier stack during this repair.

Required source delta:

1. add private identity metadata readers that compare identity.json and mqtt-bootstrap.json without reading the password file;
2. add container-local established-socket evidence for Home Assistant -> 1883;
3. add exact Broker current-auth state parsing using the KF-128/Mosquitto-2.1.2 terminal-event rules;
4. add a stable before/log+HTTP/after observation sandwich;
5. replace all three R2B runtime calls to _broker_readiness();
6. keep _ha_readiness() only if it is used as the HTTP portion of the passive oracle, or fold it into the new passive function;
7. keep the startup helper source and all five legitimate startup call sites unchanged.

Backward-compatible R2B report fields may retain broker_authenticated_readiness=true, but the repaired R2B report must add an explicit proof-method marker so it cannot be interpreted as a new active CONNECT:

~~~text
broker_authenticated_readiness=true
broker_authenticated_readiness_evidence=PASSIVE_EXISTING_HA_SESSION
runtime_probe_opened_mqtt_connection=false
homeassistant_broker_current_authenticated=true
homeassistant_mqtt_socket_count=<observed_count>
homeassistant_http_status=<200_or_401>
~~~

No R2B schema bump is required for these additive evidence fields; old historical transactions are not to be replayed.

## 8. Historical clean-reference authority preservation

Historical R2B evidence remains immutable:

~~~text
HISTORICAL_R2B_CONTROL_HEAD=e15c64ac8f0f5f482a6c8538072031734002a559
HISTORICAL_R2B_SOURCE_BLOB=819db4767cce9dd1aeedeb8fe2500f2c0fd83b91
HISTORICAL_R2B_REBIND=false
R3_REFERENCE_REBIND=false
PAIRING_BRIDGE_REFERENCE_REBIND=false
~~~

The repaired current R2B source is a successor control implementation. It must not rewrite the 2026-11-01 R2 closure documents, R3 normalized reference, R3 observer constants or pairing-readiness bridge constants.

Two historical CI workflows currently prove R2B authority by diffing the current checkout against the historical R2B head. That assertion becomes invalid once a legitimate successor R2B source exists. The repair may change only those CI assertions so they verify the pinned historical blob at HISTORICAL_R2B_CONTROL_HEAD directly, rather than requiring today's R2B source to remain byte-identical forever.

This preserves historical evidence without binding future source to a known defect.

## 9. Repair file allowlist

Product/source/test/CI implementation is limited to:

~~~text
tools/n3w_t1_clean_reference_r2b.py
tests/tools/test_n3w_t1_clean_reference_r2b.py
tests/tools/test_n3w_t1_broker_authenticated_readiness.py
.github/workflows/n3w-t1-clean-reference-r3-observer-ci.yml
.github/workflows/n3w-t1-clean-reference-pairing-readiness-bridge-ci.yml
~~~

Explicitly outside the source-repair allowlist:

~~~text
tools/n3w_t1_broker_authenticated_readiness.py
tools/n3w_t1_clean_reference_r2a.py
tools/n3w_t1_f4_activation_host.py
infra/n3w-t1/systemd/n3wfc4-services-activation.service
infra/n3w-t1/f4/n3wfc4-services-activation.service
infra/n3w-t1/clean-reference/n3wfc4-services-activation.service
host/greenhouse-manager/src/greenhouse_manager/runtime/service_identity_plan.py
host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_api.py
tools/n3w_t1_clean_reference_observer.py
tools/n3w_t1_f4_reboot_verify.py
~~~

If implementation proves that one of these frozen files must change, stop and reopen design scope rather than expanding silently.

## 10. Regression test matrix

The source-repair implementation must cover at least:

1. startup helper uses metadata client_id exactly, with no derived alternate ID;
2. valid pre-application startup readiness remains PASS;
3. wrong/alternate client ID remains rejected by the existing DynSec contract;
4. R2B executable source contains no runtime invocation of n3w-t1-broker-authenticated-readiness;
5. pre-reboot passive runtime health PASS with matching identities, socket >=1, current auth and HTTP 401;
6. HTTP 200 also passes;
7. socket count 0 is not READY;
8. _wait_post_reboot() treats socket/auth/HTTP non-convergence as bounded WAIT and later READY as success;
9. final acceptance fails if socket remains absent;
10. successful auth event followed by Mosquitto 2.1.2 disconnect/session-taken-over event is not current-authenticated;
11. a later exact reconnect restores current-authenticated;
12. same client ID with wrong username fails closed;
13. Broker log tail coverage at the limit fails closed;
14. malformed identity/socket evidence fails closed;
15. identity.json and mqtt-bootstrap.json mismatch fails closed without reading password;
16. Broker/HA container restart or identity drift inside the sample fails closed;
17. static/monkeypatch proof that passive runtime health opens no MQTT socket and sends no CONNECT;
18. exact single-file R2B package build/independent validation still passes;
19. historical R3/bridge workflows prove the pinned old R2B blob without rebinding historical references.

## 11. CI plan

No workflow dispatch is authorized by this design gate.

When implementation is separately entered, expected automatic CI is:

~~~text
N3W T1 Clean Reference R2B reboot CI
N3W T1 deployment gate CI
N3W T1 Clean Reference R3 observer CI
N3W T1 Clean Reference pairing readiness bridge CI
~~~

The implementation must not claim PASS until all triggered jobs reach terminal success. Existing project polling policy remains three checks maximum before returning the run link/status.

## 12. Security and failure properties

The repaired runtime oracle has strictly less authority than the startup credential probe:

- no password material is required;
- no production MQTT authentication attempt occurs;
- no new client session can displace Home Assistant;
- no Broker/DynSec state changes;
- no container/service restart;
- no T1 live mutation;
- no board access.

The repair therefore removes the observed measurement side effect without weakening the DynSec client-ID binding or the startup credential proof.

## 13. Gate closure

~~~text
STARTUP_READINESS_CONTRACT=PRE_APPLICATION_ONLY_EXACT_PRODUCTION_SERVICE_IDENTITY
RUNTIME_HEALTH_CONTRACT=IDENTITY_EQUALITY+ESTABLISHED_HA_1883_SOCKET+EXACT_BROKER_CURRENT_AUTH+HA_HTTP+STABLE_SANDWICH
TOTAL_EXECUTION_CALL_SITE_COUNT=8
STARTUP_CALL_SITE_COUNT=5
RUNTIME_CALL_SITE_COUNT=3
RUNTIME_PHASE_COUNT=2
REPAIR_FILE_ALLOWLIST_COUNT=5
DYNSEC_IDENTITY_BINDING_PRESERVED=true
SOURCE_REPAIR_DESIGN_RESULT=CLOSED_PASS
SOURCE_REPAIR_IMPLEMENTATION=NOT_EXECUTED

LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false

NEXT_ROUTE=CORE_UPDATER_DEPLOYED_ASSET_INTEGRITY_REPAIR
STOP=true
~~~

This gate closes only the implementation-ready design. It does not claim that KF-148 source code has already been repaired or validated.
