# N3-W R2B Board B R2 Closeout Review / Public-Safe Evidence Consolidation

Date: 2026-09-04

## Scope

This document closes the Board B branch of `N3W_THREE_BOARD_REGRESSION_RETEST`.
It consolidates the already-proven existing-identity credential recovery, current
Manager/Broker/security authority, post-recovery physical runtime liveness, and the
later Broker-observability harness detour.

This closeout does not reopen FC4 and does not authorize Board C access.

```text
NORTH_STAR=N3W_THREE_BOARD_REGRESSION_RETEST
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
FC4_REOPEN=false
BOARD_B_R2_CLOSEOUT_REVIEW=PASS
BOARD_C_ACCESS=false
AUTO_EXECUTE_NEXT=false
```

## Repository / product-source authority

```text
CURRENT_REPOSITORY_MAIN_HEAD=8dc92d36a388b164ae448dad9e61f1df3a565e93
CURRENT_REPOSITORY_MAIN_TREE=603c4fb6758e767e0482641c4363b092ff2be346
FROZEN_DEPLOYED_PRODUCT_MANAGER_SOURCE=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
FROZEN_DEPLOYED_PRODUCT_SOURCE_TREE=77b5d89164bdb966555938f838804522fe865f7e
FROZEN_BOARD_FIRMWARE_SOURCE=739d9af2bac78a3a59f92a4ae345d8f1b1dc15ab
```

Repository `main` movement after the deployed product revision is documentation-only
for this closeout and does not redefine deployed product-source authority.

## Public-safe Board B identity binding

No raw NODE_ID, SYSTEM_ID, MQTT identity, hardware identity, pairing identity,
USB serial, MAC address, T1 locator, credential material, or raw runtime log is
included.

```text
FROZEN_BOARD_B_USB_ID_SHA256=1181e146226e13f86788d1df8f1333778bbcb5da1650dd990633155c79923783
FROZEN_BOARD_B_HARDWARE_ID_SHA256=cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0
FROZEN_BOARD_B_CURRENT_PAIRING_ID_SHA256=9fc5789d1efdb5170ca7e83d476459016f330fe3d767b34cb91e11781b0fc565
FROZEN_BOARD_B_NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
BOARD_B_PHYSICAL_IDENTITY_BOUND=true
```

## Existing-identity credential recovery closure

The separately authorized Board B recovery completed once and is permanently
non-replayable.

```text
PAIRING_STATE=approved
CREDENTIAL_STATE=active
CREDENTIAL_GENERATION_BEFORE=1
CREDENTIAL_GENERATION_AFTER=2
PENDING_GENERATION_AFTER=NONE
APPLICATION_KEY_EPOCH_BEFORE=1
APPLICATION_KEY_EPOCH_AFTER=1
APPLICATION_KEY_MATERIAL_PRESERVED=true
PEER_TRUST_GENERATION_BEFORE=1
PEER_TRUST_GENERATION_AFTER=1
PEER_KEY_MATERIAL_PRESERVED=true
BROKER_CHANGEINDEX_BEFORE=30
BROKER_CHANGEINDEX_AFTER=31
BROKER_CHANGEINDEX_DELTA=1
BROKER_TARGET_CLIENT_EXACT=true
BROKER_TARGET_ROLE_EXACT=true
BROKER_TARGET_ROLE_BINDING_EXACT=true
BROKER_TARGET_ACL_SEMANTIC_EXACT=true
BROKER_TARGET_ENCODED_PASSWORD_ROTATED=true
BROKER_TARGET_PLAINTEXT_CREDENTIAL_FIELDS_ABSENT=true
NON_TARGET_BROKER_SEMANTIC_PRESERVED=true
BOARD_B_DURABLE_WRITE_EVIDENCE=VALID_RECEIPT_COMMIT_CHAIN_WITH_GENERATION2_ACTIVE
BOARD_B_DURABLE_WRITE_OBSERVED=true
BOARD_A_MUTATION=false
BOARD_C_MUTATION=false
FLASH=false
NVS_ERASE=false
MANUAL_RESET=false
MUTATION_CLOSURE_PASS=true
```

The exact recovery path preserved stable identity and the application/peer-trust key
lifecycles while rotating only the existing MQTT credential generation.

## Fresh current Manager / Broker / security authority

A later fresh security-state authority recovery snapshot rebound Board B to the
current running Manager/Broker and established the current semantic baseline.

```text
CURRENT_MANAGER_RUNNING=true
CURRENT_MANAGER_RESTART_COUNT=0
CURRENT_MANAGER_DEPLOYED_SOURCE_BOUND=true
CURRENT_BROKER_RESTART_COUNT=0
CURRENT_BROKER_CONFIG_SHA256=a55c2479df1e9ff1d5547edf487f38e7a2edca0b57ccf5dfb7a590dd331a4848
CURRENT_DYNSEC_SHA256=4c62fe66a99b1a6366c8d82c091ab87a90e772ca1796058b4982c95b091e4327
CURRENT_DYNSEC_CHANGEINDEX=35
BOARD_B_PAIRING_STATE=approved
BOARD_B_CREDENTIAL_STATE=active
BOARD_B_ACTIVE_CREDENTIAL_GENERATION=2
BOARD_B_PENDING_CREDENTIAL_GENERATION=NONE
BOARD_B_APPLICATION_KEY_EPOCH=1
BOARD_B_APPLICATION_KEY_BOUND=true
BOARD_B_PEER_TRUST_GENERATION=1
BOARD_B_SYSTEM_PEER_TRUST_BOUND=true
BOARD_B_DYNSEC_ROLE_BINDING_MATCH=true
BOARD_B_DYNSEC_ACL_SEMANTIC_EXACT=true
BOARD_B_DYNSEC_CURRENT_NAMESPACE_BOUND=true
BOARD_B_SECURITY_LIFECYCLE_SEPARATION_PRESERVED=true
BOARD_B_SECURITY_SEMANTIC_30S_STABILITY=true
R2B_BOARD_B_SECURITY_STATE_AUTHORITY_RECOVERY_SNAPSHOT=PASS
CURRENT_MANAGER_RUNTIME_REBASE_SAFE=true
BOARD_B_RUNTIME_BASELINE_BOUND=true
```

Pairing epoch, MQTT credential generation, N3-W application-key epoch, and peer-trust
generation are separate lifecycle authorities and are not numerically compared.

## Post-recovery physical runtime liveness

The final physical observation used a 20-second stabilization window followed by a
50-second authoritative verification window.

```text
STABILIZATION_PAIRING_PAYLOAD_COUNT=0
VERIFICATION_PAIRING_PAYLOAD_COUNT=0
VERIFICATION_RESET_MARKER_COUNT=0
VERIFICATION_TELEMETRY_COUNT=10
VERIFICATION_TELEMETRY_SEQ_STRICTLY_INCREASING=true
VERIFICATION_TELEMETRY_ACCEPTED_COUNT=10
VERIFICATION_TELEMETRY_REJECTED_COUNT=0
VERIFICATION_DIRECT_TELEMETRY_COUNT=10
VERIFICATION_DIRECT_ACCEPTED_COUNT=10
VERIFICATION_TELEMETRY_SPAN_SECONDS=45.002
BOARD_B_SERIAL_LIVENESS_ORACLE=true
```

The same observed Direct sequence set was correlated with current Manager durable
state:

```text
RUNTIME_AUTHORITY_CONTINUITY=true
BOARD_B_SECURITY_BASELINE_CONTINUITY=true
CANONICAL_CURSOR_PRE_PRESENT=true
CANONICAL_CURSOR_POST_PRESENT=true
CANONICAL_CURSOR_SAME_BOOT=true
CANONICAL_CURSOR_ADVANCED=true
CANONICAL_POST_LAST_SOURCE_DIRECT=true
SERIAL_VERIFICATION_REPLAY_MATCH_COUNT=10
SERIAL_VERIFICATION_REPLAY_ALL_MATCHED=true
SERIAL_TO_MANAGER_REPLAY_CORRELATION=true
BROKER_BOARD_B_AUTHORIZATION_DENIAL_COUNT=0
MANAGER_BOARD_B_REJECT_DIRECT_COUNT=0
NO_BROKER_AUTHORIZATION_DENIAL_OBSERVED=true
NO_MANAGER_DIRECT_REJECTION_OBSERVED=true
```

## Runtime-liveness adjudication

The physical Direct evidence, current Broker/Manager authority, exact 10/10 replay
correlation, and same-boot canonical-cursor advancement jointly establish Board B
runtime liveness.

```text
HIGH_LEVEL_R2B_RUNTIME_LIVENESS_ADJUDICATION=PASS
R2B_BOARD_B_RUNTIME_LIVENESS_OBSERVATION=PASS
R2_BOARD_B_RUNTIME_LIVENESS=PASS
BOARD_B_POST_RECOVERY_RUNTIME_LIVENESS=PASS
BOARD_B_RUNTIME_BASELINE_BOUND=true
BOARD_B_PAIRING_QUIESCENCE_PROVEN=true
BOARD_B_DIRECT_RUNTIME_HEALTHY=true
BROKER_QOS1_APPLICATION_ACCEPTANCE_PROVEN=true
BROKER_TO_MANAGER_DIRECT_DELIVERY_PROVEN=true
MANAGER_ACCEPTED_PIPELINE_PROVEN=true
MANAGER_DURABLE_REPLAY_CORRELATION_PROVEN=true
PRODUCT_REGRESSION_PROVEN=false
```

The narrower packet-level claim remains explicit:

```text
PACKET_LEVEL_PUBACK_CAPTURE_PERFORMED=false
WIRE_LEVEL_PUBACK_FRAME_DIRECTLY_OBSERVED=false
```

A separate wire-level PUBACK capture is not claimed and is not required to reopen the
already-proven end-to-end durable runtime-liveness chain.

## Broker-observability detour

Three later attempts to obtain Board-A-style Broker debug evidence did not produce
product-failure evidence and are classified as harness/runtime-authority incidents.

### Attempt 01

The executor used host-path atomic replacement for the single-file bind-mounted
Broker config. The running Broker did not observe the candidate. Exact restore was
proven. The executor result envelope also emitted `REMOTE_RESULT_OK=true` while
observation evidence was incomplete; high-level adjudication correctly followed
`EVIDENCE_COMPLETE=false` and UNKNOWN facts instead of the misleading envelope.

### Attempt 02

The executor preserved the host pathname inode while writing candidate bytes, but the
running Broker still did not observe the candidate. A read-only authority audit then
proved:

```text
BROKER_CONFIG_MOUNT_TYPE=bind
HOST_AND_PROCROOT_SAME_DEV_INODE=false
HOST_AND_PROCROOT_SAME_BYTES=true
PROCROOT_AND_CONTAINER_SAME_BYTES=true
```

The host pathname object and the running Broker mount-namespace object were different
inodes even though their restored bytes were equal. Current divergence is proven;
causation by Attempt 01's earlier rename is only a high-confidence inference and is
not promoted to a proven historical fact.

### Attempt 03

The executor targeted the exact running Broker container namespace directly. The
write was rejected before candidate validation. Fresh read-only recovery then proved:

```text
CONFIG_EXPECTED=true
DYNSEC_EXPECTED=true
BROKER_CONFIG_MOUNT_TYPE=bind
BROKER_CONFIG_MOUNT_RW=false
BROKER_MOUNT_OPTIONS_CONTAINS_RO=true
HOST_CONTAINER_BYTES_SAME=true
PROCROOT_CONTAINER_BYTES_SAME=true
BROKER_RESTART_COUNT=0
MANAGER_RESTART_COUNT=0
```

The live Broker config authority is therefore read-only for this running deployment.
`test -w` was not sufficient authority for actual truncate/write capability.

### Harness closeout

```text
BROKER_OBSERVABILITY_DETOUR_PRODUCT_FAILURE_PROVEN=false
BROKER_OBSERVABILITY_DETOUR_BOARD_B_FAILURE_PROVEN=false
BROKER_CONFIG_HOST_PATH_OBJECT_IS_LIVE_AUTHORITY=false
BROKER_CONFIG_PROCROOT_OBJECT_IS_LIVE_AUTHORITY=true
BROKER_CONFIG_CONTAINER_OBJECT_IS_LIVE_AUTHORITY=true
BROKER_CONFIG_LIVE_AUTHORITY_READ_ONLY=true
BROKER_CONFIG_EXACT_CURRENT_STATE_PROVEN=true
DYNSEC_EXACT_CURRENT_STATE_PROVEN=true
BROKER_RUNTIME_CONTINUITY_PROVEN=true
MANAGER_RUNTIME_CONTINUITY_PROVEN=true
```

The detour must not be repeated as a prerequisite for Board B R2 runtime-liveness
closure.

## Artifact-integrity incidents

Two non-product incidents are retained for audit completeness:

1. The first local materialization attempt for the `_01` executor failed before Gate
   execution because nested triple-quoted Python text terminated the outer authoring
   string. No authorization was claimed and no T1 mutation occurred. The artifact was
   rematerialized with a safe outer quoting form and passed syntax/compile checks.
2. When `_03` was delivered, one assistant message displayed the SHA-256 without its
   final hexadecimal character `c`. The user detected the mismatch before execution;
   the actual artifact and the user's local `shasum -a 256` both produced the correct
   64-character digest. The displayed truncated digest is invalidated and no artifact
   with that truncated digest was executed.

These incidents reinforce exact 64-hex digest-length validation and local artifact
hashing as the execution authority.

## Authorization ledger closeout

All claimed live Board B recovery/observability authorizations in this route are
one-shot and non-replayable, including:

```text
R2B-BOARD-B-EXISTING-IDENTITY-CREDENTIAL-RECOVERY-20260902-01
R2B-BOARD-B-RUNTIME-LIVENESS-OBSERVATION-20260904-01
R2B-BOARD-B-BROKER-QOS1-CANONICAL-OUTPUT-ORACLE-20260904-01
R2B-BOARD-B-BROKER-QOS1-CANONICAL-OUTPUT-ORACLE-20260904-02
R2B-BOARD-B-BROKER-QOS1-CANONICAL-OUTPUT-ORACLE-20260904-03
REPLAY_PERMITTED=false
```

## Safety boundary

```text
BOARD_C_ACCESS=false
FLASH=false
FLASH_READ=false
FLASH_WRITE=false
NVS_ERASE=false
NVS_MUTATION=false
BOARD_RESET=false
BOOT_BUTTON_ACTION=false
POWER_CYCLE=false
PAIRING_RECOVERY_REEXECUTED=false
CREDENTIAL_RECOVERY_REEXECUTED=false
HOMEASSISTANT_MUTATION=false
DATABASE_MUTATION=false
DYNSEC_MUTATION=false
BROKER_ACL_MUTATION=false
```

The bounded observability attempts are the only separately authorized Broker config
observability mutations in this closeout. Final read-only recovery proves current
Broker config, DynSec and Manager/Broker runtime continuity are exact.

## Explicit remaining boundary

```text
REBOOT_PERSISTENCE_TESTED=false
```

No operator-induced RESET, BOOT action, power-cycle or reboot was performed in the
post-recovery runtime-liveness closeout. This document does not claim reboot
persistence.

## Known-failure disposition

Existing relevant guards remain applicable:

```text
KF-010=GUARDED
KF-072=OPEN
KF-075=GUARDED
KF-078=GUARDED
KF-082=GUARDED
```

The new single-file Broker bind-mount observability authority/writeability incident is
archived separately in
`N3W_R2B_BOARD_B_TEST_INCIDENTS_AND_REGRESSION_GUARDS_20260904.md` as the public-safe
KF-085 record.

## Final Board B R2 closure

```text
BOARD_B_EXISTING_IDENTITY_CREDENTIAL_RECOVERY=PASS
BOARD_B_SECURITY_STATE_AUTHORITY=PASS
BOARD_B_PAIRING_QUIESCENCE=PASS
BOARD_B_RUNTIME_LIVENESS=PASS
R2_BOARD_B_RUNTIME_LIVENESS=PASS
BOARD_B_POST_RECOVERY_RUNTIME_LIVENESS=PASS
BOARD_B_R2_CLOSEOUT_REVIEW=PASS
PRODUCT_REGRESSION_PROVEN=false
REBOOT_PERSISTENCE_TESTED=false
```

Board B is closed for the current R2 runtime-liveness route.

## Route handoff

```text
BOARD_A_R2=FROZEN_PASS
BOARD_B_R2=FROZEN_PASS
READY_FOR_BOARD_C_R2_PRECLAIM_REVIEW=true
BOARD_C_ACCESS=false
AUTO_EXECUTE_NEXT=false
```

The next action, if separately authorized, is Board C R2 preclaim/current-authority
review. This closeout does not authorize Board C physical access.

## Related repository references

- `docs/development/N3W_R2B_KF075_CREDENTIAL_RECOVERY_PRODUCT_PATH_SOURCE_REPAIR_20260901.md`
- `docs/development/N3W_R2B_BOARD_B_EXISTING_IDENTITY_CREDENTIAL_RECOVERY_CLOSEOUT_20260902.md`
- `docs/development/N3W_R2A_BOARD_A_RUNTIME_NAMESPACE_RECOVERY_CLOSEOUT_20260903.md`
- `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
- `docs/development/N3W_R2B_BOARD_B_TEST_INCIDENTS_AND_REGRESSION_GUARDS_20260904.md`
