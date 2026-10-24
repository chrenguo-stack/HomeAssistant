# N3-W Manager Dynamic First-Pairing Window — Frozen Source Design and Acceptance Plan — 2026-10-24

## 1. Decision

This document freezes the replacement design for PR #664 first-pair onboarding.

The rejected design used an out-of-band Docker Compose `--force-recreate manager` to change Manager startup environment for a temporary pairing window. Live evidence proved that this conflicts with the deployed production supervision model: `n3wfc4-services-activation.service` owns Manager and Home Assistant in one foreground `docker compose ... --abort-on-container-exit manager homeassistant` lifecycle. Recreating Manager externally causes that foreground Compose process to abort and stop Home Assistant.

The replacement design is:

> Keep Broker, Manager and Home Assistant continuously running. Open and close first-pair capability inside the existing Manager process through a local-only dynamic pairing-window controller.

This is a source-design freeze only. It does not authorize T1 mutation, Board D access, production image deployment, pairing, or merge.

## 2. Frozen source authority

- Repository: `chrenguo-stack/HomeAssistant`
- PR: #664, draft/open
- Source base before this docs-only freeze: `85706d7507b8ce90b3447c18ab62d9c0a37afcce`
- PR branch: `fix/n3w-t1-first-pairing-onboarding-activation-20261024`
- Existing onboarding parser recovery repair is already present at the source base and related CI was 12/12 PASS.
- PR #664 remains the implementation PR. Do not create a second dependent PR unless a later review proves the scope cannot remain coherent.

## 3. Proven live failure that drives this design

The failed live `open` attempt consumed its one-shot authorization and is permanently non-replayable.

Live evidence proved:

1. the old Manager container was stopped during onboarding Manager recreation;
2. the deployed services unit immediately logged `Aborting on container exit...`;
3. Home Assistant then received Docker stop/kill events and exited with code 137;
4. Docker reported `OOMKilled=false` and kernel OOM evidence was absent;
5. Broker remained running;
6. Manager later returned to factory runtime values and pairing ports 47111/47112 were closed;
7. Board D was never paired;
8. the staged watchdog then looped because the old staged onboarding parser rejected `OPEN_RESTORE_PENDING`; that source parser defect is already repaired in PR #664.

Therefore the old assumption “Manager can be recreated while Home Assistant remains unchanged” is false for the current production supervision contract.

## 4. Product behavior to preserve

Normal production state remains unchanged:

- `GH_N3W_PRODUCT_PAIRING_ENABLED=false`;
- Manager container remains host-networked;
- no Docker ports are added to Manager;
- UDP 47111 and TCP 47112 are closed outside a bounded pairing window;
- the durable Compose value `GH_N3W_NODE_BROKER_HOST=gate-f-unbound.invalid` remains unchanged;
- `GH_N3W_PAIRING_ADVERTISED_HOST=auto` remains the portable discovery contract;
- Broker, Manager and Home Assistant service supervision is not redesigned in this task.

Dynamic pairing must not rewrite Compose or durable Manager environment.

## 5. Target runtime architecture

### 5.1 Manager-owned pairing-window controller

Add a Manager-owned runtime controller with an explicit lifecycle:

`CLOSED -> OPENING -> OPEN -> CLOSING -> CLOSED`

Only one window may exist at a time.

The controller owns the already-existing pairing composition and worker. It must reuse the existing:

- `SimplifiedProductPairingComposition`;
- `N3wSimplifiedProductPairingWorker`;
- UDP discovery runtime;
- HTTP pairing endpoint;
- `ManagerOwnedPairingSocket`;
- registration store;
- credential lifecycle;
- application-key lifecycle;
- peer-trust store.

The pairing protocol itself is not redesigned.

### 5.2 Runtime-only configuration

The durable Manager Settings object remains production/factory shaped with product pairing disabled.

When opening a window, the controller builds a bounded in-memory pairing configuration from:

- already-loaded Manager identity and provisioning credentials;
- current production CA/TLS material;
- current pairing manager ID;
- `advertised_host=auto`;
- current pairing ports;
- a route-selected Broker locator derived for the requesting local peer.

The route-selected Broker locator is runtime-only. It must not be written to Compose, env files, GitHub, public evidence, or durable Manager configuration.

### 5.3 Local-only control interface

Add a Manager-owned local control socket under the existing private runtime directory, for example:

`/run/greenhouse-manager/pairing-control.sock`

It is distinct from `pairing.sock`.

The control socket owns only pairing-window lifecycle operations:

- open;
- status;
- close.

`pairing.sock` remains dedicated to Setup Secret / pairing authorization operations.

No LAN listener, Docker port publication, HTTP admin endpoint, or remote shell protocol is introduced for control.

### 5.4 Window timeout

Manager itself is the primary timeout authority.

The pairing window accepts a bounded duration of 180–600 seconds, default 300 seconds. The controller must close the pairing runtime when the deadline expires even if:

- the Mac disconnects;
- SSH disconnects;
- the host onboarding tool exits;
- the external watchdog fails.

An existing/updated host watchdog may remain as a second layer for transaction reconciliation and verification, but it must no longer depend on Compose override or Manager recreation for normal recovery.

### 5.5 Fail-closed restart behavior

Pairing-window state is ephemeral and is not auto-restored after Manager restart.

If Manager exits during an open window, its sockets disappear with the process. The restarted Manager comes back with normal durable production configuration and pairing closed.

No mechanism may persist “open pairing window” across Manager restart.

## 6. Expected source changes

Expected implementation scope:

1. `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_manager_runtime_wiring.py`
   - attach the dynamic pairing controller to the normal N3-W Manager runtime;
   - keep normal MQTT/Direct/Relay service ownership unchanged.

2. `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_product_runtime.py`
   - only minimal refactoring needed to construct the existing pairing composition from an explicit runtime pairing configuration while normal durable Settings keep pairing disabled.

3. New runtime module for pairing-window control
   - single-window state;
   - local control socket;
   - deadline/timeout;
   - open/status/close;
   - deterministic cleanup;
   - no secret logging.

4. `host/greenhouse-manager/src/greenhouse_manager/ops/n3w_pairing_cli.py`
   - add local commands for window open/status/close;
   - preserve existing Setup Secret/repair/recovery commands.

5. `tools/n3w_t1_first_pairing_onboarding.py`
   - replace Compose override and Manager recreate with calls into the Manager local pairing-window authority;
   - retain one-shot authorization, transaction, TLS checks, first-pair state validation, success evidence and public-safe reporting.

6. Tests and CI
   - add Manager runtime lifecycle coverage;
   - rewrite PR #664 onboarding lifecycle tests around dynamic open/close.

## 7. Code that must be removed from the normal onboarding path

The replacement implementation must eliminate the normal-path dependency on:

- pairing Compose override;
- `docker compose up -d --no-deps --force-recreate manager`;
- factory Manager recreate for close;
- “Manager container ID changed” as proof that pairing opened;
- recovery logic whose normal action is to recreate Manager;
- durable mutation of `GH_N3W_PRODUCT_PAIRING_ENABLED` or `GH_N3W_NODE_BROKER_HOST`.

Historical failure evidence remains in Git/PR history and must not be rewritten away.

## 8. Source and integration test contract

### 8.1 Pairing-window controller

Tests must prove at least:

- default state is closed;
- one open succeeds;
- duplicate/concurrent open is rejected;
- invalid/non-local peer is rejected;
- 180–600 second duration contract is enforced;
- close is bounded and deterministic;
- deadline closes the window automatically;
- Manager shutdown closes the runtime;
- a completed/closed window does not reopen automatically;
- no raw Broker locator or Setup Secret appears in public result/log output.

### 8.2 Real runtime resources

At least one integration path must use real local resources rather than mocking the whole composition:

`CLOSED -> open -> UDP discovery -> HTTP health/pairing surface -> pairing.sock -> close -> all listeners/socket absent`

It must verify real UDP/TCP/Unix-socket closure after close and timeout.

### 8.3 Manager continuity

Opening and closing pairing must not reconstruct the normal Manager MQTT service.

Tests must prove:

- normal Manager service instance remains alive;
- MQTT runtime is not stopped as a side effect of pairing close;
- normal Direct/Relay readers are not closed by pairing-window cleanup;
- pairing-specific database/resource handles are released.

### 8.4 Transaction tests

PR #664 tests must exercise the real transaction parser and state transitions for:

- claim -> open -> successful close;
- claim -> open -> abort;
- claim -> open -> timeout;
- open failure before exposure;
- open failure after partial pairing-runtime construction;
- Manager/control-socket disappearance;
- watchdog failure while Manager deadline still closes exposure;
- success evidence with registration/credential/application-key/peer-trust state;
- old consumed authorization remains non-replayable.

Do not repeat the previous test gap where monkeypatching `_transaction()` bypassed the real state parser.

## 9. CI and independent source review

Before any live action:

1. Manager unit/integration tests PASS.
2. Existing greenhouse-manager CI PASS.
3. Existing N3-W pairing/recovery regression suites PASS.
4. PR #664 onboarding CI PASS.
5. Public repository safety PASS.
6. No unexpected F4/F5 production deployment regressions.
7. Independent source review confirms:
   - no Manager/HA/Broker normal restart in open/close path;
   - no durable Compose/env mutation;
   - Manager self-timeout is the primary exposure-closure authority;
   - local control socket is private and bounded;
   - recovery remains fail-closed;
   - no false-PASS path exists.

Any design-level blocker stops before image production or T1 access.

## 10. Production image and release binding

Because Manager source changes, live acceptance requires a new exact production Manager image.

Before T1 deployment, prove:

- exact source/image binding;
- ARM64 production image;
- required pairing dependencies present;
- existing Manager security settings preserved;
- production Compose still uses host network and no Manager ports;
- Broker and Home Assistant images need not change unless an independent reason is found;
- the applicable release-integrity/F4/F5 checks accept the exact new Manager image.

## 11. Current failed-live-attempt recovery gate

The current T1 failure state is not silently repaired as part of source implementation.

A separate explicit live recovery gate is required after source review/artifact readiness.

Its purpose is only to:

- preserve the consumed old transaction/evidence;
- stop/cancel the obsolete broken watchdog path safely;
- restore/verify normal Manager, Broker and Home Assistant runtime;
- prove 47111/47112 closed;
- prove the old authorization remains consumed and non-replayable.

It is not a second pairing attempt.

## 12. Dynamic-window live pre-acceptance

After deployment of the exact new Manager image, but before Board D pairing:

1. establish healthy Broker/Manager/Home Assistant baseline;
2. open a dynamic pairing window without a Board pairing transaction;
3. prove UDP 47111 and TCP 47112 are available;
4. prove Manager, Broker and Home Assistant container identity/restart counts remain unchanged;
5. prove Home Assistant remains reachable;
6. close the window and prove all pairing exposure is gone;
7. repeat with no manual close and prove Manager self-timeout closes exposure.

Board D pairing is forbidden until both manual-close and self-timeout tests pass.

## 13. Board D first-pair acceptance

Use a completely new one-shot first-pair authorization. Never replay the consumed authorization from the failed attempt.

Acceptance sequence:

`healthy baseline -> dynamic open -> Board D discovery -> private Setup Secret import -> registration/credential/key/trust commit -> dynamic close -> zero-interruption verification`

Success must be based on durable state, not a single log line:

- exactly one approved registration for the new node;
- expected active lease;
- expected credential generation;
- expected application-key state;
- expected peer-trust state;
- no Setup Secret retained in public evidence;
- pairing listeners/socket closed after completion.

## 14. Zero-interruption acceptance

The defining acceptance property is:

> Broker, Manager and Home Assistant remain continuously running throughout the normal pairing window.

For the complete pre-open -> open -> pairing -> close observation:

- Manager container identity must remain unchanged;
- Manager restart count must remain unchanged;
- Broker container identity/restart count must remain unchanged;
- Home Assistant container identity/restart count must remain unchanged;
- Manager production MQTT connectivity remains continuous;
- Home Assistant remains available;
- no Compose/service-group restart is part of normal success.

A successful “restart and recover” does not satisfy this gate.

## 15. Exceptional emergency recovery

If a pairing window reaches its deadline but the product cannot prove that pairing exposure is closed, safety takes priority over zero interruption.

Do not automatically restart the service group inside the normal pairing tool.

Instead stop and require a separate emergency recovery authorization. That recovery gate may use stronger measures, including a Manager/service-group restart, only to eliminate unproven pairing exposure and restore a known-safe baseline.

This is an exceptional fail-safe path, not normal product behavior.

## 16. Explicit non-goals

This task does not reopen:

- Direct -> Relay acceptance;
- Relay -> Direct acceptance;
- multi-relay selection;
- RF coverage;
- long-duration radio continuity;
- Board firmware/OTA/NVS;
- Home Assistant architecture;
- Broker architecture;
- systemd Manager/Home Assistant service split;
- PR #664 merge.

Post-pair telemetry may be recorded if naturally available, but it does not expand the gate into a full radio/failover reacceptance.

## 17. Stop points

Stop before proceeding if any of these occurs:

- normal dynamic open/close restarts Manager or Home Assistant;
- Broker changes unexpectedly;
- pairing exposure remains after close/deadline;
- control-socket state disagrees with actual network exposure;
- runtime Broker locator is persisted into production Compose/env;
- a window can be extended/replayed without a new bounded transaction;
- Manager restart reopens pairing;
- Setup Secret or private locator leaks into public evidence;
- CI artifact and deployed Manager image do not match;
- old failed transaction/evidence is deleted or overwritten;
- old consumed authorization is reused;
- first-pair credential/trust state is partially committed without a safe reconciliation classification.

## 18. Frozen execution sequence

1. fresh source rebind;
2. implement Manager dynamic pairing-window controller;
3. replace PR #664 Manager-recreate onboarding path;
4. run full CI and independent source review;
5. build/bind exact Manager production artifact;
6. separate live recovery of the current failed attempt;
7. deploy/verify new Manager runtime;
8. no-Board dynamic open/close acceptance;
9. no-Board self-timeout acceptance;
10. new Board D one-shot first-pair acceptance;
11. zero-interruption and final closed-exposure verification;
12. GitHub state/evidence closure;
13. STOP before any radio/failover successor.

## 19. Frozen next gate

Next gate is source-only:

`N3W_MANAGER_DYNAMIC_FIRST_PAIRING_WINDOW_SOURCE_REPAIR_20261024_01`

Defaults:

- T1 access: false
- live runtime mutation: false
- Board access: false
- firmware/OTA/NVS: false
- merge: false
- production artifact deployment: false
- automatic entry to the next gate: false

The next conversation must fresh-rebind main, PR #664 and this design document before editing source.
