# N3-W T1 U13B P3 U9 read-only preflight physical closure

Date: 2026-11-18

## Result

The frozen P3 U9 candidate completed its real-T1 read-only preflight successfully.

```text
PR=807
U9_CANDIDATE_HEAD=816cf5f2f55c895b6112edbd563cf71df8b7be93
RESULT=P3_U9_READONLY_PREFLIGHT_PASS
EXIT_CODE=0

TRANSACTION_PHASE=U8_RECOVERY_ADMISSION_COMPLETE
TRANSACTION_SHA256=c9210a75ba4496b42fd080ca4ef261cf669a56452f99531066f921a5fcbe4908
RECOVERY_CONTENT_MANIFEST_SHA256=d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3

READ_ONLY=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
U9_TRANSITION=false
U10_PLUS=false
DESTRUCTIVE_CUTOVER=false
PREDECESSOR_IMAGE_DELETE=false
TARGET_IMAGE_LOAD=false
SERVICE_MUTATION=false

APPLICATION_SERVICES_STOPPED=true
BROKER_CONTINUITY_VERIFIED=true
BACKUP_VERIFIED=true
USB_METADATA_MATCHES=true

APPLICATION_OWNER_ACTIVE_STATE=failed
APPLICATION_OWNER_SUB_STATE=failed
APPLICATION_OWNER_RESULT=exit-code
APPLICATION_OWNER_EXEC_MAIN_STATUS=130
APPLICATION_OWNER_MAIN_PID=0
APPLICATION_OWNER_NRESTARTS=0

LOCAL_RECEIPT_SHA256=c10ec0d43f4c18decf71d6c21c46fe6f38af50b22830a313eae2a908a2faf16b
```

The raw receipt remains private on the operator Mac. Only the public-safe digest and summary are archived here.

## Interpretation

The live system is still durably at U8. The read-only preflight freshly rebound:
- the exact U8 transaction digest;
- the recovery-content manifest;
- the protected Home Assistant backup;
- the quiesced Manager/Home Assistant application owner state;
- Broker continuity;
- bound USB recovery metadata.

The preflight only projected the product U8 -> U9 transition in memory. It did not create a U9 authorization ledger, did not persist a Host or USB U9 state, did not restart services, did not delete the predecessor image, did not load the target image, and did not enter U10.

## Authorization boundary

```text
U9_LIVE_AUTHORIZATION_GRANTED=false
U9_GRANT_PRESENT=false
CURRENT_LIVE_STAGE=U8_RECOVERY_ADMISSION_COMPLETE
NEXT_ONE_GATE=N3W_T1_U13B_P3_U9_LIVE_AUTHORIZATION_20261118_01
```

A later U9 execute requires:
1. an isolated grant commit whose parent is the frozen U9 candidate;
2. exact binding to the U8 transaction, U8 receipt and recovery-content manifest;
3. separate explicit operator authorization.

A successful U9 claim still stops before U10. U10 remains a separate later gate.
