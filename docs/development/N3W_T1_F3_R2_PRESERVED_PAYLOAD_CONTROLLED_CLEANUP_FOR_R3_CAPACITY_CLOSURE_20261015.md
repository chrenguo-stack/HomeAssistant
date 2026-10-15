# N3W T1 F3 R2 preserved payload controlled cleanup for R3 capacity closure — 2026-10-15

## Gate

```text
TASK=N3W_T1_F3_R2_PRESERVED_PAYLOAD_CONTROLLED_CLEANUP_FOR_R3_CAPACITY_20261015_01
RESULT=CLOSED_PASS

R2_AUTHORIZATION=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R2_20261014_01
R2_AUTHORIZATION_STATE=CONSUMED_NO_REPLAY
R3_AUTHORIZATION=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R3_20261014_01
R3_AUTHORIZATION_GRANTED=false
R3_AUTHORIZATION_CLAIMED=false
R3_AUTHORIZATION_CONSUMED=false

PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
F4_AUTHORIZATION_GRANTED=false
MERGE=false
```

## Pre-cleanup exact binding

The R3 read-only preauthorization preflight found insufficient root free space because the preserved R2 failed
transaction still contained the fully transferred Home Assistant image tar.

```text
PRE_CLEANUP_ROOT_FREE_BYTES=9416998912
R3_REQUIRED_FREE_BYTES=10135822686
PRE_CLEANUP_CAPACITY_PASS=false

R2_PRESERVED_PAYLOAD_BYTES=2448859346
R2_PAYLOAD_MANIFEST_SHA256=e2745281d37f675f6e769bc795c33a4dc766131ce44faa88ea9ffb4e87501fbf
R2_HOMEASSISTANT_TAR_SIZE_BYTES=2448553472
R2_HOMEASSISTANT_TAR_SHA256=3cebb7b532237bb8841ae3f0a1ecb5d0b0a2bbd973ce6cb18c407229953efd1e
R2_TAR_COUNT=1
R2_MANIFEST_LEDGER_BINDING=PASS
R3_LEDGER_ABSENT=true
OLDER_FAILED_PAYLOAD_PRESERVED=true
OLDER_FAILED_PAYLOAD_BYTES=287821

CONTAINERS=0
IMAGES=0
VOLUMES=0
NETWORKS=bridge,host,none
PRODUCT_LISTENERS=NONE
R2_CLEANUP_PRECHECK=PASS
```

The delete guard rebound the exact transaction directory to its R2 claim marker, exact payload manifest,
Home Assistant tar size/hash, and durable authorization ledger before deletion. No authorization ledger was
deleted or modified.

## Controlled mutation

Only the exact R2 transaction-owned preserved payload directory was removed. The R2 authorization ledger,
the earlier small failed payload, Docker/Compose baseline, and all other host state were preserved.

```text
R2_DELETE_GUARD=PASS
R2_PAYLOAD_DELETED=true
R2_LEDGER_PRESERVED=true
R3_LEDGER_ABSENT=true
OLDER_FAILED_PAYLOAD_PRESERVED=true
```

## Post-cleanup state

```text
CONTAINERS=0
IMAGES=0
VOLUMES=0
NETWORKS=bridge,host,none
PRODUCT_LISTENERS=NONE

POST_CLEANUP_ROOT_FREE_BYTES=11866021888
R3_REQUIRED_FREE_BYTES=10135822686
R3_CAPACITY_PASS=true

R2_CONTROLLED_CLEANUP=PASS
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
F4_AUTHORIZATION_GRANTED=false
```

The cleanup restores the Docker-ready minimal host capacity envelope without manufacturing authorization
replayability. R2 remains permanently consumed/no-replay.

## Next boundary

Return to the already approved read-only preauthorization gate:

```text
CURRENT_GATE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_R3_READONLY_PREAUTH_PREFLIGHT_20261015_01
NEXT_STEP=EXACT_R3_LOCAL_HOST_WRAPPER_SOURCE_BINDING_AND_FINAL_PREAUTH_CLOSURE
AUTO_EXECUTE_R3_LIVE_APPLY=false
R3_AUTHORIZATION_GRANTED=false
```

No R3 live mutation may begin until exact local execution binding is proven and the user separately grants
`N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R3_20261014_01`.
