# N3-W T1 S20 R5 real three-service secret handoff live authorization

Date: 2026-10-11

Status: GRANTED / NOT YET CLAIMED / NOT YET CONSUMED

PR: #541 OPEN DRAFT

## Authorization

```text
AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R5_20261011_01
GRANTED=true
CLAIMED=false
CONSUMED=false
REPLAY=false
```

The user explicitly granted this one-shot live mutation authorization after the R5 source/CI closure and fresh T1 read-only preclaim both passed.

## Bound source authority

```text
SOURCE_HEAD=1ecc12ded60c7ea53e0af94722a05f3b4f0e4654
EXECUTOR_SHA256=a83303191d54ba7c4c1f065a2de6abcb69a55a2eb10831da5ecb9a6e47c13b75
t1_clean_service_credential_bundle.py_SHA256=b7e42dd8f4c4a08f107c262ff4b5cf9b50b6b5e166f3ab852d6b32d513b0bc48
dynsec_api.py_SHA256=a8e29c0d7c83eeaf2dbb1ad3c119c890ea3eaaed71ad6568d6be86180c9c39f5
service_identity_plan.py_SHA256=7c66fb20d50859322598ad9e08ba0436d602b9ef36586895993e980090c0bac5
dynsec_plan.py_SHA256=2671fa7d0e3e79816fd2f3d09fa7586c3dbbbe3f08f0db8b829a72ccb19688b9
```

At grant time, comparison from the CI-bound source head to current PR head showed documentation-only delta; no executor, dependency, test, or workflow drift.

## Fresh read-only preclaim authority

The immediately preceding fresh T1 preclaim passed with:

```text
docker_container_count=0
docker_volume_count=45
docker_volume_set_sha256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
project_networks_empty=true
host_mqtt_listeners=0
guard_exact=true
broker_config_sha_match=true
broker_tls_path_contract_verified=true
broker_tls_server_name_verified=true
dynsec_baseline_exact=true
target_service_clients_absent=true
target_service_roles_absent=true
node_clients_absent=true
r1_r2_r3_r4_retained_snapshots_verified=true
r5_rollback_snapshot_absent=true
production_service_secret_destination_absent=true
authorization_claimed=false
authorization_consumed=false
```

Authority:
`docs/development/N3W_T1_S20_R5_FRESH_T1_READONLY_PRECLAIM_CLOSURE_20261011.md`.

## Mandatory execution rule

Immediately before claim, the exact CI-bound executor must re-run its own read-only preclaim. If that preclaim stops or differs, the authorization is not claimed and no live transaction may begin.

Only after that internal preclaim passes may the executor emit:

```text
AUTHORIZATION_CLAIMED=true
```

Invocation after claim consumes the one-shot authorization whether the transaction later succeeds or rolls back.

## Authorized live transaction

The authorization permits only the R5 transaction implemented by the exact bound executor:

- create the distinct R5 rollback snapshot;
- generate the three production service credential bundles;
- start only the isolated temporary Broker;
- apply exactly the provisioning, manager, and Home Assistant service roles/clients;
- verify positive credentials and wrong-client-id rejection;
- verify anonymous rejection over the repaired TLS transport;
- stop/remove the temporary Broker;
- preserve the production secret bundle on PASS;
- perform the exact postcheck.

The transaction Broker remains `--network none`, uses `armbian:8883` over container loopback with the exact CA, and uses `tmpfs` for `/mosquitto/log`.

## Explicitly not authorized

```text
production Broker start=false
production Manager start=false
production Home Assistant start=false
board access=false
R1/R2/R3/R4 replay=false
second R5 attempt=false
PR merge=false
```

If rollback is incomplete or postcheck fails after claim, stop for manual forensic/recovery; do not replay this authorization.
