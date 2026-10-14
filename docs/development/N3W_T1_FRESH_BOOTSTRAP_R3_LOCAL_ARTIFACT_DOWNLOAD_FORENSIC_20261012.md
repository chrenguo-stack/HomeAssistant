# N3-W fresh bootstrap R3 local artifact download forensic（2026-10-12）

## Outcome

The exact R3 live authorization remains granted but unclaimed.

Two consecutive attempts stopped before any T1 payload transfer because the Mac-side GitHub CLI failed while following the GitHub Actions artifact redirect to the Actions result blob endpoint.

```text
AUTHORIZATION_ID=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_03
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
PAYLOAD_TRANSFER=false
DOCKER_MUTATION=false
REMOTE_PAYLOAD_PRESERVED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
STATUS=STOP_PRECLAIM
```

This is a local artifact transport failure, not a T1 bootstrap failure and not evidence against KF-110 repair.

## Exact artifact authority

```text
PRODUCT_SOURCE_HEAD=1f191b264f246254ac1f1cb97cd38dc942f13021
ARTIFACT_ID=11729783144
ARTIFACT_DIGEST=sha256:03098b8cf5e30a4ca485da52e9e752054226b6718f3a5bf7e26b78cc88612689
PAYLOAD_ARCHIVE_SHA256=f6a3a21d390224fe91f26f85aa6b96940c45196b992db7f1318ae1cb86023d1a
PAYLOAD_MANIFEST_SHA256=b8ea6345f5699dde96a1e8b71a280b2c9e261a72dc8368cdcef323a65a25312e
ARTIFACT_EXPIRED=false
```

## Transport fallback

The fallback is limited to replacing the Mac-side `gh run download` operation.

The artifact ZIP must first be fetched from the official GitHub REST artifact endpoint and its complete ZIP SHA-256 must equal the GitHub artifact digest above. Only then may the ZIP be safely extracted.

The execution then loads the exact `host-wrapper.py` contained in that verified artifact and substitutes only its network download callback with a local copy callback. The wrapper's existing outer file-set, archive SHA, manifest sidecar, host-wrapper sidecar, current-wrapper SHA, payload manifest and capacity checks remain active before any remote staging begins.

No source, payload, artifact, authorization identity, production activation scope, board scope, or merge scope is changed.
