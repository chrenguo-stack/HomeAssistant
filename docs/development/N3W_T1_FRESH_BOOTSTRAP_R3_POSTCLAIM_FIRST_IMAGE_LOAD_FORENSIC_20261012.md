# N3-W T1 fresh bootstrap R3 postclaim first image-load forensic（2026-10-12）

## Exact outcome

```text
PRODUCT_SOURCE_HEAD=1f191b264f246254ac1f1cb97cd38dc942f13021
ARTIFACT_ID=11729783144
AUTHORIZATION_ID=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_03

ARTIFACT_DOWNLOAD=PASS
ARTIFACT_ZIP_SHA256=03098b8cf5e30a4ca485da52e9e752054226b6718f3a5bf7e26b78cc88612689
ARTIFACT_OUTER_EXTRACT=PASS

AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false
BOOTSTRAP_STATUS=STOP_PARTIAL
BOOTSTRAP_REASON=fresh_install_failed
HOST_STATUS=STOP_PARTIAL
REMOTE_PAYLOAD_PRESERVED=true
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

The R3 authorization is permanently consumed and must not be replayed.

## Cleanup proof

The installer returned `fresh_install_failed`, not `fresh_install_failed_and_cleanup_not_proven`. Its orchestration only emits the former after transaction cleanup succeeds; cleanup itself finishes by re-running the minimal-host preflight.

Independent real-T1 inventory after the failure also proves the rollback result:

```text
STATUS=PASS
INVENTORY_SHA256=e38273381de031789fff2f5c2fb37725c328cfaa9710603b6c74ba920422842d
CONTAINERS=0
IMAGES=0
VOLUMES=0
NETWORKS=bridge,host,none
PRODUCT_PATHS_PRESENT=0
PRODUCT_UNITS=0
PRODUCT_LISTENERS=0
UNKNOWN_STOP=0
DELETE_PRODUCT_STATE_CANDIDATE=0
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

## Failure-domain narrowing

The retained payload is:

```text
REMOTE_PAYLOAD=n3w-fresh-bootstrap.EOmzn8
SOURCE_HEAD=1f191b264f246254ac1f1cb97cd38dc942f13021
AUTHORIZATION_MARKER=true
CANDIDATE_TRANSACTION_DIRS=0

HOMEASSISTANT_TAR_PRESENT=true
HOMEASSISTANT_TAR_SIZE=2448553472
MANAGER_TAR_PRESENT=true
MANAGER_TAR_SIZE=59296768
BROKER_TAR_PRESENT=true
BROKER_TAR_SIZE=27556352
```

`load_images()` processes Home Assistant first and unlinks each image tar only after successful `docker load`, exact image inspect and ID/platform binding. Since all three tars remain, the first Home Assistant image step did not reach the unlink point.

The remaining failure domain is therefore:

1. Home Assistant `docker load` returned nonzero;
2. Home Assistant `docker load` exceeded its 1800-second timeout;
3. the subsequent `docker image inspect` failed;
4. the observed image ID/platform failed the exact binding comparison.

Because cleanup removed transaction-owned images, post-failure `docker image ls` cannot by itself distinguish these cases.

The absence of warning-or-higher Docker journal entries is not sufficient to classify the root cause.

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_FRESH_BOOTSTRAP_R3_FIRST_IMAGE_LOAD_READONLY_FORENSIC
READ_ONLY=true
LIVE_MUTATION=false
AUTHORIZATION_REPLAY=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541_MERGE=false
```

Use retained-payload metadata, claim timestamp, Docker image events, full Docker daemon log context and kernel storage/OOM evidence to distinguish timeout/load failure from post-load binding failure. Do not delete the retained payload before this forensic closes.
