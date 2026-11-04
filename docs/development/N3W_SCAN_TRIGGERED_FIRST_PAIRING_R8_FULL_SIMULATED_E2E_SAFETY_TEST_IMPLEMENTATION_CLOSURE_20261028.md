# N3W Scan-Triggered First Pairing R8 — Full Simulated E2E + Safety Test Implementation Closure

Date: 2026-10-28

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R8_FULL_SIMULATED_E2E_SAFETY_TEST_IMPLEMENTATION_CLOSURE_20261028_01`

## 1. Scope

This document closes the R8 simulated E2E + safety implementation/review stage only.

Included:
- fresh repository/PR rebind;
- exact-head CI closure;
- focused R8 E2E execution;
- R4-R7 regression preservation;
- independent false-PASS review;
- negative-path evidence strengthening;
- next-gate recommendation.

Not included:
- merge authorization;
- T1 access/mutation;
- board access/flashing;
- live runtime mutation;
- physical/network/LCD acceptance;
- exact release artifact nomination.

## 2. Source authority

Repository:

`chrenguo-stack/HomeAssistant`

Repository main remained exactly:

`2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`

Fresh compare against main:
- status: identical;
- ahead: 0;
- behind: 0.

R7 exact product-source authority remains:

`aee4966b39140a36a9b259a643c138e9f26d0c6d`

R8 implementation PR:

`#705`

Final exact R8 repository head:

`e299c937a7b89bb8a7b9a7432186ba46a416cd44`

PR #705 remained:
- open;
- draft;
- unmerged;
- no review threads;
- no reviews.

R8 changed no production source bytes.

## 3. Exact implementation delta

Compared with R7 exact product source, R8 changes only:

```text
.github/workflows/greenhouse-manager-ci.yml

host/greenhouse-manager/tests/runtime/
  test_n3w_scan_triggered_registration_r8_e2e.py

tests/n3w_registration/
  test_scan_triggered_first_pairing_r8_safety_contract.py
```

Therefore:

```text
PRODUCTION_SOURCE_MUTATION=false
PRODUCT_SOURCE_BYTES_UNCHANGED_FROM_R7=true
```

## 4. Exact-head CI result

Final exact R8 head:

`e299c937a7b89bb8a7b9a7432186ba46a416cd44`

Workflow summary:

```text
SUCCESS=13
FAILURE=0
PENDING=0
CONDITIONAL_SKIP=1
```

The skipped workflow was the scope-conditional
`N3W T1 fresh bootstrap deployable payload CI`.

The critical `greenhouse-manager CI` completed successfully:
- scope: PASS;
- Manager test job: PASS;
- cross-language/source-contract job: PASS.

Manager aggregate result:

```text
1479 passed
1 skipped
0 failed
```

Focused R8 Manager E2E:

```text
8 passed
0 failed
```

Focused source contracts:
- R4: 6 passed;
- R5: 9 passed;
- R6: 8 passed;
- R7: 7 passed;
- R8: 10 passed.

ESP32-C6 firmware image generation remained successful in the exact-head cross-language/build workflow.

## 5. R8 normal-flow E2E closure

The R8 Manager E2E uses:
- real `RegistrationBootstrapApp`;
- real `FirstRegistrationTransactionService`;
- real first-registration ledger;
- real `DynamicPairingWindowController`;
- real `build_simplified_product_pairing_composition`;
- real `SimplifiedPairingEndpointApp`;
- real pairing coordinator;
- real credential lifecycle store;
- real application-key store;
- real system peer-trust store;
- real `DynsecProvisioner` over test-only in-memory command transport.

The normal flow proves:

```text
phone page open
-> no transaction
-> explicit scan
-> candidate projection
-> explicit candidate click
-> real 47110 confirm
-> durable ACTIVE attempt
-> privileged 47112-equivalent listener OPEN
-> HELLO
-> BEGIN
-> Manager Setup-Secret HMAC verified
-> node HMAC proof accepted
-> HKDF bootstrap key derived
-> encrypted credential bundle decrypted
-> ledger BUNDLE_STAGED
-> exact delivery-digest ACK
-> durable Manager COMMIT
-> registration APPROVED
-> credential ACTIVE
-> application key ACTIVE
-> peer trust valid
-> privileged window CLOSED
```

No alternate test-only transaction state machine was introduced.

## 6. Public-path / no-direct-mutation review

Independent source review checked the R8 E2E file for direct internal mutation helpers.

Not present:

```text
create_active(
mark_committed(
mark_bundle_staged(
.approve(
.observe_hello(
.import_setup_secret(
.coordinator.
```

Present public/product paths include:
- `RegistrationBootstrapApp`;
- `bootstrap.handle_confirm()`;
- `endpoint.handle()`;
- `build_simplified_product_pairing_composition()`;
- real `DynsecProvisioner`.

Therefore the E2E does not pass by directly marking internal state.

## 7. 47112 lifecycle closure

R8 proves a real host-process TCP listener lifecycle using the product dynamic-window worker:

```text
before bootstrap: CLOSED
after accepted first-registration confirm: OPEN
after durable COMMIT: CLOSED
```

The actual pairing requests are injected through the real pairing endpoint with the synthetic trusted source IP.

This intentionally does not claim real T1 firewall/routing proof.

## 8. Durable-attempt-before-accept proof

R8 source contract explicitly proves Manager ordering:

```text
ledger.create_active
-> intents.activate
-> window.open_first_registration
-> return accepted result
```

Therefore the client cannot observe an accepted 47110 transaction before the durable first-registration attempt exists.

## 9. Browser secrecy closure

R8 proves both:

### Static firmware portal boundary
The actual C++ portal:
- consumes only the QR fragment scan token;
- removes the fragment from the visible URL;
- calls only node-local registration APIs;
- confirms with opaque `candidate_id`;
- never embeds Setup Secret or privileged technical locator data;
- never calls 47110/47112 directly.

### Runtime projection boundary
The simulated browser receives only:
- scan token;
- redacted node label;
- opaque candidate ID;
- product-safe candidate label;
- safe status fields.

The runtime browser projection excludes:
- Setup Secret;
- pairing ID;
- full hardware ID;
- Manager ID;
- full system ID;
- bootstrap TLS fingerprint;
- T1 host;
- bootstrap port;
- MQTT password;
- application key;
- peer key.

## 10. Multi-T1 / no-auto-select closure

R8 proves:
- multiple candidates may be presented;
- no candidate is selected automatically;
- merely presenting candidates creates no Manager transaction;
- 47112 remains CLOSED;
- clicking one candidate is the explicit user confirmation;
- selecting an invalid/stale candidate creates no transaction;
- pairing ID remains unchanged.

The R5 frozen interpretation remains:

```text
EXPLICIT_CANDIDATE_BUTTON_CLICK = USER_CONFIRMATION
AUTO_SELECT=false
SECOND_CONFIRM_BUTTON_REQUIRED=false
```

## 11. No-candidate / stale-candidate evidence strengthening

Independent R8 closure review identified that the first green implementation only proved the simulator did not call bootstrap.

That evidence was strengthened before closure.

Final exact tests also prove:
- Manager first-registration ledger remains empty;
- privileged listener remains CLOSED;
- pairing ID remains unchanged.

This strengthening produced the final exact head
`e299c937a7b89bb8a7b9a7432186ba46a416cd44`
and a fresh all-green CI round.

## 12. Wrong identity/source pre-mutation closure

R8 exercises wrong:
- source IP;
- hardware ID;
- pairing ID.

The real pairing endpoint rejects each request.

Final assertions prove:
- registration registry remains unchanged;
- first-registration attempt remains ACTIVE;
- first-registration phase remains `BOOTSTRAP_ACCEPTED`;
- privileged window remains OPEN for the legitimate transaction.

Therefore mismatched 47112 requests are rejected before registration mutation.

## 13. Pre-deadline protocol failure closure

R8 sends an invalid node proof during an accepted first-registration transaction.

It proves:
- request is rejected;
- durable attempt remains ACTIVE;
- canonical deadline remains unchanged;
- privileged window remains OPEN;
- no pairing-ID renewal occurs through this path.

This preserves the frozen rule that ordinary protocol failure is not a third normal-uptime close condition.

## 14. Single-active-transaction closure

R8 opens node A's first-registration transaction, then submits a valid node B confirm.

It proves:
- node B receives `registration_busy`;
- node A deadline remains unchanged;
- only one reconcilable first-registration attempt exists;
- B has no ledger attempt;
- only one pairing composition/window exists;
- A's privileged window remains OPEN.

V1 one-active-first-registration semantics remain intact.

## 15. ACK-response-loss recovery closure

R8 completes the exact final ACK but deliberately discards the node-side ACK response.

It then queries real 47110 status.

It proves:
- exact delivery digest returns COMMITTED;
- wrong delivery digest returns UNKNOWN/WAIT, never COMMITTED;
- status query does not create another pairing composition;
- status query does not reopen 47112;
- status query does not create a new deadline.

This validates the Manager half of the R6 pending-ACK recovery contract.

Firmware-local pending-ACK persistence/recovery remains covered by R6 focused source contracts.

## 16. Manager COMMIT ordering closure

R8 source contract proves the final-ACK durable order:

```text
ledger.claim_committing
-> cross-store reconciler classify
-> ledger.mark_committed
-> first_registration_complete_callback
```

Therefore privileged-window close callback cannot precede durable Manager COMMIT.

## 17. Canonical deadline closure

R8 retains and tests the exact frozen first-registration TTL:

```text
FIRST_REGISTRATION_TTL_SECONDS = 1800
```

No R8 path refreshes the deadline.

Status recovery does not:
- call `open_first_registration`;
- call `create_active`;
- assign a new `expires_at`.

## 18. R6 TLS boundary remains explicit

R8 does not claim Python simulation is real ESP32-C6 TLS execution.

R6 focused contracts remain a required predecessor and continue to pass.

They prove:
- TLS handshake completes before pin gate;
- selected leaf SHA-256 is checked;
- HTTP request containing Setup Secret is constructed/sent only after pin success;
- redirect/fallback behavior remains fail-closed.

R8 therefore preserves the anti-false-PASS boundary:

```text
R8_REAL_ESP32_TLS_EXECUTION=false
R8_MANAGER_PROTOCOL_E2E=true
```

## 19. R7 display authority remains preserved

R7 focused contracts remain a required predecessor and continue to pass.

R8 does not redefine UI success.

The existing product rule remains:

```text
LCD SUCCESS requires pairing_client_.provisioned() == true
```

R8 Manager COMMIT proof and R7 display-success proof remain separate, composable authorities.

## 20. DynSec test boundary

R8 replaces only the external Mosquitto command transport.

The in-memory transport models:
- createRole;
- createClient;
- setClientPassword;
- listClients;
- listRoles;
- getClient;
- getRole;
- deleteClient;
- deleteRole.

Real `DynsecProvisioner` still:
- builds commands;
- provisions;
- deprovisions;
- inspects exact client/role state.

The test does not fake a simple `committed=true` oracle.

## 21. Physical boundary

R8 does not prove:
- real ESP32-C6 network/TLS timing;
- real T1 network namespace/firewall;
- customer LAN behavior;
- physical QR scanning;
- physical LCD appearance;
- actual ST7920 electrical margin;
- board flashing;
- exact release-artifact byte identity.

Those remain later gates.

## 22. Final R8 closure result

```text
GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R8_FULL_SIMULATED_E2E_SAFETY_TEST_IMPLEMENTATION_CLOSURE_20261028_01

R7_PRODUCT_SOURCE=aee4966b39140a36a9b259a643c138e9f26d0c6d
R8_EXACT_REPOSITORY_HEAD=e299c937a7b89bb8a7b9a7432186ba46a416cd44

MAIN_DRIFT=false
PRODUCTION_SOURCE_MUTATION=false

EXACT_HEAD_CI=PASS
WORKFLOW_SUCCESS_COUNT=13
WORKFLOW_FAILURE_COUNT=0
WORKFLOW_PENDING_COUNT=0
WORKFLOW_CONDITIONAL_SKIP_COUNT=1

MANAGER_TESTS=1479_PASS_1_SKIP
R8_MANAGER_E2E=8_PASS
R8_SAFETY_CONTRACT=10_PASS

NORMAL_FLOW_E2E=PASS
REAL_47112_LISTENER_LIFECYCLE=PASS
DURABLE_ATTEMPT_BEFORE_ACCEPT=PASS
BROWSER_SECRET_BOUNDARY=PASS
MULTI_T1_NO_AUTO_SELECT=PASS
ZERO_CANDIDATE_CLOSED_WINDOW=PASS
STALE_CANDIDATE_CLOSED_WINDOW=PASS
WRONG_IDENTITY_PREMUTATION_REJECT=PASS
PREDEADLINE_FAILURE_WINDOW_STAYS_OPEN=PASS
SECOND_NODE_BUSY=PASS
ACK_RESPONSE_LOSS_STATUS_RECOVERY=PASS
FINAL_ACK_COMMIT_ORDERING=PASS
CANONICAL_1800S_DEADLINE=PASS

DIRECT_INTERNAL_STATE_MUTATION_IN_E2E=false
NEW_FALSE_PASS_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false

R8_TEST_IMPLEMENTATION=PASS
PR705_SOURCE_MERGE_READY=true

T1_ACCESS=false
BOARD_ACCESS=false
LIVE_MUTATION=false
PHYSICAL_ACCEPTANCE=false
MERGE=false
```

`PR705_SOURCE_MERGE_READY=true` means test/source review readiness only. It is not merge authorization.

## 23. R9 handoff

Frozen next stage:

```text
R9 = exact artifact build + independent artifact/source review
```

R9 must:
- choose one exact repository/source authority;
- build exact ESP32-C6 production artifact;
- bind artifact digest/fingerprint to exact source;
- independently review artifact/source continuity;
- re-run required source gates;
- avoid board/T1/live mutation;
- produce a physical-acceptance candidate only after artifact closure.

Recommended next gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R9_EXACT_ARTIFACT_BUILD_AND_INDEPENDENT_REVIEW_DESIGN_PREFLIGHT_20261028_01`

R10 remains separately authorized physical acceptance.
