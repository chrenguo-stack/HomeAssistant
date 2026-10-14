# N3-W T1 per-device fresh Armbian automated deployment — F3 preauth preparation

Date: 2026-10-14

```text
GATE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_PREAUTH_PREPARATION_20261014_01
RESULT=CLOSED_PASS_REPOSITORY_PREPARATION

REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=0030585ad88d75b399b56849dafc235429bb3299
PR542_MERGE=0030585ad88d75b399b56849dafc235429bb3299
F2_LIVE_ACCEPTED_SOURCE=33bf71de0cf35984af74e1614aca72a893890b38
F2_STATUS=CLOSED_PASS

F3_ARTIFACT_SOURCE_HEAD=3e05e82a7d7e871d2966e78e8cb5caff601a0152
F3_ARTIFACT_RUN_ID=38536117520
F3_ARTIFACT_ID=11880082975
F3_ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-3e05e82a7d7e871d2966e78e8cb5caff601a0152
F3_ARTIFACT_DIGEST=sha256:de6228bd453b0c9de31cb80778b9b50e6df8620a4c2131dcebd8fa3ff29c1f97
F3_ARTIFACT_SIZE_BYTES=2535580472
F3_ARTIFACT_EXPIRED=false
F3_ARTIFACT_EXPIRES_AT=2026-11-13T08:39:38Z
RUNTIME_PAYLOAD_SHA256=747f1c58314d10bba5e51bf3c26cb4621158a06f2f82e912511b10bbce09f752
PAYLOAD_MANIFEST_SHA256=7a20577dfe1ee61902d92441bcebc73d744cf038775993ee61e1ab05dc43b9d0

F3_AUTHORIZATION_ID=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_20261014_01
F3_AUTHORIZATION_GRANTED=false
F3_AUTHORIZATION_CLAIMED=false
F3_AUTHORIZATION_CONSUMED=false

T1_ACCESS=false
T1_FILE_WRITE=false
PACKAGE_INDEX_REFRESH=false
PACKAGE_INSTALL=false
DOCKER_MUTATION=false
PRODUCT_DEPLOYMENT=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

## 1. Repository and artifact rebind

The F3-critical installer/transport/product-runtime source carried by the exact deployable artifact remains source-equivalent to current main for this gate.

Fresh compare from artifact source `3e05e82a...` to current main `0030585a...` shows only the already-accepted PR #542 F2 execution package, F2 workflow and F2 documentation were added. No F3 bootstrap, transport, provisioning, production runtime or activation source changed after the artifact was built.

The artifact is still present and unexpired. Its workflow completed successfully and the post-upload inner binding recorded:

```text
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS
RUNTIME_PAYLOAD_SHA256=747f1c58314d10bba5e51bf3c26cb4621158a06f2f82e912511b10bbce09f752
PAYLOAD_MANIFEST_SHA256=7a20577dfe1ee61902d92441bcebc73d744cf038775993ee61e1ab05dc43b9d0
```

Therefore no rebuild is required merely because PR #542 was merged.

## 2. F3 execution is two bounded live substeps

F3 must not be declared complete after the host wrapper's `apply` returns PASS.

### F3-A — public product staging

The exact host wrapper performs, after a fresh read-only preclaim and explicit authorization:

```text
exact artifact verification
→ bounded runtime payload staging
→ durable one-shot authorization claim
→ install Docker/Compose if the fresh host still lacks them
→ one-image-at-a-time exact load: Home Assistant → Manager → Broker
→ install public product source/config/helpers/systemd material
→ enable only ingress guard + provisioning-resume units
→ stopped-boundary postcheck
```

Expected successful F3-A state:

```text
PUBLIC_PRODUCT_STAGED=true
INSTANCE_MATERIAL_ABSENT=true
EXPLICIT_PROVISIONING_REQUIRED=true
PRODUCTION_SERVICE_START=false
ACTIVATION_AUTHORIZED=false
```

### F3-B — explicit per-device provisioning

After F3-A PASS, the same F3 authorization scope continues to the already-installed explicit provisioning entry point:

```text
sudo n3w-t1-provision start --confirm "START DEVICE PROVISIONING: YES"
sudo n3w-t1-provision verify
```

This creates and verifies the per-device SYSTEM_ID / Manager identity, fresh Manager state, Broker CA/TLS/service credentials, DynSec and instance runtime while preserving the stopped production boundary.

F3 is PASS only when both F3-A and F3-B complete and the final stopped-boundary verification passes.

A successful F3 does not authorize F4. Broker/Manager/Home Assistant production activation remains a separate gate with a separate live authorization.

## 3. Mutation and authorization boundary

The exact authorization bound into the artifact is:

```text
N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_20261014_01
```

The authorization is not granted by this document.

Before any F3 live mutation, a fresh target read-only preclaim must pass against the exact artifact and current target. The preclaim does not transfer the payload, does not install Docker, does not refresh APT indexes and does not claim/consume the authorization.

After explicit F3 authorization is granted, the host wrapper may make a bounded `/var/tmp` staging write before the durable claim. The durable claim occurs before Docker/package/product mutation. Once claim state is present or uncertain after the claim boundary, the authorization is treated as consumed and replay is forbidden.

## 4. Rollback and failure semantics

F3 cleanup is transaction-owned; it must never delete unrelated target state.

Important boundary:

- if Docker/Compose installation is required and succeeds, then a later product-staging failure may clean the product transaction while leaving Docker/Compose installed;
- therefore rollback after such a failure may end at a **Docker-ready minimal host**, not the byte-for-byte original F2 host;
- that state must not be falsely described as full rollback to the pre-F3 fresh host.

If F3-A succeeds and explicit provisioning later stops/fails:

- do not rerun host-wrapper `apply`;
- the F3 authorization is already consumed;
- inspect `n3w-t1-provision status`;
- preserve the durable provisioning transaction;
- only use source-defined resume/rollback after a new high-level review and, where required, a new authorization.

No automatic retry is allowed after an ambiguous or post-claim failure.

## 5. F3 hard scope

Allowed after a future explicit F3 authorization:

```text
- exact F3 host-wrapper apply
- apt-get update only when Docker baseline install is required
- exact-version docker.io + docker-compose-v2 installation
- Docker enable/start
- exact one-image-at-a-time image loading
- public product staging
- ingress guard + provisioning-resume enablement
- explicit n3w-t1-provision start/verify
- transaction-owned cleanup / source-defined recovery
```

Forbidden throughout F3:

```text
- start/enable Broker production activation
- start/enable Manager/Home Assistant production activation
- enable broker certificate lifecycle production timer
- run the F4 production activation helper
- board/USB/serial/Flash/NVS/RF access
- Golden Master/R2C/Seal/disk-capture/clone route
- reuse any consumed historical authorization
- untracked manual target patch presented as a repair
```

## 6. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_FRESH_READONLY_PRECLAIM_20261014_01

PURPOSE=
Freshly prove the current T1 still matches the exact F3 artifact and capacity/baseline assumptions immediately before requesting the one-shot F3 live authorization.

T1_ACCESS=true:READONLY_ONLY
T1_FILE_WRITE=false
PAYLOAD_TRANSFER=false
APT_UPDATE=false
PACKAGE_INSTALL=false
DOCKER_MUTATION=false
PRODUCT_DEPLOYMENT=false
AUTHORIZATION_CLAIM=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

PASS_IF=
EXACT_ARTIFACT_BINDING_PASS
AND HOST_PRECLAIM_PASS
AND CAPACITY_ADMISSION_PASS
AND AUTHORIZATION_CLAIMED=false
AND LIVE_MUTATION=false

STOP_BOUNDARY=
After preclaim result classification. Do not execute apply and do not claim authorization.

AUTO_EXECUTE_NEXT_GATE=false
```

The private target SSH locator remains operator-managed and must not be committed to public GitHub.

## 7. Preclaim command authority

Run from the repository at exact current main `0030585ad88d75b399b56849dafc235429bb3299`, using the operator-managed T1 SSH alias:

```text
python3 tools/n3w_t1_fresh_product_staging_host.py \
  --t1 '<T1_SSH_ALIAS>' \
  --phase preflight \
  --run-id '38536117520' \
  --artifact-name 'n3w-t1-fresh-bootstrap-deployable-3e05e82a7d7e871d2966e78e8cb5caff601a0152' \
  --artifact-id '11880082975' \
  --artifact-zip-sha256 'de6228bd453b0c9de31cb80778b9b50e6df8620a4c2131dcebd8fa3ff29c1f97' \
  --archive-sha256 '747f1c58314d10bba5e51bf3c26cb4621158a06f2f82e912511b10bbce09f752' \
  --manifest-sha256 '7a20577dfe1ee61902d92441bcebc73d744cf038775993ee61e1ab05dc43b9d0'
```

Do not add `--authorization-id` in preflight mode.

## 8. Preparation closure

```text
=== N3W_T1_F3_PREAUTH_PREPARATION_CLOSURE ===

MAIN=0030585ad88d75b399b56849dafc235429bb3299
F2_CLOSED_PASS=true
F3_ARTIFACT_EXACT_BINDING=PASS
F3_ARTIFACT_SOURCE_EQUIVALENT_TO_MAIN_FOR_F3_CRITICAL_SOURCE=true
F3_TWO_SUBSTEP_MODEL_FROZEN=true
F4_ACTIVATION_SEPARATE=true

PRIVATE_TARGET_PRECLAIM=NOT_EXECUTED
F3_AUTHORIZATION_GRANTED=false
F3_AUTHORIZATION_CLAIMED=false
F3_AUTHORIZATION_CONSUMED=false

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

RESULT=CLOSED_PASS_REPOSITORY_PREPARATION
NEXT_ROUTE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_FRESH_READONLY_PRECLAIM_20261014_01
STOP=true

=== END ===
```
