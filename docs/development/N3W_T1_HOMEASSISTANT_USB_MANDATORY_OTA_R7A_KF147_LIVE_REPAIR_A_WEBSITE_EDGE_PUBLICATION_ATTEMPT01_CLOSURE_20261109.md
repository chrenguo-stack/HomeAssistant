# N3-W T1 Home Assistant mandatory-USB OTA R7A
# KF-147 Stage A website-edge publication Attempt01 closure — 2026-11-09

## Result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_LIVE_REPAIR_A_WEBSITE_EDGE_PUBLICATION_20261109_01
RESULT=FAILED_ROLLED_BACK_PASS

AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

PREMUTATION_RECHECK=PASS
EDGE_SOURCE_SHA256=58d15c950adfbedcb659fe8749d4b3b7145f91ad6dbd30cd208f78b5a2d8bdcd
PUBLIC_HTTP_BEFORE_FINAL_VALIDATION=200
LOCAL_ORIGIN_HTTP=200

FULL_GET_TIMEOUT_SECONDS=1800
FULL_GET_EXPECTED_BYTES=835309535
FULL_GET_RECEIVED_BYTES=833642496
FULL_GET_MISSING_BYTES=1667039
FAILURE_CLASS=PUBLIC_FULL_GET_VALIDATION_TIMEOUT

ROLLBACK=PASS
PRODUCT_SOURCE_DEFECT_NEW=false
OTA_ORIGIN_DEFECT_NEW=false
EDGE_SOURCE_DEFECT_NEW=false

WEBSITE_CONTAINER_RECREATE=false
OTA_CONTAINER_RECREATE=false
T1_ACCESS=false
PREPARE_REPLAY=false
USB_MUTATION=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

The exact edge source reached the intended live path and the public exact target returned HTTP 200 before the final full-body validation. The final validation command used a fixed 1800-second curl max-time and timed out after receiving 833,642,496 of 835,309,535 bytes. The bounded rollback then completed PASS.

This failure is classified as an executor/validation-budget defect. It does not reopen the hahub.top PR #4 source design, the OTA-origin source, or the already closed origin publication.

The Attempt01 authorization is consumed and must never be replayed.

## Next boundary

```text
NEXT_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_LIVE_REPAIR_A_WEBSITE_EDGE_PUBLICATION_ATTEMPT02_20261109_01
NEXT_GATE_AUTHORIZED=false
AUTO_EXECUTE_NEXT_GATE=false
```

A future Attempt02 must use a revised validation strategy or a materially larger transfer-time budget and requires fresh explicit live authorization.
