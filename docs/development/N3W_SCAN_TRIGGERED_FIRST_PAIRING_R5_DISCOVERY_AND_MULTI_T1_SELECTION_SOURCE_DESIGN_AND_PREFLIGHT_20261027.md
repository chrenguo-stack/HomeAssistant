# N3-W scan-triggered first registration — R5 discovery and multi-T1 selection source design / preflight

Date: 2026-10-27

## 0. Gate

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R5_DISCOVERY_AND_MULTI_T1_SELECTION_20261027_01
BASE_MAIN=1ae096f334b7c0b19800bdec02a2c63d6166ec08
R4_MERGE=1ae096f334b7c0b19800bdec02a2c63d6166ec08
ARCHITECTURE_AUTHORITY=docs/adr/0011-n3w-scan-triggered-first-registration.md
SOURCE_DESIGN_AUTHORITY=docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md

MODE=SOURCE_IMPLEMENTATION_AND_SIMULATED_TEST
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_MUTATION=false
LIVE_RUNTIME_MUTATION=false
MERGE=false
```

R5 implements only the frozen stage:

```text
R5 = scan-triggered discovery + multi-T1 selection
```

R6 TLS bootstrap, Setup Secret transmission, 47110 confirmation, 47112 pairing handoff and SimplePairingClient refactor are explicitly out of scope.

## 1. Reuse boundary

R5 must reuse existing proven contracts instead of creating a parallel discovery protocol.

### T1 side reused unchanged

Already merged from R1:

- `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_registration_discovery.py`
- `RegistrationCandidate`
- `gh.registration.candidate/1`
- `gh.registration.discovery-result/1`
- `gh.n3w.first-registration/1`
- UDP/47111 trusted-product-LAN admission
- `_greenhouse-reg._tcp.local.` mDNS advertisement
- candidate fields: `manager_id`, `system_id`, `system_id_hint`, `host`, `bootstrap_scheme=https`, `bootstrap_port=47110`, `bootstrap_path=/v1/registration/confirm`, `bootstrap_tls_sha256`, `protocol`, `ttl_s=30`, `busy`.

R5 does not modify Manager discovery semantics unless an exact source-contract mismatch is found.

### Node side reused

Reuse:
- R4 `RegistrationPortal` and its RAM-only scan token;
- R4 `scan_trigger_pending` handoff;
- current STA IPv4/netmask helper;
- existing `gh.discovery.query/1` request-id + nonce correlation pattern;
- existing ESP-IDF mDNS query pattern already used by `greenhouse_pairing_client`;
- existing `Esp32ManagerDiscoveryNetwork` UDP multi-response collector;
- existing `Esp32ManagerDiscoveryRandom` random adapter;
- existing product orchestrator `SimpleProductComponent`.

Do not reuse:
- legacy `SimplePairingClient::run_once()->discover_()` as the normal R5 path;
- old `gh.manager.candidate/1` schema;
- old dynamic pairing endpoint discovery;
- RSSI/latency/ID ordering as candidate-selection policy.

## 2. New node component

Add:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/
  n3w_registration_discovery.h
  n3w_registration_discovery.cpp
```

The component owns only candidate discovery and validation.

Candidate model:

```text
RegistrationCandidate
  manager_id
  system_id
  system_id_hint
  host
  bootstrap_tls_sha256
  busy
  bootstrap_port=47110
  bootstrap_path=/v1/registration/confirm
  ttl_s=30
```

Validation is exact and fail-closed:
- exact candidate schema;
- exact registration protocol;
- https only;
- port exactly 47110;
- path exactly /v1/registration/confirm;
- SHA-256 fingerprint exactly 64 lowercase hex;
- ttl exactly 30;
- safe manager/system IDs;
- nonempty short system hint;
- IPv4 endpoint only for V1.

## 3. One scan = one bounded discovery session

R4's first valid `POST /api/v1/register/start` is the trigger.

R5 behavior:

```text
IDLE
  --valid scan start-->
DISCOVERING
  --0 candidates--> ERROR_NO_CANDIDATE
  -->=1 candidates--> WAIT_CONFIRM
```

No discovery executes in IDLE.

One discovery session:
1. query mDNS `_greenhouse-reg._tcp`;
2. validate/collect candidates;
3. only when mDNS yields zero legal candidates, perform UDP/47111 fallback using the same request-id + nonce correlation contract;
4. stop after the bounded session budget;
5. dedupe by exact `manager_id + system_id + host + bootstrap_port`;
6. retain at most 4 healthy candidates;
7. no repeated background loop after completion.

Frozen R5 source budget:
- mDNS timeout: 1500 ms;
- UDP: reuse the existing bounded multi-response collector for at most 3 broadcast attempts, each with its existing 1-second collection window;
- combined mDNS + UDP blocking budget remains below the 5–10 second design ceiling;
- candidate TTL: 30 s.

R5 does not start the 1800-second registration transaction. That begins only after successful R6 bootstrap.

## 4. Candidate selection

Exactly one candidate:
- candidate is displayed on the phone;
- user confirmation is still required;
- no automatic 47110 request occurs in R5.

Multiple candidates:
- phone page displays one button per candidate;
- label is `温室主机 <system_id_hint>`;
- no host/IP/port/fingerprint/manager ID/system ID is shown;
- node does not rank by RSSI, response latency, manager ID or system ID;
- only explicit browser selection sets the selected candidate.

The selected candidate remains node-local RAM state for R6.

## 5. Portal/API extension

Keep all R4 source/token/subnet/rate guards.

`POST /api/v1/register/status` returns only product-safe state, for example:

```json
{
  "schema":"gh.registration.portal-status/1",
  "status":"wait_confirm",
  "candidates":[
    {"id":"c0","label":"温室主机 A1B2"}
  ]
}
```

Candidate IDs are node-local opaque session handles. They are not Manager IDs and are regenerated with the discovery session.

`POST /api/v1/register/confirm`:
- requires current scan token;
- accepts exact `candidate_id`;
- validates the current discovery session;
- validates the discovery session is still bound to the same current pairing ID;
- validates candidate has not expired;
- records selection in RAM;
- returns R5 source state `bootstrap_stage_pending`;
- does not open TLS and does not transmit Setup Secret.

`POST /api/v1/register/retry`:
- requires current scan token;
- clears candidate/selection state;
- starts one new bounded discovery session;
- does not rotate pairing ID;
- does not rotate the QR token solely because discovery failed.

Repeated `/start` during DISCOVERING/WAIT_CONFIRM is idempotent and does not create a second discovery session.

## 6. Concurrency

ESP-IDF HTTP server handlers execute outside the ESPHome main loop.

Therefore:
- HTTP handlers never perform mDNS/UDP discovery directly;
- handlers only enqueue/record bounded commands;
- discovery runs from `SimpleProductComponent::loop()`;
- shared portal status/candidate display data uses an explicit synchronized snapshot;
- no raw pointer/reference to a mutable candidate vector crosses the HTTP/main-loop boundary.

## 7. Failure / expiry behavior

R5 source states:
- IDLE
- DISCOVERING
- WAIT_CONFIRM
- ERROR_NO_CANDIDATE
- SELECTED_PENDING_BOOTSTRAP

Rules:
- zero candidates => recoverable no-candidate state;
- candidate TTL expiry before confirmation => reject selection and require retry;
- Wi-Fi disconnect or QR/IP regeneration clears the discovery session and selection;
- node provisioning/ACK recovery suppresses R5 ordinary discovery;
- no R5 failure renews pairing ID;
- no R5 failure erases Setup Secret.

LCD E01 and full R7 wording are not implemented in R5.

## 8. Security / privacy

Phone/browser never receives:
- Setup Secret;
- hardware ID;
- pairing ID;
- candidate host/IP;
- port;
- TLS fingerprint;
- Manager ID;
- full system ID;
- MQTT material.

Public logs must not emit the bootstrap fingerprint or raw customer IP as product evidence.

Candidate fingerprint remains internal node RAM for R6 pinning.

## 9. Source tests

Add R5 source/host-simulated tests proving:

1. no discovery before valid scan trigger;
2. one valid scan triggers exactly one bounded session;
3. repeated start is idempotent;
4. registration candidate parser rejects wrong schema/protocol/scheme/port/path/fingerprint/ttl;
5. UDP response requires exact request-id + nonce;
6. duplicate candidates within a discovery transport are deduped by manager/system/endpoint;
7. at most 4 candidates retained;
8. zero candidates reaches recoverable no-candidate state;
9. one candidate still requires browser confirmation;
10. multiple candidates never auto-select;
11. phone status contains labels/opaque IDs only and no technical locator/fingerprint;
12. stale/expired candidate cannot be selected;
13. retry starts a new session without pairing-ID renewal;
14. R5 source contains no 47110 HTTP/TLS client, Setup Secret transmission, `esp_tls` bootstrap, or `SimplePairingClient::pair_with_` call;
15. legacy idle `run_once()->discover_()` remains unreachable from ordinary unregistered product flow;
16. R4 pending-ACK recovery remains unchanged.

## 10. CI / closure

Expected CI:
- greenhouse-manager CI / N3-W source contract suite;
- F1.0-RC2 firmware compile;
- Board_D production de-harness compile;
- current-main product source convergence;
- existing relay/recovery regressions.

R5 closure does not claim:
- R6 TLS bootstrap;
- R7 full LCD UX;
- R8 E2E;
- R9 exact artifact;
- R10 physical acceptance.

## 11. Stop conditions

Stop and redesign before source mutation if implementation would require:
- transmitting Setup Secret in R5;
- calling 47110 from R5;
- automatic candidate selection when >1;
- restoring background idle discovery;
- exposing host/fingerprint/IDs to the phone;
- changing T1 registration authorization semantics;
- weakening R1/R3/R4 security or CI boundaries.
