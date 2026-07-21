# H3/N2 Stage 2D-6 Lifecycle Assembly and Startup Recovery

## Status

Stage 2D-6 assembles the previously verified persistence, candidate validation,
activation, and production runtime boundaries into one explicit controller.

Base main:

`3710d368caf7c495517d9d02fef7ee4d9f8f12b3`

Development branch:

`feature/h3-n2-stage2d6-lifecycle-assembly-20260721-v54`

## Goal

The controller closes the source-level gap between Stage 2D-5 production
adapters and a later rollback-first isolated-device acceptance package:

```text
read-only startup recovery
→ explicit active start
→ independent PREPARED validation
→ explicit generation-bound mutation authorization
→ marker-last activation
→ session-role promotion
→ terminal-state reset or reboot closure
```

It is intentionally not wired into production startup, pairing UI, a button,
action, script, or automatic credential rotation.

## Startup recovery model

`recover_startup()` authenticates and classifies persistent state without
starting MQTT or mutating persistence.

Supported safe states:

- `EMPTY` → unpaired and offline;
- `ACTIVE` → active profile recovered, explicit connection still required;
- `NO_ACTIVE_PREPARED` → first-enrollment candidate waits for validation;
- `ACTIVE_WITH_PREPARED` → current active must start before candidate validation;
- authoritative active plus stale, committed-orphan, or invalid inactive slot →
  active may start while maintenance remains blocked.

Fail-closed states:

- no active marker plus committed orphan;
- invalid authenticated record;
- conflicting generations or slots;
- storage read failure;
- live probe or activation-candidate session during startup recovery;
- live active runtime whose generation differs from persistent authority.

Fail-closed startup quiesces all controller-owned MQTT sessions and requires
reboot recovery. It does not attempt automatic cleanup.

## Explicit active start

`start_recovered_active()` is separate from recovery. This proves that recovery
alone cannot connect to a Broker.

After a successful activation and role promotion, `reset_transaction()` may
preserve the active connection. A later recovery adopts that already-live
session only when its generation exactly matches the persistent active marker.

## Candidate validation

`begin_prepared_validation()` configures the Stage 2D-4 lifecycle integration,
re-reads the PREPARED record, stages exact generations, obtains a fresh nonce,
and starts the independent Stage 2D-2 candidate probe.

`poll_validation()` advances only the validation transaction. It does not stop
the current active session and cannot commit persistence.

Duplicate validation and recovery calls are rejected while a transaction is in
progress.

## Mutation gate

`activate()` accepts a `ProfileLifecycleMutationAuthorizer` for the exact
`active_generation` and `candidate_generation`.

Denied authorization keeps the controller in `VERIFIED`; no runtime switch or
persistent write occurs. Authorization is evaluated again for each activation
attempt and is not cached across transactions.

## Activation closure

Authorized activation delegates the established order:

```text
stop old active
→ start candidate as sole runtime
→ fresh QoS 1 confirmation
→ commit marker last
→ finalize runtime session-role promotion
```

Pre-commit failures restore the old active session when authority is provable.
An indeterminate persistent state or a post-commit promotion failure quiesces all
sessions and enters `REBOOT_REQUIRED`.

## Deterministic host matrix

The host matrix uses only an in-memory backend and fake MQTT sessions. It covers:

- empty startup recovery without writes or network activity;
- active recovery with an explicit connection boundary;
- first enrollment with denied then approved mutation authorization;
- rotation requiring the current active session first;
- candidate authentication failure preserving active authority;
- activation candidate start failure and rollback;
- marker-last commit plus session-role promotion;
- two consecutive controller transactions using the promoted active session;
- stale committed-slot classification without automatic cleanup;
- storage error quiescence and non-resettable reboot closure;
- duplicate validation and recovery calls during a busy transaction.

The matrix records backend write/commit counts to prove read-only recovery and
authorization denial do not mutate persistence.

## ESP32-C6 compile-only targets

Two disabled targets compile the complete controller assembly:

- minimal ESP32-C6 DevKitM target;
- full F1.0-RC2 product-board target.

Both targets keep Wi-Fi disabled at boot. The custom component performs only
code inclusion and a compile define; it creates no C++ object and exposes no
runtime action.

## Explicit execution boundary

本阶段只进行源码、主机故障矩阵和 ESP32-C6 compile-only 验证。

- 不得连接真实 Broker；
- 不得打开或写入物理 NVS；
- 不得操作实板；
- 不得读取、烧写或 provisioning eFuse；
- 不得修改 M401A、T1、Home Assistant 或 Mosquitto；
- 不得修改生产 `f1_0_rc2.yml` 或现有产品 packages；
- 不得加入自动开机恢复、自动验证或正式 profile activation。

The next stage may prepare an isolated-device acceptance package, but execution
still requires a separate explicit authorization and rollback-first evidence.
