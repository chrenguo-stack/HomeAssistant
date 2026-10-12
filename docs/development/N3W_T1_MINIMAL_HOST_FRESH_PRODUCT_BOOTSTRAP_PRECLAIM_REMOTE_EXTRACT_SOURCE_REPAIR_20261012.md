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
