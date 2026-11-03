# N3-W T1 Core Stack R3 reference convergence and A1 entry read-only closure — 2026-11-03

```text
TASK=N3W_T1_CORE_STACK_R3_REFERENCE_CONVERGENCE_AND_A1_ENTRY_READONLY_20261103_01
RESULT=CLOSED_PASS

MAIN=e0841a5a43fd5847d5c5c40ab1cece42faedf3c8
PR773_GATE_INPUT_HEAD=aa30c1bdcc42dbea8048822de181b0b7540d6494
PR773_BRANCH=docs/n3w-r3-post-registration-runtime-business-handoff-20261103

R2_REFERENCE_REBIND=PASS
R2_REFERENCE_SHA256=89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747

R3_ENGINEERING_OBJECTIVE_COMPLETE=true
R3_REFERENCE_RECONSTRUCTION=PASS:PUBLIC_SAFE_ARCHIVED_EVIDENCE_NORMALIZATION
R3_REFERENCE_SHA256=e09139564280c700bc02b2e16360c511f780f7da7817f0d9bf0a22ff59dfcceb
R3_NORMALIZED_DELTA_SHA256=0d2ade72c9dbdc8299cc09754ed87768a02762244447c619d007951e9a522895

REFERENCE_FIELD_COUNT=150
FIELD_PATTERN_GROUP_COUNT=44
DIRECTLY_COMPARABLE_COUNT=48
EXPECTED_BUSINESS_RUNTIME_DRIFT_COUNT=58
VERSION_AXIS_DRIFT_COUNT=15
HISTORICAL_REFERENCE_GAP_COUNT=29
FRESH_READONLY_OBSERVATION_REQUIRED_COUNT=0

MANAGER_VERSION_AXIS_SEPARATED=true
STABLE_CONTRACT_BREAK_COUNT=0
NEW_PRODUCT_BLOCKER_COUNT=0
A1_INPUT_TABLE_COMPLETE=true

T1_READONLY_OBSERVER_EXECUTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PR773_MERGE=false

R3_REFERENCE_CONVERGENCE_RESULT=PASS
A1_ENTRY_READY=true
NEXT_ROUTE=N3W_T1_CORE_STACK_A1_STABLE_INVARIANT_CLASSIFICATION_20261103_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

## 1. Fresh rebind

- `main` is `e0841a5a43fd5847d5c5c40ab1cece42faedf3c8`.
- PR #773 gate-input head is `aa30c1bdcc42dbea8048822de181b0b7540d6494`; it is open and unmerged.
- Canonical current-stack authority is `infra/n3w-t1/production/t1-core-stack-current.json`, schema `gh.n3w-t1-core-stack-current-authority/2`.
- Historical Clean Reference source remains `24382caae4a1f5d459297f86e8d18f10a848ca64` with Manager `local/greenhouse-manager:fresh-24382caae4a1`.
- Current accepted product source is `b863ddd959090ca139af76bd68dbef31d773e6de` with Manager `local/greenhouse-manager:fresh-b863ddd95909`.
- Frozen R2 common-reference digest is `89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747`.

## 2. Already-closed R3 engineering facts

R3 real first registration is PASS; KF-139 is CLOSED_PASS. Post-registration Direct telemetry / Home Assistant is PASS; KF-140 is CLOSED_FALSE_POSITIVE. Historical same-boot Direct -> Relay -> Direct physical acceptance remains valid and is not repeated. Frozen R3 does not require Direct/Relay failover, sensor measurements or long-duration stability.

The R3 engineering objective is therefore complete. This gate closes only the missing reference / semantic-delta authority required before A1.

## 3. Why a naive R2 -> current R3 whole-reference compare is invalid

The historical R2 observer places product source, component image and runtime-contract identities in `stable_contracts`. During R3, KF-139 intentionally repaired and accepted a Manager A -> b863 upgrade. A direct invocation of the old compare contract would therefore label an intentional version transition as `stable_contract_drift`.

The normalized rule is:

```text
R2->R3 semantic delta
=
business-runtime delta
+
explicit Manager version axis
+
historical public-reference gaps
```

The version axis is not an exemption from later A1 reasoning. A1 must still decide which version-independent contracts are hard, soft, diagnostic or removable.

## 4. Manager version-axis separation

```text
HISTORICAL_MANAGER_SOURCE=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_MANAGER=local/greenhouse-manager:fresh-24382caae4a1

CURRENT_MANAGER_SOURCE=b863ddd959090ca139af76bd68dbef31d773e6de
CURRENT_MANAGER=local/greenhouse-manager:fresh-b863ddd95909

VERSION_AXIS_FIELD_COUNT=15
MANAGER_VERSION_AXIS_SEPARATED=true
```

Three stable-reference leaves are version-axis values: product source head, Manager image, and Manager runtime-contract hash.

Twelve runtime leaves are also version-axis contaminated by the accepted Manager update and the production service-group restart behavior: Manager container runtime (3), Home Assistant container runtime (3), Manager MQTT volatile session data (3), and Home Assistant MQTT volatile session data (3). Home Assistant image/platform/runtime-contract remain directly comparable because the HA image did not change. Broker identity remains directly comparable; Broker runtime diagnostics remain ordinary runtime-variable fields because Broker continuity was preserved.

## 5. Public-safe authority artifacts

- R3 normalized reference: `infra/n3w-t1/clean-reference/r3-normalized-reference-20261103.json`
  - `R3_REFERENCE_SHA256=e09139564280c700bc02b2e16360c511f780f7da7817f0d9bf0a22ff59dfcceb`
- R2 -> R3 normalized delta: `infra/n3w-t1/clean-reference/r2-r3-normalized-delta-20261103.json`
  - `R3_NORMALIZED_DELTA_SHA256=0d2ade72c9dbdc8299cc09754ed87768a02762244447c619d007951e9a522895`

Each digest is SHA-256 of the artifact's `payload` serialized as UTF-8 canonical JSON with recursively sorted keys, compact separators and `ensure_ascii=false`. The wrapper itself is not included in the digest.

No raw private R2 observation, raw device identity, private network locator, credential or secret is added to GitHub.

## 6. Complete common-reference comparability inventory

The observer contract contains 150 leaf reference fields. The following 44 pattern groups are exhaustive over those leaves.

| # | Field pattern | Leaf count | Owner | R2 -> R3 comparability | R3 change interpretation | A1 classification |
|---:|---|---:|---|---|---|---|
| 1 | `stable_contracts.authority.product_source_head` | 1 | core-stack | VERSION_AXIS_DRIFT | YES_VERSION_AXIS | PENDING_A1 |
| 2 | `stable_contracts.authority.r2a_control_head` | 1 | clean-reference | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 3 | `stable_contracts.authority.r2b_control_head` | 1 | clean-reference | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 4 | `stable_contracts.authority.r2a_transaction_sha256` | 1 | clean-reference | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 5 | `stable_contracts.authority.r2b_transaction_sha256` | 1 | clean-reference | HISTORICAL_REFERENCE_GAP | UNKNOWN_PUBLIC_R2_LEAF | PENDING_A1 |
| 6 | `stable_contracts.component_identity.broker.{image,platform,runtime_contract_sha256}` | 3 | broker | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 7 | `stable_contracts.component_identity.homeassistant.{image,platform,runtime_contract_sha256}` | 3 | homeassistant | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 8 | `stable_contracts.component_identity.manager.image` | 1 | manager | VERSION_AXIS_DRIFT | YES_VERSION_AXIS | PENDING_A1 |
| 9 | `stable_contracts.component_identity.manager.platform` | 1 | manager | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 10 | `stable_contracts.component_identity.manager.runtime_contract_sha256` | 1 | manager | VERSION_AXIS_DRIFT | YES_VERSION_AXIS | PENDING_A1 |
| 11 | `stable_contracts.fixed_config_sha256.*` | 3 | core-stack | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 12 | `stable_contracts.custom_component_tree_sha256` | 1 | homeassistant | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 13 | `stable_contracts.systemd_unit_sha256.*` | 7 | host-runtime | HISTORICAL_REFERENCE_GAP | UNKNOWN_PUBLIC_R2_LEAF | PENDING_A1 |
| 14 | `stable_contracts.persistent_path_metadata.*.{uid,gid,mode,type}` | 16 | persistent-state | HISTORICAL_REFERENCE_GAP | UNKNOWN_PUBLIC_R2_LEAF | PENDING_A1 |
| 15 | `stable_contracts.sqlite_schema.*.quick_check` | 3 | persistent-state | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 16 | `stable_contracts.sqlite_schema.*.user_version` | 3 | persistent-state | HISTORICAL_REFERENCE_GAP | UNKNOWN_PUBLIC_R2_LEAF | PENDING_A1 |
| 17 | `stable_contracts.sqlite_schema.*.schema_sha256` | 3 | persistent-state | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 18 | `stable_contracts.sqlite_schema.*.table_count` | 3 | persistent-state | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 19 | `stable_contracts.public_certificate_sha256.*` | 3 | tls | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 20 | `stable_contracts.dynsec_top_level_keys_sha256` | 1 | broker | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 21 | `health.system_state` | 1 | host-runtime | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 22 | `health.failed_unit_count` | 1 | host-runtime | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 23 | `health.failed_units` | 1 | host-runtime | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 24 | `health.systemd_units.*.{active,enabled}` | 14 | host-runtime | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 25 | `health.runtime_services` | 1 | core-stack | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 26 | `health.manager_current_authenticated` | 1 | manager | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 27 | `health.homeassistant_current_authenticated` | 1 | homeassistant | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 28 | `health.manager_mqtt_socket_count` | 1 | manager | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |
| 29 | `health.homeassistant_mqtt_socket_count` | 1 | homeassistant | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |
| 30 | `health.homeassistant_http_status` | 1 | homeassistant | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |
| 31 | `health.overall_pass` | 1 | core-stack | DIRECTLY_COMPARABLE | NO_CONTRACT_BREAK_PROVEN | PENDING_A1 |
| 32 | `runtime_observations.boot_id_sha256` | 1 | host-runtime | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |
| 33 | `runtime_observations.containers.broker.{container_id_sha256,started_at,restart_count}` | 3 | broker | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |
| 34 | `runtime_observations.containers.manager.{container_id_sha256,started_at,restart_count}` | 3 | manager | VERSION_AXIS_DRIFT | YES_VERSION_AXIS | PENDING_A1 |
| 35 | `runtime_observations.containers.homeassistant.{container_id_sha256,started_at,restart_count}` | 3 | homeassistant | VERSION_AXIS_DRIFT | YES_VERSION_AXIS | PENDING_A1 |
| 36 | `runtime_observations.mqtt_session.manager.{count,fingerprint,authenticated_event_count}` | 3 | manager | VERSION_AXIS_DRIFT | YES_VERSION_AXIS | PENDING_A1 |
| 37 | `runtime_observations.mqtt_session.manager.identity_sha256` | 1 | manager | HISTORICAL_REFERENCE_GAP | UNKNOWN_PUBLIC_R2_LEAF | PENDING_A1 |
| 38 | `runtime_observations.mqtt_session.homeassistant.{count,fingerprint,authenticated_event_count}` | 3 | homeassistant | VERSION_AXIS_DRIFT | YES_VERSION_AXIS | PENDING_A1 |
| 39 | `runtime_observations.mqtt_session.homeassistant.identity_sha256` | 1 | homeassistant | HISTORICAL_REFERENCE_GAP | UNKNOWN_PUBLIC_R2_LEAF | PENDING_A1 |
| 40 | `runtime_observations.sqlite.*.row_counts.*` | 17 | persistent-state | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |
| 41 | `runtime_observations.sqlite.*.{file_bytes,wal_bytes}` | 6 | persistent-state | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |
| 42 | `runtime_observations.persistent_tree_stats.*.{file_count,directory_count,total_bytes,symlink_count}` | 16 | persistent-state | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |
| 43 | `runtime_observations.dynsec_counts.{clients,groups,roles}` | 3 | broker | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |
| 44 | `runtime_observations.homeassistant_registry_counts.*.{present,count,version}` | 9 | homeassistant | EXPECTED_BUSINESS_RUNTIME_DRIFT | ALLOWED_RUNTIME_CHANGE | PENDING_A1 |

Count check:

```text
48 + 58 + 15 + 29 + 0 = 150
```

### Historical-reference-gap policy

The 29 historical gaps are public-archive gaps only. They are not evidence of current runtime failure and do not justify wiping/redeploying T1_B, replaying first registration, or redeploying historical Manager A. They remain explicit A1 provenance gaps.

No A1-required field is `FRESH_READONLY_OBSERVATION_REQUIRED`; therefore no T1 observer run is justified in this gate.

## 7. A1 input table

The table in section 6 is the complete A1 input skeleton for the common observer schema:

- `FIELD` -> field pattern plus leaf count;
- `OWNER_MODULE` -> owner column;
- `R2_VALUE_CLASS` -> archived comparable value/contract or explicit historical-reference gap;
- `R3_VALUE_CLASS` -> directly comparable, expected business-runtime drift, or explicit version-axis drift;
- `R2_CHANGED / R3_CHANGED` -> represented by the R3 change interpretation column;
- `CLASSIFICATION` -> intentionally `PENDING_A1`;
- `CONCRETE_SAFETY_REASON` -> must be supplied in A1 before any field can become a hard gate.

A1 must not promote a field to `HARD_STABLE_INVARIANT` merely because it is hashable or happened to match R2.

## 8. Stable-contract-break review

```text
ARCHIVED_EVIDENCE_CONTRADICTS_ACCEPTED_R3_COMMIT=false
CURRENT_AUTHORITY_CONTRADICTS_KF139_CLOSURE=false
STABLE_CONTRACT_BREAK_DIRECTLY_PROVEN=false
NEW_PRODUCT_BLOCKER_COUNT=0
```

Current b863 Manager differs from historical Manager A by design and is therefore not counted as a stable-contract break. The accepted R3 business facts remain intact: first registration committed, Manager Direct telemetry progressed consecutively through seq 71..101 with zero rejects/duplicates, and Home Assistant fresh MQTT receipt passed.

## 9. Gate boundary

```text
FIRST_REGISTRATION_REPLAY=false
DIRECT_RELAY_RETEST=false
SENSOR_ACCEPTANCE=false
LONG_DURATION_STABILITY=false
T1_SERVICE_RESTART=false
T1_IMAGE_CHANGE=false
DB_DYNSEC_CREDENTIAL_HA_CONFIG_WRITE=false
HISTORICAL_MANAGER_REDEPLOY=false
UPDATER_APPLY=false
PR773_MERGE=false
A1_EXECUTED=false
```

This gate ends at A1 entry. It does not perform A1 classification and does not authorize PR #773 merge.

## 10. Final closure

```text
R3_REFERENCE_CONVERGENCE_RESULT=PASS
A1_INPUT_TABLE_COMPLETE=true
A1_ENTRY_READY=true
NEXT_ONE_GATE=N3W_T1_CORE_STACK_A1_STABLE_INVARIANT_CLASSIFICATION_20261103_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```
