# N3-W T1 Home Assistant mandatory-USB OTA R7A
# KF-147 Stage A Attempt02 OTA-origin publication closure — 2026-11-09

## 1. Result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_LIVE_REPAIR_A_OTA_ORIGIN_PUBLICATION_ATTEMPT02_20261109_01
RESULT=CLOSED_PASS

AUTHORIZATION=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_LIVE_REPAIR_A_OTA_ORIGIN_PUBLICATION_ATTEMPT02_20261109_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

SOURCE_CLOSURE_HEAD=4a670ccde19cc42f4cdb1cfdddcc7d9f2a690820
SOURCE_CLOSURE_CI=28_OF_28_SUCCESS
HAHUB_PR4_HEAD=a4aa7ff3011c945555f7df77165bb5bee0f58d94
HAHUB_ROUTE_CI=SUCCESS

PREMUTATION_RECHECK=PASS
TARGET_ARCHIVE_SIZE=835309535
TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
TARGET_ATOMIC_PUBLICATION=PASS

OTA_READONLY_MOUNTS=PASS
LOCAL_ORIGIN_HTTP=200
LOCAL_ORIGIN_CONTENT_LENGTH=835309535
LOCAL_ORIGIN_CONTENT_TYPE=application/octet-stream
LOCAL_ORIGIN_CACHE_CONTROL=public, max-age=31536000, immutable
LOCAL_ORIGIN_NOSNIFF=nosniff

PUBLIC_HTTP_AFTER_ATTEMPT02=404
WEBSITE_UNTOUCHED=PASS
ROLLBACK_REQUIRED=false

T1_ACCESS=false
T1_MUTATION=false
PREPARE_REPLAY=false
USB_MUTATION=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

## 2. Pre-mutation rollback baseline

Fresh live recheck before Attempt02 proved the exact prechange state:

```text
COMPOSE_SHA256=a5e0ec296cfdf146e36c0082644e9e17a006bb71db849361d07609b3b41c615e
EDGE_SHA256=5d0ee6f27cb6351226696b44b7e4909737508dd7541d814c73cbb4cc581475b6
OTA_SHA256=9de32f252b25a4f421e3c47522874cddfb84a388afb6142b60f922f2ce03bea5

OTA_TARGET_PRESENT=false
OTA_CONTENT_RW=true
OTA_CONFIG_RW=true
LOCAL_HTTP=403
PUBLIC_HTTP=404
```

The website continuity oracle was captured before mutation and remained unchanged after Attempt02. Raw server-private locator data is intentionally excluded from this public closure.

## 3. Mutation actually performed

Attempt02 performed only the bounded OTA-origin mutation:

- exact Home Assistant 2026.10.4 inner archive atomically promoted into the dedicated OTA storage;
- OTA static-server configuration advanced to the frozen PR #4 source contract;
- OTA content/config mounts advanced from read-write to read-only;
- only `ota_server` was recreated;
- the website edge configuration/container was not modified or recreated.

The Docker Compose `version` deprecation warning was informational and did not affect execution or acceptance.

## 4. Acceptance

Local origin acceptance proved the exact immutable artifact contract:

```text
HTTP=200
CONTENT_LENGTH=835309535
CONTENT_TYPE=application/octet-stream
CACHE_CONTROL=public, max-age=31536000, immutable
X_CONTENT_TYPE_OPTIONS=nosniff
```

The public exact target intentionally remained HTTP 404 because website-edge publication is a later separately authorized gate.

## 5. Authorization disposition

Attempt01 remains consumed and replay-forbidden.

Attempt02 crossed its claim boundary, completed successfully, and is now terminal:

```text
ATTEMPT02_AUTHORIZATION_CONSUMED=true
ATTEMPT02_REPLAY_PERMITTED=false
```

No rollback was required.

## 6. Remaining boundaries

```text
OTA_ORIGIN_LIVE_PUBLICATION=PASS
WEBSITE_EDGE_PUBLICATION=false
T1_KF147_LIVE_POLICY_REPAIR=false
PREPARE_REPLAY=false
CONFIRM_USB_ERASE=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false

NEXT_STAGE=KF147_STAGE_A_EDGE_PUBLICATION_SEPARATE_GATE
AUTO_EXECUTE_NEXT_STAGE=false
NEW_AUTHORIZATION_REQUIRED=true
```

This closure does not authorize edge configuration/reload, T1 access or mutation, USB destructive work, U2+, board access, or merge.
