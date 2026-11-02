# N3W Scan-Triggered First Pairing R6 TLS Bootstrap — Source Implementation Closure

Date: 2026-10-27

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_IMPLEMENTATION_CLOSURE_20261027_01`

## 1. Scope

This document closes the source-implementation review for R6 only.

Included:
- ESP32-C6 selected-candidate TLS bootstrap to T1 port 47110;
- exact selected TLS leaf SHA-256 pinning;
- 47110 confirm/status contracts;
- handoff to existing 47112 simplified pairing;
- final-ACK proof handling;
- durable pending-ACK recovery and terminal cleanup;
- R6 source-contract CI.

Excluded:
- T1 live access or mutation;
- board access or flashing;
- physical end-to-end validation;
- production service start;
- merge.

## 2. Fresh rebind authority

Repository: `chrenguo-stack/HomeAssistant`

Main authority remains:

`2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`

Fresh compare from that SHA to `main` returned identical:
- ahead: 0
- behind: 0
- executable source drift after the R5/docs alignment baseline: none

R6 design/preflight base:

`de1cb7a07e3424182e460569e5b379a0992a572b`

R6 exact source implementation head:

`6283cff57bcd0576968df9fd2440f3aae27331a5`

PR #698:
- open
- draft
- unmerged
- base: `docs/n3w-r6-tls-bootstrap-design-preflight-20261027`
- exact head: `6283cff57bcd0576968df9fd2440f3aae27331a5`

## 3. CI closure

Exact-head CI for `6283cff57bcd0576968df9fd2440f3aae27331a5` completed with:

- SUCCESS: 18
- FAILURE: 0
- QUEUED / IN_PROGRESS: 0
- SKIPPED: 1

The skipped workflow was `N3W T1 fresh bootstrap deployable payload CI`; it was skipped by its workflow condition and is not counted as a source failure.

Previously observed failures on `cd40dd90f3a6ccb3d9a13c0c7519d4afa46f7f61` were repaired as follows:

1. ESP-IDF/lwIP compile failure:
   - `inet_pton` / `AF_INET` were not declared in `n3w_registration_bootstrap_client.cpp`.
   - repair commit: `98513ab2811172e4b4088ad1c276e0073499567a`
   - fix: add `lwip/sockets.h` beside the existing `lwip/inet.h`, matching the established R4/R5 project pattern.

2. R6 source-contract false failure:
   - the new test asserted stale helper names `decrypt_credential_bundle` and `parse_credential_bundle`;
   - the existing pairing implementation actually reuses `decrypt_simple_credential_bundle` and `parse_bundle`;
   - repair commit: `6283cff57bcd0576968df9fd2440f3aae27331a5`
   - no protocol or crypto behavior changed.

Repair delta from `cd40dd90...` to `6283cff...` was limited to two files:
- one added include in `n3w_registration_bootstrap_client.cpp`;
- two source-contract token corrections in the R6 test.

## 4. Independent source closure review

The closure review did not rely only on CI or prior PR comments. The exact source at `6283cff...` was re-read against the R6 design invariants.

### 4.1 TLS bootstrap trust boundary

PASS.

The 47110 transport:
- uses `MBEDTLS_SSL_VERIFY_REQUIRED`;
- supplies the selected host with `mbedtls_ssl_set_hostname` before handshake;
- computes SHA-256 over the received leaf certificate DER;
- compares it against the exact R5-selected leaf fingerprint with constant-time comparison;
- rejects a pin mismatch;
- constructs and writes the wire HTTP request only after `leaf_seen && leaf_matched` is proven.

The JSON request containing the Setup Secret can exist locally before the TLS call, but no Setup Secret byte is transmitted before the exact selected leaf pin is proven.

### 4.2 Bounded network behavior

PASS.

The 47110 transport:
- uses non-blocking `connect()`;
- bounds connect with `select()`;
- verifies `SO_ERROR`;
- restores blocking mode after connect;
- applies read/write socket timeouts plus monotonic TLS/HTTP deadlines;
- rejects redirect responses;
- rejects `Transfer-Encoding`;
- requires explicit `Content-Length`;
- requires JSON content type;
- enforces bounded request, header, and response sizes.

### 4.3 Selected-candidate binding

PASS.

Bootstrap starts only after explicit browser selection of the R5 candidate.

The selected candidate binds:
- manager identity;
- system identity;
- host;
- bootstrap port/path;
- exact TLS leaf SHA-256.

The node does not fall back to selecting a different T1 merely because the selected host failed.

### 4.4 Confirm response and authoritative deadline

PASS.

The confirm response parser requires the exact response shape and verifies:
- accepted status;
- exact selected manager ID;
- exact selected system ID;
- pairing port 47112;
- pairing path `/v2/pairing`;
- allowed same-subnet pairing host;
- remaining lifetime in the defined range.

The manager reports remaining seconds with ceiling semantics. The node subtracts a one-second local safety margin so it never extends the server-owned transaction lifetime due to rounding.

### 4.5 Ambiguous confirm loss

PASS.

If the 47110 confirm response is lost or transport fails:
- the node does not create a fresh pairing ID;
- the node does not create a fresh 1800-second window;
- the durable pairing intent and Setup Secret are preserved;
- a later explicit scan can submit the same transaction identity again and let T1 classify the existing transaction.

A new random pairing ID is created only after authoritative terminal classification or the existing ADR-0008 renewal path.

### 4.6 47112 pairing reuse

PASS.

R6 does not introduce a second pairing protocol.

After 47110 accept, the node calls the existing simplified pairing path and retains the existing:
- hello;
- setup-secret proof;
- HMAC/HKDF derivation;
- encrypted credential bundle;
- credential persistence.

### 4.7 Final ACK false-PASS prevention

PASS.

The node does not interpret HTTP 200 alone as successful registration.

Final success requires parsing the exact final ACK result and matching:
- schema `gh.pair.simple-status/1`;
- same session ID;
- state `consumed`;
- node ID equal to the locally persisted provisional node identity.

If that proof is absent, the node remains in pending recovery.

### 4.8 Durable pending-ACK recovery

PASS.

The pending ACK record now has:
- legacy V1 compatibility;
- current V2 recovery identity;
- pairing ID;
- manager/system identity;
- bootstrap host/port;
- original TLS leaf fingerprint;
- durable state `ACK_PENDING` or `TERMINAL_CLEANUP`.

Legacy V1 records can retry the exact old 47112 ACK but cannot invent 47110 recovery trust.

### 4.9 Status recovery and T1 relocation

PASS.

A V2 pending ACK first tries the persisted 47110 host only if it remains locally safe.

If recovery discovery is required:
- discovery is permitted only because a durable pending ACK already exists;
- a candidate must match exact manager ID;
- exact system ID;
- original TLS leaf fingerprint;
- bootstrap port/path;
- exactly one matching candidate is required.

Ambiguous matches fail closed.

### 4.10 Terminal cleanup crash safety

PASS.

For terminal `expired` / `replay_detected` classification:
1. `TERMINAL_CLEANUP` is persisted first;
2. a new random pairing intent is made durable;
3. provisional Broker state is erased;
4. provisional Peer state is erased;
5. pending ACK is erased last;
6. Setup Secret state is rehydrated if needed for the next explicit registration attempt.

A reboot while cleanup is partially complete resumes the durable terminal-cleanup path instead of treating the partial state as ordinary corruption.

### 4.11 Browser secrecy boundary

PASS.

The local registration page exposes only the selection information needed by the user.

It does not expose:
- Setup Secret;
- TLS fingerprint;
- manager/system internal identity;
- MQTT password.

## 5. False-PASS review

No new source path was found that can declare R6 registration successful by:
- HTTP status alone;
- an unpinned 47110 server;
- a different discovered T1;
- a locally renewed timeout after ambiguous response loss;
- an invalid/ambiguous relocation candidate;
- a legacy pending record with invented bootstrap trust.

No new design-scope source blocker was found in the exact reviewed head.

## 6. Closure result

`R6_SOURCE_IMPLEMENTATION=PASS`

`R6_EXACT_HEAD=6283cff57bcd0576968df9fd2440f3aae27331a5`

`EXACT_HEAD_CI=PASS`

`NEW_SOURCE_BLOCKER_COUNT=0`

`SOURCE_REPAIR_REQUIRED=false`

`PR698_SOURCE_MERGE_READY=true`

This means source implementation is ready from a source-review/CI perspective only. It is not a physical acceptance result and is not merge authorization.

## 7. Remaining boundary

Not executed in this gate:
- T1 live validation;
- board flashing;
- same-boot physical registration;
- power-loss physical recovery;
- actual TLS fingerprint mismatch injection;
- live confirm-response-loss recovery;
- live final-ACK loss recovery;
- merge.

Recommended next gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_PHYSICAL_VALIDATION_PREFLIGHT_20261027_01`

That gate should prepare exact-artifact and physical evidence requirements before any T1 or board mutation.
