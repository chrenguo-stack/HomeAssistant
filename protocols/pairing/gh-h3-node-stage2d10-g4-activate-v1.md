# GH H3/N2 Stage 2D-10 G4 ACTIVATE_PROFILE Protocol V1

## 1. Scope

This protocol defines the recovered-PREPARED first-enrollment activation contract for a later isolated ESP32-C6 run. Source, host-model and compile-only work under this protocol does not authorize a Broker, device, Flash, NVS, eFuse or production operation.

The accepted input is exactly:

```text
active_generation=0
candidate_generation=1
persistence_status=no_active_prepared
candidate_state=PREPARED
```

The only successful mutation is `ACTIVATE_PROFILE`, producing active generation 1 through marker-last commit. `PREPARE_CANDIDATE` must not be repeated and `CLEANUP_TEST_STATE` is outside this stage.

## 2. Recovered-PREPARED adoption

A fresh process after the Stage 2D-9 reboot must not call PREPARE again. It performs:

1. load the volatile test persistence key into RAM;
2. open the dedicated test partition read-only;
3. recover and authenticate candidate generation 1;
4. compare the runtime-injected candidate profile to every persisted credential field;
5. bind the exact recovered candidate to the G4 coordinator;
6. remain network-silent and write-free until validation explicitly begins.

Adoption succeeds only when:

- persistence status is exactly `no_active_prepared`;
- active generation is exactly 0;
- candidate generation is exactly 1;
- the recovered active bundle is absent;
- the recovered candidate bundle is valid;
- schema, system ID, node ID, Broker host/port, TLS server name, CA, MQTT username, client ID, password and generation all match;
- persistent write count does not increase;
- no active, candidate or probe MQTT session is live.

No write authorization is used or inherited during adoption.

## 3. State machine

```text
COLD
  └─ recover_prepared_read_only ─────────► RECOVERED_PREPARED
RECOVERED_PREPARED
  └─ begin_validation ───────────────────► VALIDATING
VALIDATING
  └─ poll_validation(success) ───────────► VERIFIED
VERIFIED
  └─ grant exact ACTIVATE authorization
  └─ activate(marker-last proven) ───────► ACTIVATED
ACTIVATED
  └─ quiesce and automatic restart
  └─ read-only active verification ──────► VERIFIED_AFTER_REBOOT
```

Failure before marker commit must leave persistent PREPARED unchanged and stop transient sessions. Failure after marker authority becomes ambiguous or after marker commit must quiesce all coordinator-owned sessions and require reboot.

## 4. Validation contract

Validation uses one independent probe session and an isolated test-only Broker profile.

Required order:

```text
configure candidate profile
→ create independent probe session
→ TLS and MQTT authentication
→ QoS 1 subscribe acknowledgement
→ publish exact test probe
→ receive exact confirmation topic and payload
→ destroy probe session
→ VERIFIED
```

Validation must not:

- start or replace a production active session;
- mutate persistence;
- consume ACTIVATE authorization;
- use Home Assistant Discovery or `gh/v1/` topics;
- retain the candidate password, CA or payload in public evidence.

## 5. ACTIVATE authorization

Activation requires two matching one-shot authorizations:

- coordinator-level `ProfileLifecycleMutationAuthorizer` approval;
- mirrored physical-driver authorization.

Both bind:

```text
operation=ACTIVATE_PROFILE
active_generation=0
candidate_generation=1
authorization_record_digest=<64 lowercase hex>
```

The grant is RAM-only, valid once, non-replayable, not inherited from PREPARE or validation and cleared on failure, reconfiguration or restart.

If only one layer consumes the grant, authority is ambiguous and the coordinator must quiesce and require reboot.

## 6. Activation ordering

For first enrollment there is no old active session. The exact successful order is:

```text
consume both exact ACTIVATE grants
→ start candidate as activation runtime
→ complete a fresh QoS 1 activation round trip
→ commit persistent active marker last
→ recover/verify active generation 1
→ promote candidate session to active role
→ clear candidate material
```

Persistent marker commit is forbidden before the fresh activation round trip succeeds.

Success requires:

- marker-last observed;
- active generation becomes 1;
- candidate generation becomes 0;
- returned active credentials are valid and generation 1;
- promoted active session is live;
- candidate and probe sessions are not live;
- both authorization layers were consumed exactly once;
- no reboot-required flag.

## 7. Failure closure

### Before marker commit

Candidate validation/start/round-trip failure:

- stop probe/candidate sessions;
- leave `no_active_prepared` authoritative;
- do not increase persistent write count;
- retain PREPARED for a separately reviewed future action;
- do not retry automatically.

Explicit commit rejection before marker authority changes:

- rollback activation runtime;
- prove active generation remains 0 and candidate generation remains 1;
- record failure without claiming activation.

### Authority ambiguous or after marker commit

Any of the following requires `REBOOT_REQUIRED`:

- mirrored authorization cannot be consumed after package authorization consumption;
- marker may have committed but commit result is not authoritative;
- marker-last ordering cannot be proven;
- active generation equals candidate generation after an error;
- candidate promotion fails after marker commit;
- sessions cannot be quiesced deterministically.

No in-memory guess may select active authority.

## 8. Automatic restart verification

After a successful activation, firmware automatically restarts without physical RESET/BOOT. The next boot performs only read-only recovery using the same private test key.

Required post-restart result:

```text
persistence_status=active
active_generation=1
candidate_generation=0
active_digest_match=true
persistent_write_count=0 for the verification process
mqtt_operation_attempted=false
write_authorization_armed=false
write_authorization_consumed=false
```

The verification process does not reconnect the Broker and does not execute activation again.

## 9. Redacted evidence

Public evidence may contain:

- stage, source and Artifact digests;
- test run digest, Broker configuration digest and authorization-record digest hash;
- initial/final generations and persistence states;
- validation/activation success booleans;
- marker-last and write-count evidence;
- session-role booleans;
- rollback/reboot disposition;
- private archive and log SHA-256 values.

Public evidence must not contain:

- Broker address or port;
- CA body;
- username, password or client ID;
- test persistence key or unlock preimage;
- raw authorization digest;
- raw board identifier or serial path;
- raw MQTT topic/payload or serial logs.

## 10. Stage boundary

This protocol does not authorize:

- a test or production Broker connection;
- board connection, erase, Flash, NVS read/write or serial access;
- eFuse, Secure Boot or Flash Encryption operations;
- M401A, T1, Home Assistant, Mosquitto or greenhouse-manager operations;
- cleanup of generation 1;
- Ready, merge, release or deployment.

Physical execution requires a new immutable G4 candidate and a new exact D2 authorization. Ready and squash merge require a later independent D4 decision.
