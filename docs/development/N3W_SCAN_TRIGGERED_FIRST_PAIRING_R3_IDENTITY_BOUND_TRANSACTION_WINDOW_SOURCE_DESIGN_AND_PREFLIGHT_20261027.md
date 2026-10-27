# N3-W scan-triggered first registration — R3 identity-bound transaction window source design and preflight

Date: 2026-10-27

## 1. Task and boundary

Task:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R3_IDENTITY_BOUND_TRANSACTION_WINDOW_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01`

Fresh source authority:

- main: `920a2e5dba24d5d3c9a6aa7aaca3fcafd2876847`
- frozen product design: `docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md`
- frozen design blob: `92f72d913e5b89281e17be3e4651670b67bd5a9f`
- R1 / R2A / R2B pre-R2C alignment: PASS
- R2C SYSTEM_PEER_KEY source implementation merge: `920a2e5dba24d5d3c9a6aa7aaca3fcafd2876847`
- R2C reviewed/merged tree: `dbd3469bbc3302a5ae32fec2af9619d73409da1a`

This gate is source design / preflight only.

No R3 product-source mutation, firmware mutation, T1 access, board access, live deployment, flash/NVS action or physical acceptance is authorized here.

## 2. Frozen R3 product contract

The frozen design requires the normal first-registration path to become one process-local + durable transaction with one absolute deadline.

Canonical product ports:

```text
47110/tcp = always-on low-privilege TLS registration bootstrap
47111/udp = always-on low-privilege registration discovery fallback
47112/tcp = privileged pairing HTTP, idle CLOSED
```

Canonical first-registration transaction:

```text
47110 confirm accepted
-> durable ACTIVE first_registration_attempt
-> current-process FirstRegistrationIntent
-> identity/source-bound 47112 opens
-> exact /hello
-> existing Setup-Secret pairing protocol
-> durable staging / COMMITTING / commit oracle
-> durable COMMITTED
-> 47112 closes
```

One canonical deadline:

```text
deadline = accepted 47110 transaction opened_at + 1800 seconds
```

No product sub-stage may refresh or extend this deadline.

## 3. Current-source findings

### 3.1 47110 remains an R1 skeleton

Current `n3w_registration_bootstrap.py` correctly provides:
- TLS transport;
- trusted-product-LAN source admission;
- bounded exact JSON schema;
- manager/system/hardware/pairing/Setup-Secret validation;
- rate limiting;
- no secret logging/persistence.

But a valid request still returns:

`first_registration_transaction_not_implemented`

No durable first-registration attempt, RAM intent or 47112 transaction is created.

### 3.2 RegistrationNetworkRuntime is not product-wired

`n3w_registration_runtime.py` can assemble:
- 47110 TLS bootstrap;
- 47111 UDP discovery;
- trusted-LAN-scoped mDNS.

But current Manager product wiring does not construct/start this runtime.

Therefore current normal Manager startup does not yet make R1 47110/47111 product-ready.

### 3.3 Current dynamic 47112 path is an engineering window, not the product transaction

`DynamicPairingWindowController.open_window(peer_ip, window_seconds)` currently:
- accepts an operator-supplied peer IP;
- validates RFC1918/private IPv4 semantics;
- derives route-selected broker host;
- opens pairing resources;
- uses an independent 180..600 second dynamic-window timer.

It does **not** bind:
- expected hardware ID;
- expected pairing ID;
- expected accepted 47110 source IP;
- the durable first-registration ledger deadline.

This engineering path remains useful and must not silently acquire normal-product authority.

### 3.4 Current 47112 endpoint mutates RegistrationRegistry before product identity/source binding

`SimplifiedPairingEndpointApp` currently:
- admits broad `is_local_source(client_ip)`;
- calls `RegistrationRegistry.observe_hello()` directly on `/v2/pairing/hello`.

There is no product-mode pre-mutation check for exact:
- hardware ID;
- pairing ID;
- source IP.

R3 must insert the first-registration intent check before `observe_hello()`.

### 3.5 RegistrationRegistry still owns a separate default pending TTL

Current `RegistrationRegistry.observe_hello()` creates a new pairing session with:

`expires_at = observed_at + pending_ttl`

It has no authorized exact-deadline override.

Therefore a first-registration `/hello` currently starts an independent timer rather than inheriting the durable 47110 transaction deadline.

### 3.6 SimplifiedPairingCoordinator still owns a separate session TTL

Current `SimplifiedPairingCoordinator.begin()` uses:

`min(observed_at + session_ttl, registration.expires_at)`

The normal session TTL is still bounded independently and historically capped at 600 seconds.

The product first-registration path therefore needs an explicit shared-deadline authority; merely raising the old max to 1800 would preserve multiple timer authorities and is rejected by this design.

### 3.7 R2A/R2B durable facts exist but are not yet connected to the live transaction path

R2A already provides:
- durable ACTIVE attempt creation;
- HELLO_OBSERVED;
- ownership prestate fields;
- BUNDLE_STAGED;
- COMMITTING;
- COMMITTED / terminal states.

R2B already provides:
- startup/deadline cross-store reconciliation;
- exact three-valued classification;
- exact-owned cleanup;
- commit-oracle recovery.

But current live `/hello -> /begin -> /establish -> /ack` does not drive those ledger transitions.

A product R3 path must not be exposed until these hooks are connected. Otherwise credentials could be staged/committed without the durable evidence required for restart safety.

### 3.8 R2C baseline is available for R3 readiness

R2C has moved SYSTEM_PEER_KEY creation/validation out of bundle issuance.

R3 may therefore initialize/validate the same peer-trust baseline before registration network readiness without giving first-registration transactions peer-trust lifecycle ownership.

## 4. R3 architecture decision

R3 adds one product transaction authority around the existing simplified pairing protocol.

Recommended new runtime modules:

```text
n3w_first_registration_intent.py
n3w_first_registration_transaction.py
```

The exact names may vary during implementation, but responsibilities may not collapse back into generic dynamic-window state.

### 4.1 FirstRegistrationIntent

Process-local, mutable, non-durable authority:

```text
hardware_id
pairing_id
source_ip
manager_id
system_id
opened_at
expires_at
setup_secret mutable buffer
active/consumed state
```

Properties:
- at most one active intent in V1;
- exact identity/source binding;
- deadline equals durable ledger `expires_at`;
- Setup Secret is never written to SQLite/logs/public diagnostics;
- secret buffer is zeroized on success, expiry, open failure and Manager/process invalidation;
- Manager restart destroys the intent;
- the intent alone never establishes replay authority.

The durable ledger remains cross-restart authority.

## 5. 47110 transaction-start service

Replace skeleton-only acceptance with an injected transaction service.

Frozen order:

```text
strict confirm validation
-> trusted product LAN admission
-> manager/system binding
-> terminal/replay pairing-id check
-> unresolved predecessor check
-> prepare non-active RAM intent
-> opened_at = now
-> expires_at = opened_at + 1800 s
-> durable ledger create_active()
-> activate RAM intent with exact same expires_at
-> open product 47112 for that exact intent
-> return accepted=true
```

The accepted response returns:
- manager/system;
- route-selected pairing host;
- port 47112;
- `/v2/pairing`;
- remaining time derived from the fixed deadline.

It does not return credentials or secrets.

### 5.1 Failure before durable INSERT

No transaction exists.

47110 must not return `accepted=true`.

The same pairing ID may be retried.

### 5.2 Failure after durable INSERT but before 47112 ready

The ACTIVE row remains with its original deadline.

The service must not delete the row and must not mint a new 1800-second deadline.

A same-process exact duplicate may retry exposure only when the current RAM intent matches all bindings.

If RAM intent is absent/mismatched, fail closed and route through R2B reconciliation.

### 5.3 Exact duplicate

An exact same-process duplicate requires equality of:
- hardware ID;
- pairing ID;
- source IP;
- manager/system;
- active ledger row;
- current RAM intent.

It reuses the original `opened_at/expires_at`.

No deadline refresh is permitted.

## 6. Product 47112 window

Keep existing engineering:

`open_window(peer_ip, window_seconds)`

as a separate engineering/control path.

Add product-only internal operation conceptually equivalent to:

`open_first_registration(intent)`

Product-window requirements:
- 47112 is CLOSED while idle;
- product open does not use the 180..600 engineering-window bound;
- product open uses the absolute intent/ledger deadline;
- broker route selection may use the already accepted source IP;
- application-layer request admission uses exact source IP, not generic `is_local_source()`;
- product window carries expected hardware ID and pairing ID;
- product diagnostics expose only hashes/non-secret state.

Engineering control socket cannot manufacture a product first-registration intent.

## 7. Identity/source-bound /hello

Before any `RegistrationRegistry.observe_hello()` mutation in product mode:

1. exact source IP equals intent source IP;
2. request hardware ID equals intent hardware ID;
3. request pairing ID equals intent pairing ID;
4. current time <= intent/ledger deadline;
5. ledger row is still ACTIVE and exactly bound;
6. current-process intent is active and unconsumed.

Any mismatch rejects before durable registration mutation.

Only after those checks:
- call `observe_hello()` with the exact authorized absolute deadline;
- require accepted/duplicate semantics consistent with the same transaction;
- durably mark ledger `HELLO_OBSERVED`;
- import Setup Secret into the existing coordinator;
- return normal hello result.

## 8. RegistrationRegistry exact-deadline override

Extend `observe_hello()` with an optional internal first-registration-only authorized deadline.

Default callers retain current `pending_ttl_s` behavior.

For the R3 product path:
- the new session `expires_at` equals the passed absolute ledger deadline exactly;
- the deadline must be timezone-aware and later than `now`;
- a duplicate existing PENDING row must have the same stored expiry; mismatch fails closed;
- the override may not update/extend an existing row;
- ordinary repair and legacy/engineering callers remain unchanged.

## 9. Simplified pairing shared-deadline authority

Do not solve R3 by globally changing the old session TTL to 1800.

Add an explicit first-registration deadline authority to the coordinator/path.

For a product first-registration session:
- `begin()` uses the RegistrationRegistry/ledger absolute deadline directly;
- `establish()`, status and ACK all use that same expiry;
- no `now + 120`, `now + 600` or renewed 1800-second budget is introduced.

For ordinary engineering pairing/repair/recovery:
- current session TTL behavior remains unchanged.

## 10. Live ledger / ownership hooks are mandatory before product exposure

R3 product pairing may not expose a credential-mutating `/begin` path while the live ledger is disconnected.

Required first-registration hooks:

### 10.1 HELLO

After exact-bound `observe_hello()` succeeds:

`ledger.mark_hello_observed(pairing_id)`

### 10.2 Before DynSec creation

The exact deterministic generation-1 target must be inspected absent, then persist:
- exact node ID;
- `dynsec_prestate_absent=true`.

Only then may DynSec provisioning create the target.

### 10.3 Before application-key staging

Prove exact node has no predecessor epoch, then persist:
- `application_key_prestate_absent=true`.

Only then may the initial STAGED key be created.

### 10.4 After complete staging and encrypted delivery assembly

Before returning credentials:
- compute delivery digest;
- persist `BUNDLE_STAGED`;
- persist node ID;
- persist application-key epoch;
- persist digest SHA-256.

The response must not leave the process before this durable write succeeds.

### 10.5 ACK / commit

On an exact final delivery-digest ACK:

```text
durably mark COMMITTING
-> application-key commit
-> CredentialLifecycle commit
-> exact cross-store commit oracle
-> durably mark COMMITTED
-> only then return committed success
```

Once COMMITTING is durable, generic legacy rollback semantics may not erase commit-oracle evidence merely because a later local call raises. R2B reconciliation becomes authoritative for ambiguous crash/error completion.

This requires a first-registration-specific commit path or hooks around the existing coordinator; it must not weaken ordinary repair/recovery behavior.

## 11. Deadline expiry

At the fixed deadline:
- product 47112 closes;
- RAM secret/intent is zeroized/invalidated;
- no new pairing step may proceed;
- R2B deadline reconciliation classifies durable state;
- exact-owned cleanup occurs only after DEFINITELY_NOT_COMMITTED;
- terminal reason is `expired`;
- the pairing ID remains a replay tombstone.

No operation refreshes the deadline.

## 12. Manager restart / startup readiness

R3 product registration services use this startup order:

```text
normal Manager/MQTT runtime available
-> initialize/validate R2C peer-trust baseline
-> open required private stores read-only/read-write as designed
-> run R2B startup reconciliation for every reconcilable attempt
-> require no UNKNOWN / FAILED registration blocker
-> assemble/start 47110 TLS + 47111 UDP/mDNS
-> keep 47112 CLOSED
```

Manager restart:
- destroys all RAM first-registration intents;
- never resumes old 47112;
- old ACTIVE attempts are reconciled/terminalized before registration listeners become ready;
- normal Manager telemetry should remain available even when registration readiness fails closed.

R3 must not make a registration-only failure an unnecessary global MQTT/telemetry outage.

## 13. 47110 pending-ACK status operation

The frozen overall design requires low-privilege:

`POST /v1/registration/status`

R3 T1-side transaction wiring should implement this while the required ledger/oracles are in scope.

Request binds:
- manager/system;
- hardware ID;
- pairing ID;
- delivery digest.

It:
- uses trusted-product-LAN admission;
- does not require/reopen 47112;
- never returns secrets;
- may accept a changed source IP within the current trusted product LAN because this is cross-restart status recovery;
- reports only COMMITTED / TERMINAL_NOT_COMMITTED / WAIT / UNKNOWN according to the frozen R2B classifier semantics.

Node-side consumption of this endpoint remains later firmware work.

## 14. Manager runtime composition

Current `N3wDynamicPairingManagerMqttService` is the closest safe base because it keeps normal MQTT/telemetry independent from a temporary 47112 window.

R3 should evolve the normal N3-W product service toward one composite registration sub-runtime rather than activating the old always-on `N3wSimplifiedProductManagerMqttService` path.

Required ownership:
- normal MQTT/telemetry stays owned by Manager;
- registration sub-runtime owns 47110/47111;
- first-registration transaction controller owns temporary product 47112;
- engineering dynamic control remains separate;
- product and engineering windows are mutually exclusive;
- shutdown closes all registration listeners/windows without changing durable baseline facts.

The old `n3w_product_pairing_enabled=true` always-on 47112 semantics must not become the target product path.

## 15. Expected bounded source scope

Expected new/modified runtime files:

1. `n3w_first_registration_intent.py` — new process-local intent authority.
2. `n3w_first_registration_transaction.py` — new transaction orchestration.
3. `n3w_registration_bootstrap.py` — real confirm + status operations through injected transaction service.
4. `n3w_registration_runtime.py` — compose bootstrap/discovery with transaction service.
5. `n3w_dynamic_pairing_window.py` — add separate product `open_first_registration()` path while preserving engineering `open_window()`.
6. `n3w_simplified_pairing_endpoint.py` — product-mode exact source/hardware/pairing guard before `observe_hello()`.
7. `registration.py` — optional exact absolute deadline override.
8. `n3w_simplified_pairing.py` — first-registration shared deadline and commit hooks.
9. `n3w_simplified_provisioning.py` — only the hooks required to durably prove ownership before external staging.
10. `n3w_manager_runtime_wiring.py` — startup reconciliation/readiness and registration sub-runtime ownership.
11. `n3w_simplified_product_runtime.py` — only if needed to expose a reusable R2C baseline-init/composition seam without opening 47112.

R2A/R2B modules may be called, but their frozen classifier/cleanup semantics must not be rewritten unless a focused review proves an implementation defect.

Any expansion into firmware, QR/browser/LCD or general Direct/Relay logic is out of scope.

## 16. Required source tests

### A. 47110 start ordering
Prove:
- invalid/untrusted request creates no ledger row/intent/window;
- durable ACTIVE exists before accepted response;
- accepted response is impossible when durable INSERT fails;
- post-INSERT window-open failure preserves ACTIVE with original deadline;
- exact duplicate does not refresh deadline;
- conflicting identity/source returns conflict/busy.

### B. Identity/source binding
Prove wrong source, hardware or pairing ID is rejected before `observe_hello()`.
Prove zero RegistrationRegistry mutation on mismatch.

### C. Shared deadline
Prove:
- ledger, RAM intent, RegistrationRegistry and pairing session all expose exactly the same absolute deadline;
- begin at T+1700 has only 100 seconds remaining;
- no hidden 120/600-second cap;
- duplicate confirm does not produce a new 1800-second window.

### D. Idle/open/close port semantics
Prove:
- 47110/47111 ready while idle;
- 47112 closed while idle;
- one valid transaction opens 47112;
- success/expiry/shutdown closes 47112;
- second product transaction cannot open concurrently.

### E. Live ledger phase integration
Prove:
- HELLO_OBSERVED is durable before begin;
- prestate evidence is durable before DynSec/application-key side effects;
- BUNDLE_STAGED is durable before credentials leave Manager;
- COMMITTING is durable before external commit;
- COMMITTED only after exact oracle PASS.

### F. Crash/failure matrices
Inject failure:
- before ACTIVE insert;
- after ACTIVE insert before window open;
- after hello;
- after DynSec create before full stage proof;
- after BUNDLE_STAGED;
- after COMMITTING before first external commit;
- between application-key and CredentialLifecycle commit;
- after cross-store commit before ledger COMMITTED.

Expected result must match R2B COMMITTED / DEFINITELY_NOT_COMMITTED / UNKNOWN semantics; UNKNOWN never destructive-cleans.

### G. Restart readiness
Prove startup reconciliation runs before 47110/47111 listeners.
UNKNOWN/FAILED predecessor keeps registration listeners closed.
Normal MQTT/telemetry service remains independently runnable.

### H. 47110 status
Prove exact hardware/pairing/digest binding, no secret output, changed trusted-LAN source permitted, and no 47112 reopen.

### I. Engineering regression
Existing `open_window(peer_ip, seconds)` control path remains separate and its current tests continue to pass.
Engineering path cannot create a product ledger attempt or FirstRegistrationIntent.

## 17. Explicit R3 non-goals

```text
FIRMWARE_REGISTRATION_PORTAL=false
QR_GENERATION=false
PHONE_BROWSER_UI=false
NODE_SCAN_DISCOVERY=false
NODE_BOOTSTRAP_CLIENT=false
PENDING_ACK_NODE_FIRMWARE=false
LCD_INTEGRATION=false
PHYSICAL_ACCEPTANCE=false
T1_LIVE_DEPLOYMENT=false
BOARD_ACCESS=false
WHOLE_NVS_RESET=false
```

## 18. Preflight result

No design blocker was found, but R3 is materially larger than a timer/window edit.

The safe implementation boundary is the complete T1-side transaction shell described above.

```text
R3_DESIGN_RESULT=PASS
R3_DESIGN_BLOCKER_COUNT=0
R3_IMPLEMENTATION_REQUIRED=true
R3_IMPLEMENTATION_READY=true

R3_PRODUCT_TRANSACTION_AUTHORITY=LEDGER_PLUS_CURRENT_PROCESS_INTENT
R3_CANONICAL_FIRST_REGISTRATION_TTL_SECONDS=1800
R3_DEADLINE_REFRESH_ALLOWED=false
R3_47110_ALWAYS_ON_WHEN_REGISTRATION_READY=true
R3_47111_ALWAYS_ON_WHEN_REGISTRATION_READY=true
R3_47112_IDLE_CLOSED=true
R3_47112_BINDING=HARDWARE_ID_PLUS_PAIRING_ID_PLUS_SOURCE_IP
R3_ENGINEERING_OPEN_WINDOW_SEPARATE=true
R3_LIVE_LEDGER_PHASE_HOOKS_REQUIRED=true
R3_STARTUP_RECONCILIATION_BEFORE_LISTENERS=true
R3_PENDING_ACK_STATUS_T1_SIDE_REQUIRED=true
R3_GLOBAL_TELEMETRY_GATED_BY_REGISTRATION=false

FIRMWARE_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
```

## 19. Implementation staging recommendation

Because R3 touches transaction authority, listener exposure and cross-store commit semantics, implementation should be one source gate but may use multiple commits inside the same PR:

```text
R3-S1 intent + exact deadline + RegistrationRegistry override
R3-S2 identity-bound product 47112 + bootstrap transaction start
R3-S3 live ledger staging/COMMITTING hooks + status recovery
R3-S4 Manager startup reconciliation + 47110/47111 readiness
R3-S5 focused failure matrix + repository CI + Exact Closure
```

Do not merge a partially exposed product path. Until S1-S4 are all present and focused review passes, the PR remains Draft and is not product-ready.

## 20. Next gate

After this docs-only design/preflight is reviewed and merged, enter:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R3_IDENTITY_BOUND_TRANSACTION_WINDOW_SOURCE_IMPLEMENTATION_20261027_01`

That source gate may mutate only the bounded T1/Manager source and tests described above. Firmware, T1 live deployment, boards and physical acceptance remain separately authorized later gates.
