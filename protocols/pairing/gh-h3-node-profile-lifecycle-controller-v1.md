# GH H3 Node Profile Lifecycle Controller v1

## 1. Scope

This contract defines the Stage 2D-6 assembly that coordinates persistent
profile recovery, independent candidate validation, runtime activation, and
marker-last commit.

The contract does not authorize a physical node, real Broker, physical NVS,
eFuse operation, production startup hook, or automatic credential rotation.

## 2. Controller composition

The controller composes the already verified boundaries:

```text
PairingPersistentStore
+ ProductionCandidateMqttTransport
+ ProductionProfileLifecycleRuntime
+ PairingProfileLifecycleIntegration
+ explicit mutation authorizer
```

The candidate probe session remains separate from both the current active
session and the activation candidate session.

## 3. Startup recovery

`recover_startup()` is read-only. It may inspect authenticated persistent
records and classify the startup state, but it shall not:

- open an MQTT connection;
- validate a PREPARED candidate;
- commit or erase a persistent record;
- perform stale-slot maintenance;
- promote a candidate;
- invoke an automatic lifecycle action.

The required dispositions are:

| Persistent state | Disposition | Runtime action |
| --- | --- | --- |
| EMPTY | UNPAIRED | remain offline |
| ACTIVE | ACTIVE_READY | require explicit active start |
| NO_ACTIVE_PREPARED | PREPARED_FIRST_ENROLLMENT | wait for explicit validation |
| ACTIVE_WITH_PREPARED | ACTIVE_WITH_PREPARED | start active explicitly, then validate candidate |
| ACTIVE plus stale committed slot | ACTIVE_WITH_MAINTENANCE_PENDING | active may start; cleanup remains blocked |
| ACTIVE_WITH_COMMITTED_ORPHAN | ACTIVE_WITH_MAINTENANCE_PENDING | active may start; cleanup remains blocked |
| ACTIVE_WITH_INVALID_INACTIVE | ACTIVE_WITH_MAINTENANCE_PENDING | active may start; cleanup remains blocked |
| NO_ACTIVE_COMMITTED_ORPHAN | FAULT_REBOOT_REQUIRED | no MQTT session |
| INVALID_RECORD / CONFLICT / STORAGE_ERROR | FAULT_REBOOT_REQUIRED | quiesce and require recovery |

A live runtime discovered during recovery must exactly match the authoritative
active generation. Any live candidate session, live probe client, or active
generation mismatch requires fail-closed quiescence.

## 4. Explicit active start

Starting the recovered active profile is a separate method. Recovery alone must
never establish a network connection.

When a promoted active session is already live after a completed controller
transaction, a later recovery may adopt it only if its generation exactly
matches persistent authority.

## 5. Candidate validation

Validation is allowed only for `NO_ACTIVE_PREPARED` or
`ACTIVE_WITH_PREPARED`.

For rotation, the authoritative active session must already be live and match
the recovered active generation. The validation sequence is:

```text
recover PREPARED
→ stage runtime generations
→ generate fresh nonce
→ create independent probe session
→ authenticate and subscribe at QoS 1
→ publish telemetry probe at QoS 1
→ compare complete confirmation topic and payload
→ destroy probe session
```

Validation failure must leave the active marker and active runtime unchanged.

## 6. Mutation authorization

`activate()` requires a per-call `ProfileLifecycleMutationAuthorizer` approval
for `COMMIT_PREPARED_PROFILE` bound to the exact active and candidate
generations.

A missing or denied authorization:

- leaves the controller in VERIFIED;
- does not stop the active session;
- does not start the activation candidate session;
- does not write persistence;
- permits a later explicitly authorized retry.

Authorization is not inferred from startup, validation success, compile-time
configuration, or a previously completed transaction.

## 7. Activation and promotion

After authorization, order remains:

```text
stop old active
→ start activation candidate as sole runtime
→ confirm fresh round trip
→ commit persistent active marker last
→ finalize session-role promotion
```

A successful commit followed by promotion failure is a post-commit ambiguous
runtime state. All sessions must be quiesced and reboot recovery required.

A pre-commit candidate failure shall restore the old active runtime when its
authority is provable. Persistence remains `ACTIVE_WITH_PREPARED` so a later
explicit retry is possible.

## 8. Transaction exclusivity

Only one controller transaction may be in progress. Duplicate recovery,
validation, activation, or reset calls outside their allowed phases must fail
without changing persistent authority.

`reset_transaction()` is permitted only after ACTIVATED, ROLLED_BACK, or FAILED.
It clears controller-local transaction state but may preserve a successfully
promoted active session for exact-generation adoption during the next recovery.

REBOOT_REQUIRED is terminal for the running process and cannot be reset into a
new transaction.

## 9. Stage 2D-6 execution boundary

Stage 2D-6 is limited to source implementation, deterministic host fault matrix,
and ESP32-C6 compile-only verification. It does not:

- connect to a real Broker;
- open or write physical NVS;
- read, provision, or burn eFuse;
- flash or operate an ESP32-C6 board;
- modify M401A, T1, Home Assistant, or Mosquitto;
- add production startup recovery or profile activation;
- modify production `f1_0_rc2.yml` or existing product packages.
