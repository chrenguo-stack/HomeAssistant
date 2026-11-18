# N3-W T1 U13B P3 U8 read-only preflight physical result

Date: 2026-11-18

## Scope

This record archives the real-T1 read-only preflight for the U8 recovery-admission checkpoint. It does not authorize or execute the U8 state transition.

```text
PR=807
U8_EXECUTION_CANDIDATE=e78b80642f7e71a88ae086f3d7b6c54c34defb99
P3_FROZEN_PRODUCT_SOURCE=cddadc5bff1a00d4392de33680a5b0ad0acace1e
U8_AUTHORIZATION_GRANTED=false
U8_AUTHORIZATION_CLAIMED=false
U8_AUTHORIZATION_CONSUMED=false
U8_TRANSITION=false
U9_PLUS=false
READ_ONLY=true
```

## Local source check

The exact candidate source check passed:

```text
SOURCE_CHECK_PASS
u8_grant_present=false
```

The first operator command pre-created the evidence directory. Because the executor requires ownership of creating that directory, it stopped locally with `FileExistsError:errno_17` before SSH/T1 access. No T1 access, authorization claim, state transition, or mutation occurred in that local-only stop.

The corrected invocation did not pre-create the evidence root and proceeded to the real-T1 read-only preflight.

## Real-T1 result

```text
STATUS=P3_U8_READONLY_PREFLIGHT_PASS
EXIT_CODE=0
SCHEMA=gh.n3w-t1-u13b-p3-u8-recovery-admission/1
STAGE=u7_verified_for_u8

TRANSACTION_PHASE=U7_HA_QUIESCED_DATA_BACKUP_PREPARING
TRANSACTION_SHA256=2f45f6eee5fa59d0dafe53cedc23c11d62de35e949fb645ea8fd74b3d8d861a2
U7_RECEIPT_SHA256=27739cf29a883c4ee58d8cc6094099f4fd4e36a056dd94acfeb28d29bb203e73

APPLICATION_SERVICES_STOPPED=true
APPLICATION_OWNER_ACTIVE_STATE=failed
APPLICATION_OWNER_SUB_STATE=failed
APPLICATION_OWNER_RESULT=exit-code
APPLICATION_OWNER_EXEC_MAIN_STATUS=130
APPLICATION_OWNER_MAIN_PID=0
APPLICATION_OWNER_NRESTARTS=0

BACKUP_VERIFIED=true
BROKER_CONTINUITY_VERIFIED=true
USB_METADATA_MATCHES=true
USB_FREE_BYTES=28132188160
USB_REQUIRED_FREE_BYTES=1610612736
RECOVERY_CONTENT_MANIFEST_SHA256=d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3

AUTHORIZATION_CLAIMED=null
AUTHORIZATION_CONSUMED=null
REPLAY_PERMITTED=false
U8_TRANSITION=false
U9_PLUS=false
READ_ONLY=true
```

Operator-local raw evidence:

```text
EVIDENCE_ROOT=<operator-private-evidence-root>
RECEIPT_FILE=p3-u8-result.json
RECEIPT_SHA256=ac15a39fb9266fdaf89805c03a7be92f70e096c822100de1504088bf1020ce84
```

The raw receipt remains private on the operator Mac. Only its digest and public-safe summary are archived here.

## Disposition

The real T1 is still durably at U7. This preflight proves that the U7 transaction, protected HA backup, recovery artifacts, USB metadata, application quiescence, Broker continuity, and capacity admission remain suitable for the separately authorized U8 write.

This result does **not** itself mean U8 has executed.

```text
U8_READONLY_PREFLIGHT=PASS
CURRENT_LIVE_STAGE=U7
NEXT_CURRENT_T1_WRITE=U8_RECOVERY_ADMISSION
U8_WRITE_AUTHORIZATION_REQUIRED=true
CURRENT_T1_U9_PLUS=false
```

Before the current T1 enters U9, the project plan requires physical validation of pre-cutover recovery on the spare T1. That validation must cover the U7 final-check false-stop class, interrupted upgrade process, and host/USB one-sided persistence, and must prove safe resume or predecessor-service recovery from the customer-visible path.
