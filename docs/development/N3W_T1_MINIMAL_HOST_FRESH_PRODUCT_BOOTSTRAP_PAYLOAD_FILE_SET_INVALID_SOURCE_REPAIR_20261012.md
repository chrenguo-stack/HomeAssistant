# N3-W T1 minimal-host fresh bootstrap payload file-set invalid source repair（2026-10-12）

## Observed live outcome

The explicitly authorized `N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_02` attempt stopped before durable authorization claim:

```text
BOOTSTRAP_STATUS=STOP
BOOTSTRAP_REASON=payload_file_set_invalid
HOST_STATUS=STOP_PRECLAIM
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REMOTE_PAYLOAD_REMOVED=true
REMOTE_PAYLOAD_PRESERVED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

The host wrapper proved remote staging cleanup after the preclaim failure. No Docker/product mutation was reported.

## Root cause

The deployable workflow created `payload-manifest.json` and its exact `files` inventory, then executed a live-adapter rehearsal by importing the bootstrap module directly from the payload tree with `importlib`.

Python bytecode caching can create `__pycache__/*.pyc` under that payload tree after the manifest inventory has been frozen. The workflow then archived the entire payload tree. The resulting archive could therefore contain regular files that were not listed in the manifest.

The workflow's existing post-upload checks proved archive/sidecar/executor hashes and inner manifest binding, but did not re-run the payload file-set verifier after the rehearsal and immediately before archive creation.

The real T1 correctly failed closed when `_load_manifest()` compared the extracted actual regular-file set with the manifest set.

## Repair

The deployable workflow now:

1. runs the payload-tree rehearsal with `PYTHONDONTWRITEBYTECODE=1`;
2. re-runs the bootstrap `self-check` after all payload-tree rehearsal activity and immediately before calculating manifest/archive hashes;
3. explicitly rejects any regular file under a `__pycache__` directory before archive creation.

A source regression test requires the bytecode suppression and the final post-rehearsal file-set self-check.

## Authorization rotation

```text
PREDECESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_02
PREDECESSOR_OUTCOME=STOP_PRECLAIM
PREDECESSOR_CLAIMED=false
PREDECESSOR_CONSUMED=false
PREDECESSOR_REMOTE_PAYLOAD_REMOVED=true
PREDECESSOR_REPLAY=false_due_to_exact_source_supersession

SUCCESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_03
SUCCESSOR_GRANTED=false
SUCCESSOR_CLAIMED=false
SUCCESSOR_CONSUMED=false
```

A replacement exact artifact and fresh real-T1 read-only preexecution are required before any successor authorization may be requested.


## R3 exact-head / replacement artifact / live preexecution closure

```text
SOURCE_HEAD=1f191b264f246254ac1f1cb97cd38dc942f13021
EXACT_HEAD_WORKFLOWS=25/25 PASS

ARTIFACT_ID=11729783144
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-1f191b264f246254ac1f1cb97cd38dc942f13021
ARTIFACT_DIGEST=sha256:03098b8cf5e30a4ca485da52e9e752054226b6718f3a5bf7e26b78cc88612689
PAYLOAD_ARCHIVE_SHA256=f6a3a21d390224fe91f26f85aa6b96940c45196b992db7f1318ae1cb86023d1a
PAYLOAD_MANIFEST_SHA256=b8ea6345f5699dde96a1e8b71a280b2c9e261a72dc8368cdcef323a65a25312e

FRESH_BOOTSTRAP_INNER_BINDING=PASS
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS
```

Real T1 minimal-host inventory:

```text
STATUS=PASS
INVENTORY_SHA256=c75fc8a09d1db556f3af7abdf9dd0cf4f70135c46e8311db9143d17c5a00d3a7
CONTAINERS=0
IMAGES=0
VOLUMES=0
NETWORKS=bridge,host,none
PRODUCT_PATHS=0
PRODUCT_UNITS=0
PRODUCT_LISTENERS=0
UNKNOWN_STOP=0
DELETE_CANDIDATES=0
```

Replacement artifact live read-only host preflight:

```text
STATUS=PASS
PHASE=preflight
PAYLOAD_TRANSFER=false
DOCKER_MUTATION=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

REMOTE_FREE_BYTES=11764998144
REQUIRED_FREE_BYTES=10222810574
REQUIRED_PEAK_BYTES=4854101454
MINIMUM_POST_PEAK_FREE_BYTES=5368709120
FREE_AFTER_ESTIMATED_PEAK_BYTES=6910896690
CAPACITY_PASS=true
```

KF-110 is now `GUARDED_SOURCE / LIVE_REVALIDATION_PENDING`. Source/CI/artifact/preexecution are closed. The repaired post-manifest file-set protection has not yet been exercised by a fresh real-T1 apply using the R3 artifact.

```text
SUCCESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_03
SUCCESSOR_GRANTED=false
SUCCESSOR_CLAIMED=false
SUCCESSOR_CONSUMED=false
```
