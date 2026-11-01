# T1_Core_Stack clean reference and stable invariants design

Date: 2026-10-31

Status: DESIGN_FROZEN_INTEGRATED

## 1. Canonical name

The production application stack on T1 is formally named:

```text
T1_Core_Stack
```

It contains exactly three product services:

```text
T1_Core_Stack
├── greenhouse-manager
├── Home Assistant
└── Mosquitto Broker
```

The name does not include Armbian, Docker/Compose, systemd, maintenance transactions,
upgrade executors, recovery tools, CI, SSH transport, or factory/provisioning tooling.
Those are host/platform/operations layers around the product stack.

## 2. Current maturity conclusion

```text
BROKER_PRODUCT_MATURITY=HIGH
HOMEASSISTANT_PRODUCT_MATURITY=HIGH
MANAGER_PRODUCT_MATURITY=HIGH_BUT_STILL_ACTIVE
T1_CORE_STACK_PRODUCT_BASELINE=BASICALLY_COMPLETE

UPGRADE_CONTROL_ARCHITECTURE=NOT_CONVERGED
RECOVERY_CONTROL_ARCHITECTURE=NOT_CONVERGED
```

The recent E03 failures are classified primarily as upgrade/maintenance control failures,
not evidence that the normal three-service product stack is fundamentally incomplete.

## 3. Clean reference starting point

Future upgrade architecture is designed from a clean production reference, not from a
long-running T1 historical snapshot.

```text
CLEAN_T1_CORE_REFERENCE=
official Armbian
+ required host runtime
+ freshly deployed T1_Core_Stack
+ explicit provisioning complete
+ three product services accepted
+ one controlled reboot accepted
+ no customer nodes paired yet
+ no accumulated customer runtime history
```

The clean reference is a product contract, not a byte-for-byte snapshot of one T1.

## 4. Validation philosophy

Every candidate validation point must be classified as one of:

```text
HARD_STABLE_INVARIANT
SOFT_RUNTIME_CHECK
DIAGNOSTIC_ONLY
REMOVE
```

A value may be a hard invariant only when:

1. it is expected to remain stable across normal operation on every healthy T1; and
2. violating it creates a concrete upgrade-safety or product-compatibility risk.

Normal runtime drift must not become an upgrade blocker merely because it differs from a
historical baseline.

Examples that are normally runtime-variable or diagnostic rather than hard invariants:

- container ID;
- PID;
- service start time;
- historical restart count;
- exact current MQTT socket count;
- whole runtime database SHA-256;
- whole Dynamic Security state SHA-256;
- log SHA-256;
- current node/client/entity count.

## 5. Per-module reference model

Each T1_Core_Stack module should be upgraded against its own stable reference.

### 5.1 greenhouse-manager

Candidate hard-reference inputs should be limited to stable properties such as:

- artifact/content identity;
- software/protocol version;
- entrypoint and runtime user contract;
- host-network contract where required;
- fixed configuration contract;
- persistent data paths;
- persistent schema compatibility;
- secret/TLS mount contract;
- required Broker and Home Assistant interface compatibility;
- minimum post-upgrade product-health behavior.

### 5.2 Home Assistant

Candidate hard-reference inputs should be limited to stable properties such as:

- image/manifest identity and supported version;
- fixed N3-W configuration contract;
- n3w_mqtt_bootstrap component compatibility;
- persistent /config location;
- MQTT integration compatibility;
- HTTP/service availability after convergence.

### 5.3 Mosquitto Broker

Candidate hard-reference inputs should be limited to stable properties such as:

- image/manifest identity and supported version;
- fixed broker configuration contract;
- TLS/listener roles;
- Dynamic Security schema/role contract;
- persistence location;
- compatibility required by Manager, Home Assistant and nodes.

Dynamic client counts, node identities, runtime connection counts and whole DynSec state
hashes are not product identity.

## 6. Upgrade boundary principle

Default upgrade scope is one module at a time.

```text
MANAGER_UPGRADE -> Manager only
HOMEASSISTANT_UPGRADE -> Home Assistant only
BROKER_UPGRADE -> Broker only
```

Cross-module coordinated upgrade is used only when an explicit compatibility change
requires it.

A module upgrade should verify current capability and safe state, not exact equality with a
historical runtime snapshot.

## 7. Terminal maintenance principle

Historical maintenance records remain audit evidence. They should not permanently
participate in normal future runtime gating after they are resolved.

A future converged model should prefer terminal outcomes such as:

```text
COMMITTED
ROLLED_BACK
RESOLVED_TO_PREDECESSOR
BLOCKED_UNRESOLVED
```

Only unresolved maintenance should block a new upgrade. A historical BLOCKED transaction
with a successfully committed recovery should not require permanent exemption logic in
future upgrades.

## 8. Offline deployment status

Current implementation has an important split:

```text
T1_CORE_STACK_IMAGE_DEPLOYMENT_OFFLINE_CAPABLE=true
FRESH_ARMBIAN_END_TO_END_AIRGAPPED_INSTALL=false
```

The repository already supports exact offline loading of the three product images and uses
local immutable runtime tags with `pull_policy: never`, avoiding live registry pulls during
product deployment.

However, the current per-device fresh-Armbian route can still install Docker Engine /
Compose and host packages from configured APT sources. Therefore a newly flashed Armbian
host is not yet guaranteed to reach a complete T1_Core_Stack deployment with zero network
dependency.

A future full offline installer must also carry and bind all required host packages and
dependencies, not only the three product image archives.

## 9. Planned clean-reference evidence collection

Before designing the final simplified upgrade architecture, collect a fresh clean reference
from a reinstalled T1:

1. install official Armbian;
2. establish required host runtime;
3. deploy a clean T1_Core_Stack;
4. complete explicit provisioning;
5. verify Broker, Manager and Home Assistant;
6. perform one controlled reboot and re-verify;
7. before pairing nodes or accumulating business history, collect module identity,
   configuration, persistent-path and interface-contract evidence;
8. classify every observed field into HARD_STABLE_INVARIANT, SOFT_RUNTIME_CHECK,
   DIAGNOSTIC_ONLY or REMOVE;
9. repeat selected observations after normal runtime/reboot to prove which fields actually
   remain stable.

## 10. Clean reference versus upgrade validation

A clean T1_Core_Stack is a reference system, not an upgrade target by itself.

```text
CLEAN_REFERENCE_PURPOSE=MEASURE_STABLE_PRODUCT_INVARIANTS
UPGRADE_VALIDATION_REQUIRES_VERSION_DELTA=true
UPGRADE_BASELINE=A
UPGRADE_TARGET=B
```

Upgrade validation starts only after the clean-reference work identifies the stable invariant
set. The default first real product upgrade is expected to be a Manager-only A -> B update
because Manager remains the most actively developed T1_Core_Stack component.

```text
MANAGER_A_TO_B:
  MUTATE=greenhouse-manager
  HOME_ASSISTANT_MUTATION=false
  MOSQUITTO_MUTATION=false
  HOST_PLATFORM_MUTATION=false
```

A deliberately meaningless version bump should not be created merely to make an upgrade
test exist when a real Manager successor is expected soon. A mechanism-only synthetic
successor may be used later only if architecture verification needs it.

### 10.1 Dual-T1 role model

```text
T1_A_ROLE=LEGACY_UPGRADE_AND_FAILURE_SPECIMEN
T1_A_WIPE=false

T1_B_ROLE=CLEAN_REFERENCE_AND_CLEAN_UPGRADE_TARGET
T1_B_WIPE_AND_REINSTALL_ARMBIAN=true
```

T1_A preserves the real successor-upgrade E03 failure history:
- historical BLOCKED maintenance/recovery evidence;
- a second successor retry that reached candidate deployment publish;
- Manager/Home Assistant stopped at the failure boundary;
- maintenance gate conflict reported as `multiple_active_transactions`.

The repository also contains a separate historical Manager first-registration E03 business
bug involving stale ACTIVE registration/deadline ownership. Do not assume that exact business
bug is still present on T1_A; prove it by fresh read-only evidence before selecting it as a
T1_A upgrade test case.

T1_B is the clean measurement machine and the first clean-upgrade target.

### 10.2 Canonical upgrade tool

```text
UPGRADE_TOOL=T1_Core_Updater
CLI=t1-core-updater
```

T1_Core_Updater is responsible for:
- inspect;
- plan;
- per-component upgrade;
- rollback;
- status.

It is not responsible for:
- flashing/installing Armbian;
- host kernel/platform upgrade;
- initial T1 product installation;
- board firmware upgrade.

---

## 11. Local artifact reuse boundary

The Mac exact-artifact cache mechanism remains a valid optimization, but cache validity is
always tied to exact artifact identity.

The artifact accepted on 2026-10-15 is historical for the new clean-reference route because
Manager/product source advanced afterward:

```text
HISTORICAL_LOCAL_ARTIFACT_ID=11954286988
HISTORICAL_LOCAL_ARTIFACT_ZIP_SHA256=047a40ed640bc1bfcbc8adb7007da2a4eea1f8abedffbc3cb2e2a4d9f6817928
HISTORICAL_LOCAL_ARTIFACT_REUSE_ALLOWED=false
CACHE_MECHANISM_REUSE_ALLOWED=true
```

The next frozen T1_Core_Stack artifact should be downloaded/built once, verified, stored in
the durable Mac exact-artifact cache, and reused until that exact artifact identity changes.

Detailed phased route:

```text
docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_DEVELOPMENT_PLAN_20261101.md
```

## 11. Current stop point

PR #745 is not automatically integrated by this design decision. The current live T1
remains a failed-upgrade evidence source until its minimal read-only evidence is archived.

```text
PR745_AUTO_MERGE=false
PREWIPE_PRIVATE_EVIDENCE_ARCHIVED=true
PREWIPE_PRIVATE_EVIDENCE_SHA256=711359c2b6a3522daac4ce9697a20b9876b71f202b44d6c79f65eda79f67025c
OLD_T1_RUNTIME_MAY_BE_DISCARDED=true
LIVE_UPGRADE_RETRY=false
BOARD_ACCESS=false
```

Next architecture work should use the clean T1_Core_Stack reference to redesign module
upgrade contracts from the stable invariant set instead of extending historical
transaction/recovery exceptions.
