# N3-W T1 Home Assistant mandatory-USB OTA
# KF-146 OTA control DynSec source repair and live read-only confirmation — 2026-11-09

```text
KF=KF-146
STATUS=SOURCE_REPAIR_IMPLEMENTED_FUNCTIONAL_CI_PASS_LIVE_REPAIR_PENDING
SOURCE_REPAIR_HEAD=41e0300e23351343bfe85f610d104cf533484e8e
PR=800
PREPARE_AUTHORIZATION_CONSUMED=true
PREPARE_REPLAY=false
USB_INSERTION=false
CONFIRM_USB_ERASE=false
LIVE_BROKER_MUTATION=false
MERGE=false
```

## Incident

After KF-145 live repair, Home Assistant registered the `N3-W T1` device and the
`准备 Home Assistant 升级` button. The user pressed PREPARE exactly once under the already
granted Boundary B authorization.

The immediate read-only postcheck proved:

```text
HA_USB_TRANSACTION_PRESENT=false
HA_USB_PREPARE_STATE_PRESENT=false
POST_PREPARE_RESULT=STOP_TRANSACTION_ABSENT
USB_LIKE_DISK_COUNT=0
```

Therefore the PREPARE UI action did not reach the host updater.

## Source root cause

The button publishes to:

```text
gh/v1/<system_id>/control/t1/homeassistant/ota
```

The service identity plan did not authorize the product path:

- Home Assistant lacked exact `publishClientSend` on the OTA control topic.
- Manager lacked exact `subscribePattern`, `publishClientReceive`, and
  `unsubscribePattern` on the same topic.

This is distinct from KF-145, which covered Manager publishing Home Assistant Discovery topics.

## Source repair

At source head `41e0300e23351343bfe85f610d104cf533484e8e`:

- Manager gains exactly three receive-side ACLs for the OTA control topic.
- Home Assistant gains exactly one send-side ACL for the OTA control topic.
- No broad `gh/#` or `homeassistant/#` publish permission is introduced.
- The PREPARE Discovery button command topic is cross-checked against both service identity plans.
- Real isolated Mosquitto + Dynamic Security integration proves Home Assistant publish → Manager
  receive on the exact control topic.
- Historical consumed S20 authority remains frozen; current ACL expansion must continue to
  fail closed against the historical executor.

Functional source CI at this head:

```text
greenhouse-manager_CI=SUCCESS:42536106786
M2_DYNAMIC_SECURITY_CI=SUCCESS:42536106920
S20_REAL_SERVICE_HANDOFF_CI=SUCCESS:42536106795
FAST_SOURCE_CI=SUCCESS:42536106856
PUBLIC_REPOSITORY_SAFETY_CI=SUCCESS:42536106929
```

The Core Stack current-authority workflow failed only because the newest Current State Index
section omitted the existing authority link; this is a documentation alignment defect and is
repaired separately without changing product behavior.

## Live read-only confirmation

Production Broker state after KF-145 remains:

```text
OTA_CONTROL_TOPIC=gh/v1/ghs-7c6601c27939d904/control/t1/homeassistant/ota
MANAGER_ROLE_PRESENT=true
HA_ROLE_PRESENT=true
MANAGER_ACL_COUNT=20
HA_ACL_COUNT=9

MANAGER_OTA_CONTROL_SUBSCRIBE_COUNT=0
MANAGER_OTA_CONTROL_RECEIVE_COUNT=0
MANAGER_OTA_CONTROL_UNSUBSCRIBE_COUNT=0
HA_OTA_CONTROL_PUBLISH_COUNT=0

FOUR_OTA_CONTROL_ACLS_ABSENT=true
READONLY_RESULT=PASS_KF146_LIVE_CONFIRMED
```

A Manager log line showed that the client attempted to subscribe to the OTA control topic.
That line is not authorization evidence. The authoritative Broker role readback proves that
the subscription/receive ACLs are absent, and no HA-USB transaction was created after PREPARE.

## Safety disposition

```text
BOUNDARY_B_STATUS=STOPPED_AFTER_CONSUMED_PREPARE_WITHOUT_TRANSACTION
PREPARE_REPLAY_ALLOWED=false
USB_INSERTION_ALLOWED=false
CONFIRM_USB_ERASE=false
```

A new PREPARE authorization must not be created until production DynSec is repaired and the
control path is live-revalidated.

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF146_OTA_CONTROL_DYNSEC_LIVE_APPLY_20261109_01
AUTHORIZATION_GRANTED=false
```

The live apply is expected to add exactly four ACLs:
- Manager: subscribePattern / publishClientReceive / unsubscribePattern.
- Home Assistant: publishClientSend.

Production mutation requires a separate explicit authorization.
