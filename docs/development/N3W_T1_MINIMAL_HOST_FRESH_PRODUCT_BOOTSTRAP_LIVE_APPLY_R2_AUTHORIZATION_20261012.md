# N3-W T1 minimal-host fresh product bootstrap live apply R2 authorization（2026-10-12）

```text
AUTHORIZATION_ID=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_02
USER_APPROVAL=EXPLICIT
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_ALLOWED=true_before_claim_only

PRODUCT_SOURCE_HEAD=9b12116ef28d795696d1fa1353851fe51d7bebae
ARTIFACT_ID=11726716679
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-9b12116ef28d795696d1fa1353851fe51d7bebae
ARTIFACT_DIGEST=sha256:c575c64422c538e9de68fb00e9cdcb099241526864375f02c4c0d1883d80f891
PAYLOAD_ARCHIVE_SHA256=d39c7d843cccac93a0cc6538b83637846c91f36bc8752f0aaadf2af69743f241
PAYLOAD_MANIFEST_SHA256=317d6f45a60d69145271ba6e3ceebb595957d0bc2f7dcfce03c23ffec17084aa

PREEXECUTION_R2=CLOSED_PASS
KF109=GUARDED_SOURCE / LIVE_REVALIDATION_PENDING
PRODUCTION_SERVICE_START_AUTHORIZED=false
BOARD_ACCESS=false
PR541_MERGE=false
```

This authorization is one-shot and applies only to the fresh product staging transaction using the exact replacement artifact above.

Once the repository-owned executor emits the durable `authorization_claimed` event, the authorization is permanently consumed and must never be replayed. Any unknown outcome after remote apply starts is also treated as consumed/no-replay.

This authorization does not permit production Broker/Manager/Home Assistant activation, firmware/NVS/RF work, board access, or PR merge.
