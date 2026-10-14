# N3-W T1 minimal-host fresh product bootstrap live apply authorization（2026-10-12）

```text
AUTHORIZATION_ID=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_01
USER_APPROVAL=EXPLICIT
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_ALLOWED=true_before_claim_only

PRODUCT_SOURCE_HEAD=2118eb09524ef4c475b381c17b7740c202388446
PRODUCT_SOURCE_TREE=6504ef649a8a80406a7c41bd996fbd280122058d
ARTIFACT_ID=11725615364
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-2118eb09524ef4c475b381c17b7740c202388446
ARTIFACT_DIGEST=sha256:b7bc83ef7e8b68e8e6ce06a68f4a355b424409f50b13b108014039fa5f79d8fd
PAYLOAD_ARCHIVE_SHA256=ae6f61477b62c50a71c786e03b830aecb9835c3ccaab925cb2db02aac99399ce
PAYLOAD_MANIFEST_SHA256=b0cc5dbafcdf842f20ded406f775356623346008fd212dee6f68a6cbc1018f8a

REAL_T1_PREEXECUTION_READONLY=PASS
LIVE_MUTATION_NOT_YET_STARTED=true
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541_MERGE=false
```

This authorization is single-use. Once the repository-owned executor emits the durable `authorization_claimed` event, it is permanently consumed. Any unknown outcome after remote apply starts must also be treated as consumed/no-replay. A preclaim failure proven to occur before remote apply starts may remain unconsumed.

The authorization permits the fresh product staging transaction only. It does not authorize production Broker/Manager/Home Assistant activation, board access, firmware/NVS/RF work, or PR merge.
