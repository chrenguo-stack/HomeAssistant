# N3-W T1 Core Stack A1 stable-invariant classification closure — 2026-11-03

```text
TASK=N3W_T1_CORE_STACK_A1_STABLE_INVARIANT_CLASSIFICATION_20261103_01
RESULT=CLOSED_PASS

PR773_A1_INPUT_HEAD=8feb62f674fd4da4c24c581da888b5ff4e79646c
PR773_BRANCH=docs/n3w-r3-post-registration-runtime-business-handoff-20261103
R2_REFERENCE_SHA256=89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747
R3_REFERENCE_SHA256=e09139564280c700bc02b2e16360c511f780f7da7817f0d9bf0a22ff59dfcceb
R3_NORMALIZED_DELTA_SHA256=0d2ade72c9dbdc8299cc09754ed87768a02762244447c619d007951e9a522895
A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7

REFERENCE_FIELD_COUNT=150
REFINED_FIELD_PATTERN_COUNT=58
HARD_STABLE_INVARIANT_COUNT=32
SOFT_RUNTIME_CHECK_COUNT=40
DIAGNOSTIC_ONLY_COUNT=67
REMOVE_COUNT=11

LIVE_T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCT_SOURCE_CHANGE=false
PR773_MERGE=false

A1_RESULT=PASS
A2_ENTRY_READY=true
NEXT_ONE_GATE=N3W_T1_CORE_STACK_A2_PER_MODULE_UPGRADE_ARCHITECTURE_20261103_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

## 1. Classification contract

A1 does **not** mean “32 values can never change forever”.

- `HARD_STABLE_INVARIANT`: exact/per-instance/version-bound value is stable during healthy normal operation. Unexpected drift creates a concrete upgrade-safety or compatibility risk, so mutation must stop until an explicit supported migration/version transition is selected.
- `SOFT_RUNTIME_CHECK`: historical equality is not required. Check a semantic rule, allowed range or supported version set. Unsafe state may still stop/defer an upgrade.
- `DIAGNOSTIC_ONLY`: useful evidence, but this field alone never blocks an upgrade.
- `REMOVE`: remove from the future A2 updater gate/normal observer. Historical frozen evidence remains intact.

The old whole-snapshot rule is rejected:

```text
WHOLE_HISTORICAL_REFERENCE_EQUALITY_AS_UPGRADE_GATE=false
PER_MODULE_CONTRACTS_REQUIRED=true
VERSION_BOUND_HARD_IDENTITY_ALLOWED=true
NORMAL_RUNTIME_DRIFT_ALLOWED=true
```

## 2. Key design decisions

1. **Module image/platform/runtime contract stays hard.** Broker, Home Assistant and Manager must be bound to an explicit approved baseline or target. Manager A -> b863 is a version transition, not permission for arbitrary image drift.
2. **Whole Compose SHA is not hard.** It crosses module boundaries and would defeat the intended Manager-only / HA-only / Broker-only upgrade architecture. Module runtime/config contracts remain the gate.
3. **Persistent ownership/type and DB schema identity matter.** Unexpected path owner/type or unknown schema can cause failed writes, data loss or unsafe rollback. Exact file mode and schema version are checked semantically where valid alternatives/migrations can exist.
4. **TLS trust anchors are different from the server certificate.** FC4 CA and System CA are persistent identity/trust material and are hard per-instance. Broker `server.pem` may legitimately renew, so its exact SHA is diagnostic only; A2 must validate chain/hostname/validity semantics instead.
5. **Runtime history is not product identity.** Container IDs, start times, restart counts, boot ID, socket fingerprints, row counts, DB sizes, tree sizes, DynSec counts and HA entity/device counts do not become hard gates.
6. **Opaque aggregate health is removed.** `health.overall_pass` is dropped because it embeds the old observer's exact socket-count assumptions. A2 must recompute health from explicit A1 rules.
7. **Historical R2 transaction/control fields are retired from live gating.** They remain audit evidence only and do not permanently participate in future upgrades.

## 3. Complete 150-leaf A1 table

The prior 44 comparability groups are refined into 58 uniform-classification patterns so fields with different safety meaning are not forced into one class.

| # | Field pattern | Leaves | Owner | R2/R3 comparability | A1 classification | Concrete safety reason |
|---:|---|---:|---|---|---|---|
| 1 | `stable_contracts.authority.product_source_head` | 1 | core-stack | VERSION_AXIS_DRIFT | **DIAGNOSTIC_ONLY** | Repository source head is useful provenance, but docs/tools-only commits can change it without changing the deployed product. Gate the actual approved image/runtime contract instead. |
| 2 | `stable_contracts.authority.r2a_control_head` | 1 | clean-reference | DIRECTLY_COMPARABLE | **REMOVE** | R2A control-plane head is historical experiment provenance, not a live product contract. Preserve it only in frozen reference evidence. |
| 3 | `stable_contracts.authority.r2b_control_head` | 1 | clean-reference | DIRECTLY_COMPARABLE | **REMOVE** | R2B control-plane head is historical experiment provenance, not a live product contract. Preserve it only in frozen reference evidence. |
| 4 | `stable_contracts.authority.r2a_transaction_sha256` | 1 | clean-reference | DIRECTLY_COMPARABLE | **REMOVE** | Historical R2A transaction bytes must not become a permanent runtime gate after the transaction is terminal and archived. |
| 5 | `stable_contracts.authority.r2b_transaction_sha256` | 1 | clean-reference | HISTORICAL_REFERENCE_GAP | **REMOVE** | Historical R2B transaction bytes are not a current product invariant; the public gap must not trigger destructive recreation or future upgrade blocking. |
| 6 | `stable_contracts.component_identity.broker.image` | 1 | broker | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | The approved Broker image is part of the module identity. An unexpected image means the updater cannot prove which code/config contract it is about to mutate. |
| 7 | `stable_contracts.component_identity.broker.platform` | 1 | broker | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | The production artifact is built for the approved platform. A platform mismatch can make image execution or rollback unsafe. |
| 8 | `stable_contracts.component_identity.broker.runtime_contract_sha256` | 1 | broker | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | This binds the Broker launch contract such as user, network mode, mounts, security options and port bindings. Silent drift can weaken security or break persistence/listener behavior. |
| 9 | `stable_contracts.component_identity.homeassistant.image` | 1 | homeassistant | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | The approved Home Assistant image is a module identity input. Unexpected code means compatibility and rollback assumptions are no longer proven. |
| 10 | `stable_contracts.component_identity.homeassistant.platform` | 1 | homeassistant | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | Home Assistant must run on the supported production platform; a mismatch invalidates the frozen artifact/runtime assumptions. |
| 11 | `stable_contracts.component_identity.homeassistant.runtime_contract_sha256` | 1 | homeassistant | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | The runtime contract binds mounts, network and security properties that protect /config persistence and MQTT/HTTP behavior. |
| 12 | `stable_contracts.component_identity.manager.image` | 1 | manager | VERSION_AXIS_DRIFT | **HARD_STABLE_INVARIANT** | Manager image identity must be explicit for each baseline/target. The R3 A->b863 change proves the value may change only through an authorized version transition, not ordinary runtime drift. |
| 13 | `stable_contracts.component_identity.manager.platform` | 1 | manager | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | Manager artifact compatibility depends on the supported platform; mismatch makes execution and rollback assumptions unsafe. |
| 14 | `stable_contracts.component_identity.manager.runtime_contract_sha256` | 1 | manager | VERSION_AXIS_DRIFT | **HARD_STABLE_INVARIANT** | Manager mounts, host-network use, runtime user and security settings are part of the supported module contract. Silent drift can break MQTT, persistence or credential ownership. |
| 15 | `stable_contracts.fixed_config_sha256./etc/n3wfc4/docker-compose.yml` | 1 | core-stack | DIRECTLY_COMPARABLE | **DIAGNOSTIC_ONLY** | A whole-Compose byte hash crosses module boundaries and would over-couple independent upgrades. A2 should gate each module by its runtime/config contract instead. |
| 16 | `stable_contracts.fixed_config_sha256./opt/HomeAssistant/infra/n3w-t1/broker/mosquitto.conf` | 1 | broker | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | The Broker fixed configuration defines listener, TLS and Dynamic Security behavior. Unexpected byte drift can change exposure or authentication semantics. |
| 17 | `stable_contracts.fixed_config_sha256./opt/HomeAssistant/infra/n3w-t1/production/homeassistant-configuration.yaml` | 1 | homeassistant | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | The fixed N3-W Home Assistant configuration is part of the supported integration contract; unplanned drift can break MQTT/bootstrap behavior. |
| 18 | `stable_contracts.custom_component_tree_sha256` | 1 | homeassistant | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | n3w_mqtt_bootstrap code is part of the Home Assistant product integration. Unexpected tree drift changes product behavior without a declared HA/module version transition. |
| 19 | `stable_contracts.systemd_unit_sha256.*` | 7 | host-runtime | HISTORICAL_REFERENCE_GAP | **DIAGNOSTIC_ONLY** | Exact unit-file bytes belong to the host/operations layer, not T1_Core_Stack module identity. A2 should check required unit semantics/state, not exact historical file hashes. |
| 20 | `stable_contracts.persistent_path_metadata.*.{uid,gid,type}` | 12 | persistent-state | HISTORICAL_REFERENCE_GAP | **HARD_STABLE_INVARIANT** | Persistent paths must remain the expected object type and be owned by the service identity that must read/write them. Unexpected ownership/type drift can cause data loss, startup failure or unsafe writes. |
| 21 | `stable_contracts.persistent_path_metadata.*.mode` | 4 | persistent-state | HISTORICAL_REFERENCE_GAP | **SOFT_RUNTIME_CHECK** | Permissions must remain safe and usable, but a stricter valid mode can differ from the historical exact value. Gate by allowed permission policy, not byte-for-byte mode equality. |
| 22 | `stable_contracts.sqlite_schema.*.quick_check` | 3 | persistent-state | DIRECTLY_COMPARABLE | **SOFT_RUNTIME_CHECK** | Database integrity must be healthy before mutation, but this is a runtime health predicate rather than product identity. |
| 23 | `stable_contracts.sqlite_schema.*.user_version` | 3 | persistent-state | HISTORICAL_REFERENCE_GAP | **SOFT_RUNTIME_CHECK** | Schema version may intentionally advance during a supported migration. The updater must require a supported/migratable value rather than historical equality. |
| 24 | `stable_contracts.sqlite_schema.*.schema_sha256` | 3 | persistent-state | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | The exact current schema is stable during normal operation and determines whether a migration/rollback is safe. A2 may allow an explicit set of predecessor/target schema hashes, but unknown schema must stop mutation. |
| 25 | `stable_contracts.sqlite_schema.*.table_count` | 3 | persistent-state | DIRECTLY_COMPARABLE | **REMOVE** | Table count is a weak derivative of schema identity and adds no safety signal once the schema hash/version are checked. |
| 26 | `stable_contracts.public_certificate_sha256./etc/n3wfc4/tls/ca.pem` | 1 | tls | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | The FC4 private CA is the trust anchor used by Broker/Manager/nodes and is not replaced during ordinary server-certificate renewal. Unexpected change can break fleet TLS trust. |
| 27 | `stable_contracts.public_certificate_sha256./etc/n3wfc4/tls/server.pem` | 1 | tls | DIRECTLY_COMPARABLE | **DIAGNOSTIC_ONLY** | The Broker server certificate is lifecycle-managed and may be renewed while remaining valid under the same CA and hostname contract. Exact certificate bytes must not be a permanent gate. |
| 28 | `stable_contracts.public_certificate_sha256./var/lib/greenhouse-manager/identity/system-ca.pem` | 1 | tls | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | System CA is persistent greenhouse identity/recovery material. Rotation must be an explicit trust-migration operation, not ordinary module-runtime drift. |
| 29 | `stable_contracts.dynsec_top_level_keys_sha256` | 1 | broker | DIRECTLY_COMPARABLE | **HARD_STABLE_INVARIANT** | The Dynamic Security document structure is part of Broker authentication compatibility. Unknown structural drift can make authorization parsing or rollback unsafe. |
| 30 | `health.system_state` | 1 | host-runtime | DIRECTLY_COMPARABLE | **SOFT_RUNTIME_CHECK** | The host must be in an acceptable operating state before/after an upgrade, but exact historical state text is runtime health rather than product identity. |
| 31 | `health.failed_unit_count` | 1 | host-runtime | DIRECTLY_COMPARABLE | **REMOVE** | This is redundant with the failed-unit list. A2 should inspect relevant failed units directly instead of maintaining two gates for the same fact. |
| 32 | `health.failed_units` | 1 | host-runtime | DIRECTLY_COMPARABLE | **SOFT_RUNTIME_CHECK** | Current failed units matter to upgrade safety, but policy should distinguish relevant product/host failures from unrelated historical exact equality. |
| 33 | `health.systemd_units.*.{active,enabled}` | 14 | host-runtime | DIRECTLY_COMPARABLE | **SOFT_RUNTIME_CHECK** | Required activation/guard/timer semantics must be healthy, but service state is a runtime condition and some units are intentionally quiescent. |
| 34 | `health.runtime_services` | 1 | core-stack | DIRECTLY_COMPARABLE | **SOFT_RUNTIME_CHECK** | The three product services should be present when the stack is converged, but running-service presence is a runtime health condition, not immutable artifact identity. |
| 35 | `health.manager_current_authenticated` | 1 | manager | DIRECTLY_COMPARABLE | **SOFT_RUNTIME_CHECK** | Manager must authenticate to Broker for normal operation. This is a minimum post-upgrade product-health behavior. |
| 36 | `health.homeassistant_current_authenticated` | 1 | homeassistant | DIRECTLY_COMPARABLE | **SOFT_RUNTIME_CHECK** | Home Assistant must authenticate to Broker for normal operation; this is runtime health, not product identity. |
| 37 | `health.manager_mqtt_socket_count` | 1 | manager | EXPECTED_BUSINESS_RUNTIME_DRIFT | **DIAGNOSTIC_ONLY** | Exact live socket count can change transiently and is explicitly disqualified from hard equality. Authentication/functional continuity are stronger gates. |
| 38 | `health.homeassistant_mqtt_socket_count` | 1 | homeassistant | EXPECTED_BUSINESS_RUNTIME_DRIFT | **DIAGNOSTIC_ONLY** | Exact Home Assistant MQTT socket count is runtime-variable and should not gate by historical equality. |
| 39 | `health.homeassistant_http_status` | 1 | homeassistant | EXPECTED_BUSINESS_RUNTIME_DRIFT | **SOFT_RUNTIME_CHECK** | HTTP availability is required after convergence, but multiple statuses such as 200/401 can be valid; use an allowed semantic set. |
| 40 | `health.overall_pass` | 1 | core-stack | DIRECTLY_COMPARABLE | **REMOVE** | This aggregate bakes old observer assumptions, including exact socket-count rules. Keeping it would preserve the very over-gating A1 is meant to remove. |
| 41 | `runtime_observations.boot_id_sha256` | 1 | host-runtime | EXPECTED_BUSINESS_RUNTIME_DRIFT | **DIAGNOSTIC_ONLY** | Boot identity necessarily changes after reboot and is useful only to correlate evidence within one boot. |
| 42 | `runtime_observations.containers.broker.{container_id_sha256,started_at,restart_count}` | 3 | broker | EXPECTED_BUSINESS_RUNTIME_DRIFT | **DIAGNOSTIC_ONLY** | Container instance ID, start time and historical restart count are runtime history; healthy restart/recreate changes them. |
| 43 | `runtime_observations.containers.manager.{container_id_sha256,started_at,restart_count}` | 3 | manager | VERSION_AXIS_DRIFT | **DIAGNOSTIC_ONLY** | Manager container instance history changes during an authorized Manager upgrade and must not become a stable gate. |
| 44 | `runtime_observations.containers.homeassistant.{container_id_sha256,started_at,restart_count}` | 3 | homeassistant | VERSION_AXIS_DRIFT | **DIAGNOSTIC_ONLY** | Home Assistant container instance history can change during service-group restart even when HA code is unchanged; retain only for forensic timing. |
| 45 | `runtime_observations.mqtt_session.manager.count` | 1 | manager | VERSION_AXIS_DRIFT | **REMOVE** | This duplicates the Manager socket count already exposed in health and adds no independent upgrade-safety information. |
| 46 | `runtime_observations.mqtt_session.manager.{fingerprint,authenticated_event_count}` | 2 | manager | VERSION_AXIS_DRIFT | **DIAGNOSTIC_ONLY** | Connection fingerprint and historical authentication-event count change across reconnects and are useful for forensics, not gating. |
| 47 | `runtime_observations.mqtt_session.manager.identity_sha256` | 1 | manager | HISTORICAL_REFERENCE_GAP | **HARD_STABLE_INVARIANT** | Manager MQTT username/client identity is provisioned persistent identity. Unexpected change without coordinated credential/DynSec migration can break authentication or bind the wrong principal. |
| 48 | `runtime_observations.mqtt_session.homeassistant.count` | 1 | homeassistant | VERSION_AXIS_DRIFT | **REMOVE** | This duplicates the Home Assistant socket count already exposed in health. |
| 49 | `runtime_observations.mqtt_session.homeassistant.{fingerprint,authenticated_event_count}` | 2 | homeassistant | VERSION_AXIS_DRIFT | **DIAGNOSTIC_ONLY** | Connection fingerprint and authentication-event history change with reconnects and service restarts. |
| 50 | `runtime_observations.mqtt_session.homeassistant.identity_sha256` | 1 | homeassistant | HISTORICAL_REFERENCE_GAP | **HARD_STABLE_INVARIANT** | Home Assistant MQTT identity must remain bound to the intended principal unless a coordinated credential/DynSec migration is explicitly performed. |
| 51 | `runtime_observations.sqlite.*.row_counts.*` | 17 | persistent-state | EXPECTED_BUSINESS_RUNTIME_DRIFT | **DIAGNOSTIC_ONLY** | Business rows legitimately grow/change with registrations, telemetry and replay history. Counts are useful diagnostics but must not block ordinary upgrades by historical equality. |
| 52 | `runtime_observations.sqlite.*.{file_bytes,wal_bytes}` | 6 | persistent-state | EXPECTED_BUSINESS_RUNTIME_DRIFT | **DIAGNOSTIC_ONLY** | Database and WAL sizes vary with normal use, checkpoints and compaction; exact values are not product identity. |
| 53 | `runtime_observations.persistent_tree_stats.*.{file_count,directory_count,total_bytes}` | 12 | persistent-state | EXPECTED_BUSINESS_RUNTIME_DRIFT | **DIAGNOSTIC_ONLY** | Persistent trees naturally grow and shrink with normal product operation; these values are capacity/forensic signals only. |
| 54 | `runtime_observations.persistent_tree_stats.*.symlink_count` | 4 | persistent-state | EXPECTED_BUSINESS_RUNTIME_DRIFT | **SOFT_RUNTIME_CHECK** | Unexpected symlinks can make backup/restore or mutation follow unintended paths. Check a safety policy, but do not assume exact historical tree equality. |
| 55 | `runtime_observations.dynsec_counts.{clients,groups,roles}` | 3 | broker | EXPECTED_BUSINESS_RUNTIME_DRIFT | **DIAGNOSTIC_ONLY** | Client count changes with node population, and group/role counts alone are too weak to prove authorization semantics. They should not gate by exact count. |
| 56 | `runtime_observations.homeassistant_registry_counts.*.present` | 3 | homeassistant | EXPECTED_BUSINESS_RUNTIME_DRIFT | **SOFT_RUNTIME_CHECK** | Required HA registry documents should exist in a converged installation, but this is a runtime/storage health predicate. |
| 57 | `runtime_observations.homeassistant_registry_counts.*.count` | 3 | homeassistant | EXPECTED_BUSINESS_RUNTIME_DRIFT | **DIAGNOSTIC_ONLY** | Entity/device/config-entry counts legitimately change with discovery and customer use. |
| 58 | `runtime_observations.homeassistant_registry_counts.*.version` | 3 | homeassistant | EXPECTED_BUSINESS_RUNTIME_DRIFT | **SOFT_RUNTIME_CHECK** | Home Assistant may migrate storage versions. The updater should require a supported/understood version, not exact equality to the clean reference. |

Count proof:

```text
32 + 40 + 67 + 11 = 150
48 DIRECTLY_COMPARABLE
+ 58 EXPECTED_BUSINESS_RUNTIME_DRIFT
+ 15 VERSION_AXIS_DRIFT
+ 29 HISTORICAL_REFERENCE_GAP
= 150
```

## 4. Historical-gap treatment

The 29 historical public-reference gaps do not prevent A1 semantic classification. A field can still be classified by its product meaning. For example, persistent path ownership/type and MQTT principal identity are safety-relevant even though the exact R2 public leaf was not preserved.

What A1 **does not** claim is retrospective byte equality for those missing R2 leaves. No T1 wipe, historical Manager redeploy, first-registration replay or new observer run is justified to reconstruct them.

## 5. A2 input

A2 must consume A1 as a policy model, not as a single 150-field equality compare.

```text
A2_MANAGER_DEFAULT_SCOPE=MANAGER_ONLY
A2_HOMEASSISTANT_DEFAULT_SCOPE=HOMEASSISTANT_ONLY
A2_BROKER_DEFAULT_SCOPE=BROKER_ONLY

A2_HARD_GATE_MODE=BASELINE_OR_TARGET_BOUND
A2_SOFT_GATE_MODE=SEMANTIC_PREDICATE
A2_DIAGNOSTIC_MODE=NON_BLOCKING
A2_REMOVE_MODE=NOT_IN_NORMAL_UPDATER_GATE
```

The machine-readable authority is:

`infra/n3w-t1/clean-reference/a1-stable-invariant-classification-20261103.json`

with:

`A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7`

## 6. Gate boundary

```text
T1_READONLY_OBSERVER_EXECUTED=false
T1_SERVICE_RESTART=false
T1_IMAGE_CHANGE=false
DB_DYNSEC_CREDENTIAL_HA_CONFIG_WRITE=false
BOARD_ACCESS=false
UPDATER_APPLY=false
PRODUCT_SOURCE_CHANGE=false
PR773_MERGE=false
A2_EXECUTED=false
```

## 7. Final closure

```text
A1_RESULT=CLOSED_PASS
A1_CLASSIFICATION_COMPLETE=true
A2_ENTRY_READY=true
NEXT_ONE_GATE=N3W_T1_CORE_STACK_A2_PER_MODULE_UPGRADE_ARCHITECTURE_20261103_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```
