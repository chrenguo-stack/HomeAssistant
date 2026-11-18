# N3-W T1 pre-U9 Spare-T1 recovery validation disposition

Date: 2026-11-18

## Decision

The previously planned pre-U9 physical recovery validation on the non-production Spare T1 is **deferred and skipped for the current U13B P3 acceptance sequence**.

Reason: the Spare T1 currently contains data that must be preserved and therefore must not be modified, fault-injected, reset, reimaged, service-mutated, or otherwise used as a destructive recovery test target.

This is an operator decision for the current acceptance sequence.

## Boundary

```text
SPARE_T1_ACCESS=false
SPARE_T1_MUTATION=false
SPARE_T1_FAULT_INJECTION=false
SPARE_T1_SERVICE_MUTATION=false
SPARE_T1_STORAGE_MUTATION=false
SPARE_T1_REIMAGE=false

PRE_U9_SPARE_T1_RECOVERY_PHYSICAL_VALIDATION=DEFERRED_NOT_EXECUTED
CURRENT_SEQUENCE_DISPOSITION=SKIP
CUSTOMER_RECOVERY_PHYSICAL_PROOF=NOT_CLAIMED
```

The source-review finding remains valid: U0-U8 are classified as predecessor-authoritative, but the current daemon startup path does not yet provide a complete U7/U8 re-entry recovery action that restores already-quiesced Manager/Home Assistant services after a later process/host failure.

Therefore this deferred test must not be represented as PASS. It remains a retained follow-up item for a future disposable or explicitly authorized test T1.

## Current T1 consequence

Skipping the Spare-T1 physical test removes it as a blocking step in the current U13B P3 acceptance sequence **by operator decision**, but does not create any new live-write authorization.

The current live T1 remains at U7 after the successful U8 read-only preflight. U8 write and any U9+ transition remain governed by their own explicit authorization gates.

```text
CURRENT_T1_STAGE=U7
CURRENT_T1_U8_READONLY_PREFLIGHT=PASS
CURRENT_T1_U8_WRITE_EXECUTED=false
CURRENT_T1_U9_PLUS=false
U8_WRITE_AUTHORIZATION_REQUIRED=true
```

## Retained follow-up

When a disposable or explicitly mutable Spare T1 becomes available, re-open the physical recovery matrix covering at least:

- durable U7/U8 with application services quiesced;
- updater/process interruption;
- host/USB asymmetric persistence;
- predecessor service restoration;
- Broker continuity;
- HA page/history/new telemetry recovery;
- no accidental U9+ transition or authorization claim.
