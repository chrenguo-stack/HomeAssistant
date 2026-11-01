# N3-W T1 minimal-host fresh bootstrap preclaim remote extract source repair（2026-10-12）

## Observed live preclaim failure

The explicitly authorized `N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_01` attempt stopped before authorization claim and before Docker/product mutation.

```text
STATUS=STOP_PRECLAIM
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
DOCKER_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REMOTE_PAYLOAD_PRESERVED=true
```

The remote payload preparation command failed in Python parsing before extraction:

```text
SyntaxError: invalid syntax
root=Path(sys.argv[1]);archive=root/'payload.tar.gz';def sha(path):
                                                       ^^^
```

Root cause: the host wrapper generated a compact `python3 -c` program with compound statements (`def`, and subsequently `with`) following semicolons. Python grammar permits semicolon-separated simple statements only; compound statements cannot appear in that position.

This is a preclaim host/transport harness defect, not a fresh-product constructor failure.

## Repair

The remote extraction program is now emitted as a normal multiline Python program with explicit failure reasons for archive SHA, unsafe member paths, links/special members and manifest SHA.

Regression coverage executes the exact generated remote program locally against a real tar archive and also proves that a symlink member is rejected before extraction. This closes the gap left by prior tests, which mocked `_remote_prepare_payload` and therefore could not detect invalid generated Python syntax.

Because the executable host wrapper changed after the previous exact artifact was authorized, the previous grant is superseded even though it was never claimed or consumed.

```text
PREDECESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_01
PREDECESSOR_OUTCOME=STOP_PRECLAIM
PREDECESSOR_CLAIMED=false
PREDECESSOR_CONSUMED=false
PREDECESSOR_REPLAY=false_due_to_exact_source_supersession

SUCCESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_02
SUCCESSOR_GRANTED=false
SUCCESSOR_CLAIMED=false
SUCCESSOR_CONSUMED=false
```

The successor may not be granted until corrected exact-head CI, a replacement deployable artifact binding, stale preclaim staging-residue handling, and a fresh real-T1 read-only preexecution all pass.


## First corrected CI classification

The first corrected exact-head CI exposed two non-product follow-up defects:

1. the deployable focused test still asserted predecessor authorization `..._01` after source rotation to `..._02`; source/runtime behavior was already on `..._02`;
2. public repository safety correctly rejected the previously archived literal private T1 IPv4 address in the read-only closure document.

Both are corrected without T1 access or live mutation. The extractor source repair remains unchanged.


## R2 exact-head / replacement artifact / live preexecution closure

```text
SOURCE_HEAD=9b12116ef28d795696d1fa1353851fe51d7bebae
EXACT_HEAD_WORKFLOWS=25/25 PASS

ARTIFACT_ID=11726716679
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-9b12116ef28d795696d1fa1353851fe51d7bebae
ARTIFACT_DIGEST=sha256:c575c64422c538e9de68fb00e9cdcb099241526864375f02c4c0d1883d80f891
PAYLOAD_ARCHIVE_SHA256=d39c7d843cccac93a0cc6538b83637846c91f36bc8752f0aaadf2af69743f241
PAYLOAD_MANIFEST_SHA256=317d6f45a60d69145271ba6e3ceebb595957d0bc2f7dcfce03c23ffec17084aa

FRESH_DEPLOYMENT_GATE=PASS
FRESH_LIVE_ADAPTER_PRECOMMIT_REHEARSAL=PASS
FRESH_BOOTSTRAP_INNER_BINDING=PASS
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS
```

The exact old preclaim staging residue was deleted only after proving: single matching staging directory, root ownership, mode 0700, no authorization claim marker, exact one-file set, and exact predecessor payload SHA. No Docker or product mutation was performed.

Post-clean minimal-host inventory:

```text
STATUS=PASS
INVENTORY_SHA256=b6e596279756511b985bf01b8a5fa0698ee4fa85edc4539af82facdac428e745
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

REMOTE_FREE_BYTES=11765043200
REQUIRED_FREE_BYTES=10222810574
REQUIRED_PEAK_BYTES=4854101454
MINIMUM_POST_PEAK_FREE_BYTES=5368709120
FREE_AFTER_ESTIMATED_PEAK_BYTES=6910941746
CAPACITY_PASS=true
```

KF-109 is now `GUARDED_SOURCE / LIVE_REVALIDATION_PENDING`. The source/CI/artifact/preexecution defect chain is closed; the repaired extractor itself has not yet been exercised on the real T1 after claim, so the live revalidation flag remains until the next explicitly authorized one-shot apply.

```text
SUCCESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_02
SUCCESSOR_GRANTED=false
SUCCESSOR_CLAIMED=false
SUCCESSOR_CONSUMED=false
```
