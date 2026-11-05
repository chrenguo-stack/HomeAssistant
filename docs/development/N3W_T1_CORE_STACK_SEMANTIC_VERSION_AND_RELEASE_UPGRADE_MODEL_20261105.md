# N3-W T1 Core Stack semantic version and release-upgrade model

Date: 2026-11-05

## 1. Gate

```text
TASK=N3W_T1_CORE_STACK_SEMANTIC_VERSION_AND_RELEASE_UPGRADE_MODEL
STATE=SOURCE_MODEL_IMPLEMENTATION

BASE_MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774
UPSTREAM_HA_PREPARATION_HEAD=2631729ec77045695424ce6bacb1fd0fa6685437

LIVE_T1_MUTATION=false
SERVICE_RESTART=false
IMAGE_LOAD=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
CREDENTIAL_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This model adds a product-release layer above the already existing exact component updater.
It does not replace the updater and does not change the already accepted Manager U1 result.

## 2. Product identity

T1_Core_Stack is the production software product composed of:

- greenhouse-manager;
- Home Assistant;
- Mosquitto Broker;
- the runtime contract needed to run those three components together.

The product has two separate identities:

```text
stack_version = human/product semantic version
release_id    = exact content-addressed release identity
```

Example:

```text
T1_Core_Stack 1.1.0
release_id=<sha256 of exact release material>
```

A semantic version is not an exact artifact identity. A release ID is not a user-facing product
version. Both are required.

## 3. Version rules

The product version format is strict:

```text
MAJOR.MINOR.PATCH
```

Policy:

- PATCH: bounded compatible repair with no intended product capability expansion;
- MINOR: compatible component update, feature addition, or compatible runtime-contract change;
- MAJOR: incompatible product contract, persistent-state migration model, deployment architecture,
  or other change that cannot be accepted as a normal compatible successor.

A component does not need to change merely because the Stack version changes. A new Stack release
is a new accepted combination of all three components plus the runtime contract.

Accepted releases are immutable:

```text
same stack_version -> exactly one accepted release_id
```

If exact accepted content changes after publication, a new semantic version is required.

## 4. Current accepted release

The already accepted live stack is now assigned the product version:

```text
T1_CORE_STACK_VERSION=1.0.0
T1_CORE_STACK_RELEASE_ID=5debfbe23356d67ea5ff095f7ffc3e5443d771ddb4241589fa496b901ff2b7d9
```

Machine-readable authority:

`infra/n3w-t1/releases/t1-core-stack-1.0.0.json`

This designation does not change any T1 runtime bytes. It only gives the current accepted
combination an explicit product release identity.

The release contains:

```text
Manager        local/greenhouse-manager:fresh-5b32e1ae8210
Home Assistant local/n3w-homeassistant:2026.10.0-0c73235a
Broker         local/n3w-mosquitto:2.1.2-3184566d

Manager binding        dynamic
Home Assistant binding legacy_static
Broker binding         legacy_static
```

The immutable image identities are bound by the strongest already available repository authority:
Manager exact tar SHA256 and HA/Broker exact manifest digest SHA256.

## 5. Release schema

The source contract is implemented in:

`tools/n3w_t1_core_stack_release.py`

Schema:

```text
gh.n3w-t1-core-stack-release/1
```

A release binds:

- `stack_version`;
- exact `release_id`;
- product source head;
- all three component image references;
- all three component immutable identities;
- linux/arm64 platform;
- live Compose path;
- per-component image-binding mode;
- Manager/HA shared service owner;
- Broker independent service owner.

The `release_id` is SHA256 over canonical release material with `release_id` itself omitted.
Therefore changing a component image, immutable identity, source head, binding mode, or service
ownership changes the exact release identity.

## 6. Upgrade plan

The Stack layer compares two complete release manifests and produces a bounded change set.

For the intended first successor:

```text
FROM=T1_Core_Stack 1.0.0
TO=T1_Core_Stack 1.1.0
```

Expected change set:

```text
Manager        KEEP
Home Assistant UPGRADE
Broker         KEEP
Runtime        UPDATE
```

The runtime update is the HA image-binding convergence:

```text
legacy_static -> dynamic
```

The stack planner also binds:

- predecessor release ID;
- target release ID;
- rollback authority release ID;
- target-acceptance commit rule.

The target semantic version must be greater than the predecessor. An empty semantic-version bump
with no component or runtime-contract change is rejected.

## 7. Stack transaction semantics

A component updater transaction and a Stack release transaction are different layers.

The existing T1_Core_Updater remains the component mutation engine. It owns exact image
verification, component mutation, health checks, component rollback, interruption handling, and
component transaction evidence.

The new Stack layer owns:

- current committed Stack release;
- target Stack release;
- full change set;
- ordering across runtime-contract and component mutations;
- Stack-level commit;
- Stack-level rollback authority;
- final whole-stack acceptance.

The Stack version must not change when the first mutation starts.

Freeze:

```text
CURRENT_COMMITTED_STACK=1.0.0
TARGET_STACK=1.1.0
STACK_TRANSACTION=IN_PROGRESS
```

During a transaction, the live host may temporarily match neither complete release. This transient
state is permitted only while an explicit Stack transaction is active and has an exact predecessor
rollback authority.

Only after full target acceptance:

```text
TARGET_STACK_ACCEPTANCE=PASS
CURRENT_COMMITTED_STACK=1.1.0
STACK_TRANSACTION=COMMITTED
```

## 8. Important correction to the earlier HA route

The earlier HA preparation placed live HA template convergence before exact HA target-package
creation. That is not acceptable once Stack release semantics are introduced.

Reason: a live HA binding mutation would make the host stop matching the committed 1.0.0 release
before a complete 1.1.0 target and rollback authority exist.

Therefore:

```text
HA template convergence READONLY preflight
= may proceed early

HA template convergence LIVE mutation
= must not proceed independently
```

The live convergence mutation becomes an internal step of the authorized 1.0.0 -> 1.1.0 Stack
transaction.

This prevents a persistent unversioned intermediate state.

## 9. Revised 1.0.0 -> 1.1.0 route

Freeze the new ordering:

```text
S0_SOURCE_MODEL_AND_HA_COMPATIBILITY
-> S1_HA_TEMPLATE_CONVERGENCE_READONLY_PREFLIGHT
-> S2_EXACT_HA_2026_10_4_ARTIFACT
-> S3_BUILD_EXACT_STACK_1_1_0_RELEASE
-> S4_STACK_UPGRADE_PLAN_AND_SOURCE_SIMULATION
-> S5_FRESH_READONLY_PREMUTATION_BASELINE
-> S6_EXPLICIT_STACK_UPGRADE_AUTHORIZATION
-> S7_LIVE_STACK_TRANSACTION
     -> converge HA binding legacy_static -> dynamic
     -> apply exact HA component target through T1_Core_Updater
     -> verify Manager/HA/Broker and runtime contract
-> S8_TARGET_STACK_1_1_0_ACCEPTANCE
-> S9_EXPLICIT_STACK_ROLLBACK_PROOF
     -> restore HA predecessor
     -> restore predecessor runtime-template binding
     -> prove exact Stack 1.0.0 acceptance
-> S10_FRESH_AUTHORIZATION_AND_FINAL_1_1_0_REAPPLY
-> S11_FINAL_STACK_1_1_0_ACCEPTANCE
```

No live Stack mutation is authorized by this document.

## 10. 1.1.0 target policy

The intended first target remains:

```text
STACK_VERSION=1.1.0

Manager        unchanged from 1.0.0
Home Assistant 2026.10.4 exact ARM64 artifact
Broker         unchanged from 1.0.0

Manager binding        dynamic
Home Assistant binding dynamic
Broker binding         legacy_static
```

However, `t1-core-stack-1.1.0.json` must not be finalized yet.

The exact HA 2026.10.4 ARM64 artifact identity is still missing. Until it exists:

```text
STACK_1_1_0_RELEASE_READY=false
STACK_1_1_0_RELEASE_ID=UNASSIGNED
```

A source-level compatibility review is not sufficient to mint the final Stack release.

## 11. Stack-level acceptance

A component PASS is necessary but not sufficient.

The target Stack release may commit only when all of the following match the target release and
product contract:

- Manager exact image/identity expected;
- HA exact image/identity expected;
- Broker exact image/identity expected;
- expected image-binding modes;
- expected service ownership;
- Manager MQTT authenticated;
- HA MQTT authenticated;
- HA HTTP ready;
- Broker TLS/listener contract healthy;
- persistent-state contract accepted;
- no unexpected peer image drift;
- no incomplete component transaction;
- no incomplete Stack transaction recovery;
- exact target release ID bound.

The final product result is:

```text
T1_CORE_STACK_UPGRADE=1.0.0->1.1.0
TARGET_STACK_ACCEPTANCE=PASS
```

not merely `HOMEASSISTANT_UPGRADE=PASS`.

## 12. Stack-level rollback

Rollback authority is the complete predecessor release manifest.

For the first successor proof:

```text
ROLLBACK_AUTHORITY=T1_Core_Stack 1.0.0
```

Rollback must therefore restore both:

- the predecessor Home Assistant image;
- the predecessor HA runtime binding mode.

Manager and Broker are verified as unchanged, not opportunistically rewritten.

A rollback that restores only the HA image but leaves the HA binding mode at the 1.1.0 contract
does not restore exact Stack 1.0.0 and cannot count as Stack rollback PASS.

## 13. User-facing product behavior

Normal product UI should expose:

```text
Current system version: T1 Core Stack 1.0.0
Available version:      T1 Core Stack 1.1.0
```

Internal component versions remain available for diagnostics, but the farmer-facing update target is
the Stack release, not independent Home Assistant/Mosquitto/Manager versions.

Home Assistant upstream releases do not automatically become product releases. They first pass
compatibility review, exact artifact build, integration acceptance, rollback proof, and Stack
release publication.

## 14. Boundaries and next gate

```text
STACK_1_0_0_RELEASE_FROZEN=true
STACK_1_1_0_VERSION_RESERVED=true
STACK_1_1_0_RELEASE_READY=false

HA_TEMPLATE_READONLY_PREFLIGHT_ALLOWED=true
HA_TEMPLATE_LIVE_MUTATION_ALLOWED=false
INDEPENDENT_HA_COMPONENT_APPLY_ALLOWED=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_HOMEASSISTANT_RUNTIME_TEMPLATE_CONVERGENCE_READONLY_PREFLIGHT_20261105_01
NEXT_GATE_LIVE_MUTATION=false
MERGE=false
```

After the read-only convergence proof, the route goes to exact HA artifact + exact Stack 1.1.0
release construction. It does not go directly to the live convergence mutation.
