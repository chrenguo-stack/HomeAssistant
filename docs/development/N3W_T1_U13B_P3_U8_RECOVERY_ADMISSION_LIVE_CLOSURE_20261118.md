# N3-W T1 U13B P3 U8 recovery-admission live execution closure

Date: 2026-11-18

## Result

The separately authorized one-shot U8 recovery-admission write completed successfully on the current T1.

```text
PR=807
CANDIDATE_HEAD=e78b80642f7e71a88ae086f3d7b6c54c34defb99
GRANT_HEAD=525f18ca2c38a792826f885f43132cefdea29f6d
AUTHORIZATION_ID=N3W_T1_U13B_P3_U8_RECOVERY_ADMISSION_20261118_01
AUTHORIZATION=CLAIMED_CONSUMED_NO_REPLAY
RESULT=P3_U8_RECOVERY_ADMISSION_PASS
EXIT_CODE=0

TRANSACTION_PHASE=U8_RECOVERY_ADMISSION_COMPLETE
TRANSACTION_SHA256=c9210a75ba4496b42fd080ca4ef261cf669a56452f99531066f921a5fcbe4908
RECOVERY_CONTENT_MANIFEST_SHA256=d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3

USB_U8_VERIFIED=true
USB_METADATA_MATCHES=true
BACKUP_VERIFIED=true
APPLICATION_SERVICES_STOPPED=true
BROKER_CONTINUITY_VERIFIED=true

APPLICATION_OWNER_ACTIVE_STATE=failed
APPLICATION_OWNER_SUB_STATE=failed
APPLICATION_OWNER_RESULT=exit-code
APPLICATION_OWNER_EXEC_MAIN_STATUS=130
APPLICATION_OWNER_MAIN_PID=0
APPLICATION_OWNER_NRESTARTS=0

U8_TRANSITION=true
U9_PLUS=false
READ_ONLY=false
REPLAY_PERMITTED=false

LOCAL_RECEIPT_SHA256=8340d0b4a5be925c954932113b8c593668e83b5f60d1271714f2ce91d521a63a
```

The operator-local raw receipt remains private. Only the public-safe digest and result summary are archived here.

## Meaning

U8 is now a durable live checkpoint, not a read-only projection.

The host transaction and the bound USB recovery metadata both reached `U8_RECOVERY_ADMISSION_COMPLETE`. The exact target archive, predecessor recovery authority, protected Home Assistant backup, production prestate, and recovery-capacity admission are all bound into the recovery-content manifest.

Manager and Home Assistant remain quiesced. Broker continuity remains verified.

No U9 transition occurred.

## Authorization disposition

The U8 grant is consumed and cannot be replayed.

```text
U8_AUTHORIZATION_REPLAY=false
U8_EXECUTE_RETRY=false
```

Any later U9 live-authorization claim requires its own source package, fresh read-only preclaim verification, and separate explicit authorization.

## Spare-T1 recovery-validation disposition

The previously planned Spare-T1 physical pre-cutover recovery validation remains deferred for this sequence because the Spare T1 currently contains data that must not be modified.

This U8 PASS does not claim that deferred customer-recovery physical proof has been completed.

## Next boundary

```text
CURRENT_LIVE_STAGE=U8_RECOVERY_ADMISSION_COMPLETE
NEXT_SOURCE_GATE=P3_U9_LIVE_AUTHORIZATION_PACKAGE_AND_READONLY_PRECLAIM
U9_AUTHORIZATION_GRANTED=false
U10_PLUS=false
```

The repository already contains the earlier generic R36 U9 live-authorization successor as design/reference evidence. P3 must bind its own exact U8 transaction and receipt; the historical R36 package must not be reused directly.
