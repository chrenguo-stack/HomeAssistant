# N3-W T1_Core_Updater Manager A -> B source design — 2026-11-02

## 1. Scope

This document freezes the first canonical T1_Core_Updater product path required by the clean-reference architecture.

```text
UPGRADE_TOOL=T1_Core_Updater
CLI=t1-core-updater
COMPONENT=greenhouse-manager
BASELINE_A=local/greenhouse-manager:fresh-24382caae4a1
TARGET_B=local/greenhouse-manager:fresh-3539c8f871e2
HOME_ASSISTANT_IMAGE_MUTATION=false
BROKER_IMAGE_MUTATION=false
HOST_PLATFORM_MUTATION=false
BOARD_ACCESS=false
LIVE_T1_MUTATION=false
MAIN_MERGE=false
```

The updater is a generic per-component lifecycle tool. It does not encode KF-131, E03, pairing IDs, hardware IDs, or historical maintenance transaction identities.

## 2. Exact target authority

```text
PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
EXACT_ARM64_RUN=41409298801
EXACT_ARTIFACT_ID=13124977192
EXACT_ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-3539c8f871e2cb63f18462009fa03a5eb36d39fd
EXACT_ARTIFACT_DIGEST_SHA256=f01dfc79fe2e2f1b20127f718487afe32f939b0ec09b47ad628fc88e6ff79b77
POST_UPLOAD_BINDING=PASS

TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-3539c8f871e2
TARGET_MANAGER_IMAGE_ID=sha256:2a1362b828a1f09b392713ba7fb40e91359e932690e525e4d03fe9873b9c1522
TARGET_MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0
TARGET_MANAGER_TAR_SIZE_BYTES=62688768
TARGET_PLATFORM=linux/arm64
```

The Manager-only upgrade package must copy the exact Manager tar from the already verified three-image artifact. It must not rebuild the Manager image.

The same artifact must also contain a self-contained `t1-core-updater.pyz` assembled from the reviewed updater source at the current control-plane head. Its SHA-256 is recorded in the package binding so later T1 staging does not depend on an unbound repository checkout.

## 3. Rollback compatibility proof

Fresh source comparison from predecessor source
`24382caae4a1f5d459297f86e8d18f10a848ca64`
to target source
`3539c8f871e2cb63f18462009fa03a5eb36d39fd`
shows only two changed paths under `host/greenhouse-manager/`:

1. `src/greenhouse_manager/runtime/n3w_first_registration_transaction.py`
2. `tests/runtime/test_n3w_first_registration_transaction.py`

There is no Manager database schema change, migration, credential-lifecycle change, application-key lifecycle change, or other Manager product module change in this A -> B delta.

Therefore this exact target may declare:

```text
ROLLBACK_COMPATIBLE=true
```

This proof is target-specific. Future targets must prove rollback compatibility independently.

## 4. Stable upgrade contract

The clean-reference runtime authority is:

- production owner: `n3wfc4-services-activation.service`;
- Manager and Home Assistant are supervised together;
- Broker remains independently running;
- Manager image selection is the unique `GH_MANAGER_IMAGE=` line in
  `/etc/n3wfc4/docker-compose.env`;
- canonical Compose uses `${GH_MANAGER_IMAGE:?GH_MANAGER_IMAGE required}`;
- image pulls are forbidden by `pull_policy: never`.

The updater must not perform an out-of-band Manager-only Compose recreate.

## 5. Read-only operations

### inspect

`t1-core-updater inspect` proves:

- Broker/services/registration-guard units active and enabled;
- exact services-owner ExecStart/ExecStop contract;
- one valid Compose and Compose-env authority;
- exactly one Manager image binding;
- Manager and HA host-network contract;
- pull-policy contract;
- current Broker/Manager/HA runtime identities;
- expected product listener set.

It emits only public-safe runtime identities and hashes.

### plan

`t1-core-updater plan` additionally binds:

- current predecessor image ref and image ID;
- target manifest;
- target image prestate: absent or exact;
- optional local Manager tar SHA-256;
- rollback availability.

It performs no T1 mutation.

## 6. Apply transaction

Apply requires all of:

```text
ROOT=true
CONFIRMATION=T1_CORE_UPDATER_MANAGER_APPLY
AUTHORIZATION_ID_PREFIX=N3W_T1_CORE_UPDATER_MANAGER_
TARGET_TAR_SHA256=exact
ROLLBACK_COMPATIBLE=true
```

Bounded order:

1. fresh inspect;
2. prove predecessor image authority;
3. prove target tag absent or exact;
4. create one durable updater transaction;
5. load exact Manager image only if absent;
6. stop Manager + HA through `n3wfc4-services-activation.service`;
7. prove Broker continuity;
8. atomically replace only the unique `GH_MANAGER_IMAGE=` line;
9. render Compose and prove the only effective change is Manager image;
10. start Manager + HA through the same systemd owner;
11. prove exact target Manager image;
12. prove HA image/network identity continuity;
13. prove Broker container/image/start/restart/listener continuity;
14. commit transaction.

The updater does not interpret product-specific first-registration business state. Product post-upgrade acceptance remains a separate read-only gate.

## 7. Automatic rollback

Before the application-services stop boundary, a failure does not restart healthy services.

After the stop boundary, a failed apply must:

1. stop Manager + HA if necessary;
2. restore predecessor `GH_MANAGER_IMAGE`;
3. start through the production owner;
4. prove predecessor exact image;
5. prove HA image continuity;
6. prove Broker continuity.

If rollback cannot be proven, transaction state becomes `FAILED_EMERGENCY`.

A process exit or host reboot does not erase transaction ownership. If a durable
`APPLYING` transaction remains:

- `AUTHORIZED` / `TARGET_IMAGE_LOADED`: explicit rollback may close it without restarting healthy application services, after proving predecessor runtime and stable HA/Broker identity;
- `STOPPING_APPLICATION_SERVICES` / `APPLICATION_SERVICES_STOPPED` /
  `MANAGER_BINDING_PUBLISHED` / `TARGET_RUNTIME_STARTED`: explicit rollback uses the
  frozen predecessor image and stable HA/Broker identity to restore A even when Manager/HA
  are currently stopped;
- any unsupported phase or `FAILED_EMERGENCY` remains fail-closed for forensic handling.

The transaction stores only stable recovery authority for HA/Broker. Container IDs,
start timestamps and restart counters are not required across a host reboot.

## 8. Explicit rollback

A later explicit rollback is allowed only when:

- current transaction is `COMMITTED`;
- target manifest was `rollback_compatible=true`;
- target exact image is currently active;
- predecessor image ref still resolves to the frozen predecessor image ID;
- explicit confirmation is supplied.

The same systemd owner and continuity rules apply.

## 9. Transaction lifecycle

Canonical local state:

`/var/lib/n3w-t1-core-updater/manager-upgrade.json`

Terminal states:

```text
COMMITTED
ROLLED_BACK
```

A non-terminal transaction blocks a new apply. Before the next apply, a terminal transaction is moved into the private history directory rather than becoming a permanent global upgrade blocker.

All apply/rollback mutations hold one non-blocking process-level `flock` across the complete transaction. A second mutating invocation fails closed with `upgrade_transaction_busy`. The private state root and history directory reject symlink and permission drift.

## 10. Source / test boundaries

The source must contain no KF-131/E03-specific identity or pairing/hardware binding.

Required simulated coverage includes:

- unique environment-line replacement;
- duplicate binding fail-closed;
- effective Compose delta limited to Manager image;
- read-only plan;
- successful Manager-only apply;
- post-start failure automatic rollback;
- explicit committed rollback;
- interrupted pre-stop transaction recovery;
- interrupted post-stop transaction recovery;
- terminal transaction archival;
- non-terminal transaction blocking;
- process-level mutation lock exclusivity;
- symlinked transaction-root rejection;
- unproven rollback target rejection;
- absence of historical E03/KF-131 identity coupling.

## 11. Current gate

```text
SOURCE_IMPLEMENTATION=true
SIMULATION=true
GITHUB_CI=true
MANAGER_ONLY_PACKAGE_PRODUCTION=true
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
MAIN_MERGE=false
```

After source/CI/package closure, the next live phase starts with a fresh read-only
`inspect/plan` against T1_A. Actual apply remains a separately authorized mutation boundary.
