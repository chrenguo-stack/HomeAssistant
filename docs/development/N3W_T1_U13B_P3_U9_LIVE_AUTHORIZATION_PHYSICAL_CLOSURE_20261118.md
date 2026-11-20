# N3-W T1 U13B P3 U9 live authorization physical closure

Date: 2026-11-18

## Result

The separately authorized one-shot P3 U9 write completed successfully on the real T1.

```text
PR=807
U9_CANDIDATE_HEAD=816cf5f2f55c895b6112edbd563cf71df8b7be93
U9_GRANT_HEAD=31a7c5daed754db4a189c1d27b81795ef60abc0b
AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_P3_U9_20261118_01
RESULT=P3_U9_LIVE_AUTHORIZATION_CLAIM_PASS
EXIT_CODE=0

TRANSACTION_PHASE=U9_LIVE_AUTHORIZATION_CLAIMED
TRANSACTION_SHA256=2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b
RECOVERY_CONTENT_MANIFEST_SHA256=d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3

AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
U9_TRANSITION=true
USB_U9_VERIFIED=true
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

LOCAL_RECEIPT_SHA256=f752ba02a58084baf9232b8af67e3fad4ec91048f11d516040bd3749e8755e53
```

The raw receipt remains private on the operator Mac. Only the public-safe digest and summary are archived here.

## Interpretation

Host and bound USB metadata both reached the durable U9 checkpoint. The U9 authorization is now consumed and must never be replayed.

The U9 operation did not:
- enter U10;
- delete the predecessor image;
- load the target image;
- restart Manager or Home Assistant;
- perform destructive cutover.

The MQTT Broker continuity check remained valid while Manager and Home Assistant stayed quiesced.

## Authorization boundary

```text
CURRENT_LIVE_STAGE=U9_LIVE_AUTHORIZATION_CLAIMED
U9_AUTHORIZATION=CONSUMED_NO_REPLAY
U10_PLUS=false
U10_AUTHORIZED=false
NEXT_ONE_GATE=P3_U10_READONLY_PREFLIGHT_SOURCE_AND_BINDING_REVIEW
```

U10 is a separate destructive capacity-release boundary and requires its own source/read-only gate and later explicit operator authorization before any predecessor-image deletion.
