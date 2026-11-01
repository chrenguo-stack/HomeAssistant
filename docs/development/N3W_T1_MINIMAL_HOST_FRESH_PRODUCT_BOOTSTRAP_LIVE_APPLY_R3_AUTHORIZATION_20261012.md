# N3-W T1 minimal-host fresh product bootstrap live apply R3 authorization（2026-10-12）

```text
AUTHORIZATION_ID=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_03
USER_APPROVAL=EXPLICIT
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_ALLOWED=true_before_claim_only

PRODUCT_SOURCE_HEAD=1f191b264f246254ac1f1cb97cd38dc942f13021
ARTIFACT_ID=11729783144
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-1f191b264f246254ac1f1cb97cd38dc942f13021
ARTIFACT_DIGEST=sha256:03098b8cf5e30a4ca485da52e9e752054226b6718f3a5bf7e26b78cc88612689
PAYLOAD_ARCHIVE_SHA256=f6a3a21d390224fe91f26f85aa6b96940c45196b992db7f1318ae1cb86023d1a
PAYLOAD_MANIFEST_SHA256=b8ea6345f5699dde96a1e8b71a280b2c9e261a72dc8368cdcef323a65a25312e

PREEXECUTION_R3=CLOSED_PASS
KF109=GUARDED_SOURCE / LIVE_REVALIDATED
KF110=GUARDED_SOURCE / LIVE_REVALIDATION_PENDING
PRODUCTION_SERVICE_START_AUTHORIZED=false
BOARD_ACCESS=false
PR541_MERGE=false
```

This authorization is one-shot and applies only to the fresh product staging transaction using the exact replacement artifact above.

Once the repository-owned executor emits the durable `authorization_claimed` event, the authorization is permanently consumed and must never be replayed. Any unknown outcome after remote apply starts is also treated as consumed/no-replay.

This authorization does not permit production Broker/Manager/Home Assistant activation, firmware/NVS/RF work, board access, or PR merge.
