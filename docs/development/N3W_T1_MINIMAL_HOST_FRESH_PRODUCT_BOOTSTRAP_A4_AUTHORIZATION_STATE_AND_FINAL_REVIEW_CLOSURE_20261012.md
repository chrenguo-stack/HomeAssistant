# N3-W T1 minimal-host fresh product bootstrap A4 authorization-state repair and final review closure（2026-10-12）

## Scope

```text
TASK=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_A4_AUTHORIZATION_UNKNOWN_OUTCOME_SOURCE_REPAIR_20261012_01
FINAL_REVIEW=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_EXACT_HEAD_ARTIFACT_FINAL_SOURCE_AND_EXECUTION_PATH_REVIEW_20261012_01
SCOPE=GITHUB_AND_HOST_ONLY
T1_ACCESS=false
LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541_MERGE=false
```

## A4 defect and repair

The independent final review found one substantive defect in the repository-owned host wrapper. After the remote executor had started, transport exceptions while probing the durable claim marker, or while removing the remote payload after a successful executor result, could fall through the generic preflight exception handler. That handler hard-coded the result as unclaimed/unconsumed and no Docker mutation.

This was unsafe because the one-shot authorization might already have been consumed.

The repaired host wrapper now preserves execution phase and claim knowledge across exceptions:

- before remote apply starts, a proven preclaim failure remains unclaimed/unconsumed;
- after remote apply starts, any unresolved claim outcome fails closed as consumed/no-replay;
- a seen durable claim is preserved as claimed+consumed;
- executor PASS followed only by remote payload cleanup failure is reported as `STOP_POSTSUCCESS_CLEANUP`, with the successful apply result and consumed/no-replay state retained;
- unknown outcome is never rewritten as a clean preflight failure.

Focused regression coverage includes marker-probe failure with a seen claim, marker-probe failure without a seen claim, post-success cleanup failure, and a proven preclaim failure. The deployable workflow focused suite reports `51 passed`.

## Exact source and CI binding

```text
PRODUCT_SOURCE_HEAD=2118eb09524ef4c475b381c17b7740c202388446
PRODUCT_SOURCE_TREE=6504ef649a8a80406a7c41bd996fbd280122058d

EXACT_HEAD_WORKFLOW_COUNT=25
EXACT_HEAD_WORKFLOW_PASS_COUNT=25
ALL_EXACT_HEAD_CI=PASS

FRESH_BOOTSTRAP_DEPLOYABLE_RUN_ID=38200203089
FRESH_BOOTSTRAP_DEPLOYABLE_CI=PASS
```

## Exact deployable artifact

```text
ARTIFACT_ID=11725615364
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-2118eb09524ef4c475b381c17b7740c202388446
ARTIFACT_SIZE_BYTES=814751044
ARTIFACT_DIGEST=sha256:b7bc83ef7e8b68e8e6ce06a68f4a355b424409f50b13b108014039fa5f79d8fd

PAYLOAD_ARCHIVE_SHA256=ae6f61477b62c50a71c786e03b830aecb9835c3ccaab925cb2db02aac99399ce
PAYLOAD_MANIFEST_SHA256=b0cc5dbafcdf842f20ded406f775356623346008fd212dee6f68a6cbc1018f8a

FRESH_DEPLOYMENT_GATE=PASS
FRESH_LIVE_ADAPTER_PRECOMMIT_REHEARSAL=PASS
FRESH_BOOTSTRAP_INNER_BINDING=PASS
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS
PRODUCTION_SERVICE_START=false
```

The GitHub workflow uploaded the artifact, downloaded that exact artifact again, verified the artifact digest, outer file set, payload archive sidecar, host-wrapper sidecar, manifest digest and inner executor digest. The chat-side GitHub connector does not need to re-download the approximately 815 MB artifact to establish this binding; the authoritative post-upload re-download verification occurred inside the exact-head workflow.

## Final A1-A10 review

```text
A1_PAYLOAD_EXTRACTION_AND_BINDING=PASS
A2_OFFLINE_IMAGE_LOAD_AND_PLATFORM_BINDING=PASS
A3_PRECLAIM_MINIMAL_HOST_PREFLIGHT=PASS
A4_DURABLE_CLAIM_AND_NO_REPLAY=PASS
A5_FRESH_IDENTITY_STATE_BROKER_DYNSEC=PASS
A6_RUNTIME_STAGING_OWNERSHIP_AND_PERMISSIONS=PASS
A7_COMMIT_BOUNDARY_AND_TRANSACTION_CLEANUP=PASS
A8_STOPPED_POSTCHECK=PASS
A9_NO_PRODUCTION_ACTIVATION=PASS
A10_NO_BOARD_OR_MERGE_SCOPE_EXPANSION=PASS

FINAL_SOURCE_EXECUTION_PATH_REVIEW=PASS
```

### A1
Outer artifact identity is exact-bound by digest and sidecars. Both local archive inspection and remote extraction reject absolute/path-traversal members, symlink/hardlink members and special members. The manifest is single-member, size-bounded and SHA-bound; the executor re-validates the exact payload file inventory and hashes.

### A2
All three runtime images are packaged before live execution. The live executor uses only `docker load --input`, validates exact image ID plus `arm64/linux`, and deletes each tar after successful load. No post-claim registry pull exists. Production Compose uses local image references and `pull_policy: never`.

### A3
The installer contract validates the minimal-host preflight before the authorization claim callback. The preflight is read-only and requires aarch64, Docker/Compose/NetworkManager/route/DNS/NTP readiness, capacity, zero containers/images/volumes/product networks/listeners/product paths, absent product units/firewall state, preserved SSH/default Docker networks and same-filesystem commit eligibility.

### A4
The durable marker is created with exclusive creation, no-follow where supported, mode 0600 and fsync before the claim event is emitted. Host-side post-start transport ambiguity now propagates as consumed/no-replay rather than being reset to preflight. Regression coverage and exact-head CI are green.

### A5
Fresh identity, Manager/N3-W state, Broker TLS/CA/service credentials and DynSec are created from an empty product baseline. Constructor containers use `--network none`. DynSec requires exactly the service identities/roles while node client/role counts remain zero. Final read-only audit again requires state, DynSec and credential node counts all equal zero.

### A6
Runtime staging creates only the declared product roots. Manager/N3-W writable state is owned by UID/GID 999, DynSec data and Broker server key by Broker UID/GID 1883, service secrets are mode-restricted, and the exact runtime source bundle plus fresh image-lock are staged into the canonical product locations.

### A7
Commit targets must still be absent immediately before commit. The minimal preflight proves the staging/target parents are on the same filesystem, and each committed path is recorded as transaction-owned. Any failure after mutation starts invokes cleanup; cleanup removes transaction-owned containers/networks/paths/images, daemon-reloads, and must re-prove the original minimal preflight. Failure to prove cleanup becomes recovery-required rather than success.

### A8
The stopped postcheck requires zero containers before the final isolated audit, exact three-image identity set, zero volumes, only default Docker networks, zero product listeners, no active product firewall, the ingress-guard unit loaded but inactive and not enabled, exact required product paths, forbidden activation/dispatcher paths absent, deployment gate PASS and zero node credentials. The final audit container is isolated with `--network none` and `--rm`.

### A9
No live bootstrap execution path starts/enables/restarts production services or runs `docker compose up`. Compose restart policies are `no`; Manager and Home Assistant remain behind the application profile. Activation/dispatcher/certificate-lifecycle paths remain explicitly absent at this stage.

### A10
The reviewed path contains no board/USB/serial/Flash/NVS/RF operation and no PR merge action. CI evidence confirms T1 access/live mutation/production service start/board access were false.

## Authorization ledger

```text
PROPOSED_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_01
GRANTED=false
CLAIMED=false
CONSUMED=false
REPLAY_STATE=NOT_APPLICABLE_NOT_GRANTED
```

The source/artifact PASS does not grant live apply authorization.

## Next stage

```text
NEXT_ONE_GATE=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_PREEXECUTION_READONLY
AUTO_EXECUTE_NEXT_GATE=false

LIVE_PREEXECUTION_MUTATION=false
NEW_AUTHORIZATION_REQUIRED_BEFORE_LIVE_APPLY=true
PR541_MERGE=false
```

The next gate may only freshly re-prove the real T1 minimal-host baseline and exact artifact eligibility. It must not apply the product or claim the future live authorization.
