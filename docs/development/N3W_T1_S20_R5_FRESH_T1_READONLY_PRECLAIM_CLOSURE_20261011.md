# N3-W T1 S20 R5 fresh T1 read-only preclaim closure

Date: 2026-10-11

Status: CLOSED_PASS / LIVE_APPLY_NOT_AUTHORIZED

PR: #541 OPEN DRAFT

## 1. Gate

```text
GATE=N3W_T1_S20_R5_FRESH_T1_READONLY_PRECLAIM_20261011_01
AUTHORIZATION=NOT_REQUIRED_READONLY
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
```

The gate used the exact CI-bound R5 executor and its four frozen Python dependencies streamed into T1 memory. No repository checkout, Python source file, bytecode, snapshot, service credential, Broker container, DynSec mutation, or production service was created by this gate.

## 2. Remote host identity

```text
REMOTE_HOST=armbian
REMOTE_ARCH=aarch64
REMOTE_KERNEL=6.18.26-ophub
REMOTE_DOCKER=29.7.1
REMOTE_PREFLIGHT=PASS
```

## 3. Exact source binding

```text
SOURCE_HEAD=1ecc12ded60c7ea53e0af94722a05f3b4f0e4654
EXECUTOR_SHA256=a83303191d54ba7c4c1f065a2de6abcb69a55a2eb10831da5ecb9a6e47c13b75
t1_clean_service_credential_bundle.py_SHA256=b7e42dd8f4c4a08f107c262ff4b5cf9b50b6b5e166f3ab852d6b32d513b0bc48
dynsec_api.py_SHA256=a8e29c0d7c83eeaf2dbb1ad3c119c890ea3eaaed71ad6568d6be86180c9c39f5
service_identity_plan.py_SHA256=7c66fb20d50859322598ad9e08ba0436d602b9ef36586895993e980090c0bac5
dynsec_plan.py_SHA256=2671fa7d0e3e79816fd2f3d09fa7586c3dbbbe3f08f0db8b829a72ccb19688b9
```

The executor reported:

```text
executor_bound=true
source_dependencies_bound=true
```

## 4. Runtime baseline

```text
docker_container_count=0
docker_volume_count=45
docker_volume_set_sha256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b

project_network_container_counts:
  n3wfc4-private=0
  n3wfc4-services=0

guard.active=true
guard.enabled=true
guard.input_first_jump=true
guard.docker_user_first_jump=true
guard.terminal_drop=true

host_listener_counts:
  1883=0
  8883=0
  18883=0
```

The R4 orphan-volume recovery baseline therefore remains exact.

## 5. Broker / TLS contract

```text
broker_config_sha_match=true
broker_tls_path_contract_verified=true
tls_file_bind_contract_verified=true
broker_tls_server_name_verified=true
```

Exact local Broker image:

```text
image_id=sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408
platform=linux/arm64
index_digest=sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408
arm64_manifest_digest=sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
```

## 6. DynSec and retained evidence

```text
dynsec_sha_match=true
s18_backup_sha_match=true

dynsec_inventory.client_count=1
dynsec_inventory.target_service_clients_absent=true
dynsec_inventory.target_service_roles_absent=true
dynsec_inventory.node_clients_absent=true
dynsec_inventory.default_acl_baseline=true

r1_retained_snapshot_verified=true
r2_retained_snapshot_verified=true
r3_retained_snapshot_verified=true
r4_retained_snapshot_verified=true

rollback_snapshot_absent=true
r5_rollback_snapshot_absent=true
```

## 7. Secret-state precondition

```text
secret_destination_absent=true
secret_parent_state=absent
```

No production three-service secret bundle exists yet.

## 8. Closure

```text
R5_FRESH_T1_READONLY_PRECLAIM=PASS
R5_PRECLAIM_STATUS=PASS
R5_PRECLAIM_AUTHORIZATION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R5_20261011_01

LIVE_MUTATION=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_ACCESS=false
```

The prior import-transport stop is superseded by this successful memory-only streamed dependency bundle execution.

## 9. Live apply boundary

The successful read-only preclaim does not itself grant live mutation.

A separate explicit one-shot user authorization is still required:

```text
PROPOSED_AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R5_20261011_01
GRANTED=false
CLAIMED=false
CONSUMED=false
REPLAY=false
```

If later granted, execution must fresh-rebind the exact source and immediately re-run the read-only preclaim before claim. Any drift stops before claim.

The R5 apply transaction may then create the new R5 rollback snapshot, generate the three production service credential bundles, start only the isolated temporary Broker, apply/verify the three service identities, stop the temporary Broker, and perform exact postcheck.

Production Broker/Manager/Home Assistant startup, board access, and PR merge remain outside this authorization.
