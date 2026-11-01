# N3-W Three-Board Regression / Retest Final Closeout

Date: 2026-09-04

## 1. Scope

This document is the consolidated public-safe final archive for
`N3W_THREE_BOARD_REGRESSION_RETEST`.

It closes the sequential R2 runtime-liveness revalidation of Board A, Board B and
Board C after FC4 Final Physical Acceptance had already been frozen PASS.

This archive does not reopen FC4, does not authorize any new Board access, and does
not redefine deployed product-source authority.

```text
NORTH_STAR=N3W_THREE_BOARD_REGRESSION_RETEST
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
FC4_REOPEN=false

BOARD_A_R2=FROZEN_PASS
BOARD_B_R2=FROZEN_PASS
BOARD_C_R2=FROZEN_PASS

N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=ALL_THREE_BOARDS_PASS
PRODUCT_REGRESSION_PROVEN=false
```

## 2. Final repository authority

This final archive is bound to the post-PR357 current `main` authority:

```text
BOUND_REPOSITORY_MAIN_HEAD=
a2a515d4326943efa22fc1a011c35ec2d7288985

BOUND_REPOSITORY_MAIN_TREE=
57bfb5943b4ba002d80188bffb63c740d844506a
```

The bound main commit is the documentation-only merge of PR #357. Its merge commit
message explicitly states that product source remains unchanged.

```text
PR357_HEAD=a3d73341d17aaaf3abfa66a599e91226dcfb37ec
PR357_MERGE_COMMIT=a2a515d4326943efa22fc1a011c35ec2d7288985
PR357_MERGED=true
```

The merge commit parents are:

```text
PARENT_1=641decb66644c0aa51cdae5154ee50bf527c3c87
PARENT_2=a3d73341d17aaaf3abfa66a599e91226dcfb37ec
```

## 3. Frozen deployed product authorities

Repository documentation movement after the deployed product revision does not
redefine product runtime/source authority.

```text
FROZEN_DEPLOYED_PRODUCT_MANAGER_SOURCE=
8fbedc7e0778ce91d146cd5f0772bebdd20ad13a

FROZEN_DEPLOYED_PRODUCT_SOURCE_TREE=
77b5d89164bdb966555938f838804522fe865f7e

FROZEN_BOARD_FIRMWARE_SOURCE=
739d9af2bac78a3a59f92a4ae345d8f1b1dc15ab
```

## 4. FC4 acceptance boundary

The pre-existing FC4 final archive records:

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=PASS
CURRENT_ROUTE_NODE=FC4_FINAL_PHYSICAL_ACCEPTANCE_COMPLETE
CURRENT_PRODUCT_BLOCKER=NONE_PROVEN
REMAINING_PHYSICAL_BOARD_C_GATE_COUNT=0
```

R2 did not reopen the FC4 route. It independently revalidated current deployed
runtime behavior board by board.

## 5. Board A R2 closure

Board A retained its stable node identity but published QoS1 telemetry under a
predecessor system namespace. Current Broker/DynSec authority correctly rejected the
stale namespace.

The proved root cause was:

```text
BOARD_A_ROOT_CAUSE=STALE_PREVIOUS_SYSTEM_NAMESPACE_PERSISTED_IN_BOARD_RUNTIME_STATE
BOARD_A_NODE_IDENTITY=CORRECT
BOARD_A_SYSTEM_NAMESPACE=STALE_PREVIOUS_SYSTEM
BROKER_CURRENT_DYNSEC_ROLE=CURRENT_SYSTEM_CORRECT
RESULT=QOS1_PUBLISH_NOT_AUTHORIZED
```

The scoped recovery preserved stable node identity, did not widen Broker ACLs, did not
change Manager system identity, restored the exact product application and returned
the Board to the current runtime namespace through the normal product path.

Final physical/runtime proof included:

```text
TARGET_NODE_QOS1_TELEMETRY_COUNT=9
CURRENT_SYSTEM_QOS1_TELEMETRY_COUNT=9
STALE_SYSTEM_QOS1_TELEMETRY_COUNT=0
OTHER_SYSTEM_QOS1_TELEMETRY_COUNT=0
CURRENT_SYSTEM_PUBACK_SUCCESS_COUNT=9
CURRENT_SYSTEM_PUBACK_NOT_AUTHORIZED_COUNT=0
MISSING_PUBACK_COUNT=0

BROKER_TO_MANAGER_CURRENT_SYSTEM_QOS1_DELIVERY_COUNT=9
MANAGER_CANONICAL_TELEMETRY_PUBLISH_COUNT=9
MANAGER_AVAILABILITY_PUBLISH_COUNT=9
DIRECT_TO_CANONICAL_CORRELATED_CYCLES=9
MAX_DIRECT_TO_CANONICAL_LATENCY_MS=87
```

Board A final adjudication:

```text
BOARD_A_CURRENT_SYSTEM_NAMESPACE_RECOVERY_PROVEN=true
BROKER_TO_MANAGER_DIRECT_DELIVERY_PROVEN=true
MANAGER_ACCEPTED_PIPELINE_PROVEN=true
BOARD_A_POST_RECOVERY_RUNTIME_LIVENESS=PASS
R2_BOARD_A_RUNTIME_LIVENESS=PASS
BOARD_A_R2_ADJUDICATION=PASS_AFTER_SCOPED_RUNTIME_NAMESPACE_RECOVERY
PRODUCT_REGRESSION_PROVEN=false
```

Board A also established the route lessons now associated with KF-083 and KF-084:
current-system namespace residue must be distinguished from stable node identity, and
an exact deployed firmware artifact must not be replaced by an assumed byte-identical
rebuild.

## 6. Board B R2 closure

Board B required the existing-identity MQTT credential-recovery product path. The
recovery preserved stable identity, application-key material and peer-trust material
while rotating only the MQTT credential generation.

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

MUTATION_CLOSURE_PASS=true
```

A later fresh current-authority snapshot proved current Manager/Broker, security
lifecycle and DynSec current-namespace authority before the physical liveness gate.

Final physical observation used a 20-second stabilization window followed by a
50-second verification window:

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
```

The same Direct sequence set was correlated 10/10 with Manager durable replay and
same-boot canonical-cursor advancement.

```text
HIGH_LEVEL_R2B_RUNTIME_LIVENESS_ADJUDICATION=PASS
R2_BOARD_B_RUNTIME_LIVENESS=PASS
BOARD_B_POST_RECOVERY_RUNTIME_LIVENESS=PASS
BOARD_B_PAIRING_QUIESCENCE_PROVEN=true
BOARD_B_DIRECT_RUNTIME_HEALTHY=true
BROKER_QOS1_APPLICATION_ACCEPTANCE_PROVEN=true
BROKER_TO_MANAGER_DIRECT_DELIVERY_PROVEN=true
MANAGER_ACCEPTED_PIPELINE_PROVEN=true
MANAGER_DURABLE_REPLAY_CORRELATION_PROVEN=true
PRODUCT_REGRESSION_PROVEN=false
```

### Board B Broker-observability detour

Three later attempts to obtain a stronger Board-A-style Broker debug oracle did not
prove a product failure. They exposed harness/runtime-authority issues around a
single-file Docker bind mount.

The final read-only recovery established:

```text
BROKER_CONFIG_HOST_PATH_OBJECT_IS_LIVE_AUTHORITY=false
BROKER_CONFIG_PROCROOT_OBJECT_IS_LIVE_AUTHORITY=true
BROKER_CONFIG_CONTAINER_OBJECT_IS_LIVE_AUTHORITY=true
BROKER_CONFIG_LIVE_AUTHORITY_READ_ONLY=true
BROKER_CONFIG_EXACT_CURRENT_STATE_PROVEN=true
DYNSEC_EXACT_CURRENT_STATE_PROVEN=true
BROKER_RUNTIME_CONTINUITY_PROVEN=true
MANAGER_RUNTIME_CONTINUITY_PROVEN=true
```

The public-safe Board B incident ledger records:

```text
KF-085=RESOLVED
KF_085_DOMAIN=PHYSICAL_HARNESS
```

The route correction is permanent: host pathname identity or `test -w` alone is not
live mutation authority for a running single-file bind mount.

The separate wire-level PUBACK capture was correctly demoted from a closeout blocker
because the required durable end-to-end runtime semantics had already been proven.

## 7. Board C R2 closure

Board C entered R2 as an already-registered current product identity. Historical
first-registration/setup-secret material was not reused as current authority.

The corrected current-authority preclaim resolved exactly one current Board C lineage
candidate and proved:

```text
BOARD_C_CURRENT_IDENTITY_UNIQUE=true
BOARD_C_PAIRING_STATE=approved
BOARD_C_REPAIR_AUTHORIZED=false
BOARD_C_CURRENT_ACTIVE_LEASE_COUNT=1
BOARD_C_CURRENT_OPEN_HISTORY_COUNT=1
BOARD_C_PRIOR_RETIRED_LEASE_COUNT=1
BOARD_C_PRIOR_RELEASED_HISTORY_COUNT=1
BOARD_C_CURRENT_REGISTRATION_AUTHORITY=PASS

BOARD_C_CURRENT_CREDENTIAL_AUTHORITY=PASS
BOARD_C_CURRENT_APPLICATION_KEY_AUTHORITY=PASS
BOARD_C_CURRENT_PEER_TRUST_AUTHORITY=PASS
BOARD_C_CURRENT_DYNSEC_AUTHORITY=PASS
```

Credential generation, application-key epoch, pairing audit epoch and peer-trust
generation remained separate lifecycle authorities and were not numerically coupled.

Final Board C physical observation used the same bounded pattern as Board B:

```text
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
```

The same Direct sequence set was correlated 10/10 with Manager durable replay and
same-boot canonical-cursor advancement. No Broker authorization denial and no Manager
Direct rejection were observed.

```text
HIGH_LEVEL_R2C_RUNTIME_LIVENESS_ADJUDICATION=PASS
R2_BOARD_C_RUNTIME_LIVENESS=PASS
BOARD_C_POST_RECOVERY_RUNTIME_LIVENESS=PASS
BOARD_C_PAIRING_QUIESCENCE_PROVEN=true
BOARD_C_DIRECT_RUNTIME_HEALTHY=true
BOARD_C_CURRENT_SYSTEM_NAMESPACE_RUNTIME_PROVEN=true
BROKER_QOS1_APPLICATION_ACCEPTANCE_PROVEN=true
BROKER_TO_MANAGER_DIRECT_DELIVERY_PROVEN=true
MANAGER_ACCEPTED_PIPELINE_PROVEN=true
MANAGER_DURABLE_REPLAY_CORRELATION_PROVEN=true
PRODUCT_REGRESSION_PROVEN=false
```

### Board C pre-execution incidents

Two non-product incidents were retained in the Board C closeout:

1. A host-side procroot SQLite path-domain open failure. The corrected executor moved
   the read to the exact current Manager container namespace with SQLite `mode=ro` and
   `PRAGMA query_only=ON`; the successor preclaim passed. This maps to KF-045.
2. The first physical preclaim saw zero Espressif USB identities because Board C had
   not been connected. Authorization was not claimed or consumed, no serial open
   occurred, and the same exact preclaim was legitimately retried after connection.

Neither incident proved a Board C or product regression.

## 8. Cross-board runtime conclusion

The three boards are independently closed on the current R2 route:

```text
BOARD_A_R2=FROZEN_PASS
BOARD_B_R2=FROZEN_PASS
BOARD_C_R2=FROZEN_PASS

BOARD_A_CURRENT_SYSTEM_RUNTIME_PROVEN=true
BOARD_B_CURRENT_SYSTEM_RUNTIME_PROVEN=true
BOARD_C_CURRENT_SYSTEM_RUNTIME_PROVEN=true

N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=ALL_THREE_BOARDS_PASS
PRODUCT_REGRESSION_PROVEN=false
```

The route proves current deployed runtime liveness across all three boards under the
current Manager/Broker/security authority.

## 9. Common evidence model retained

The route converged on:

```text
ONE_LOGICAL_GATE=true
ONE_EXECUTOR=true
ONE_FRESH_SNAPSHOT=true
ONE_HIGH_LEVEL_ADJUDICATION=true
```

For host-only read-only work, current runtime/container namespace authority takes
precedence over stale host-path assumptions.

For physical liveness, the bounded oracle is:

- exact current Board identity binding;
- read-only serial observation;
- stabilization before verification;
- no pairing payload during steady state;
- no reset marker during verification;
- strictly increasing telemetry sequence;
- zero rejected Direct telemetry;
- current Manager/Broker authority continuity;
- exact serial-to-replay correlation;
- same-boot canonical-cursor advancement;
- no Broker authorization denial;
- no Manager Direct rejection.

Auxiliary INFO log lines are not promoted above durable/canonical evidence.

## 10. Packet-level evidence boundary

Board A has a direct bounded Broker-side PUBACK proof from its scoped recovery route.
Board B and Board C do not claim wire-level PUBACK frame capture:

```text
BOARD_B_PACKET_LEVEL_PUBACK_CAPTURE_PERFORMED=false
BOARD_C_PACKET_LEVEL_PUBACK_CAPTURE_PERFORMED=false
BOARD_B_WIRE_LEVEL_PUBACK_FRAME_DIRECTLY_OBSERVED=false
BOARD_C_WIRE_LEVEL_PUBACK_FRAME_DIRECTLY_OBSERVED=false
```

This is not a blocker for R2 runtime-liveness closure because both boards have the
required durable end-to-end application acceptance, Broker-to-Manager delivery and
Manager durable correlation evidence.

## 11. Reboot-persistence boundary

Board B and Board C post-recovery runtime-liveness closeouts did not perform an
operator-induced reset, BOOT action, power-cycle or reboot.

```text
REBOOT_PERSISTENCE_TESTED=false
```

This final archive therefore does not claim reboot-persistence validation. The R2
North Star was current runtime-liveness regression/retest, not a reboot-persistence
campaign.

## 12. Known Failures / regression guards

The central `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` remains the primary domain/status
authority for indexed records. The Board B public-safe incident addendum remains the
authority for KF-085 until/unless it is separately folded into the central index.

Important guards exercised by this R2 route include:

```text
KF-010=GUARDED
KF-045=GUARDED
KF-057=GUARDED
KF-058=GUARDED
KF-071=GUARDED
KF-072=OPEN
KF-075=GUARDED
KF-078=GUARDED
KF-082=GUARDED
KF-083=RESOLVED
KF-084=OPEN
KF-085=RESOLVED_IN_R2B_ADDENDUM
```

No new product-domain failure was proven by the final Board B or Board C liveness
work.

## 13. Non-blocking repository residual

PR #355 remains open and documentation-only. It restores the Navigator/read-only
validation strategy and is not required to prove this three-board runtime-liveness
result.

```text
PR_355_STATE=open
PR_355_MERGED=false
PR_355_DOCUMENTATION_ONLY=true
```

## 14. Authorization and safety boundary

All claimed physical/recovery authorizations in the R2 route are one-shot and
non-replayable after consumption.

The PR #357 merge authorization was consumed exactly once and advanced main only by
the documentation-only Board C closeout merge.

This final archive materialization performs repository documentation mutation only.
It authorizes no T1 or product-runtime mutation.

```text
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
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
DATABASE_MUTATION=false
HOMEASSISTANT_MUTATION=false
SERVICE_RESTART=false
```

## 15. Final archive materialization note

Before this branch existed, repository file-creation requests against the intended
branch returned `404 Branch not found`. Those requests performed no repository write.
The branch was then created explicitly from the exact bound main SHA before the final
archive file was written. This is a repository-operation sequencing incident, not a
product or runtime failure, and no new KF is assigned here.

## 16. Final R2 adjudication

```text
N3W_THREE_BOARD_REGRESSION_RETEST_CLOSEOUT_REVIEW=PASS
N3W_THREE_BOARD_REGRESSION_RETEST_FINAL_ARCHIVE_REVIEW=PASS_PENDING_FINAL_ARCHIVE_PR_MERGE

BOARD_A_R2=FROZEN_PASS
BOARD_B_R2=FROZEN_PASS
BOARD_C_R2=FROZEN_PASS

N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=ALL_THREE_BOARDS_PASS
PRODUCT_REGRESSION_PROVEN=false

FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
FC4_REOPEN=false

REBOOT_PERSISTENCE_TESTED=false
```

The three-board runtime-liveness route is technically closed PASS. Repository final
archive completion becomes true only after this consolidated documentation-only PR is
merged and a fresh post-merge `main` authority is rebound.

## 17. Final route handoff

```text
THREE_BOARD_RUNTIME_LIVENESS_CLOSEOUT_READY=true
CONSOLIDATED_FINAL_ARCHIVE_MATERIALIZED=true
REPOSITORY_FINAL_ARCHIVE_COMPLETE=false
READY_FOR_CONSOLIDATED_FINAL_ARCHIVE_PR_REVIEW=true

BOARD_ACCESS=false
AUTO_EXECUTE_NEXT=false
```

No further physical Board operation is required for this R2 closeout.

## 18. Related repository records

- `docs/development/N3W_FC4_FINAL_PHYSICAL_ACCEPTANCE_CLOSURE_V1.0_20260831.md`
- `docs/development/N3W_R2A_BOARD_A_RUNTIME_NAMESPACE_RECOVERY_CLOSEOUT_20260903.md`
- `docs/development/N3W_R2B_BOARD_B_R2_CLOSEOUT_REVIEW_PUBLIC_SAFE_20260904.md`
- `docs/development/N3W_R2B_BOARD_B_TEST_INCIDENTS_AND_REGRESSION_GUARDS_20260904.md`
- `docs/development/N3W_R2C_BOARD_C_R2_CLOSEOUT_REVIEW_PUBLIC_SAFE_20260904.md`
- `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
