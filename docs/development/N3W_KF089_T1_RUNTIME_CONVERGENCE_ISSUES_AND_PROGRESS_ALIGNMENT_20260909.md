# N3-W KF-089 T1 Runtime Convergence — Issues Archive and Progress Alignment

Date: 2026-09-09  
Status: `CURRENT_RUNTIME_ALIGNMENT_AUTHORITY`  
Scope: public-safe T1 runtime convergence archive; no raw credentials, private host paths, private addresses, board identities, Setup Secret, raw NVS, or private evidence locators are included.

## 1. Why this detour exists

The active N3-W/KF-089 route was originally blocked before fresh RF execution because Board A Direct telemetry was no longer freshly proven after a power-loss / T1-runtime disturbance. During the T1 investigation, the host was found to contain historical Docker runtime residue: two Manager-like containers and two Broker-like containers. Runtime authority had to be rebound before any cleanup.

The user authorized a bounded T1 cleanup strategy: preserve Home Assistant and all N3-W authority/state, allow InfluxDB/Grafana data to be discarded if present, remove obsolete N3-W runtime residue, and rematerialize exactly one Broker + one Manager from a clean single-lineage deployment definition.

Current cleanup is still an infrastructure detour. It does not reopen frozen FC4 product acceptance and does not change the frozen firmware/product-source authority.

## 2. Valuable issues found in this conversation

### T1RC-001 — Duplicate Manager/Broker runtime residue created authority ambiguity

Observed:

```text
RAW_MANAGER_LIKE_COUNT=2
AUTHORITATIVE_MANAGER_COUNT=1
LEGACY_MANAGER_COUNT=1

RAW_BROKER_LIKE_COUNT=2
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_BROKER_COUNT=1
```

Impact: name-based container inspection was not sufficient to determine the active production authority. Historical Compose/runtime objects could mislead diagnostics and repair actions.

Resolution in this conversation:

- exact authoritative Manager and Broker were rebound from image/Compose/config/runtime lineage evidence;
- legacy Manager and legacy Broker were proven to have no retained-client or shared-state dependency;
- one legacy Manager, one legacy Broker, and two legacy Docker networks were removed;
- post-removal inventory reached one Manager-like and one Broker-like object, with authoritative runtime preserved.

Regression rule: never identify Manager/Broker authority by container name alone. Fresh runtime binding must include Compose lineage, image authority, mounts/config authority, and current client dependency evidence.

Status: `RESOLVED_IN_CURRENT_RUNTIME`.

### T1RC-002 — Read-only executor created and removed a temporary inventory file

Observed:

```text
READONLY_SCOPE_VIOLATION=true
T1_MUTATION=false
DOCKER_RUNTIME_MUTATION=false
```

The gate was declared read-only but the executor briefly created and removed a temporary inventory file. No Docker/runtime object changed.

Impact: the evidence remained useful for planning but was not eligible as a clean read-only acceptance closure.

Regression rule: strict read-only gates must use stdout, pipes, command substitution, or in-memory processing only. Temporary file creation is a scope violation even when immediately removed.

Status: `GUARDED_BY_EXECUTION_CONTRACT`.

### T1RC-003 — Historical Broker exit was initially over-classified as TLS-fatal

Evidence recovered during the T1 outage investigation:

- authoritative Broker had exited with code 255;
- TLS listener/runtime error evidence existed;
- the final recovered TLS error occurred roughly nineteen hours before the Broker exit;
- Broker continued running after that TLS event;
- TLS CA/certificate/private-key authority was present, parseable, chain-valid, and valid at the time of the later Broker exit;
- no certificate expiry, cert/key mismatch, rotation failure, or TLS reload failure was proven.

The earlier `TLS_RUNTIME_FATAL` terminal interpretation was therefore superseded.

Regression rule: a runtime error may only be classified as terminal/cause-of-exit if its temporal and lifecycle relationship to the exit is proven. Long-separated earlier errors are supporting history, not exit causality.

Status: `RESOLVED_CLASSIFICATION`; exact exit-255 origin remains historically unresolved.

### T1RC-004 — T1 reboot did not restore the authoritative Broker

Historical current-boot evidence showed:

- Docker daemon restored after T1 boot;
- authoritative Manager later appeared/restored;
- authoritative Broker remained exited and had no proven automatic restart attempt;
- both authoritative Broker and Manager used an `unless-stopped` restart policy;
- the exact Docker restore-decision provenance was not recoverable.

A bounded one-time Broker start later succeeded; Broker remained healthy and Manager stabilized.

Regression rule: final T1 convergence acceptance must include a controlled reboot/boot-recovery test after the clean runtime is healthy. Container existence plus `unless-stopped` is not sufficient proof that Docker will restore the service after host reboot.

Status: `OPEN_FOR_POST_CONVERGENCE_REBOOT_ACCEPTANCE`.

### T1RC-005 — Manager password/mount anomaly was real evidence but not the active root cause

During the earlier Manager restart-loop investigation a password-source/mount anomaly was recovered. Later authority recovery proved the correct Manager/Broker lineage, and bounded Broker start stabilized Manager without password repair.

The anomaly must therefore be retained as diagnostic evidence but not promoted to root cause without fresh authentication evidence.

Regression rule: do not repair or rotate credentials merely because a historical credential-source anomaly exists. Require current MQTT authentication rejection or direct authority mismatch first.

Status: `RETAINED_NOT_ACTIVE_ROOT_CAUSE`.

### T1RC-006 — Hot preservation package became stale while Broker/Manager were still running

A clean deployment and preservation package was successfully materialized, but immediately before destructive rematerialization the following mutable state no longer matched its hot backup:

```text
BROKER_DATA_BACKUP_STILL_EQUALS_SOURCE=FAIL
MANAGER_SQLITE_BACKUP_STILL_EQUALS_SOURCE=FAIL
MANAGER_RELAY_KEY_BACKUP_STILL_EQUALS_SOURCE=FAIL
PRESERVATION_PACKAGE_STALE=true
```

Static authorities such as Broker config/DynSec/TLS and Manager/Provisioning credentials still matched.

Resolution:

- Manager was stopped first;
- Broker was stopped second;
- mutable state was allowed to quiesce;
- Broker data, Manager SQLite and relay-key state were refreshed;
- equality and no-write-during-backup checks all passed;
- rollback recipe was rebound to the fresh quiesced snapshot.

Regression rule: destructive rematerialization of stateful runtime must use a quiesced snapshot, not a hot mutable-state backup, unless an application-consistent online snapshot mechanism is explicitly proven.

Status: `GUARDED_BY_QUIESCED_PRESERVATION`.

### T1RC-007 — Clean Broker runtime succeeded, but clean Manager failed with `ENETUNREACH`

During clean rematerialization:

- old authoritative Manager and Broker were removed from a fully quiesced/rollback-safe state;
- clean Broker created and started successfully;
- Broker remained running for 60 s with restart count 0, required listener present, TLS listener present, DynSec PASS, and no fatal error;
- clean Manager created successfully but immediately entered repeated failure/restart behavior;
- fatal stage was later recovered as `TCP_CONNECT` with `ENETUNREACH`;
- bounded Manager-only rollback was attempted, but the rolled-back Manager also remained unable to reach the Broker.

This proved the failure was not specific to clean Manager source/config alone.

Status: `ROOT_CAUSE_MOVED_TO_BROKER/HOST_NETWORK_PATH`.

### T1RC-008 — Broker host publication semantics were lost at Docker runtime materialization

Detailed forensic evidence proved all upper layers were correct:

```text
RAW_RECIPE_PUBLICATION=PRESENT
EFFECTIVE_COMPOSE_PUBLICATION=PRESENT
CONTAINER_HOSTCONFIG_PUBLICATION=PRESENT
CONTAINER_RUNTIME_PUBLICATION=ABSENT
OLD_SUCCESSFUL_HOST_PUBLICATION=PRESENT
```

More specifically:

- private Compose declared three Broker port publications including TLS 8883;
- `docker compose config` retained those publications;
- the actual recreated Broker was created from the expected patched Compose file/project/service;
- `HostConfig.PortBindings` contained the three bindings, including 8883;
- `NetworkSettings.Ports` did not contain the expected runtime mapping;
- `docker port` returned zero mappings;
- the old successful Broker snapshot proved real host port bindings, not merely `ExposedPorts`;
- the old successful Manager-to-Broker path used Docker host port binding.

Current root classification:

```text
ROOT_DOMAIN=DOCKER_RUNTIME
ROOT_CLASS=HOST_PORT_BINDING_RUNTIME_MATERIALIZATION_FAILURE
ROOT_SUBCLASS=HOSTCONFIG_BINDING_PRESENT_NETWORKSETTINGS_MAPPING_ABSENT
```

Regression rule: distinguish all three layers explicitly:

```text
Config.ExposedPorts
HostConfig.PortBindings
NetworkSettings.Ports / docker port runtime mapping
```

A Compose `ports:` declaration or HostConfig binding is not sufficient evidence that a host publication was actually programmed by Docker.

Status: `OPEN`.

### T1RC-009 — Recreating Broker with a corrected publication recipe did not repair the runtime mapping

A bounded repair attempted to reproduce the previously successful host publication contract exactly. The patched recipe had zero non-publication deltas and passed offline Compose validation. Broker recreation again passed all internal runtime checks, but host publication was still absent and host-to-Broker TLS connectivity still failed.

This ruled out a simple Compose declaration/override/file-selection problem and moved the fault below Compose/container configuration into Docker runtime networking/programming.

Status: `OPEN`; current next forensic target is Docker host-port materialization.

### T1RC-010 — Previous reboot failure and current port-binding failure have similar symptoms but are not yet proven to share one root cause

Earlier T1 reboot issue:

```text
Broker did not restore/start
Manager could not use Broker
```

Current issue:

```text
Broker is running and internally healthy
HostConfig.PortBindings is correct
runtime host-port mapping is absent
Manager cannot reach Broker
```

Therefore:

```text
SAME_USER_VISIBLE_SYMPTOM=true
SAME_DIRECT_ROOT_CAUSE=false
COMMON_SUBSYSTEM_CANDIDATE=DOCKER_RUNTIME_NETWORKING
COMMON_ROOT_CAUSE_PROVEN=false
```

Regression rule: do not merge these incidents into one root cause until Docker daemon/network evidence proves the connection.

Status: `OPEN_CORRELATION`.

### T1RC-011 — Current `ENETUNREACH` has a direct historical comparator in existing KF-035

The central known-failure index already contains an OPEN guard, `KF-035 / FC4 host-network Manager / Broker TLS continuity`. That historical incident proved an important deployment fact:

- Manager intentionally runs with host networking;
- the Broker remains containerized and must publish TLS 8883 to the exact host-side address actually resolved by the Manager's own image/network namespace;
- assuming all loopback hostnames resolve to the same address is invalid;
- historical `Network is unreachable` was caused by using host-side resolution as authority instead of exact Manager-image + host-network `getaddrinfo()` evidence.

The adjacent `KF-034` explains why Manager host networking is intentional: Docker bridge/`ports` could not carry the required limited-broadcast pairing path, so the final-product Manager deployment uses host networking.

Current evidence is not yet sufficient to declare the present incident a recurrence of KF-035 because the present failure is one layer lower in Docker runtime bookkeeping:

```text
HostConfig.PortBindings=PRESENT
NetworkSettings/runtime mapping=ABSENT
```

However, KF-035 becomes the primary historical comparator. The next forensic must therefore prioritize checking whether the current `HostConfig.PortBindings` target a specific host address/interface that is now absent or down before classifying the incident as a generic Docker daemon/NAT defect.

Freeze:

```text
HISTORICAL_GUARD_CORRELATION=KF-035
KF035_RECURRENCE_PROVEN=false
KF035_BIND_ADDRESS_HYPOTHESIS_REQUIRES_FRESH_READONLY_CHECK=true
```

Status: `OPEN_CORRELATION`.

## 3. T1 cleanup progress reached in this conversation

### 3.1 Inventory / authority convergence

Completed:

```text
AUTHORITATIVE_MANAGER_COUNT=1
LEGACY_MANAGER_COUNT=0
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_BROKER_COUNT=0
LEGACY_NETWORK_REMOVE_COUNT=2
```

The legacy Broker had no retained-client dependency, no shared config/DynSec/TLS/data authority, no current Compose authority, and no boot-orchestration requirement before removal.

### 3.2 Preservation / rollback readiness

Completed:

```text
BROKER_PRESERVATION_PACKAGE_COMPLETE=true
MANAGER_PRESERVATION_PACKAGE_COMPLETE=true
HA_NON_TARGET_PRESERVATION_BOUNDARY_COMPLETE=true
PRIVATE_ROLLBACK_RECIPE_COMPLETE=true
QUIESCED_PRESERVATION_READY=true
```

The final preservation package is based on a quiesced Manager/Broker state and was equality-checked before destructive rematerialization.

### 3.3 Clean Broker status

Current clean Broker:

```text
BROKER_RUNNING=true
BROKER_RESTART_COUNT=0
BROKER_REQUIRED_LISTENER_PRESENT=true
BROKER_TLS_LISTENER_PRESENT=true
BROKER_DYNSEC_RUNTIME=PASS
BROKER_CONFIG_AUTHORITY=PASS
BROKER_DYNSEC_AUTHORITY=PASS
BROKER_TLS_AUTHORITY=PASS
BROKER_DATA_CONTINUITY=PASS
BROKER_RESTART_POLICY=unless-stopped
```

However:

```text
HOSTCONFIG_PORTBINDINGS_PRESENT=true
CONTAINER_RUNTIME_PUBLICATION=ABSENT
HOST_TO_BROKER_PUBLICATION_REACHABLE=false
```

### 3.4 Manager status

Current Manager object is the bounded rolled-back Manager. It was deliberately stopped after the failed Broker-publication repair and must remain stopped during the next Docker networking forensic.

```text
CURRENT_MANAGER_STATE=STOPPED
CURRENT_MANAGER_CONFIG_REPAIR_REQUIRED=false
CURRENT_MANAGER_CREDENTIAL_REPAIR_REQUIRED=false
```

The previously observed fatal path was:

```text
TCP_CONNECT -> ENETUNREACH
```

### 3.5 Home Assistant status

Home Assistant remains a non-target service and has not been restarted/recreated as part of this cleanup. It is expected to reconnect naturally after Broker host reachability is restored.

## 4. Current physical boundary

Fresh RF execution has not resumed.

```text
BOARD_A_STATE=BATTERY_POWERED_AT_FIXED_RELAY_ANCHOR_POSITION
BOARD_B_STATE=UNPOWERED_AT_QUALIFIED_RF_POSITION
BOARD_B_APP1_SCHEMA_V4_DEPLOYED=true
BOARD_B_POST_DEPLOYMENT_APPLICATION_SESSION_CREATED=false
```

Board B must remain unpowered at the qualified RF position until a future explicit physical gate. No Board A reset/power action is part of the current T1 detour.

The original RF execution was interrupted before the canonical Board A Direct prewindow was completed; Board B was not powered and the 120 s RF observation did not start.

## 5. Source / product authority alignment

```text
REPOSITORY_MAIN_AT_ALIGNMENT_BASE=406f6022cc8a4267397a338156592aa507a3ff3a
REPOSITORY_MAIN_TREE_AT_ALIGNMENT_BASE=6bf72d98097fdd32354451a5b177fe1b28b2a15a
PRODUCT_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
DIAGNOSTIC_SCHEMA_VERSION=4
```

No product firmware/source change was made by the T1 cleanup detour. Documentation-only descendants do not redefine product-source authority.

## 6. KF-089 product status remains frozen

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_AUTONOMOUS_DISCOVERY_ENTRY=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=NOT_PROVEN
KF089_AUTHENTICATED_RELAY_ACQUISITION=NOT_PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=DISCOVERY_ADVERTISEMENT_ACCEPTANCE
```

The T1 runtime detour does not change this product-level acceptance boundary.

## 7. Current blocker and next ONE gate

Current blocker:

```text
CURRENT_BLOCKER=T1_DOCKER_HOST_PORT_BINDING_RUNTIME_MATERIALIZATION_FAILURE
```

Next ONE gate:

```text
NEXT_ONE_GATE=N3W_KF089_T1_DOCKER_HOST_PORT_BINDING_RUNTIME_READONLY_FORENSIC_20260909_01
```

The next gate is read-only and must keep:

```text
CLEAN_BROKER_RUNNING=true
CURRENT_MANAGER_RUNNING=false
BOARD_ACCESS=false
BOARD_MOVEMENT=false
RF_EXECUTION=false
T1_MUTATION=false
```

Primary forensic targets, in priority order:

1. exact `HostConfig.PortBindings` HostIP class and whether any required explicit bind address/interface is currently present and UP — this is the direct KF-035 comparator;
2. exact Docker network driver/bridge/veth materialization;
3. host-to-container direct reachability;
4. host listener/socket evidence;
5. userland-proxy policy/process state;
6. iptables/nftables/NAT chains and exact Broker publish rules;
7. Docker daemon network/programming errors near Broker create;
8. comparison with the old successful Broker network object;
9. whether the two removed legacy networks were truly unrelated;
10. Docker daemon network-config drift.

No Manager restart, Broker recreate, route/firewall mutation, Docker daemon restart, or T1 reboot is authorized by this forensic gate.

## 8. Exit criteria for the T1 convergence detour

The T1 cleanup detour is not complete until all of the following are proven:

```text
MANAGER_LIKE_COUNT=1
BROKER_LIKE_COUNT=1
LEGACY_MANAGER_COUNT=0
LEGACY_BROKER_COUNT=0
N3W_ACTIVE_COMPOSE_LINEAGE_COUNT=1

BROKER_HOST_PUBLICATION_RUNTIME=PASS
BROKER_TLS_DYNSEC_RUNTIME=PASS
MANAGER_TO_BROKER_TLS_MQTT=PASS
HA_TO_BROKER_RUNTIME_CONTINUITY=PASS

T1_RUNTIME_RESIDUE_POSTCHECK=PASS
T1_CONTROLLED_REBOOT_BOOT_RECOVERY=PASS
```

Only after the clean T1 baseline is proven should the route return to Board A Direct re-verification and then, if that passes, the canonical RF prewindow / fresh RF execution sequence.

## 9. Final convergence closure — 2026-09-10

The T1 runtime-convergence detour is closed. The final read-only post-reboot
acceptance proved one authoritative Manager, one authoritative Broker, the
required Broker two-network topology, live host publication for all required
Broker mappings, and automatic recovery after one controlled T1 reboot.

The final root cause and repair closure is:

- the previous successful Broker topology used both the private/internal
  network and the external reachability network;
- the successor/rematerialization recipe omitted the external network
  attachment, leaving the clean Broker internal-only and preventing host
  publication from becoming usable by Manager;
- the exact external reachability network attachment was restored;
- runtime host mappings, including TLS 8883, were restored and verified after
  rematerialization and reboot;
- Manager recovered its TLS MQTT session and remained healthy;
- Home Assistant had a post-reboot live authenticated MQTT relationship with
  the current authoritative Broker, proven by an exact runtime socket to the
  current Broker TLS endpoint;
- the controlled T1 reboot acceptance passed without manual container repair,
  runtime residue reappearing, or a second reboot.

```text
ROOT_DOMAIN=T1_RUNTIME_CONVERGENCE
ROOT_CLASS=T1_RUNTIME_CONVERGENCE_FINAL_ACCEPTANCE_PASS
ROOT_SUBCLASS=SINGLE_MANAGER_SINGLE_BROKER_TWO_NETWORK_REBOOT_RECOVERY_AND_HA_CONTINUITY_PROVEN
ROOT_CAUSE_RUNTIME_CONFIRMED=true
INCIDENT_ROOT_DOMAIN=DEPLOYMENT_NETWORK
INCIDENT_ROOT_CLASS=CLEAN_BROKER_SECOND_NETWORK_ATTACHMENT_LOST
INCIDENT_ROOT_SUBCLASS=EXTERNAL_REACHABILITY_NETWORK_OMITTED_DURING_REMATERIALIZATION
NETWORK_ATTACHMENT_LOSS_STAGE=SUCCESSOR_RECIPE_MATERIALIZATION
CONTROLLED_REBOOT_REGRESSION_AFTER_REPAIR=PASS
T1_RUNTIME_CONVERGENCE_FINAL_ACCEPTANCE=PASS
```

No product source, firmware, Broker configuration, Manager source, workflow,
board, or RF state was changed by this closeout. The active detour is none;
the next route is the Board A Direct post-T1 recovery read-only verification.
