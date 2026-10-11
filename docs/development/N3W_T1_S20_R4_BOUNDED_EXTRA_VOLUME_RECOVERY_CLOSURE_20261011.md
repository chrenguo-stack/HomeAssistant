# N3-W T1 S20 R4 bounded extra-volume recovery closure

Date: 2026-10-11

Status: CLOSED_PASS

PR: #541 OPEN DRAFT

## Authorization

```text
AUTHORIZATION=N3W_T1_S20_R4_BOUNDED_EXTRA_VOLUME_RECOVERY_20261011_01
GRANTED=true
CLAIMED=true
CONSUMED=true
SECOND_ATTEMPT_AUTHORIZED=false
```

The authorization was consumed by one exact Docker volume deletion attempt only.

## Pre-delete evidence

```text
CONTAINER_COUNT=0
VOLUME_COUNT=46
VOLUME_SET_SHA256=918671f58a589f5edfd47ecce0e5a7cde9f2b104a99e5b72bd79b4b20cee9999
CANDIDATE_CREATED_AT=2026-10-11T00:15:12+08:00
CANDIDATE_LABELS={"com.docker.volume.anonymous":""}
CANDIDATE_REFERENCE_COUNT=0
DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
BROKER_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
S18_SHA256=93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da
PRIVATE_NETWORK_CONTAINERS=0
SERVICES_NETWORK_CONTAINERS=0
GUARD_ACTIVE=active
GUARD_ENABLED=enabled
TCP1883=0
TCP8883=0
TCP18883=0
```

All R1-R4 retained DynSec snapshots matched the frozen baseline SHA and owner/mode `0:0:600`.

## Exact mutation

The sole mutation was:

```text
docker volume rm a16dba0851cd3fee17660cf65029622951c7b7d99cbe066b9d177605b62db2e7
```

Result:

```text
DELETE_RC=0
```

No second deletion attempt was made or authorized.

## Post-delete evidence

```text
CANDIDATE_PRESENT=false
CONTAINER_COUNT=0
VOLUME_COUNT=45
VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
BROKER_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
PRIVATE_NETWORK_CONTAINERS=0
SERVICES_NETWORK_CONTAINERS=0
GUARD_ACTIVE=active
GUARD_ENABLED=enabled
TCP1883=0
TCP8883=0
TCP18883=0
```

## Closure

```text
RECOVERY_RESULT=PASS
R4_VOLUME_DRIFT_RECOVERED=true
FROZEN_45_VOLUME_SET_RESTORED=true
AUTHORIZATION_CONSUMED=true
SECOND_ATTEMPT_AUTHORIZED=false
PRODUCTION_SERVICE_START=false
R5_APPLY=false
BOARD_ACCESS=false
PR_MERGE=false
```

The live T1 state is restored to the frozen pre-R4 Docker volume inventory and all checked security/runtime baselines remain unchanged.

## Remaining source defect

Recovery of the existing orphan does not prevent recurrence.

The exact Mosquitto image declares `/mosquitto/data` and `/mosquitto/log` as image volumes. The R4 transaction Broker explicitly bind-mounts `/mosquitto/data` but does not override `/mosquitto/log`. Docker therefore created an anonymous volume for `/mosquitto/log`.

Before any future live apply, source must explicitly make `/mosquitto/log` ephemeral without creating a Docker volume, and regression coverage must prove the transaction Broker lifecycle does not change the Docker volume set.

```text
NEXT_ONE_GATE=N3W_T1_S20_TRANSACTION_BROKER_LOG_VOLUME_LEAK_SOURCE_REPAIR_20261011_01
LIVE_T1_MUTATION=false
R5_APPLY=false
```
