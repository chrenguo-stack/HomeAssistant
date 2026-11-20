# N3-W T1 pre-U9 customer recovery source review and Spare-T1 entry plan

Date: 2026-11-18

## Trigger

P3 U8 read-only preflight passed on the current T1 while the durable transaction remained at U7. Before the current T1 enters U9, the customer recovery acceptance plan requires a physical pre-cutover recovery proof on the non-production Spare T1.

## Source review result

The existing transaction model correctly classifies every U0-U8 phase as predecessor-authoritative:

```text
classify_power_loss_reentry(U0..U8)=PRE_U9_PREDECESSOR_AUTHORITY
```

The frozen power-loss contract also requires that if Home Assistant was quiesced at U7, the predecessor application services are restarted only after proving pre-U9 transaction authority.

The current daemon startup path does not yet implement that recovery action.

`build_server()` constructs `HaUsbIpcExecutor` and calls `start_background_recovery()`. That method currently performs automatic recovery only for:

```text
U1 -> discovery worker
U2/U3 -> resume prepare worker
```

It has no U7 or U8 branch. Therefore a daemon/process restart while the durable transaction is U7/U8 does not by itself restore the already-quiesced Home Assistant/Manager services.

The product already has a bounded service-restoration primitive in the U7 runtime-owner contract:

```text
resume_homeassistant_after_backup_failure()
```

and the U7 controller uses it when an exception occurs inside the backup operation. The missing behavior is re-entry recovery after the backup has already been durably written and a later wrapper/process/host failure leaves the system at U7/U8 with application services stopped.

## Product impact

This is a delivery blocker for the desired customer property:

```text
upgrade fails before U9
-> predecessor remains authority
-> product proves transaction/runtime facts
-> application services recover
-> customer page/history/new telemetry return
```

The existing phase classifier is necessary but insufficient. A test harness that only checks the returned classification would false-PASS the customer-visible requirement.

## Bounded repair direction

Add one pre-U9 recovery coordinator owned by the host-side HA OTA daemon.

Required behavior for U7/U8 re-entry:

1. read and validate the durable transaction under the existing transaction authority;
2. prove phase is U7 or U8 and no U9 live authorization has been claimed/consumed;
3. prove predecessor image remains present and is the expected runtime authority;
4. validate the bound recovery media and required recovery artifacts where the phase contract requires them;
5. inspect the application service owner and Manager/Home Assistant containers;
6. if predecessor services are already healthy, perform no restart and report recovered;
7. if services are fully quiesced, start them through the existing production systemd owner;
8. wait for the existing product readiness contract, not merely process/container appearance;
9. preserve Broker continuity;
10. leave the transaction at U7/U8; do not fabricate U9, commit, rollback, or consume authorization;
11. expose a bounded recovery/error status to the customer-facing OTA control path.

Fail closed when runtime/transaction/media facts are ambiguous.

## Spare-T1 physical matrix before current-T1 U9

The non-production Spare T1 must prove at least:

- U7 terminal-check false-stop after a valid durable backup;
- updater process interruption after durable U7;
- host transaction written while USB mirror is one step behind;
- USB mirror written while host transaction is one step behind;
- application owner terminal states `inactive/dead/success` and verified `failed/failed/exit-code` with MainPID=0;
- no restart when predecessor application services are already healthy;
- actual restart when application services are quiesced;
- Broker remains continuous;
- Home Assistant page becomes reachable;
- historical data remains readable;
- new greenhouse telemetry resumes;
- no U9+ transition and no live authorization claim.

## Current boundaries

```text
CURRENT_T1_STAGE=U7
CURRENT_T1_U8_READONLY_PREFLIGHT=PASS
CURRENT_T1_U8_WRITE_EXECUTED=false
CURRENT_T1_U9_PLUS=false

SPARE_T1_TARGET=non-production staging
SPARE_T1_MUTATION_AUTHORIZED=false
SPARE_T1_FAULT_INJECTION_AUTHORIZED=false

NEXT_ONE_GATE=SPARE_T1_PRE_U9_RECOVERY_READONLY_BASELINE
```

The first Spare-T1 action is read-only host/runtime/source capability binding. Fault injection and service mutation remain a later explicitly bounded live gate.
