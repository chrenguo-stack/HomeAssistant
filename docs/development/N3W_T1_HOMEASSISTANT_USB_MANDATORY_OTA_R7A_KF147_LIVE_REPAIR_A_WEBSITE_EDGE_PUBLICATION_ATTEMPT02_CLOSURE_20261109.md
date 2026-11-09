# N3-W T1 Home Assistant mandatory-USB OTA R7A
# KF-147 Stage A website-edge publication Attempt02 closure — 2026-11-09

## Result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_LIVE_REPAIR_A_WEBSITE_EDGE_PUBLICATION_ATTEMPT02_20261109_01
RESULT=CLOSED_PASS

AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

PREMUTATION_RECHECK=PASS
EDGE_SOURCE_SHA256=58d15c950adfbedcb659fe8749d4b3b7145f91ad6dbd30cd208f78b5a2d8bdcd
EDGE_RELOAD=PASS

PUBLIC_HTTP=200
PUBLIC_CONTENT_LENGTH=835309535
PUBLIC_CONTENT_TYPE=application/octet-stream
PUBLIC_CACHE_CONTROL=public, max-age=31536000, immutable
PUBLIC_NOSNIFF=nosniff

PUBLIC_FIRST_1MIB_SHA256=3003efa13893fc80ebaac6436b4becb7c8d8e912747b17b1cb83906572324f0c
PUBLIC_LAST_1MIB_SHA256=9f3c4c57dc2928f9d275d2bddf1cb3242b5da9dd96758f6c366c9bf64d5c828f
LOOPBACK_HTTPS_FULL_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973

WEBSITE_CONTAINER_RECREATED=false
WEBSITE_RELOAD=PASS
OTA_CONTAINER_UNTOUCHED=PASS
WEBSITE_ROOT_HTTP=200
ROLLBACK_REQUIRED=false

WEBSITE_EDGE_PUBLICATION_ATTEMPT02=PASS

T1_ACCESS=false
T1_MUTATION=false
PREPARE_REPLAY=false
USB_MUTATION=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

## Validation strategy

Attempt02 intentionally did not repeat Attempt01's 835 MB public self-download. Public validation covered the exact HTTPS route, headers and body using HEAD plus the first and last 1 MiB ranges. Complete byte identity was then validated through loopback HTTPS/SNI, forcing `ota.hahub.top` to `127.0.0.1` while preserving TLS/SNI and traversing the website edge to the OTA origin.

The full loopback SHA-256 matches the frozen Home Assistant 2026.10.4 archive:

```text
eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
```

## Closure

Stage A OTA publication is now complete:

```text
OTA_ORIGIN_LIVE=PASS
WEBSITE_EDGE_LIVE=PASS
PUBLIC_OTA_ROUTE=PASS
```

Attempt01 remains consumed and replay-forbidden. Attempt02 is also consumed and replay-forbidden.

The next boundary is the separately authorized T1 KF-147 live policy repair. This closure does not authorize T1 access/mutation, PREPARE replay, USB destructive work, U2+, board work, or merge.
