# GH H3/N2 Isolated Acceptance Protocol V1

## 1. Scope

This protocol defines the Stage 2D-7 source contract for a later isolated
ESP32-C6 acceptance run. It does not authorize or implement a live device
binding.

The Stage 2D-7 build remains:

- offline at startup;
- read-only at startup;
- without a default Broker;
- without a default persistence key;
- without an MQTT component or command transport;
- without an NVS backend instance;
- without eFuse access;
- without an automatic recovery, validation, activation, or cleanup hook.

Stage 2D-8 must add a separately reviewed driver that binds this protocol to a
dedicated test board, temporary Broker, and explicitly approved test NVS.

## 2. Roles

- **operator**: reviews exact generations and grants one write operation;
- **acceptance package**: enforces command order, authorization consumption,
  redaction, and cleanup prerequisites;
- **isolated driver**: performs the later hardware-specific read, write, MQTT,
  and cleanup operations;
- **volatile test key provider**: holds an operator-injected 32-byte test key in
  RAM and refuses all derivation before loading or after destruction;
- **evidence sink**: receives only the redacted evidence object.

The Stage 2D-7 repository contains only the package interfaces and host model.
It contains no concrete physical-NVS or live-MQTT driver.

## 3. State machine

```text
COLD
  └─ inspect_read_only ───────────────► READ_ONLY
READ_ONLY
  └─ load_test_configuration ─────────► CONFIG_LOADED
CONFIG_LOADED
  └─ grant PREPARE authorization
  └─ prepare_candidate ───────────────► PREPARED
PREPARED
  └─ begin_validation ────────────────► VALIDATING
VALIDATING
  └─ poll_validation(success) ────────► VERIFIED
VERIFIED
  └─ grant ACTIVATE authorization
  └─ activate(marker-last proven) ────► ACTIVATED
PREPARED / VERIFIED / ACTIVATED / FAILED
  └─ export_evidence
  └─ grant CLEANUP authorization
  └─ cleanup_test_state ──────────────► CLEANED

Any authority ambiguity, unconsumed activation authorization, or missing
marker-last proof closes to REBOOT_REQUIRED and quiesces all driver sessions.
```

Illegal order is rejected without silently advancing the state. Operator input
errors such as a missing authorization or an incorrect generation pair remain
retryable. Driver failures are recorded as `FAILED`; authority ambiguity is
terminal and becomes `REBOOT_REQUIRED`.

## 4. Startup and default-off contract

The only first command is `inspect_read_only`.

A valid read-only inspection must report:

- no active MQTT session started by the acceptance package;
- no candidate MQTT session;
- no candidate probe session;
- a read-only observation marker from the driver;
- active and candidate generations, if present;
- persistence and controller state names;
- no increase caused by the inspection in persistent write evidence.

The dedicated test target has Wi-Fi `enable_on_boot: false` and no `mqtt:`
component. Merely compiling ESP-IDF MQTT and NVS support does not instantiate or
start either service.

## 5. Runtime-injected test configuration

The test configuration schema is:

`gh.h3.n2.stage2d7-isolated-test-config/1`

Required non-secret evidence fields:

- firmware commit SHA;
- complete test configuration SHA-256 digest;
- temporary Broker configuration SHA-256 digest;
- test device identifier;
- test run identifier.

Required candidate fields are held only in RAM and are never exported:

- isolated Broker host and port;
- TLS server name;
- temporary CA;
- temporary username and password;
- test-only client ID;
- test-only topic root;
- candidate credential generation.

Isolation constraints:

- system, node, client, device, and run identifiers begin with `gh-test-`;
- topic root begins with `gh-test/`;
- topic root contains the exact test run identifier;
- `homeassistant` and `gh/v1/` are forbidden;
- MQTT wildcards are forbidden;
- candidate generation is nonzero and greater than the observed active
  generation;
- no field has a repository default.

## 6. Volatile test key provider

Stage 2D-7 and Stage 2D-8 do not use eFuse-HMAC.

The test provider:

- contains no compiled key;
- rejects an all-zero key;
- refuses derivation before an explicit RAM load;
- derives test record keys only for a nonzero generation and physical slot;
- zeroizes the RAM key on cleanup, reconfiguration, reboot closure, and object
  destruction;
- has no fallback to `FixedPersistenceKeyProvider` or eFuse;
- is prohibited from production firmware and packages.

The key itself, its digest, and derived keys are not evidence fields.

## 7. Write authorization contract

Every persistent write operation requires a new authorization:

1. `PREPARE_CANDIDATE`;
2. `ACTIVATE_PROFILE`;
3. `CLEANUP_TEST_STATE`.

An authorization is bound to:

- exactly one operation;
- exact active generation;
- exact candidate generation;
- a 64-character operator-provided authorization-record digest.

The digest identifies the reviewed approval record; it is not a device secret
and is still excluded from logs and evidence.

Authorization properties:

- one use only;
- RAM only;
- not cached;
- not inherited from validation;
- not inherited from an earlier write;
- not valid after reconfiguration or reboot;
- not valid if either generation changes;
- activation succeeds only if the driver calls the Stage 2D-6
  `ProfileLifecycleMutationAuthorizer` interface and consumes the grant.

A driver that reports activation success without consuming authorization is
considered unsafe. The package quiesces the driver and requires reboot.

## 8. Command results

Package phases:

- `cold`
- `read_only`
- `config_loaded`
- `prepared`
- `validating`
- `verified`
- `activating`
- `activated`
- `failed`
- `reboot_required`
- `cleaned`

Failure codes:

- `none`
- `invalid_configuration`
- `invalid_state`
- `read_only_inspection_failed`
- `test_key_required`
- `test_configuration_invalid`
- `generation_mismatch`
- `authorization_invalid`
- `authorization_not_armed`
- `authorization_not_consumed`
- `prepare_failed`
- `validation_start_failed`
- `validation_failed`
- `activation_failed`
- `evidence_export_failed`
- `cleanup_requires_evidence`
- `cleanup_failed`
- `reboot_required`

## 9. Evidence format

Schema:

`gh.h3.n2.stage2d7-isolated-evidence/1`

Required fields:

```json
{
  "schema": "gh.h3.n2.stage2d7-isolated-evidence/1",
  "firmware_commit_sha": "<40 lowercase hex>",
  "test_configuration_digest": "<64 lowercase hex>",
  "broker_configuration_digest": "<64 lowercase hex>",
  "test_device_identifier": "gh-test-...",
  "test_run_id": "gh-test-...",
  "phase": "activated",
  "last_command": "export_evidence",
  "final_status_code": "none",
  "active_generation": 2,
  "candidate_generation": 0,
  "persistence_status": "active",
  "controller_phase": "activated",
  "sessions": {
    "active": true,
    "candidate": false,
    "probe": false
  },
  "marker_last_observed": true,
  "failure_injection_point": "none",
  "rollback_completed": false,
  "rollback_result": "not_applicable",
  "persistent_write_count": 2,
  "authorization": {
    "armed": false,
    "consumed": true
  },
  "cleanup_confirmed": false,
  "reboot_required": false,
  "transition_count": 12
}
```

Evidence must never contain:

- Broker host or port;
- TLS server name;
- CA body;
- username or password;
- client credentials;
- raw candidate configuration;
- test key or derived key;
- authorization digest;
- validation nonce;
- complete certificate or MQTT payload.

A second evidence export after cleanup records `cleanup_confirmed=true` while
retaining only the non-secret run and configuration digests.

## 10. Cleanup contract

Cleanup is itself a persistent write and therefore requires a fresh,
generation-bound `CLEANUP_TEST_STATE` authorization.

Cleanup is rejected until at least one evidence export succeeds.

A successful cleanup must prove:

- no active, candidate, or probe session remains;
- temporary candidate state has been removed;
- the driver reports cleanup confirmation;
- volatile test key material is destroyed;
- RAM candidate credentials are zeroized;
- pending authorization is cleared;
- the package reaches `cleaned`.

Cleanup is forbidden in `reboot_required`. Authority must first be recovered by
a separately reviewed Stage 2D-8 procedure.

## 11. Stage 2D-8 physical fault matrix

Stage 2D-7 freezes the following test cases but does not execute them:

| ID | Injection point | Expected safe result | Required evidence |
|---|---|---|---|
| P01 | before PREPARED write | no candidate record | zero new writes, active unchanged |
| P02 | after candidate record, before commit | recovery classifies incomplete write | exact recovery status, no MQTT |
| P03 | after PREPARED commit | PREPARED remains auditable | candidate generation and slot summary |
| V01 | candidate validation interrupted | active session unaffected | probe role stopped, PREPARED retained |
| V02 | candidate TLS hostname mismatch | validation fails | TLS mismatch code, no activation |
| V03 | Broker authentication rejected | validation fails | auth rejection code, active unchanged |
| V04 | network disconnect and recovery | deterministic retry or timeout | timestamps, retry count, final result |
| A01 | verified but not authorized | no write and no runtime switch | authorization_not_armed |
| A02 | stale generation authorization | no write and no runtime switch | generation_mismatch |
| A03 | old active stopped, then power loss | recovery proves authority or quiesces | session role and recovery state |
| A04 | candidate session start failure | old active restored | rollback_completed=true |
| A05 | QoS 1 round-trip timeout | old active restored | failure point and rollback result |
| A06 | active marker write rejected | old active restored; orphan exposed | marker evidence and orphan status |
| A07 | marker write authority unreadable | quiesce and reboot required | no live sessions, reboot_required=true |
| A08 | marker committed, promotion incomplete | quiesce and reboot required | marker committed, promotion incomplete |
| A09 | promotion then immediate reboot | new active recovered exactly | generation equality and session role |
| N01 | NVS read error | fail closed | storage_error, no cleanup attempt |
| N02 | runtime/persistent generation drift | quiesce | both generations and mismatch code |
| R01 | two consecutive rotations | each grant is unique and one-shot | two independent authorization records |
| C01 | cleanup after success | test state removed | cleanup confirmation and zero live sessions |
| C02 | cleanup then first enrollment | clean baseline works | EMPTY recovery followed by new PREPARED |

Each test run uses a unique board identifier, run identifier, Broker credentials,
client IDs, topic root, and authorization records. No run may share production
Mosquitto, Home Assistant Discovery, greenhouse-manager, or node topics.

## 12. Stage boundary

Stage 2D-7 completion proves only source contracts, host behavior, redaction, and
compile compatibility. It does not prove physical NVS atomicity, power-loss
behavior, TLS, Broker ACL, ESP-MQTT callbacks, or ESP32-C6 timing.

No Stage 2D-8 action is authorized by this document.
