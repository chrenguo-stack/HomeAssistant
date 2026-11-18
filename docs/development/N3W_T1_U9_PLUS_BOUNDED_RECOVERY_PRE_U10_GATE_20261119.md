# N3-W T1 U9+ bounded recovery pre-U10 gate

Date: 2026-11-19

## Purpose

Prevent a read-only or stage-level PASS from being mistaken for customer-safe destructive upgrade readiness.

Attempt 05 proves that the current real T1 has an exact target archive, exact predecessor recovery archive, verified pre-upgrade HA data backup, bound USB continuity, sufficient recovery capacity and a durable U9 transaction.

Architecture/source design already defines automatic image+data rollback, U9-U12 rollback eligibility, U13B completion only after both predecessor image and HA data are restored, deterministic power-loss classification, and same-UUID recovery-media continuity. However, the R2 implementation closure used synthetic USB/Docker/HA data and did not claim live-T1 destructive rollback acceptance. The current P3 engineering sequence also paused for investigation between stages, so its elapsed downtime is not a customer recovery-time measurement.

Therefore destructive U10 remains blocked until this gate closes.

## Frozen recovery behavior

For U9-U12 failures, recovery authority is the durable host transaction plus the same bound USB filesystem UUID and the verified recovery-content manifest.

If actual state is safely forward-resumable within budget, resume only the legal adjacent phase. Otherwise enter rollback/recovery, verify the exact predecessor recovery asset and pre-upgrade HA data backup, restore predecessor image and data, restore production binding, start predecessor runtime, verify customer-visible health, and only then report recovered/ROLLED_BACK.

If the bound USB is absent after U9: RECOVERY_MEDIA_REQUIRED=true; AUTO_REPLAY=false; AUTO_FORMAT_OTHER_USB=false; AUTO_SUBSTITUTE_OTHER_USB=false.

The local recovery entry must remain available independently of Home Assistant so the user can be told to reinsert the original disk. Unverifiable recovery material enters maintenance state; it must not fabricate success.

## Customer-visible completion oracle

Recovery is complete only when all are true:
1. exact predecessor image/binding is authoritative and healthy;
2. Home Assistant page is reachable;
3. greenhouse Manager is ready;
4. Broker continuity is healthy;
5. new greenhouse telemetry is visible again;
6. pre-upgrade historical data expected by the rollback contract is readable;
7. host and USB transaction records agree on terminal recovery state;
8. no one-shot destructive authorization is replayed.

A container merely running is insufficient.

## Timing contract

Timing starts when application services are stopped and ends only when the customer-visible completion oracle passes.

PRE_CUTOVER_RECOVERY_TARGET<=5min
POST_CUTOVER_RECOVERY_TARGET<=15min

These are engineering acceptance targets, not a customer promise, until measured on representative hardware/data/USB conditions. The current long-running P3 sequence is excluded from timing evidence because it intentionally paused between gates.

## Fault-injection acceptance matrix

Before customer release cover at least:
- failure immediately before predecessor runtime deletion;
- failure after predecessor runtime/container deletion but before predecessor image deletion;
- failure after predecessor image deletion but before durable U10 recording;
- power loss after destructive deletion before U10 durable recording;
- power loss after durable U10 before target load;
- target load failure;
- target loaded but U11 not durably recorded;
- target start failure;
- target starts but health acceptance fails;
- power loss during U11/U12;
- bound USB temporarily absent after U9, then the same UUID is reinserted;
- wrong/replacement USB after U9;
- slow supported USB and large supported HA data set.

Each case records recovery path, terminal state, page/Manager/telemetry readiness and elapsed outage.

## Initial source review result

The first read-only source review found a concrete integration blocker.

- tools/n3w_t1_core_updater_ha_daemon.py builds HaUsbIpcExecutor and invokes start_background_recovery() at daemon startup.
- HaUsbIpcExecutor.start_background_recovery() only handles U1 by restarting discovery and U2/U3 by resuming preparation.
- HaUsbIpcExecutor.submit() accepts only PREPARE, CONFIRM_USB_ERASE and INSTALL. INSTALL calls the prepare controller to revalidate and request install; it is not a U9+ destructive/recovery coordinator.
- tools/n3w_t1_core_updater_ha_usb.py contains U9-U13 rollback and recovery state transitions, and the repository contains stage-specific engineering executors for U10/U11/U12/U13B, but those are not equivalent to an always-on product recovery path.

Conclusion: architecture/state-machine capability exists, but customer-safe U9+ automatic recovery is not yet integrated into the installed product daemon. This is tracked as KF-168 and blocks destructive U10.

## Closure sequence

1. source review of the actual U9-U13 recovery coordinator/executor used by production;
2. add missing deterministic reconciliation/fault-injection hooks and tests if needed;
3. prove no false-PASS can declare recovery before image+data+customer-health checks pass;
4. run representative real-T1 destructive/rollback acceptance under separate explicit authorization;
5. measure recovery time and only then freeze a customer-facing time commitment.

CURRENT_LIVE_STAGE=U9_LIVE_AUTHORIZATION_CLAIMED
U9_AUTHORIZATION=CONSUMED_NO_REPLAY
U10_READONLY_PREFLIGHT=PASS
U10_DESTRUCTIVE_AUTHORIZATION=false
U11_PLUS_AUTHORIZATION=false
NEXT_ONE_GATE=N3W_T1_U9_PLUS_BOUNDED_RECOVERY_SOURCE_REVIEW_AND_ACCEPTANCE_DESIGN
