# N3-W T1 Core Stack A2 per-module upgrade architecture closure — 2026-11-03

```text
TASK=N3W_T1_CORE_STACK_A2_PER_MODULE_UPGRADE_ARCHITECTURE_20261103_01
RESULT=CLOSED_PASS

PR773_A2_INPUT_HEAD=021ce42350333636412b1056cac46f490243c654
A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7
A2_ARCHITECTURE_SHA256=447f57f3563cb7766f145a2ea005d5d79d1beee7585ed07c6572ce2b3a833faa

UPDATER_CONCEPT=KEEP
REWRITE_FROM_SCRATCH=false
CURRENT_UPDATER_SOURCE=MANAGER_SPECIALIZED
A2_TARGET_ARCHITECTURE=GENERIC_CORE_PLUS_COMPONENT_ADAPTERS

MANAGER_UPGRADE_SCOPE=MANAGER_IMAGE_BINDING_ONLY_BY_DEFAULT
HOMEASSISTANT_UPGRADE_SCOPE=HOMEASSISTANT_IMAGE_BINDING_ONLY_BY_DEFAULT
BROKER_UPGRADE_SCOPE=BROKER_IMAGE_BINDING_ONLY_BY_DEFAULT

CURRENT_SYSTEMD_OWNERSHIP=KEEP
WHOLE_HISTORICAL_REFERENCE_EQUALITY_AS_GATE=false
GENERIC_150_FIELD_RUNTIME_POLICY_ENGINE=false
DEFAULT_MUTATION_PROFILE=IMAGE_ONLY_V1
CROSS_MODULE_AUTO_CHAIN=false
ONE_ACTIVE_UPDATER_TRANSACTION=true

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCT_SOURCE_CHANGE=false
PR773_MERGE=false

A2_RESULT=CLOSED_PASS
A2_SOURCE_IMPLEMENTATION_REQUIRED=true
U0_ENTRY_READY=false
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_A2_PER_MODULE_SOURCE_IMPLEMENTATION_20261103_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

## 1. Why A2 needs a source refactor before U0

The current `T1_Core_Updater` is production-proven for Manager A -> B, but its source is still Manager-specific:

- target schema is `gh.n3w-t1-core-updater-manager-target/1`;
- confirmation and authorization prefixes are Manager-specific;
- the only dynamic image binding is `GH_MANAGER_IMAGE`;
- candidate validation assumes only the Manager image may change;
- transaction state file is named `manager-upgrade.json`;
- stop/start/recovery logic is written around the Manager + Home Assistant service group.

Therefore A1 completion does not make U0 immediately executable. A2 freezes the architecture first, then one source-only implementation/CI gate must generalize the updater without touching the live T1.

## 2. Main architecture decision

Do **not** rewrite the updater from scratch.

Keep the proven durable transaction, exact portable image verification, atomic binding publication, explicit rollback, process lock and fresh-runtime reconciliation concepts. Refactor the Manager-specific parts into:

```text
T1_Core_Updater
├── Generic transaction/core
├── Generic host primitives
├── Manager adapter
├── Home Assistant adapter
└── Broker adapter
```

A2 explicitly rejects a generic “evaluate all 150 A1 fields from JSON” rule engine. The A1 JSON remains traceability/test authority. Runtime checks are typed, reviewed code with explicit module meaning.

## 3. What “module-only upgrade” means

Module-only means **only the selected module's version binding is mutated**.

It does not mean that no other process may restart. The existing production ownership model is preserved:

- `n3wfc4-services-activation.service` owns Manager + Home Assistant together;
- `n3wfc4-broker-activation.service` owns Broker independently;
- out-of-band Compose recreate remains forbidden.

Consequences:

| Target | Image/config mutation | Expected lifecycle side effect |
|---|---|---|
| Manager | Manager binding only | Manager + HA service group restarts; HA image/config stays unchanged |
| Home Assistant | HA binding only | Manager + HA service group restarts; Manager image/config stays unchanged |
| Broker | Broker binding only | application group is quiesced, Broker restarts, then Manager + HA restart/reconnect |

This preserves KF-129's proven supervision boundary instead of inventing a second owner.

## 4. Uniform image binding

The current fresh Compose has dynamic Manager binding but literal HA/Broker images. A2 requires one uniform pattern:

```text
GH_MANAGER_IMAGE
GH_HOMEASSISTANT_IMAGE
GH_BROKER_IMAGE
```

All three remain `pull_policy: never`.

The implementation gate must update the fresh Compose/bootstrap contract so `/etc/n3wfc4/docker-compose.env` contains exactly one binding for each product image. The updater uses one generic atomic single-line replacement primitive and never logs the environment file contents.

A whole Compose hash remains diagnostic, not an upgrade gate. In `IMAGE_ONLY_V1`, rendered Compose validation must prove that the only effective service change is the selected component's image.

## 5. Target manifest V2

Freeze a generic schema:

```text
gh.n3w-t1-core-updater-target/2
```

Required concepts:

- component = manager | homeassistant | broker;
- mutation_profile = IMAGE_ONLY_V1;
- target image reference and platform;
- exact image archive SHA-256 and artifact binding;
- expected predecessor image reference;
- rollback compatibility proof;
- target-specific compatibility evidence with current peer contracts;
- A1 classification digest.

Do not treat a Docker-local image ID created on a build host as portable cross-host authority. The exact tar/portable image identity is authoritative. After verification on T1, record the T1-local runtime image ID in the transaction for that transaction only.

## 6. A1 -> A2 execution rules

A1's 150 fields become four implementation behaviors:

| A1 class | A2 behavior |
|---|---|
| HARD_STABLE_INVARIANT | exact per-instance or explicit baseline/target contract; unknown drift stops mutation |
| SOFT_RUNTIME_CHECK | semantic predicate / supported set; benign value changes are allowed |
| DIAGNOSTIC_ONLY | collect if useful, never block by this field alone |
| REMOVE | absent from the normal updater gate |

A2 must not reintroduce these as hard gates:

- container ID;
- service start time;
- historical restart count;
- exact MQTT socket count;
- DB row count/size/WAL size;
- persistent-tree size/counts;
- DynSec client/group/role counts;
- HA entity/device/config-entry counts;
- whole Compose SHA;
- exact Broker server-certificate SHA.

The server certificate is validated semantically: chain, hostname and validity. FC4 CA/System CA remain per-instance hard trust/identity anchors.

## 7. Common preflight

Before any mutation:

1. exact updater package/target manifest/policy binding;
2. root + explicit one-shot authorization;
3. one global updater mutation lock;
4. no unresolved/non-terminal current updater transaction;
5. exact predecessor image binding;
6. exact target tar portable identity;
7. target platform supported;
8. target-specific rollback compatibility proven;
9. A1 hard per-instance contracts readable and valid;
10. A1 soft preconditions safe;
11. no proven conflicting current maintenance operation.

Historical terminal transactions never permanently block a new upgrade.

An active pairing/registration or other proven conflicting product operation causes **defer**, not historical-reference failure. A Broker upgrade additionally defers while certificate lifecycle mutation is active.

## 8. Manager adapter

### Mutation

```text
TARGET=manager
BINDING=GH_MANAGER_IMAGE
QUIESCE=stop n3wfc4-services-activation.service
PUBLISH=replace Manager image binding only
ACTIVATE=start n3wfc4-services-activation.service
BROKER_IMAGE_MUTATION=false
HA_IMAGE_MUTATION=false
```

### Required postconditions

- target Manager image/platform/runtime contract exact;
- Manager persistent path ownership/type intact;
- Manager schemas supported; in IMAGE_ONLY_V1 unknown/schema-changing targets are rejected unless state compatibility is separately proven;
- Manager MQTT identity unchanged and authenticated;
- HA hard identity/config/component contract unchanged;
- HA MQTT/HTTP health restored;
- Broker hard contract/listener/TLS health intact.

Manager/HA container IDs and restart counters may change and are diagnostic only.

## 9. Home Assistant adapter

### Mutation

```text
TARGET=homeassistant
BINDING=GH_HOMEASSISTANT_IMAGE
QUIESCE=stop n3wfc4-services-activation.service
PUBLISH=replace HA image binding only
ACTIVATE=start n3wfc4-services-activation.service
MANAGER_IMAGE_MUTATION=false
BROKER_IMAGE_MUTATION=false
```

### Required postconditions

- target HA image/platform/runtime contract exact;
- fixed HA N3-W configuration unchanged under IMAGE_ONLY_V1;
- `n3w_mqtt_bootstrap` tree unchanged under IMAGE_ONLY_V1;
- /config path ownership/type safe;
- HA MQTT identity unchanged and authenticated;
- HA HTTP returns an allowed healthy status;
- HA registry documents present and storage versions supported;
- Manager hard image/runtime contract unchanged and Manager MQTT restored;
- Broker hard contract intact.

A future HA target that requires config/custom-component or irreversible `.storage` migration is not an IMAGE_ONLY_V1 target. It requires a later explicit migration design.

## 10. Broker adapter

### Mutation

Broker has a dependency boundary, so its controlled sequence is:

```text
stop application owner
stop broker owner
replace GH_BROKER_IMAGE only
start broker owner
wait Broker listener/TLS/DynSec readiness
start application owner
wait Manager + HA authenticated readiness
```

### Required postconditions

- target Broker image/platform/runtime contract exact;
- Mosquitto fixed configuration unchanged under IMAGE_ONLY_V1;
- Dynamic Security structural contract supported;
- Broker persistence path ownership/type safe;
- FC4 CA and System CA hard identities unchanged;
- Broker server certificate semantically valid; exact server-cert bytes are not a gate;
- Manager and HA image/runtime contracts unchanged;
- Manager and HA successfully reauthenticate after Broker restart;
- required listener contract restored.

This architecture does not promise zero Broker downtime. It promises bounded, explicit, recoverable downtime with no unrelated image mutation.

## 11. Generic transaction V2

Freeze one global transaction model:

```text
STATE_ROOT=/var/lib/n3w-t1-core-updater
ACTIVE_TRANSACTION=upgrade.json
HISTORY=history/
ONE_ACTIVE_MUTATION=true
```

Generic phases:

```text
AUTHORIZED
TARGET_IMAGE_READY
QUIESCING
QUIESCED
TARGET_BINDING_PUBLISHED
ACTIVATING
TARGET_RUNTIME_STARTED
VERIFYING
COMMITTED
ROLLBACK_AUTHORIZED
ROLLBACK_QUIESCING
ROLLBACK_BINDING_RESTORED
ROLLBACK_ACTIVATING
ROLLED_BACK
FAILED_EMERGENCY
```

Recovery is selected from **fresh runtime classification plus transaction history**, never from a stale phase string alone.

Rules retained from V2 Manager experience:

- predecessor already healthy -> close `ROLLED_BACK` without mutation;
- target healthy but transaction non-terminal -> default explicit recovery is rollback, never silent commit;
- known stopped state + known binding -> restore predecessor through the module adapter;
- unknown binding/runtime or hard A1 drift -> fail closed;
- terminal COMMITTED/ROLLED_BACK history is archived before a new transaction and does not remain a permanent blocker.

## 12. Legacy transaction migration

Current Manager updater uses `manager-upgrade.json` with transaction schema V1.

A2 source implementation must not silently reinterpret a non-terminal V1 transaction.

```text
V1_TERMINAL -> archive as historical evidence when V2 first mutates
V1_NONTERMINAL -> STOP; use explicit legacy reconciliation
V1_AUTHORIZATION -> never replay into V2
```

This directly implements the frozen rule that only unresolved current maintenance may block a new upgrade.

## 13. Rollback policy

IMAGE_ONLY_V1 accepts only targets with target-specific rollback compatibility proof.

Rollback restores the predecessor image binding and uses the same production owner sequence as apply. It then re-runs hard/soft postchecks for the predecessor.

If a target requires an irreversible DB/storage/config migration, it is **not** accepted merely because an image tar exists. A later migration-capable profile must explicitly define backup, forward migration, rollback/restore and compatibility semantics.

## 14. Independent post-upgrade product acceptance

Updater `COMMITTED` means:

> the technical component transaction reached the target and minimum A1 runtime health passed.

It does **not** by itself mean repository/product acceptance is complete.

Keep a separate post-upgrade acceptance gate:

- Manager: product behavior / MQTT / relevant business path;
- Home Assistant: HTTP, MQTT, integration/registry behavior;
- Broker: TLS/listeners, Manager+HA reconnect, relevant node path when required.

Only that later gate advances canonical repository `live_deployment` authority.

## 15. PR #745 disposition

Fresh PR review shows #745 changes only E03 maintenance activation-gate/recovery lineage files. It does not implement the generic T1_Core_Updater.

A2 disposition:

```text
PR745_AUTO_MERGE=false
PR745_IMPLEMENTATION_HARVEST=false
PR745_HISTORICAL_EVIDENCE=KEEP
```

Keep only its general lessons:

- fail closed;
- reconcile from fresh runtime facts;
- terminal history is not a permanent blocker;
- consumed authorizations are never replayed.

Do not carry forward E03-specific BLOCKED exemptions, gate-lineage chains or postpublish predecessor special recovery into the new updater.

## 16. Source implementation gate before U0

The original clean-reference route showed A2 -> U0. Fresh source review proves a bounded implementation bridge is required because the current updater and fresh Compose are still Manager-specialized.

Required next gate:

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_A2_PER_MODULE_SOURCE_IMPLEMENTATION_20261103_01
```

It is source/test only and must implement:

1. target manifest V2;
2. transaction V2;
3. component adapter interface;
4. three dynamic image bindings;
5. typed A1 common/module checks;
6. Manager regression adapter;
7. Home Assistant adapter;
8. Broker adapter;
9. safe V1 terminal history migration;
10. no-cross-component-mutation tests;
11. per-component fault matrices;
12. CI + independent source review.

Only after that source gate closes PASS can U0 freeze a real baseline A under the new architecture.

## 17. Boundary

```text
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
UPDATER_APPLY=false
PRODUCT_SOURCE_CHANGE=false
PR745_MERGE=false
PR773_MERGE=false
U0_EXECUTED=false
```

## 18. Final closure

```text
A2_RESULT=CLOSED_PASS
A2_ARCHITECTURE_FROZEN=true
A2_SOURCE_IMPLEMENTATION_REQUIRED=true
U0_ENTRY_READY=false
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_A2_PER_MODULE_SOURCE_IMPLEMENTATION_20261103_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```
