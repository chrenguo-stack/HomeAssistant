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
