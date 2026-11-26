# N3-W T1 Core Stack OTA V1.3 — R8V13-07 Thin Re-entry-Aware Executor Convergence

Date: 2026-11-24  
PR: #824  
Physical T1 mutation: none in this convergence stage

## 1. Authorization

```text
AUTHORIZATION_SCOPE=R8V13_07_THIN_REENTRY_AWARE_EXECUTOR_CONVERGENCE
AUTHORIZATION_STATUS=APPROVED
```

The authorization covers operator-executor architecture convergence and execution-path CI only. It does not authorize a new physical T1 attempt, R8V13-08, Broker OTA, reboot, merge, or release.

## 2. Live execution authority

```text
LIVE_HA_RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
LIVE_HA_RECOVERY_SOURCE_HEAD=90ce32ce4b6c329fd38c2771e352d129d6d00a86
CORE_SOURCE_DRIFT=false
```

The five critical core modules remain byte-identical between the live pyz source authority and the current PR core source.

## 3. Executor replacement

Retired historical shell executor:

```text
tools/execution_packages/n3w/t1_ota_r8v13_07/
N3W_T1_R8V13_07_FRESH_TRANSACTION_A_INSTALL_TO_TERMINAL_20261124_01.sh
```

It is now an exit-64 retirement stub and cannot execute INSTALL/cutover.

Successor:

```text
tools/execution_packages/n3w/t1_ota_r8v13_07/
N3W_T1_R8V13_07_THIN_REENTRY_AWARE_INSTALL_TO_TERMINAL_20261124_01.py
```

CI candidate source head:

```text
80f2befd4636ba6b1f17b1d2b9f1c7701377ed06
```

Executor Git blob at that head:

```text
9e8d48ae49fef6917be0b511caaf6b228e3d0e76
```

## 4. Converged execution ownership

The successor executor does not:

- invoke live `--resume-pending` directly;
- stop/restart application services;
- load/remove Docker images;
- manipulate containers;
- format/unmount USB;
- implement target install/rollback actions.

It dispatches product work only through:

```text
n3w-t1-ha-recovery-retry.service
```

Before dispatch, the live product's `require_recovery_install()` validates recovery unit/timer/boot-guard installation.

## 5. Durable re-entry model

The executor classifies only product-validated durable transaction state.

Real T1 transaction reads use:

```text
HaUsbStateStore().read()
```

Supported entry states:

- clean ACTIVE/U4;
- ACTIVE/U5 before destructive ownership;
- ACTIVE/U6 without predecessor_start;
- ACTIVE pre-cutover recovery states with predecessor_start;
- ACTIVE U9-U12 recovery responsibility;
- COMMITTED/U13A;
- ROLLED_BACK/U13B;
- pre-cutover restored ROLLED_BACK/U6|U7|U8;
- retired no-mutation ROLLED_BACK/U4 failure.

No shell-local mutation flag is used as replay authority.

## 6. INSTALL and authority semantics

U4 submits INSTALL exactly once through:

```text
--maintenance-submit-approved-release INSTALL
```

U5/U6 re-entry does not resubmit INSTALL.

Install authority uses product:

```text
requested_install_binding_sha256()
--issue-install-authority
```

The outer executor no longer hard-codes an old terminal authority binding.

A current authority is reused only when schema, binding, authorization ID, launch SHA, and expiry exactly match the current request. Otherwise the product authority publisher decides whether replacement is admitted.

## 7. Release pin semantics

Release pin is required only for pre-destructive U4/U5/U6 intent/authority work.

Recovery and terminal classification do not depend on the approved release manifest.

When the only resolver failure is pin expiry, the executor verifies all non-expiry fields before refresh, including product `SHA256` validation for `predecessor_binding_sha256`, then changes only `expires_at_unix`, fsyncs, and reruns the product resolver.

## 8. Product recovery ownership

After authority readiness the executor starts the product recovery service.

It permits at most one bounded second service dispatch when durable state remains product-reentrant.

If durable state remains ACTIVE after the bounded continuation:

```text
FRESH_TX_A_INSTALL_RESULT=PENDING_PRODUCT_RECOVERY
PRODUCT_RECOVERY_OWNER=n3w-t1-ha-recovery-retry.service+timer
DO_NOT_SUBMIT_INSTALL_AGAIN=true
```

The executor does not invent a new rollback route.

## 9. Terminal semantics

Success:

```text
COMMITTED / U13A_COMMITTED
```

requires exact authorization consumption, target activation, acceptance receipt, target runtime, Manager runtime, and Broker runtime.

Rollback terminal accepts both:

```text
ROLLED_BACK / U13B_ROLLED_BACK
```

and the source-defined pre-cutover restored terminal:

```text
ROLLED_BACK / U6|U7|U8
pre_cutover_predecessor_restored=true
recovery_required=false
```

This fixes the previous outer-executor false-nonterminal classification.

## 10. Execution-path tests

New test authority:

```text
tests/tools/test_n3w_t1_ota_r8v13_07_thin_reentry_executor.py
```

It contains 21 explicit orchestration tests, including:

- clean U4 -> commit;
- U5 re-entry without INSTALL replay;
- U6/no-predecessor_start forward re-entry;
- pre-cutover recovery handoff;
- post-authorization recovery handoff;
- U12 forward commit;
- bounded second worker dispatch;
- terminal no-replay;
- pre-cutover rollback terminal classification;
- U4 no-mutation failure no replay;
- product-timer ownership after bounded nonterminal result;
- exact transaction drift stop;
- no local mutation flags/fixed workdir;
- no direct live --resume-pending;
- authority reuse/replaceability contract;
- malformed committed receipt rejection;
- product recovery-install guard;
- recovery independence from approved manifest;
- product SHA256 validation before expired pin refresh.

The focused workflow additionally executes selected existing `test_n3w_t1_core_updater_ha_usb_r2.py` product fault-injection tests for target import/activation, single-image rollback, and boot recovery.

## 11. CI status

The earlier run `45412479065` was superseded by PR concurrency and finished `CANCELLED`; it is not sealing evidence.

The authoritative replacement run on the docs-aligned PR head completed successfully:

```text
EXECUTOR_SOURCE_HEAD=80f2befd4636ba6b1f17b1d2b9f1c7701377ed06
CI_EXECUTED_HEAD=dca5658b653a2c16e40912ff8fff2abd8c0ff3a5
EXECUTOR_BLOB=9e8d48ae49fef6917be0b511caaf6b228e3d0e76
FOCUSED_CI_RUN=45412793881
FOCUSED_CI_STATUS=SUCCESS
COMPILE_FOCUSED_R8_SOURCES=PASS
VALIDATE_R8_SHELL_EXECUTORS=PASS
FOCUSED_ORCHESTRATION_SUITE=56_PASSED
PRODUCT_RECOVERY_FAULT_INJECTION=25_PASSED_71_DESELECTED
EXECUTOR_SHA256=70b648fb03231723efcbea568fe373fdd57db5dc49aa7048c04392edaa3d691c
EXECUTOR_DRIFT=false
CI_SEALING=PASS
```

The convergence source and CI are sealed. Per user direction, physical execution remains blocked until a new conversation first performs an independent review of this executor convergence and confirms no blocker.

## 12. Current physical boundary

Unchanged from Attempts 01/02:

```text
TRANSACTION_ID=d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4
STATUS=ACTIVE
PHASE=U4_READY_TO_INSTALL
RECOVERY_REQUIRED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_ID_SHA256=null
PREDECESSOR_START_PRESENT=false
```

```text
LIVE_T1_EXECUTION=BLOCKED_PENDING_NEW_CHAT_INDEPENDENT_EXECUTOR_REVIEW
R8V13_08_BLOCKED=true
BROKER_OTA=false
HOST_REBOOT=false
MERGE=false
RELEASE=false
```
