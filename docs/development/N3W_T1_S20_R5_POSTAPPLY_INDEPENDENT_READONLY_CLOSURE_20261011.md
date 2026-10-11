# N3-W T1 S20 R5 post-apply independent read-only closure

Date: 2026-10-11

Status: CLOSED_PASS

PR: #541 OPEN DRAFT

## Gate

```text
GATE=N3W_T1_S20_R5_POSTAPPLY_INDEPENDENT_READONLY_CLOSURE_20261011_01
AUTHORIZATION=READ_ONLY
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
```

This audit was performed after the R5 transaction executor had exited. It did not reuse the transaction's success result as the only authority.

## Independent host result

```text
REMOTE_HOST=armbian
REMOTE_ARCH=aarch64
REMOTE_KERNEL=6.18.26-ophub
REMOTE_DOCKER=29.7.1
STATUS=PASS
```

## Docker / network / guard

```text
docker_container_count=0
docker_volume_count=45
docker_volume_set_sha256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
n3wfc4-private_container_count=0
n3wfc4-services_container_count=0
guard_active=true
guard_enabled=true
guard_input_first_jump=true
guard_docker_user_first_jump=true
guard_terminal_drop=true
host_listener_1883=0
host_listener_8883=0
host_listener_18883=0
```

The R4 anonymous-volume recurrence guard therefore remained effective across the successful R5 transaction.

## Production service identity state

```text
dynsec_sha256=95d99839ec9a6b8003e1375883a3f9263a92e0dbc49c8ca5478196027081a90a
service_client_count=3
service_role_count=3
node_client_created=false
credential_bundle_verified=true
bundle_service_count=3
bundle_node_credential_count=0
bundle_secret_values_included=false
```

The independent verifier confirmed the exact post-apply service-role/client contract and no pre-created node credential.

## Credential ownership

```text
manager=999:999:600
provisioning=999:999:600
homeassistant=0:0:600
homeassistant_bootstrap=0:0:600
```

The credential bundle remained internally self-consistent and no secret value was emitted by the audit.

## Home Assistant handoff state

```text
homeassistant_runtime_verified=false
```

This is expected at this boundary: Home Assistant has not yet been started. R5 proves creation and handoff material integrity, not live HA config-flow consumption.

## Retained rollback evidence

```text
r1_retained_snapshot_verified=true
r2_retained_snapshot_verified=true
r3_retained_snapshot_verified=true
r4_retained_snapshot_verified=true
r5_rollback_snapshot_verified=true
transaction_material_absent=true
```

## Broker image authority

```text
exact_broker_image_local_arm64=true
image_id=sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408
platform=linux/arm64
index_digest=sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408
arm64_manifest_digest=sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
```

## Authorization ledger

```text
AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R5_20261011_01
GRANTED=true
CLAIMED=true
CONSUMED=true
REPLAY=false
SECOND_ATTEMPT_AUTHORIZED=false
```

The R5 authorization is permanently consumed.

## Final S20 result

```text
S20_THREE_SERVICE_SECRET_HANDOFF=CLOSED_PASS
R5_TRANSACTION_APPLY=PASS
R5_EXECUTOR_POSTCHECK=PASS
R5_INDEPENDENT_POSTAPPLY_AUDIT=PASS
PRODUCTION_SERVICE_IDENTITIES=3
PRODUCTION_NODE_IDENTITIES=0
PRODUCTION_SECRET_BUNDLE=VERIFIED
PRODUCTION_BROKER_STARTED=false
PRODUCTION_MANAGER_STARTED=false
PRODUCTION_HOMEASSISTANT_STARTED=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

S20 is complete. The next stage must not replay R5. It may only prepare the production stack activation boundary from the already-created service identities and secret bundle.

```text
NEXT_ONE_GATE=N3W_T1_PRODUCTION_STACK_ACTIVATION_READONLY_PREEXECUTION_20261011_01
GATE_MODE=SOURCE_AND_T1_READ_ONLY
LIVE_RUNTIME_MUTATION=false
NEW_EXPLICIT_AUTHORIZATION_REQUIRED_FOR_ACTIVATION=true
```
