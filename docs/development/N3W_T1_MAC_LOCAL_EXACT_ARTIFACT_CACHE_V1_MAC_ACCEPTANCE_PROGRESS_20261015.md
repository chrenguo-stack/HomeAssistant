# N3-W T1 Mac 本地 exact artifact cache V1 Mac acceptance progress
# 2026-10-15

## Attempt 1

```text
TASK=N3W_T1_MAC_LOCAL_EXACT_ARTIFACT_CACHE_V1_MAC_ACCEPTANCE_20261015_01
RESULT=STOP_PRECACHE_METADATA_NETWORK

EXECUTABLE_SOURCE_HEAD=d1a7847c1e0612ac80b31b85262011110f329794
ARTIFACT_ID=11953163662
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-d1a7847c1e0612ac80b31b85262011110f329794
ARTIFACT_ZIP_SHA256=6f0ec341494bc6ba2a9b9d03a2c3968b708241dd069408a3dc72f63f3e79a89c

FAILURE_STAGE=github_artifact_metadata_lookup
FAILURE_SURFACE=gh_api
FAILURE_CLASS=NETWORK_EOF
CACHE_POPULATION_STARTED=false
LARGE_ARTIFACT_DOWNLOAD_STARTED=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
EXPLICIT_DEVICE_PROVISIONING=false
F4=false
BOARD_ACCESS=false
```

Observed Mac error:

```text
FreshHostTransportError:
command_failed:gh:1:Get "https://api.github.com/repos/chrenguo-stack/HomeAssistant/actions/artifacts/11953163662": EOF
```

The failure happened in `_artifact_metadata()`, before `_populate_artifact_cache()`.
Therefore the exact artifact was not downloaded and no cache entry was published.

Fresh GitHub-side verification after the failure confirms the target artifact still exists and is unexpired:

```text
ARTIFACT_ID=11953163662
EXPIRED=false
SIZE_BYTES=2535588821
DIGEST=sha256:6f0ec341494bc6ba2a9b9d03a2c3968b708241dd069408a3dc72f63f3e79a89c
```

No evidence currently indicates artifact drift or an authentication rejection. The observed failure is a transport EOF on the lightweight metadata request.

## Next step

Run a minimal Mac-side `gh api` metadata probe first. If it succeeds with the exact ID/name/digest/expired tuple, rerun the same Mac acceptance command. Do not change cache contents manually.

If repeated metadata EOF reproduces, return to source repair and add bounded retry around the metadata lookup before continuing acceptance.


## Attempt 2 — reproducible Mac API transport failure

The minimal Mac read-only probe was repeated outside the acceptance wrapper:

```text
gh api repos/chrenguo-stack/HomeAssistant/actions/artifacts/11953163662
→ net/http: TLS handshake timeout
```

This independently reproduces the first attempt's API EOF at the same lightweight metadata boundary.

```text
MAC_GITHUB_API_TRANSIENT_REPRODUCED=true
FIRST_FAILURE=EOF
SECOND_FAILURE=TLS_HANDSHAKE_TIMEOUT
ARTIFACT_DRIFT_EVIDENCE=false
AUTH_REJECTION_EVIDENCE=false
CACHE_POPULATION_STARTED=false
LARGE_ARTIFACT_DOWNLOAD_STARTED=false
T1_ACCESS=false
```

GitHub-side connector evidence continues to show artifact ID 11953163662 as unexpired with the exact expected digest.

## Acceptance-discovered source repair

The Mac acceptance uncovered a source robustness gap: artifact metadata used `gh api` with no bounded transport retry.
The repair replaces that network call with authenticated `curl` using:

```text
IPv4=true
HTTP1_1=true
RETRY=3
RETRY_ALL_ERRORS=true
RETRY_DELAY_SECONDS=2
CONNECT_TIMEOUT_SECONDS=20
MAX_METADATA_TIME_SECONDS=120
```

The artifact redirect lookup receives the same bounded retry contract. The large artifact transfer keeps exact
SHA-256 verification and is strengthened to retry all transport errors up to five retries; the outer host timeout
is extended for the one-time multi-gigabyte population.

New regression coverage proves metadata lookup uses the IPv4/HTTP1.1/retry curl path and that the prior
`gh api` network path is no longer used for artifact metadata.

The F2 exact host-wrapper blob binding is updated with the repaired wrapper.

```text
SOURCE_REPAIR_IN_PROGRESS=true
T1_ACCESS=false
PROVISIONING=false
F4=false
BOARD_ACCESS=false
MERGE=false
```

Mac acceptance must not resume until the repaired exact-head CI and newly generated exact deployable artifact pass.


## Source repair CI closure / Mac acceptance resume authority

```text
REPAIRED_SOURCE_HEAD=13b08208c91400a7e6a91ddbc47620a6146eb2a1
CI_TOTAL=14
CI_SUCCESS=14
CI_FAILURE=0
CI_PENDING=0

FRESH_DEPLOYABLE_RUN_ID=38696945364
FRESH_DEPLOYABLE_JOB_ID=116295658889
ARTIFACT_ID=11954286988
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-13b08208c91400a7e6a91ddbc47620a6146eb2a1
ARTIFACT_SIZE_BYTES=2535589326
ARTIFACT_ZIP_SHA256=047a40ed640bc1bfcbc8adb7007da2a4eea1f8abedffbc3cb2e2a4d9f6817928
RUNTIME_PAYLOAD_SHA256=bc884befe99d223ce39788bab0b5555ff34faebd050c0dffbeebc77c523f7097
PAYLOAD_MANIFEST_SHA256=10c4f298c1034694a93d260970dac09c1a495f7d0b337922de0ba48698874a6c

FRESH_BOOTSTRAP_INNER_BINDING=PASS
FRESH_TRANSPORT_V2_POST_UPLOAD_BINDING=PASS
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS
```

The repaired exact artifact is unexpired and bound to the repaired source head. Mac acceptance may resume using this
new artifact only. The older artifact ID 11953163662 remains historical evidence and must not be used for the
repaired acceptance.

The acceptance remains Mac-local only:

```text
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
EXPLICIT_DEVICE_PROVISIONING=false
F4=false
BOARD_ACCESS=false
MERGE=false
```
