# N3-W R2C Board C R2 Closeout Review / Public-Safe Evidence Consolidation

Date: 2026-09-04

## 1. Scope

This document closes the Board C branch of `N3W_THREE_BOARD_REGRESSION_RETEST`.

It consolidates:

- the fresh Board C current-authority read-only preclaim;
- Board C durable registration / credential / application-key / peer-trust / DynSec authority;
- the one-shot physical runtime-liveness observation;
- the two pre-execution harness/operator incidents encountered before the final physical observation.

This closeout does **not** reopen FC4 and does not authorize any further Board access.

```text
NORTH_STAR=N3W_THREE_BOARD_REGRESSION_RETEST
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
FC4_REOPEN=false

BOARD_C_R2_CLOSEOUT_REVIEW=PASS
BOARD_C_ACCESS=false
AUTO_EXECUTE_NEXT=false
```

## 2. Repository / product-source authority

Fresh GitHub read-back at closeout:

```text
CURRENT_REPOSITORY_MAIN_HEAD=
641decb66644c0aa51cdae5154ee50bf527c3c87

CURRENT_REPOSITORY_MAIN_TREE=
be3593b24918c12693b418844bf763cd22001bc2
```

The current `main` commit is the documentation-only merge of PR #356 and explicitly
states that product source remains unchanged.

Frozen deployed authorities remain:

```text
FROZEN_DEPLOYED_PRODUCT_MANAGER_SOURCE=
8fbedc7e0778ce91d146cd5f0772bebdd20ad13a

FROZEN_DEPLOYED_PRODUCT_SOURCE_TREE=
77b5d89164bdb966555938f838804522fe865f7e

FROZEN_BOARD_FIRMWARE_SOURCE=
739d9af2bac78a3a59f92a4ae345d8f1b1dc15ab
```

Documentation-only repository movement does not redefine deployed product-source
authority.

## 3. Public-safe Board C identity binding

No raw NODE_ID, SYSTEM_ID, MQTT username/client ID, hardware identity, pairing
identity, USB serial, MAC address, T1 locator, credential material, private key,
Setup Secret, raw serial output, raw Broker log, or raw Manager log is included.

```text
CURRENT_SYSTEM_ID_SHA256=
f300f10844ecfc75f12a0deb789ce9ddb41209c38307e65436e81d43ad4658d9

BOARD_C_USB_ID_SHA256=
f889b2d278a5fae4c21d6697f1f149c723026d54898243674fdf1c0e68268ae5

BOARD_C_HARDWARE_ID_SHA256=
d6ef3f98a35f06a5a8b8e7716a015e17336242128b314a1b3244b114fc6f72e2

BOARD_C_NODE_ID_SHA256=
73cd4e91562d425ec90acd114b622ee448680b5e011742744eb15fe54e9dd497

BOARD_C_CURRENT_PAIRING_ID_SHA256=
2861ead5a41a865f98d19843222561d5bf0d512b634d8ab6020d7ea0d5fe9489

BOARD_C_CURRENT_IDENTITY_UNIQUE=true
BOARD_C_USB_BINDING=PASS
```

## 4. Fresh current Manager / Broker authority

The final successful preclaim rebound the exact current Manager and Broker before
any Board C serial access:

```text
PRE_RUNTIME_AUTHORITY_EXACT=true
POST_RUNTIME_AUTHORITY_EXACT=true
MANAGER_SOURCE_EXACT=true

MANAGER_RESTART_COUNT=0
BROKER_RESTART_COUNT=0

BROKER_CONFIG_SHA256=
a55c2479df1e9ff1d5547edf487f38e7a2edca0b57ccf5dfb7a590dd331a4848

DYNSEC_SHA256=
4c62fe66a99b1a6366c8d82c091ab87a90e772ca1796058b4982c95b091e4327

DYNSEC_CHANGEINDEX=35

READONLY_SNAPSHOT_RUNTIME_CONTINUITY=true
SNAPSHOT_REQUIRED_AUTHORITY_COMPLETE=true
SNAPSHOT_READONLY_BOUNDARY_PRESERVED=true
```

## 5. Board C durable registration lineage

The fresh current-authority preclaim found exactly one current Board C lineage
candidate and proved the current stable identity while preserving historical retired
identity history:

```text
BOARD_C_LINEAGE_CANDIDATE_COUNT=1
BOARD_C_CURRENT_IDENTITY_UNIQUE=true

BOARD_C_PAIRING_STATE=approved
BOARD_C_PAIRING_AUDIT_EPOCH=991
BOARD_C_REPAIR_AUTHORIZED=false

BOARD_C_CURRENT_ACTIVE_LEASE_COUNT=1
BOARD_C_CURRENT_OPEN_HISTORY_COUNT=1

BOARD_C_PRIOR_RETIRED_LEASE_COUNT=1
BOARD_C_PRIOR_RELEASED_HISTORY_COUNT=1

BOARD_C_CURRENT_REGISTRATION_AUTHORITY=PASS
```

`BOARD_C_PAIRING_AUDIT_EPOCH=991` is a Manager-local compatibility/audit sequence.
It is not numerically compared with MQTT credential generation, N3-W application-key
epoch, or peer-trust generation.

## 6. Credential lifecycle authority

```text
BOARD_C_CURRENT_CREDENTIAL_ASSIGNMENT_COUNT=1
BOARD_C_CREDENTIAL_NODE_MATCH=true
BOARD_C_CREDENTIAL_PAIRING_MATCH=true

BOARD_C_CREDENTIAL_STATE=active
BOARD_C_ACTIVE_CREDENTIAL_GENERATION=1

BOARD_C_CURRENT_CREDENTIAL_AUTHORITY=PASS
```

The executor's raw normalized display rendered Python `None` as:

```text
BOARD_C_PENDING_CREDENTIAL_GENERATION=UNKNOWN
```

However, the credential-authority PASS predicate required `pending_generation is None`.
For closeout semantics this is therefore normalized as:

```text
BOARD_C_PENDING_CREDENTIAL_GENERATION=NONE
```

This is a presentation-normalization issue, not an evidence gap.

## 7. Application-key and peer-trust authority

```text
BOARD_C_APPLICATION_KEY_NODE_ROW_COUNT=1
BOARD_C_APPLICATION_KEY_NODE_ACTIVE=true

BOARD_C_APPLICATION_KEY_EPOCH_ROW_COUNT=1
BOARD_C_APPLICATION_KEY_ACTIVE_COUNT=1
BOARD_C_APPLICATION_KEY_GRACE_COUNT=0
BOARD_C_APPLICATION_KEY_STAGED_COUNT=0
BOARD_C_APPLICATION_KEY_ENABLED_RUNTIME_COUNT=1
BOARD_C_APPLICATION_KEY_MAX_EPOCH=1

BOARD_C_CURRENT_APPLICATION_KEY_AUTHORITY=PASS

CURRENT_SYSTEM_PEER_TRUST_ROW_COUNT=1
CURRENT_SYSTEM_PEER_TRUST_GENERATION=1
CURRENT_SYSTEM_PEER_TRUST_KEY_LENGTH_VALID=true

BOARD_C_CURRENT_PEER_TRUST_AUTHORITY=PASS
```

Credential generation, application-key epoch, and peer-trust generation are separate
lifecycle authorities. Their values happen to be `1` here but are not treated as a
single coupled epoch.

## 8. Dynamic Security authority

The current Board C MQTT identity is uniquely present in current DynSec and is bound
to the expected role and current-system namespace:

```text
BOARD_C_DYNSEC_CLIENT_UNIQUE=true
BOARD_C_DYNSEC_ROLE_UNIQUE=true

BOARD_C_DYNSEC_CLIENT_EXACT=true
BOARD_C_DYNSEC_ROLE_BINDING_EXACT=true

BOARD_C_DYNSEC_ENCODED_PASSWORD_PRESENT=true
BOARD_C_DYNSEC_PLAINTEXT_PASSWORD_ABSENT=true

BOARD_C_DYNSEC_ACL_SEMANTIC_EXACT=true
DYNSEC_DEFAULT_ACCESS_EXACT=true
BOARD_C_DYNSEC_CURRENT_NAMESPACE_BOUND=true

BOARD_C_CURRENT_DYNSEC_AUTHORITY=PASS
```

## 9. Current-authority preclaim closure

The corrected current-authority preclaim completed:

```text
HIGH_LEVEL_R2C_CURRENT_AUTHORITY_ADJUDICATION=PASS

R2C_BOARD_C_CURRENT_AUTHORITY_CONSOLIDATED_READONLY_PRECLAIM=PASS

BOARD_C_RUNTIME_BASELINE_BOUND=true
BOARD_C_SECURITY_BASELINE_BOUND=true
BOARD_C_CURRENT_IDENTITY_BOUND=true

READY_FOR_BOARD_C_R2_RUNTIME_LIVENESS_OBSERVATION=true
```

At this point runtime liveness itself remained unclaimed until the separate physical
observation.

## 10. Physical runtime-liveness observation

One exact Board C USB identity was found, no process already had the serial device
open, and the authorization was claimed only immediately before the read-only serial
open.

```text
ESPRESSIF_USB_IDENTITY_COUNT=1
BOARD_C_USB_BINDING=PASS
BOARD_C_SERIAL_PORT_COUNT=1
SERIAL_DEVICE_OPEN_PROCESS_COUNT=0

AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CLAIM_POINT=BEFORE_SERIAL_OPEN
```

The observation used a 20-second stabilization window followed by a 50-second
verification window:

```text
BOARD_C_SERIAL_READ=PASS

STABILIZATION_SECONDS=20
VERIFICATION_SECONDS=50
TOTAL_SERIAL_OBSERVATION_SECONDS=70

STABILIZATION_PAIRING_PAYLOAD_COUNT=0

VERIFICATION_PAIRING_PAYLOAD_COUNT=0
VERIFICATION_RESET_MARKER_COUNT=0

VERIFICATION_TELEMETRY_COUNT=10
VERIFICATION_TELEMETRY_SEQ_STRICTLY_INCREASING=true

VERIFICATION_TELEMETRY_ACCEPTED_COUNT=10
VERIFICATION_TELEMETRY_REJECTED_COUNT=0

VERIFICATION_DIRECT_TELEMETRY_COUNT=10
VERIFICATION_DIRECT_ACCEPTED_COUNT=10

VERIFICATION_TELEMETRY_SPAN_SECONDS=45.008

BOARD_C_SERIAL_LIVENESS_ORACLE=true
```

## 11. Board-to-Manager durable correlation

The same Direct telemetry sequence set was correlated with current Manager durable
state:

```text
RUNTIME_AUTHORITY_CONTINUITY=true
BOARD_C_SECURITY_BASELINE_CONTINUITY=true

CANONICAL_CURSOR_PRE_PRESENT=true
CANONICAL_CURSOR_POST_PRESENT=true
CANONICAL_CURSOR_SAME_BOOT=true
CANONICAL_CURSOR_ADVANCED=true
CANONICAL_POST_LAST_SOURCE_DIRECT=true

SERIAL_VERIFICATION_REPLAY_MATCH_COUNT=10
SERIAL_VERIFICATION_REPLAY_ALL_MATCHED=true
SERIAL_TO_MANAGER_REPLAY_CORRELATION=true
```

Broker and Manager runtime evidence remained non-rejecting:

```text
BROKER_LOG_READ_SUCCESS=true
MANAGER_LOG_READ_SUCCESS=true

BROKER_BOARD_C_AUTHORIZATION_DENIAL_COUNT=0
BROKER_BOARD_C_DISCONNECT_COUNT=0
BROKER_BOARD_C_CONNECT_COUNT=0

MANAGER_BOARD_C_ACCEPT_DIRECT_INFO_COUNT=16
MANAGER_BOARD_C_REJECT_DIRECT_COUNT=0

NO_BROKER_AUTHORIZATION_DENIAL_OBSERVED=true
NO_MANAGER_DIRECT_REJECTION_OBSERVED=true

MANAGER_ACCEPT_INFO_LOG_IS_AUXILIARY=true
```

`BROKER_BOARD_C_CONNECT_COUNT=0` is not a failure condition: this Gate did not require
a reconnect, and current runtime continuity plus the observed Direct→Manager durable
pipeline proves the existing connection/data path remained live.

## 12. Runtime-liveness adjudication

The combined physical serial evidence, exact current security/runtime authority,
10/10 replay correlation, same-boot canonical-cursor advancement, and absence of
authorization/rejection evidence establish Board C runtime liveness.

```text
HIGH_LEVEL_R2C_RUNTIME_LIVENESS_ADJUDICATION=PASS

R2C_BOARD_C_RUNTIME_LIVENESS_OBSERVATION=PASS
R2_BOARD_C_RUNTIME_LIVENESS=PASS

BOARD_C_POST_RECOVERY_RUNTIME_LIVENESS=PASS
BOARD_C_RUNTIME_BASELINE_BOUND=true
BOARD_C_SECURITY_BASELINE_CONTINUITY=true

BOARD_C_PAIRING_QUIESCENCE_PROVEN=true
BOARD_C_DIRECT_RUNTIME_HEALTHY=true
BOARD_C_CURRENT_SYSTEM_NAMESPACE_RUNTIME_PROVEN=true

BROKER_QOS1_APPLICATION_ACCEPTANCE_PROVEN=true
BROKER_TO_MANAGER_DIRECT_DELIVERY_PROVEN=true
MANAGER_ACCEPTED_PIPELINE_PROVEN=true
MANAGER_DURABLE_REPLAY_CORRELATION_PROVEN=true

PRODUCT_REGRESSION_PROVEN=false
```

Packet-level evidence remains deliberately narrower:

```text
PACKET_LEVEL_PUBACK_CAPTURE_PERFORMED=false
WIRE_LEVEL_PUBACK_FRAME_DIRECTLY_OBSERVED=false
```

No wire-level PUBACK frame is claimed. A separate Broker debug mutation is not
required for R2 runtime-liveness closure.

## 13. One-shot authorization closeout

```text
AUTHORIZATION=
R2C-BOARD-C-RUNTIME-LIVENESS-OBSERVATION-20260904-01

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

AUTHORIZATION_RESULT=EVIDENCE_COMPLETE
REPLAY_PERMITTED=false
```

This authorization is permanently non-replayable.

## 14. Safety / mutation boundary

The successful physical Gate remained read-only:

```text
BOARD_ACCESS=true
USB_ACCESS=true
SERIAL_OPEN=true

SERIAL_WRITE=false
SERIAL_WRITE_BYTE_COUNT=0
DTR_RTS_EXPLICIT_TOGGLE=false

BOARD_RESET=false
BOOT_BUTTON_ACTION=false
POWER_CYCLE=false

FLASH_READ=false
FLASH_WRITE=false

NVS_READ=false
NVS_ERASE=false
NVS_MUTATION=false

PAIRING_RECOVERY=false
CREDENTIAL_RECOVERY=false

MANAGER_MUTATION=false
BROKER_MUTATION=false
DYNSEC_MUTATION=false
HOMEASSISTANT_MUTATION=false
DATABASE_MUTATION=false
SERVICE_RESTART=false

BROKER_DEBUG_CONFIG_MUTATION=false
```

## 15. Explicit remaining boundary

```text
REBOOT_PERSISTENCE_TESTED=false
```

No operator-induced RESET, BOOT action, power-cycle, or reboot was performed in the
Board C R2 runtime-liveness observation. This closeout therefore does not claim reboot
persistence.

That boundary does not block the R2 runtime-liveness closure because the current task
was current-runtime liveness, not reboot-persistence validation.

## 16. Incidents encountered during Board C R2

### Incident C-R2-01 — procroot SQLite path-domain failure

The first current-authority executor successfully rebound current Manager/Broker but
then failed with:

```text
REMOTE_ERROR_CLASS=OperationalError
```

The error hash matched SQLite `unable to open database file`.

The executor attempted host-side SQLite access through a
`/proc/<manager-pid>/root/...` path-domain. No Board access occurred and no live
authorization was claimed.

Classification:

```text
DOMAIN=PHYSICAL_HARNESS
FAILURE_CLASS=SQLITE_PROCROOT_PATH_DOMAIN_OPEN_FAILURE

CURRENT_RUNTIME_AUTHORITY_FAILURE_PROVEN=false
BOARD_C_FAILURE_PROVEN=false
DATABASE_CORRUPTION_PROVEN=false
PRODUCT_REGRESSION_PROVEN=false
```

The corrected executor moved the SQLite read into the exact current Manager container
namespace and used `mode=ro + PRAGMA query_only=ON`; the successor preclaim then PASSed.

This incident maps to the existing recovery/runtime DB path-domain guard family
(KF-045) rather than a product defect.

### Incident C-R2-02 — Board C not connected before physical preclaim

The first physical liveness invocation stopped before authorization claim:

```text
ESPRESSIF_USB_IDENTITY_COUNT=0
BOARD_C_USB_BINDING=FAIL

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

BOARD_ACCESS=false
SERIAL_OPEN=false
```

The operator then confirmed Board C had not been connected.

Classification:

```text
DOMAIN=OPERATOR_PRECONDITION
FAILURE_CLASS=BOARD_C_NOT_CONNECTED

USB_ORACLE_DEFECT_PROVEN=false
BOARD_C_FAILURE_PROVEN=false
PRODUCT_REGRESSION_PROVEN=false
```

Because the authorization had never been claimed or consumed, the exact same
preclaim was legitimately retried after connecting Board C. The second invocation
bound exactly one Board C USB identity and proceeded to successful evidence collection.

No new global KF number is assigned by this local closeout artifact.

## 17. Known-failure / regression-guard disposition

Relevant existing guards remain applicable:

```text
KF-010=GUARDED
KF-045=GUARDED
KF-058=GUARDED
KF-071=GUARDED
KF-072=OPEN
KF-078=GUARDED
KF-082=GUARDED
KF-083=GUARDED
```

Key enforcement for this route:

- use the exact runtime/container namespace for DB authority when host-path/procroot
  semantics are ambiguous;
- preserve UNKNOWN as UNKNOWN until independently observed;
- keep physical serial capture bound to one exact device and a no-write/no-reset
  contract;
- do not treat an auxiliary Manager INFO line as the sole product oracle;
- do not promote packet-level PUBACK capture to a runtime-liveness prerequisite once
  the durable end-to-end chain is proven.

## 18. Final Board C R2 closure

```text
BOARD_C_CURRENT_AUTHORITY=PASS
BOARD_C_SECURITY_STATE_AUTHORITY=PASS
BOARD_C_PAIRING_QUIESCENCE=PASS
BOARD_C_RUNTIME_LIVENESS=PASS

R2_BOARD_C_RUNTIME_LIVENESS=PASS
BOARD_C_POST_RECOVERY_RUNTIME_LIVENESS=PASS
BOARD_C_R2_CLOSEOUT_REVIEW=PASS

PRODUCT_REGRESSION_PROVEN=false
REBOOT_PERSISTENCE_TESTED=false
```

Board C is closed for the current R2 runtime-liveness route.

## 19. Three-board R2 status

```text
BOARD_A_R2=FROZEN_PASS
BOARD_B_R2=FROZEN_PASS
BOARD_C_R2=FROZEN_PASS

N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=ALL_THREE_BOARDS_PASS

PRODUCT_REGRESSION_PROVEN=false
```

## 20. Route handoff

```text
READY_FOR_N3W_THREE_BOARD_REGRESSION_RETEST_CLOSEOUT_REVIEW=true

BOARD_ACCESS=false
AUTO_EXECUTE_NEXT=false
```

The next logical Gate is the overall `N3W_THREE_BOARD_REGRESSION_RETEST_CLOSEOUT_REVIEW`.
This document itself does not authorize further physical Board access.

## 21. Repository references

Relevant current repository records include:

- `docs/development/N3W_FC4_FINAL_PHYSICAL_ACCEPTANCE_CLOSURE_V1.0_20260831.md`
- `docs/development/N3W_R2A_BOARD_A_RUNTIME_NAMESPACE_RECOVERY_CLOSEOUT_20260903.md`
- `docs/development/N3W_R2B_BOARD_B_R2_CLOSEOUT_REVIEW_PUBLIC_SAFE_20260904.md`
- `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`

This Board C closeout is archived in the repository as a public-safe documentation record.
No runtime, board, firmware, credential, or security-state mutation is authorized by this file.
