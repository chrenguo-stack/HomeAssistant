# N3W Scan-Triggered First Pairing R8 — Full Simulated E2E + Safety Source Design and Preflight

Date: 2026-10-28

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R8_FULL_SIMULATED_E2E_SAFETY_SOURCE_DESIGN_AND_PREFLIGHT_20261028_01`

## 1. Gate scope

This gate is design / preflight only.

Allowed:
- fresh repository / PR rebind;
- exact-source read-only review;
- simulated E2E architecture design;
- regression/safety matrix design;
- CI design;
- docs-only GitHub archive.

Not allowed:
- production source mutation;
- T1 access or mutation;
- board access or flashing;
- live runtime mutation;
- production service start;
- secret transport to a real T1;
- physical acceptance;
- merge.

R8 is the frozen stage:

```text
R8 = full simulated end-to-end + regression / safety
```

Physical acceptance remains R10.

## 2. Fresh authority rebind

Repository:

`chrenguo-stack/HomeAssistant`

Repository main remains exactly:

`2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`

Fresh compare:
- status: identical
- ahead: 0
- behind: 0

R7 exact product-source authority:

`aee4966b39140a36a9b259a643c138e9f26d0c6d`

R7 source implementation:
- PR #702
- open
- draft
- unmerged

R7 docs-only closure:
- PR #703
- head `6ee56d967a8f68a541e0fa6d041b7c92e51e9cc7`

R8 product-source authority remains the R7 exact source head
`aee4966b39140a36a9b259a643c138e9f26d0c6d`.

The R7 closure commit is documentation-only and does not redefine product-source authority.

## 3. Frozen upstream requirements

Primary authorities:
- `docs/adr/0011-n3w-scan-triggered-first-registration.md`
- `docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md`
- R1-R7 exact source closures

The frozen end-to-end simulated-browser requirement is:

```text
1. phone-like client opens node page
2. starts scan session
3. receives one/multiple T1 candidates
4. confirms
5. proves T1 47112 transition CLOSED -> OPEN -> CLOSED
6. proves Manager COMMIT
7. proves browser never handles Setup Secret
```

Frozen system invariants remain:
- idle unregistered node performs no T1 discovery;
- 47110 is always-on low-privilege bootstrap;
- 47111 is always-on low-privilege discovery;
- 47112 is privileged and closed while idle;
- 47112 opens only for one exact first-registration transaction;
- V1 allows one active first-registration transaction;
- Manager COMMIT or canonical deadline are the only normal-uptime close conditions;
- Manager restart is a separate fail-closed process boundary;
- Setup Secret never enters the phone/browser surface;
- final success remains bound to durable Manager COMMIT;
- no manual secret copy.

## 4. R8 proof boundary

R8 is a **composition/protocol simulation**, not a physical-firmware acceptance.

R8 may prove:
- browser/public projection semantics;
- scan/selection/confirmation ordering;
- real Manager discovery/bootstrap/transaction/ledger behavior;
- real Manager 47112 pairing endpoint behavior;
- real pairing HMAC/HKDF/encrypted-bundle protocol behavior;
- real Manager credential/application-key/peer-trust durable COMMIT;
- real dynamic 47112 listener lifecycle in the host test process;
- pending-ACK Manager-side status recovery;
- cross-component safety invariants.

R8 does **not** prove:
- ESP32-C6 physical radio behavior;
- real ESP-IDF TLS socket timing;
- real ST7920 LCD electrical/visual behavior;
- physical QR camera readability;
- actual T1 host firewall/network namespace behavior;
- real customer LAN routing;
- exact release artifact reproducibility.

Those remain R9/R10 responsibilities.

## 5. Critical anti-false-PASS rule

R8 must not use a Python TLS client to claim that the ESP32-C6 R6 TLS transport was physically or byte-for-byte validated.

R6 already proves by exact source contract:
- exact selected leaf SHA-256 pin is checked;
- Setup Secret request bytes are not emitted before successful pin verification;
- pin mismatch fails closed;
- no redirect/fallback path exists.

R8 re-runs those R6 contracts unchanged.

R9 binds the exact firmware artifact.

R10 performs physical/network acceptance.

Therefore:

```text
R8_MANAGER_E2E=true
R8_PROTOCOL_E2E=true
R8_BROWSER_FLOW_SIMULATION=true
R8_REAL_47112_LISTENER_LIFECYCLE=true

R8_REAL_ESP32_TLS_EXECUTION=false
R8_PHYSICAL_LCD=false
R8_PHYSICAL_T1=false
```

## 6. Existing reusable production components

R8 must reuse real product code wherever it matters to Manager correctness.

### 6.1 Trusted-LAN / discovery

Reuse:
- `TrustedProductLanState`
- `build_registration_udp_response`
- `RegistrationCandidate`
- exact R1 schemas and admission rules

The simulated source IP is a documentation-safe test address such as:

`192.0.2.44`

with a simulated trusted product subnet:

`192.0.2.0/24`

No real customer subnet enters evidence.

### 6.2 47110 bootstrap

Reuse real:
- `RegistrationBootstrapApp`
- `FirstRegistrationTransactionService`
- `FirstRegistrationIntentStore`
- first-registration ledger
- exact busy/terminal/status semantics

The R8 node-side simulation invokes the real bootstrap application in-process with the exact synthetic source IP.

This tests the actual Manager application boundary without pretending the Python test is the firmware TLS stack.

### 6.3 Dynamic 47112 window

Reuse real:
- `DynamicPairingWindowController`
- `open_first_registration()`
- real first-registration callback/close behavior
- real `N3wSimplifiedProductPairingWorker`

The controller already exposes injectable:
- `route_resolver`
- `composition_factory`
- `worker_factory`
- monotonic/wall clocks

No new production test seam is required.

### 6.4 Pairing composition

Reuse real:
- `build_simplified_product_pairing_composition`
- `SimplifiedPairingEndpointApp`
- `SimplifiedPairingCoordinator`
- `SimplifiedProvisioningStager`
- registration SQLite state
- credential lifecycle store
- application-key lifecycle
- system peer-trust store
- exact first-registration ledger hooks

### 6.5 Pairing cryptography

The node-like simulator reuses existing protocol helpers to:
- verify Manager Setup-Secret HMAC proof;
- build node HMAC proof;
- derive HKDF bootstrap key;
- decrypt the encrypted credential bundle;
- submit the exact delivery digest ACK.

No alternate pairing protocol may be implemented.

## 7. Test-only DynSec transport

The real product composition normally uses the MQTT Dynamic Security provisioner.

R8 must not contact a real Broker.

Use the same style already proven by
`test_n3w_first_registration_reconciliation.py`:

```text
FakeDynsecTransport
-> real DynsecProvisioner
-> real create/list/get/delete command semantics
```

The fake transport must model:
- createRole;
- createClient;
- listClients;
- listRoles;
- getClient;
- getRole;
- deleteClient;
- deleteRole.

It must preserve exact client/role documents used by the real commit oracle.

A fake method that simply returns “committed=true” is forbidden.

This ensures Manager COMMIT still traverses the real cross-store oracle.

## 8. Actual 47112 listener proof

R8 must prove 47112 exposure with a real host-process TCP listener.

Use a free loopback test port assigned as the configured pairing HTTP port.

The production dynamic controller remains CLOSED before bootstrap. No product pairing composition exists, so the test port must reject a connection.

After a valid 47110 first-registration bootstrap:
- the real dynamic controller constructs the first-registration composition;
- the real pairing HTTP server binds/serves the configured test port;
- the test port must accept TCP connections.

After durable Manager COMMIT:
- the completion callback closes the dynamic window;
- the worker/composition closes the pairing HTTP server;
- the test port must again reject connections.

Frozen proof:

```text
before confirm: 47112-equivalent test port CLOSED
after accepted 47110: OPEN
after durable Manager COMMIT: CLOSED
```

The loopback socket is only a harness locator.

It is **not** treated as a product-authorized source.

All first-registration application calls still use the exact synthetic trusted-product source IP.

## 9. Why the 47112 product requests are invoked in-process

The identity-bound pairing endpoint requires the exact accepted source IP.

A single-host CI process cannot honestly originate a normal TCP request whose peer appears as the synthetic product-LAN address without introducing network namespace/interface mutation.

Therefore:
- TCP probing is used only to prove listener lifecycle;
- real pairing requests call the real `SimplifiedPairingEndpointApp.handle()` in-process with the exact synthetic accepted source IP.

This is an explicit simulation boundary, not hidden approximation.

R8 must not claim this proves host firewall rules or real network routing.

Those are covered by existing host/source contracts and later physical acceptance.

## 10. Test harness roles

R8 should introduce test-only helper roles.

Recommended test file:

`host/greenhouse-manager/tests/runtime/test_n3w_scan_triggered_registration_r8_e2e.py`

Optional helper, if needed:

`host/greenhouse-manager/tests/runtime/n3w_r8_e2e_harness.py`

No helper may be installed into production package code.

### 10.1 PhoneLikeBrowser

Owns only browser-visible material:
- current scan token;
- redacted node label;
- opaque candidate IDs;
- product-safe candidate labels;
- browser status strings.

It must never receive:
- Setup Secret;
- pairing ID;
- full hardware ID;
- candidate host/IP;
- bootstrap port;
- TLS fingerprint;
- Manager ID;
- full system ID;
- MQTT credentials;
- application key;
- system peer key.

It records every browser-visible request/response payload for final privacy assertions.

### 10.2 SimulatedNodeRegistrationClient

Owns node-private material:
- full hardware ID;
- pairing ID;
- Setup Secret;
- full selected `RegistrationCandidate`;
- TLS fingerprint;
- 47110/47112 target data;
- decrypted credential bundle.

It is test-only.

It may:
- create the exact discovery query;
- consume real Manager discovery result;
- project safe candidate IDs/labels to PhoneLikeBrowser;
- issue real bootstrap app calls;
- issue real pairing endpoint calls;
- perform existing pairing crypto.

It may **not**:
- directly insert/modify first-registration ledger rows;
- directly approve registration;
- directly activate credentials;
- directly stage/activate application keys;
- directly mark Manager COMMIT;
- directly force dynamic-window state.

Those mutations must occur only through real product Manager APIs.

### 10.3 ManagerHarness

Owns:
- real `RegistrationRegistry`;
- real `FirstRegistrationTransactionService`;
- real `DynamicPairingWindowController`;
- real product pairing composition;
- real credential/application-key/peer-trust stores;
- real `DynsecProvisioner` over test transport.

The composition factory may capture the created composition for test observability.

Capture is read/drive access to the real endpoint, not alternate authority.

## 11. Browser source binding

The Python browser simulator does not execute ESP-IDF `httpd`.

Therefore R8 must also add a source-safety contract against the exact firmware portal source.

Recommended file:

`tests/n3w_registration/test_scan_triggered_first_pairing_r8_safety_contract.py`

It must prove the actual C++ browser page still:
- reads only `#t=<scan token>`;
- calls `history.replaceState` to remove the fragment from the visible URL;
- POSTs only `gh.registration.portal-action/1`;
- uses:
  - `/api/v1/register/start`
  - `/api/v1/register/status`
  - `/api/v1/register/confirm`
  - `/api/v1/register/retry`
- sends `candidate_id` on confirm;
- does not contain `setup_secret`;
- does not contain pairing ID/full hardware ID/fingerprint/MQTT material fields;
- renders only opaque candidate ID + product-safe label data supplied by the node;
- does not directly call 47110 or 47112.

This binds the simulated phone flow to the actual firmware portal contract without introducing a parallel production implementation.

## 12. R5 confirmation wording resolution

ADR-0011 describes user confirmation conceptually as “确认联机注册”.

The later stage-specific R5 design freezes:
- one button per candidate;
- explicit browser selection is mandatory;
- clicking the candidate is the confirmation action;
- no automatic selection.

Current implementation follows that R5 contract.

Therefore R8 does **not** introduce a second confirmation button.

Frozen interpretation:

```text
EXPLICIT_CANDIDATE_BUTTON_CLICK = USER_CONFIRMATION
AUTO_SELECT=false
SECOND_CONFIRM_BUTTON_REQUIRED=false
```

A future UX wording preference may be handled separately, but it is not an R8 safety blocker.

## 13. Mandatory normal-flow E2E

R8 must include one complete normal-flow test with the following sequence.

### Step 0 — idle

Assert:
- phone has not started a scan;
- no first-registration ledger ACTIVE row exists;
- dynamic controller state is CLOSED;
- 47112-equivalent test port is closed;
- no pairing composition exists.

### Step 1 — phone opens node page

Phone receives only:
- node-local registration page semantics;
- scan token from the QR fragment.

Assert:
- opening page alone creates no Manager transaction;
- no discovery call has run;
- 47112 remains closed.

### Step 2 — valid scan start

Phone sends the exact portal-action shape.

The simulated node runs one discovery session using the real Manager discovery response builder.

Assert:
- discovery runs once;
- browser gets only redacted node label + opaque candidate ID + safe label;
- no secret/locator is exposed;
- 47112 remains closed.

### Step 3 — explicit candidate confirmation

Phone explicitly selects one candidate.

The simulated node:
- resolves opaque ID to its private full candidate;
- builds the exact 47110 confirm request;
- includes Setup Secret only in the private node->Manager request;
- calls the real `RegistrationBootstrapApp`.

Assert:
- browser-visible payload contains no Setup Secret;
- durable first-registration ACTIVE row exists before accepted result is observed;
- one exact intent is active;
- dynamic controller becomes OPEN;
- 47112-equivalent TCP port becomes reachable;
- canonical deadline is exactly 1800 seconds from transaction open.

### Step 4 — HELLO

Node sends real:
`gh.pair.hello/1`

through the real `SimplifiedPairingEndpointApp`.

Assert:
- accepted source IP/hardware/pairing binding is exact;
- ledger phase advances to HELLO_OBSERVED;
- Setup Secret is imported from the first-registration intent, not browser input.

### Step 5 — BEGIN

Node sends real:
`gh.pair.simple-begin/1`

Assert:
- Manager HMAC proof verifies with the node-owned Setup Secret;
- returned expiry does not exceed the canonical first-registration deadline.

### Step 6 — ESTABLISH

Node builds the real node HMAC proof and submits
`gh.pair.simple-establish/1`.

Assert:
- encrypted credential bundle is returned;
- node decrypts it with the real HKDF-derived bootstrap key;
- bundle schema is exact;
- node ID/system ID/credential material are internally consistent;
- ledger is BUNDLE_STAGED before encrypted bundle success is accepted.

### Step 7 — final ACK

Node submits:
`gh.pair.simple-ack/1`
with exact delivery digest.

Assert before treating response as success:
- pairing endpoint response state is CONSUMED;
- durable first-registration ledger is COMMITTED;
- registration is APPROVED;
- node lease is ACTIVE;
- credential lifecycle generation 1 is ACTIVE;
- application key epoch is ACTIVE/resolvable;
- DynSec exact client/role exist;
- system peer-trust baseline remains valid.

### Step 8 — close

Boundedly wait for the real first-registration completion callback.

Assert:
- dynamic controller reaches CLOSED;
- close reason is committed;
- 47112-equivalent TCP port is closed;
- old active intent is consumed/cleared;
- no second transaction was created.

### Step 9 — privacy

Serialize every browser-visible object collected during Steps 1–8.

Assert it contains none of:
- Setup Secret value;
- pairing ID;
- full hardware ID;
- candidate host;
- bootstrap TLS fingerprint;
- Manager ID;
- full system ID;
- MQTT password;
- application key;
- system peer key.

The browser may retain only its scan token and opaque candidate handle.

## 14. Multi-T1 E2E safety

R8 must include a multi-candidate test.

At least two legal candidates are presented to the phone.

Assert before explicit selection:
- no candidate is selected automatically;
- no 47110 transaction exists;
- 47112 remains closed.

After explicit selection:
- only that candidate's private node-side data is used;
- browser still sees no technical endpoint data.

The test must not implement RSSI/latency/ID ranking.

A decoy candidate may be test-only and need not create a second live Manager composition, provided the test proves no automatic selection and exact opaque-ID mapping.

## 15. Busy second-node safety

R8 must prove the V1 single-active-transaction rule across the composition boundary.

Sequence:
1. node A successfully opens first registration;
2. before A commits/expires, node B submits a valid trusted-LAN 47110 confirm.

Assert:
- B receives `registration_busy`;
- A's pairing window/deadline remains unchanged;
- B does not consume or renew its pairing ID;
- B does not create a second 47112 listener/composition;
- A may still complete normally.

No hidden global 120/600-second budget may appear.

## 16. Pre-deadline protocol failure safety

After an accepted first-registration transaction opens 47112, send a deliberately invalid pairing request, for example:
- wrong node proof;
- wrong hardware ID;
- wrong pairing ID;
- wrong source IP.

Assert:
- failure is rejected;
- durable COMMIT does not occur;
- canonical deadline is not refreshed;
- pairing ID is not renewed;
- normal-uptime 47112 window remains OPEN before the deadline.

This proves protocol failure is not an unauthorized third close condition.

Identity/source mismatch must be proven to occur before registration mutation.

## 17. ACK-response-loss recovery

R8 must include a commit/response-loss scenario.

Sequence:
1. complete HELLO/BEGIN/ESTABLISH;
2. submit the exact final ACK to the real pairing endpoint;
3. deliberately discard the returned ACK response in the node simulator;
4. verify Manager durable ledger is COMMITTED and dynamic window closes;
5. query real 47110 status with exact:
   - manager ID;
   - system ID;
   - hardware ID;
   - pairing ID;
   - delivery digest.

Assert:
- status returns COMMITTED;
- wrong delivery digest returns WAIT/UNKNOWN semantics, never committed;
- no new 47112 window is opened by status;
- no new first-registration deadline is created.

This is the Manager-side half of R6 pending-ACK recovery.

The firmware-local ACK_PENDING persistence/cleanup remains covered by R6 source contracts.

## 18. No-candidate recovery

R8 must prove:
- a valid user scan with zero candidates produces the safe no-candidate projection;
- no 47110 transaction is created;
- 47112 remains closed;
- retry requires another explicit browser action;
- pairing ID is unchanged.

R7's E01 rendering remains covered by the exact R7 source contract.

R8 does not pretend to physically observe LCD pixels.

## 19. Candidate-expiry recovery

R8 safety must preserve:
- candidate expiry before confirmation => no bootstrap;
- stale candidate selection => no transaction;
- retry uses same pairing ID;
- no Setup Secret is exposed to phone.

The exact firmware E07 mapping remains R7 source authority.

## 20. Trusted-LAN regression aggregation

R8 must re-run, not duplicate, the existing trusted-LAN contracts covering:
- exact current `eth0` unique IPv4 subnet;
- no generic RFC1918 fallback;
- loopback/link-local/IPv6 fail closed;
- state re-read rather than predecessor-subnet cache;
- 47110/47111/47112 same authority semantics;
- mDNS interface scoping;
- host guard source-contract checks.

The R8 E2E harness uses a documentation subnet only.

It does not replace those tests.

## 21. Restart/reconciliation regression aggregation

R8 must re-run the existing R2/R3 suites covering:
- restart before HELLO;
- restart after HELLO;
- BUNDLE_STAGED cleanup;
- COMMITTING exact commit recovery;
- UNKNOWN fail closed;
- terminal cleanup re-entry;
- cleanup failure blocking successor transaction;
- old pairing replay tombstones;
- deadline reconciliation;
- pending-ACK COMMITTED / terminal / WAIT / UNKNOWN behavior.

Do not recreate all crash matrices inside the new E2E test.

The purpose of R8 is to prove the layers compose while retaining those already-proven safety guards.

## 22. Pairing-security regression aggregation

R8 CI must continue to run the existing vectors/contracts that prove:
- Setup Secret HMAC;
- HKDF bootstrap;
- encrypted credential bundle;
- exact delivery-digest ACK;
- replay tombstones.

The new normal-flow E2E also exercises these primitives once through the real endpoint path.

## 23. R4-R7 regression aggregation

R8 must explicitly keep the focused source contracts for:
- R4 portal/token/browser secrecy;
- R5 scan-triggered discovery/multi-T1 selection;
- R6 TLS bootstrap/final ACK/pending recovery;
- R7 LCD states/errors/glyph/hardware-SPI/page-5 visibility.

A green R8 E2E cannot replace those focused contracts.

## 24. Test-owned resources and cleanup

Every R8 E2E test must:
- use `tmp_path` private databases/directories;
- use documentation-safe addresses only;
- use a dynamically selected free TCP port;
- close dynamic controller/composition in `finally`;
- verify no worker/listener survives test cleanup;
- zero/clear explicit mutable secret buffers when the helper owns them where practical;
- never print the Setup Secret or decrypted credential bundle to test output;
- never commit generated private key/certificate material.

No Docker daemon, T1, board or external Mosquitto dependency is allowed.

## 25. TLS certificate handling in R8

The main R8 composition does not need to prove firmware TLS pin execution.

If a test certificate is needed for an existing Manager constructor, it must be:
- ephemeral;
- test-only;
- generated or fixture-local;
- never treated as production authority.

No production certificate/private key is used.

## 26. Timing strategy

R8 must remain fast and deterministic.

Use injected clocks where the production components already support them.

Do not sleep for 1800 seconds.

Normal successful E2E should complete in seconds.

For asynchronous dynamic-window close after COMMIT:
- use a bounded polling helper;
- total wait <= 2 seconds;
- fail if CLOSED is not proven.

Deadline/restart long-time behavior remains covered by existing accelerated-clock tests.

## 27. Browser privacy proof

Browser secrecy is more than a source-string grep.

R8 must assert both:

### Static source boundary
Actual C++ portal page/API contains no Setup Secret path.

### Runtime simulated projection
Every object handed to `PhoneLikeBrowser` is recursively inspected.

Forbidden key names and exact secret values are rejected.

At minimum forbid:
- `setup_secret`
- `pairing_id`
- `hardware_id`
- `manager_id`
- `system_id`
- `bootstrap_tls_sha256`
- `mqtt_password`
- `n3w_application_key`
- `system_peer_key`

Opaque `candidate_id`, redacted node suffix and product-safe candidate label are allowed.

## 28. Public evidence rule

R8 test failure messages and GitHub comments must not print:
- Setup Secret;
- decrypted credential bundle;
- private key material;
- customer subnet;
- raw external secrets.

Documentation-safe synthetic IDs/addresses are allowed.

## 29. Source mutation plan

Initial R8 implementation should be **test-first and test-only**.

Expected files:

```text
host/greenhouse-manager/tests/runtime/
  test_n3w_scan_triggered_registration_r8_e2e.py
  [optional] n3w_r8_e2e_harness.py

tests/n3w_registration/
  test_scan_triggered_first_pairing_r8_safety_contract.py

.github/workflows/
  greenhouse-manager-ci.yml
```

No production source mutation is expected.

If the new E2E exposes a real product-source blocker:
- the failure must be independently diagnosed;
- repair must preserve the already-frozen R1-R7 semantics;
- repair scope must be documented in the R8 PR;
- architecture widening requires a design delta;
- no physical/live mutation is authorized.

## 30. CI design

### 30.1 greenhouse-manager test job

The existing full Manager pytest suite must remain green.

Add a named focused step, or equivalent visible job evidence, for:

`test_n3w_scan_triggered_registration_r8_e2e.py`

This gives a clear R8 result instead of relying only on a large aggregate test count.

### 30.2 cross-language/source-contract job

After R7 focused contracts, add:

`tests/n3w_registration/test_scan_triggered_first_pairing_r8_safety_contract.py`

Continue to run R4/R5/R6/R7 contracts unchanged.

### 30.3 firmware compilation

Existing F1.0-RC2 production N3-W compile remains mandatory.

R8 does not need a new firmware target.

## 31. Focused R8 normal-flow assertions

The implementation test must explicitly produce machine assertions for:

```text
IDLE_47112_CLOSED=true
PAGE_OPEN_DOES_NOT_START_TRANSACTION=true
SCAN_STARTS_ONE_DISCOVERY=true
MULTI_T1_AUTO_SELECT=false
BROWSER_SETUP_SECRET_EXPOSURE=false
CONFIRM_CREATES_ONE_ACTIVE_ATTEMPT=true
ACTIVE_DURABLE_BEFORE_ACCEPTED=true
47112_OPENS_AFTER_CONFIRM=true
HELLO_IDENTITY_SOURCE_BOUND=true
PAIRING_HMAC_PASS=true
PAIRING_HKDF_DECRYPT_PASS=true
BUNDLE_STAGED_BEFORE_SUCCESS=true
FINAL_ACK_DIGEST_BOUND=true
MANAGER_LEDGER_COMMITTED=true
REGISTRATION_APPROVED=true
CREDENTIAL_ACTIVE=true
APPLICATION_KEY_ACTIVE=true
SYSTEM_PEER_TRUST_VALID=true
47112_CLOSES_AFTER_COMMIT=true
SUCCESSOR_TRANSACTION_NOT_CREATED=true
```

## 32. Focused R8 negative/recovery assertions

At minimum:

```text
INVALID_SCAN_TOKEN_STARTS_NOTHING=true
ZERO_CANDIDATE_OPENS_NO_WINDOW=true
STALE_CANDIDATE_OPENS_NO_WINDOW=true
SECOND_NODE_BUSY=true
WRONG_47112_SOURCE_REJECTED_PREMUTATION=true
WRONG_47112_HARDWARE_REJECTED_PREMUTATION=true
WRONG_47112_PAIRING_REJECTED_PREMUTATION=true
PREDEADLINE_PROTOCOL_FAILURE_WINDOW_STAYS_OPEN=true
ACK_RESPONSE_LOSS_STATUS_RECOVERS_COMMITTED=true
WRONG_STATUS_DIGEST_NEVER_COMMITTED=true
```

Existing R1-R7/R2-R3 tests cover the larger crash/deadline matrix.

## 33. Stop conditions during R8 implementation

Stop and classify a source blocker if any of the following occurs:
- full normal flow cannot reach durable COMMITTED without bypassing production Manager APIs;
- 47112 remains open after durable COMMIT;
- 47112 opens before valid bootstrap;
- browser must receive Setup Secret or technical candidate locator to finish;
- multiple candidates are auto-selected;
- final ACK success can precede durable ledger COMMITTED;
- a pre-deadline protocol error closes the product-owned first-registration window;
- wrong source/hardware/pairing can mutate registration state;
- status query opens/refreshes 47112 or refreshes the transaction deadline;
- R8 requires weakening trusted-LAN or secret boundaries.

A simple test-harness construction error is not a product blocker.

## 34. What R8 PASS will mean

R8 PASS means:

> The exact R7 source stack, when composed through real Manager registration/pairing/commit components and a test-only phone/node simulator, completes the frozen first-registration protocol with correct privileged-window lifecycle, durable COMMIT authority and browser secrecy, while all prior safety/regression contracts remain green.

R8 PASS does **not** mean:
- physical board tested;
- exact artifact frozen;
- LCD appearance accepted;
- customer LAN tested;
- release ready.

## 35. Preflight result

```text
GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R8_FULL_SIMULATED_E2E_SAFETY_SOURCE_DESIGN_AND_PREFLIGHT_20261028_01

BASE_PRODUCT_SOURCE=aee4966b39140a36a9b259a643c138e9f26d0c6d
MAIN_DRIFT=false

R8_ARCHITECTURE=REAL_MANAGER_COMPOSITION_PLUS_TEST_ONLY_PHONE_NODE_SIMULATOR
REAL_MANAGER_LEDGER=true
REAL_MANAGER_PAIRING_ENDPOINT=true
REAL_MANAGER_CROSS_STORE_COMMIT=true
REAL_47112_TEST_LISTENER_LIFECYCLE=true
TEST_ONLY_DYNSEC_TRANSPORT=true

R8_ESP32_TLS_EXECUTION_CLAIM=false
R8_PHYSICAL_LCD_CLAIM=false
R8_PHYSICAL_T1_CLAIM=false

PRODUCTION_SOURCE_CHANGE_REQUIRED=false
TEST_FIRST_IMPLEMENTATION=true

R5_EXPLICIT_CANDIDATE_CLICK_COUNTS_AS_CONFIRMATION=true
SECOND_CONFIRM_BUTTON_REQUIRED=false

T1_ACCESS=false
BOARD_ACCESS=false
LIVE_MUTATION=false
MERGE=false

R8_TEST_IMPLEMENTATION_ELIGIBLE=true
PREFLIGHT_RESULT=PASS_READY_FOR_TEST_IMPLEMENTATION
```

## 36. Next executable gate

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R8_FULL_SIMULATED_E2E_SAFETY_TEST_IMPLEMENTATION_20261028_01`

The implementation gate starts test-first with no expected production-source mutation.
