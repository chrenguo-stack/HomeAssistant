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

`inspect` does not create a lock file, staging file, transaction record or runtime override. It does not enter the exclusive mutation lock. Open/close concurrency is protected by a transient kernel `flock` on the already-existing private provisioning directory itself, so lock acquisition creates no persistent filesystem object.

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

The transaction is durably claimed before any pairing exposure. Once claimed:

```text
authorization_consumed=true
replay_allowed=false
```

Before the runtime override is written or Manager recreation begins, the exact running tool bytes are copied into a root-owned mode-0600 current-boot namespace under `/run`, and a transient systemd timer is armed.

The watchdog uses `systemd-run --on-active=` to create a current-boot timer + service. The command line contains only the authorization SHA-256, never the authorization ID, Board/T1 locator, pairing ID or Setup Secret. The transient service uses `Type=exec`, and the tool verifies the timer is actually active before pairing can be opened.

```text
WINDOW_AUTO_CLOSE=true
WATCHDOG_PERSISTENT_UNIT=false
WATCHDOG_CURRENT_BOOT_ONLY=true
WATCHDOG_ARMED_BEFORE_PAIRING_MUTATION=true
WATCHDOG_RAW_LOCATOR_ARGUMENT=false
WATCHDOG_SETUP_SECRET_ARGUMENT=false
OPEN_WINDOW_DEFAULT_SECONDS=300
OPEN_WINDOW_MIN_SECONDS=180
OPEN_WINDOW_MAX_SECONDS=600
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

If Manager recreation has started and post-recreate verification fails, the tool performs one safety rollback to the base Compose Manager configuration and verifies the pairing listeners are closed. This is a rollback of the authorized transition, not a retry of pairing. The watchdog is then cancelled only after the factory-safe state is observed.

If the controlling SSH/operator path disappears, the transient watchdog reaches the durable transaction deadline and performs the same factory restore. A timeout can end only as `CLOSED_TIMEOUT` or `CLOSED_TIMEOUT_PREOPEN`; it can never manufacture `CLOSED_PASS`.

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

Closure first requires the watchdog still to be present for a successful in-window acceptance. It then recreates only Manager from the original base Compose without the override, removes the private runtime override, records `FACTORY_RESTORED`, and only then cancels the transient watchdog. It requires:

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

If the watchdog has disappeared unexpectedly, a successful pairing result is classified `CLOSED_FAIL_WATCHDOG_LOST` after the factory-safe Manager state is restored. If the deadline has already elapsed, it is classified `CLOSED_FAIL_WINDOW_EXPIRED`. Neither can become PASS.

## 8. Persistence and privacy

Private transaction:

```text
/var/lib/n3w-t1-provisioning/FIRST_PAIRING_ONBOARDING.json
```

Private current-boot runtime namespace:

```text
/run/n3w-first-pairing-onboarding/
  manager-pairing.override.yml
  onboarding-watchdog.py
```

The watchdog copy is byte-bound to the claimed tool SHA-256 and is mode-0600. The transient systemd unit name is derived from an authorization hash. No persistent unit file is installed.

The transaction may contain the live peer and Broker locator because it is private target state. Public command output contains only the Broker locator SHA-256.

The runtime override, watchdog tool copy and transient timer are not persistent across reboot. A reboot therefore does not silently reopen pairing. The installed base Compose remains pairing-disabled.

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
- successful close requires approved registration plus committed MQTT credential, N3-W application-key and system peer-trust evidence;
- credential generation/key epoch mismatch and incomplete credential state fail closed;
- system peer-trust identity/generation/key-material validity is required;
- read-only inspect is regression-protected against persistent lock-file creation;
- Compose-return ambiguity is resolved only by final observed factory state;
- watchdog arming precedes any pairing mutation and exposes only authorization hash;
- watchdog timeout restores factory state and can never produce pairing PASS;
- terminal watchdog invocation is read-only/no-op;
- current-boot watchdog copy is exact-byte-bound and private;
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

EXACT_HEAD=79aeaacdd80e76157a4fd2c310df3717ae096dd7
EXACT_HEAD_SOURCE_REVIEW=PASS
EXACT_HEAD_CI=PASS
RELATED_CI=12_OF_12_PASS
PUBLIC_REPOSITORY_SAFETY=PASS
NEW_SOURCE_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false

TASK=N3W_T1_FIRST_PAIRING_ONBOARDING_ACTIVATION_SOURCE_DESIGN_AND_REPAIR_20261024_01
RESULT=CLOSED_PASS

NEXT_ONE_GATE=N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_READONLY_PREFLIGHT_20261024_01
NEXT_GATE_T1_MUTATION=false
NEXT_GATE_BOARD_MUTATION=false
NEXT_GATE_PAIRING_EXECUTION=false
LIVE_PAIRING_REQUIRES_SEPARATE_EXPLICIT_AUTHORIZATION=true
PR664_MERGE=false
```

## 12. Exact-head review findings repaired before live use

The source-only review found and repaired two blockers before any T1/Board execution:

1. an intermediate helper edit accidentally inserted the exact-success count check recursively inside `_security_state_counts()`; this was detected by exact-head source inspection and moved into `_first_pair_success_evidence()`;
2. the first Manager recreation implementation used successful command return as the oracle for whether rollback was needed. A timeout could have meant the recreate happened but the return was lost. The repaired path marks mutation as started before invoking Compose and always uses observed factory state as the safety oracle.

```text
LIVE_T1_IMPACT_FROM_REVIEW_FINDINGS=false
BOARD_IMPACT_FROM_REVIEW_FINDINGS=false
```

### Read-only preflight correction

Exact-head review found that the first implementation wrapped every command, including `inspect`, in a lock helper that created a persistent lock file. Although it did not alter product state, that violated the stated read-only contract. The repaired implementation:

```text
INSPECT_PERSISTENT_MUTATION=false
INSPECT_EXCLUSIVE_MUTATION_LOCK=false
OPEN_CLOSE_LOCK=FLOCK_EXISTING_PRIVATE_DIRECTORY
LOCK_FILE_CREATED=false
```

The transaction writer also validates the already-existing private parent instead of chmod/mkdir-normalizing it as a side effect.

## 13. Bounded-window source review

A later exact-head review found that a ledger deadline alone did not make the pairing exposure bounded: if the operator SSH path vanished after Manager recreation, UDP/47111 and TCP/47112 could remain open indefinitely.

The source repair now makes the deadline operational rather than documentary:

```text
CLAIM
→ exact private watchdog copy under /run
→ transient systemd timer observed active
→ runtime override
→ Manager-only recreate
→ pairing OPEN
→ manual success/abort close OR watchdog timeout
→ factory Manager restored
→ pairing listeners closed
```

The systemd contract was checked against the upstream systemd-run documentation: timer options create a transient timer/service pair, `--on-active=` is a monotonic timer, and `Type=exec` is available for stricter command-start semantics.

Public command-failure diagnostics are also redacted: raw stderr/stdout is not emitted. The tool reports command/return-code plus SHA-256 of the diagnostic text.

```text
PAIRING_WINDOW_LEDGER_ONLY=false
PAIRING_WINDOW_RUNTIME_BOUNDED=true
RAW_COMMAND_ERROR_TEXT_PUBLIC=false
```

## 14. Recovery watchdog fail-open closure

Final exact-head failure review found a blocker in the first bounded-window implementation.

The unsafe sequence was:

```text
Manager onboarding mutation started
→ post-open validation failed
→ immediate factory restore failed
→ transaction marked STOPPED_OPEN_FAILED
→ watchdog cancelled
```

That could remove the last automatic recovery mechanism while the pairing listeners were still potentially exposed.

A second related gap existed at timeout: the first watchdog service was one-shot. If its factory restore failed, no automatic retry was guaranteed.

The repair changes the recovery state machine to:

```text
OPEN validation failure
→ immediate factory restore attempt

restore PASS
→ STOPPED_OPEN_FAILED
→ watchdog may be cancelled
→ factory-safe state already proven

restore FAIL
→ OPEN_RESTORE_PENDING
→ watchdog is NOT cancelled
→ watchdog service is started immediately
→ pending state is nonterminal
→ recovery service retries on failure
→ observed factory-safe state
→ CLOSED_RECOVERY_AFTER_OPEN_FAILURE
```

At deadline:

```text
watchdog restore FAIL
→ TIMEOUT_RESTORE_PENDING
→ service exits nonzero
→ systemd Restart=on-failure
→ RestartSec=10s
→ retry factory restore
→ only observed factory-safe state becomes terminal
```

The transient watchdog service now carries:

```text
Type=exec
Restart=on-failure
RestartSec=10s
```

`OPEN_RESTORE_PENDING` and `TIMEOUT_RESTORE_PENDING` are explicitly nonterminal. Neither can become a pairing PASS.

The source tests now require:

- watchdog arming to include the restart policy;
- immediate open rollback failure to retain/start watchdog recovery;
- no watchdog cancellation on unresolved factory restore;
- timeout restore failure to enter a retryable pending state;
- pending recovery to run immediately rather than wait for the original deadline;
- successful recovery after an open failure to terminate as `CLOSED_RECOVERY_AFTER_OPEN_FAILURE`, never `CLOSED_PASS`.

```text
FAIL_OPEN_RECOVERY_PATH_CLOSED=true
PENDING_RECOVERY_IS_TERMINAL=false
WATCHDOG_RESTORE_RETRY_ENABLED=true
LIVE_T1_IMPACT_FROM_THIS_REVIEW=false
BOARD_IMPACT_FROM_THIS_REVIEW=false
```

## 15. Source closure

Final exact-head closure review completed after the recovery-watchdog repair.

The final review specifically rechecked:

- claim-before-mutation ordering;
- pairing-disabled factory baseline preservation;
- route-selected Broker locator and TLS identity separation;
- Manager-only recreation;
- Broker/Home Assistant continuity;
- read-only `inspect` behavior;
- private transaction metadata and tool binding;
- Setup Secret exclusion from public/runtime command surfaces;
- acknowledged credential/key/peer-trust success evidence;
- watchdog arming before pairing mutation;
- open failure rollback;
- unresolved open rollback retaining automatic recovery;
- deadline timeout recovery;
- watchdog restore failure remaining retryable;
- pending recovery states remaining nonterminal;
- terminal success requiring the watchdog to remain valid through the accepted window;
- public error-output redaction;
- repository private-network-literal safety.

Final CI on exact head:

```text
N3W T1 first-pairing onboarding CI=PASS
Public repository safety CI=PASS
greenhouse-manager CI=PASS
M2 Dynamic Security CI=PASS
M2 private Mosquitto CI=PASS
M2 manager runtime secret ownership CI=PASS
H3 N2 Stage2B3 Pairing Runtime CI=PASS
M2 node auth native board lab CI=PASS
M2 node auth board lab CI=PASS
M2 node auth isolated lab CI=PASS
C-07 node retirement CI=PASS
M0 vertical slice CI=PASS
```

Closure classification:

```text
SOURCE_DESIGN=COMPLETE
SOURCE_REPAIR=COMPLETE
BOUNDED_PAIRING_WINDOW=PASS
FAIL_OPEN_RECOVERY_PATH=PASS
FALSE_PASS_PATH_FOUND_AT_FINAL_REVIEW=true
FALSE_PASS_PATH_REPAIRED=true
NEW_SOURCE_BLOCKER_COUNT=0
SOURCE_GATE=CLOSED_PASS

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
PAIRING_EXECUTION=false
MERGE=false
```

No live authorization is inherited from this source closure.

## 16. Live read-only preflight feedback: absent pairing-only security stores

The first live read-only onboarding preflight reached the accepted factory marker, then stopped while attempting to open one of the pairing-only security databases in read-only SQLite mode.

Initial classification:

```text
CHECKER_FALSE_STOP=true
PRODUCT_FAILURE_PROVEN=false
T1_MUTATION=false
BOARD_D_MUTATION=false
PAIRING_EXECUTION=false
```

Source review confirmed the deeper lifecycle contract:

- the production Manager selector uses the normal simplified N3-W service while `GH_N3W_PRODUCT_PAIRING_ENABLED=false`;
- the product pairing composition is built only after pairing is enabled;
- `credential-lifecycle.sqlite3` and `system-peer-trust.sqlite3` are created by the product pairing composition through its private-database initialization path;
- therefore those two databases may legitimately be absent in the factory pairing-disabled clean baseline;
- `relay-authorization.sqlite3` remains required because the normal N3-W runtime already consumes the application-key provider.

This exposed a source blocker in the first onboarding tool implementation: `_security_state_counts()` treated the two pairing-only databases as mandatory pre-existing files. The result would have been a safe pre-mutation false stop on a valid clean T1.

The repair now defines:

```text
PAIRING_DISABLED_CLEAN_BASELINE:

credential-lifecycle.sqlite3 absent
    => credential_assignments=0

system-peer-trust.sqlite3 absent
    => peer_trust_records=0

relay-authorization.sqlite3 absent
    => FAIL

existing optional DB symlink/non-file
    => FAIL

existing optional DB without expected table
    => FAIL

existing credential or peer-trust rows
    => FIRST_PAIR_SECURITY_STATE_NOT_CLEAN
```

Post-pair success remains strict:

```text
credential_assignments=1
peer_trust_records=1
application_key_active_nodes=1
application_key_epochs=1
```

Regression coverage now includes:

- valid clean baseline with both pairing-only databases absent;
- stale peer-trust state blocking first-pair clean eligibility;
- optional pairing DB symlink failing closed.

This finding re-opened the source gate after the earlier closure. A new exact-head CI and closure review are required before any further live preflight.

```text
PREVIOUS_SOURCE_CLOSURE_SUPERSEDED=true
NEW_SOURCE_BLOCKER_FOUND_BY_LIVE_READONLY_PREFLIGHT=true
SOURCE_BLOCKER_CLASS=VALID_ABSENT_PAIRING_ONLY_DATABASES_REJECTED
SOURCE_REPAIR_IMPLEMENTED=true
T1_MUTATION=false
BOARD_D_MUTATION=false
```

## 17. Source re-closure after live read-only feedback

The source repair for valid absent pairing-only security stores is now closed on exact head:

```text
EXACT_HEAD=1a6839f47c8d3c638683a16bfc8f30c100a4f1f5
N3W_T1_FIRST_PAIRING_ONBOARDING_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI=PASS
GREENHOUSE_MANAGER_CI=PASS
M2_DYNAMIC_SECURITY_CI=PASS
M2_PRIVATE_MOSQUITTO_CI=PASS
M2_MANAGER_RUNTIME_SECRET_OWNERSHIP_CI=PASS
H3_N2_STAGE2B3_PAIRING_RUNTIME_CI=PASS
M2_NODE_AUTH_NATIVE_BOARD_LAB_CI=PASS
M2_NODE_AUTH_BOARD_LAB_CI=PASS
M2_NODE_AUTH_ISOLATED_LAB_CI=PASS
C07_NODE_RETIREMENT_CI=PASS
M0_VERTICAL_SLICE_CI=PASS
RELATED_CI=12_OF_12_PASS
```

Final source classification for the factory clean baseline:

```text
credential-lifecycle.sqlite3:
  absent => clean zero state
  present + expected schema + zero rows => clean zero state
  present with rows => not clean
  symlink/non-file/wrong schema => FAIL

system-peer-trust.sqlite3:
  absent => clean zero state
  present + expected schema + zero rows => clean zero state
  present with rows => not clean
  symlink/non-file/wrong schema => FAIL

relay-authorization.sqlite3:
  must exist
  expected schema required
  active node/key rows must be zero for first-pair clean state
```

Post-pair acceptance remains exact and requires all three credential domains to exist and bind to the same first-registration identity:

```text
credential_assignments=1
peer_trust_records=1
application_key_active_nodes=1
application_key_epochs=1
```

The first live read-only preflight did not consume any live authorization and caused no target mutation.

```text
SOURCE_GATE=CLOSED_PASS
NEW_SOURCE_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false
LIVE_READONLY_PREFLIGHT_CAN_RESUME=true

T1_MUTATION=false
BOARD_D_MUTATION=false
PAIRING_EXECUTION=false
LIVE_AUTHORIZATION_CONSUMED=false
MERGE=false
```

## 18. Live read-only preflight feedback: Python 3.14 strict X.509 default

The resumed live read-only preflight passed the complete factory/clean-state, route-selection and systemd-watchdog checks, but the host-side TLS probe failed with:

```text
ssl.SSLCertVerificationError:
certificate verify failed: Missing Authority Key Identifier
```

Observed target state at the stop remained healthy:

```text
MANAGER_RUNNING=true
BROKER_RUNNING=true
HOMEASSISTANT_RUNNING=true
RESTART_COUNT=0/0/0
PAIRING_ENABLED=false
UDP_47111=0
TCP_47112=0
TCP_8883=1
REGISTRATION_AND_PAIRING_COUNTS=0
PAIRING_ONLY_SECURITY_STORES=ABSENT_AND_ZERO
APPLICATION_KEY_STATE=ZERO
BOARD_D_SOURCE_IS_LOCAL=true
ROUTE_SELECTED_IPV4_PRIVATE=PASS
WATCHDOG_UNIT_COUNT=0
T1_MUTATION=false
BOARD_D_MUTATION=false
PAIRING_EXECUTION=false
```

Independent source review found a checker/source mismatch rather than proof of a Broker runtime failure.

Existing production TLS authorities, including the F4 activation runtime probe and Broker certificate lifecycle probes, explicitly construct:

```text
ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
check_hostname=true
verify_mode=ssl.CERT_REQUIRED
load_verify_locations(CA)
```

The first onboarding tool instead used `ssl.create_default_context()` for its host-side external Broker probe. On the current T1 host Python 3.14 runtime, that default context applies stricter X.509 verification behavior and rejects the currently accepted chain because an Authority Key Identifier extension is absent.

The repair aligns onboarding with the already-established production TLS authority:

- explicit `PROTOCOL_TLS_CLIENT`;
- `CERT_REQUIRED`;
- hostname verification remains enabled;
- the configured private CA remains mandatory;
- SNI/server identity remains `armbian`;
- the live peer DER certificate must additionally hash-match the installed `server.pem`;
- the Manager-namespace Broker probe also uses the explicit context rather than version-dependent `create_default_context()`.

This repair does not disable CA verification or hostname verification and does not accept arbitrary certificates.

Regression coverage now rejects reintroduction of `create_default_context()` into either onboarding TLS probe and asserts the explicit production context contract.

Separate hardening note:

The live result proves the currently deployed certificate chain is not compatible with the stricter Python 3.14 default X.509 policy because of the missing Authority Key Identifier. That is not required to classify the current Broker/runtime as failed because the frozen production TLS authority and runtime clients use the established explicit verification contract. It should nevertheless remain a follow-up certificate-profile hardening item rather than being silently treated as fully strict-X.509-compatible.

```text
CHECKER_FALSE_STOP=true
BROKER_RUNTIME_FAILURE_PROVEN=false
ONBOARDING_TLS_SOURCE_MISMATCH_FOUND=true
SOURCE_REPAIR_IMPLEMENTED=true
STRICT_X509_AKI_HARDENING=FOLLOWUP
T1_MUTATION=false
BOARD_D_MUTATION=false
```

## 19. Source re-closure after Python 3.14 TLS checker mismatch

The TLS probe repair is closed on exact head:

```text
EXACT_HEAD=820afb0f449e38e7937cda635a144b07b4df55d4
RELATED_CI=12_OF_12_PASS
N3W_T1_FIRST_PAIRING_ONBOARDING_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI=PASS
GREENHOUSE_MANAGER_CI=PASS
M2_DYNAMIC_SECURITY_CI=PASS
M2_PRIVATE_MOSQUITTO_CI=PASS
M2_MANAGER_RUNTIME_SECRET_OWNERSHIP_CI=PASS
H3_N2_STAGE2B3_PAIRING_RUNTIME_CI=PASS
M2_NODE_AUTH_NATIVE_BOARD_LAB_CI=PASS
M2_NODE_AUTH_BOARD_LAB_CI=PASS
M2_NODE_AUTH_ISOLATED_LAB_CI=PASS
C07_NODE_RETIREMENT_CI=PASS
M0_VERTICAL_SLICE_CI=PASS
```

Final onboarding TLS authority now matches the established production probe contract:

```text
SSLContext(PROTOCOL_TLS_CLIENT)
check_hostname=true
verify_mode=CERT_REQUIRED
private CA required
server_hostname=armbian
live peer certificate required
live peer certificate SHA256 == installed server.pem SHA256
```

Manager-namespace TLS verification uses the same explicit client context rather than a Python-version-dependent default context.

The live Python 3.14 strict-default failure is therefore classified as a checker mismatch, not as proof of current Broker runtime failure.

```text
SOURCE_GATE=CLOSED_PASS
NEW_SOURCE_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false
LIVE_READONLY_PREFLIGHT_CAN_RESUME=true

STRICT_X509_AKI_HARDENING=FOLLOWUP_NONBLOCKING
T1_MUTATION=false
BOARD_D_MUTATION=false
PAIRING_EXECUTION=false
LIVE_AUTHORIZATION_CONSUMED=false
MERGE=false
```
