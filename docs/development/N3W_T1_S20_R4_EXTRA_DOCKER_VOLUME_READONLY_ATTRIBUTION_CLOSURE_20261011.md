# N3-W T1 S20 R4 extra Docker volume readonly attribution closure

Date: 2026-10-11

Status: CLOSED_PASS / EXACT_R4_PROVENANCE / DELETION_NOT_AUTHORIZED

Repository: `chrenguo-stack/HomeAssistant`

PR: #541, OPEN DRAFT

Merge: FORBIDDEN

Board access: false

## 1. Gate

```text
EXECUTION_ID=N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_20261011_01
AUTHORIZATION=NOT_REQUIRED_READONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
```

This gate was strictly read-only. No Docker volume was deleted, no container was started, no production service was started, and no board was accessed.

## 2. Fresh baseline

Fresh T1 read-only evidence immediately before attribution:

```text
HOST=armbian
ARCH=aarch64
CONTAINER_COUNT=0
VOLUME_COUNT=46
VOLUME_SET_SHA256=918671f58a589f5edfd47ecce0e5a7cde9f2b104a99e5b72bd79b4b20cee9999

DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
BROKER_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6

GUARD_ACTIVE=active
GUARD_ENABLED=enabled
PROJECT_PRIVATE_NETWORK_CONTAINERS=0
PROJECT_SERVICES_NETWORK_CONTAINERS=0
```

This matches the known R4 post-failure baseline: product/security state restored, with the single known residual being 45 -> 46 Docker volumes.

## 3. Exact extra-volume identity

Exactly one current volume was created during the R4 transaction window:

```text
EXTRA_VOLUME_IDENTITY=a16dba0851cd3fee17660cf65029622951c7b7d99cbe066b9d177605b62db2e7
CREATED_AT=2026-10-11T00:15:12+08:00
DRIVER=local
SCOPE=local
LABEL=com.docker.volume.anonymous
```

All other current volumes predate R4.

## 4. Exact R4 provenance

Docker volume events directly bind the candidate to the R4 temporary Broker container:

```text
1791648912 create  a16dba0851cd3fee17660cf65029622951c7b7d99cbe066b9d177605b62db2e7
1791648912 mount   a16dba0851cd3fee17660cf65029622951c7b7d99cbe066b9d177605b62db2e7
                   container=0c8b4bb8787d7c02cffe0e301eb0a17299f91aac2fc75e8f1f83d46950bd7911
                   destination=/mosquitto/log
1791648934 unmount a16dba0851cd3fee17660cf65029622951c7b7d99cbe066b9d177605b62db2e7
                   container=0c8b4bb8787d7c02cffe0e301eb0a17299f91aac2fc75e8f1f83d46950bd7911
```

The R4 container event stream identifies the same container ID as the transaction container lifecycle:

```text
1791648912 create
1791648912 start
repeated mosquitto_rr readiness execs
1791648933 kill
1791648934 die
1791648934 destroy
```

The exact Mosquitto image declares:

```text
Config.Volumes={
  /mosquitto/data,
  /mosquitto/log
}
```

The R4 executor explicitly bind-mounts the host DynSec data directory to `/mosquitto/data` but does not supply a mount for `/mosquitto/log`. Docker therefore created the anonymous `/mosquitto/log` volume. The runtime event stream directly proves this relation; it is no longer inference.

## 5. Current references

Fresh final read-only evidence:

```text
CONTAINER_COUNT=0
VOLUME_COUNT=46
```

Therefore no current container can reference the candidate volume.

```text
CURRENT_CONTAINER_REFERENCE_COUNT=0
```

## 6. Closure

```text
R4_EXTRA_DOCKER_VOLUME_ATTRIBUTION=PASS
EXTRA_VOLUME_IDENTITY=a16dba0851cd3fee17660cf65029622951c7b7d99cbe066b9d177605b62db2e7
EXTRA_VOLUME_DESTINATION=/mosquitto/log
R4_TRANSACTION_PROVENANCE=true
CURRENT_CONTAINER_REFERENCE_COUNT=0

SAFE_DELETION_NOT_YET_AUTHORIZED=true
READY_FOR_BOUNDED_VOLUME_RECOVERY_AUTHORIZATION=true

LIVE_RUNTIME_MUTATION=false
VOLUME_DELETE=false
BOARD_ACCESS=false
STOP=true
```

The previous attribution blocker is closed. The remaining manual-recovery action is a separately authorized deletion of exactly this one proven R4-created orphan volume, followed by an exact postcheck restoring the frozen 45-volume set.

## 7. Next stage

```text
NEXT_STAGE=N3W_T1_S20_R4_BOUNDED_EXTRA_VOLUME_RECOVERY_AUTHORIZATION_DESIGN
PROPOSED_AUTHORIZATION=N3W_T1_S20_R4_BOUNDED_EXTRA_VOLUME_RECOVERY_20261011_01
GRANTED=false
AUTO_EXECUTE=false
SECOND_ATTEMPT_ALLOWED=false
```

The bounded recovery must re-prove immediately before deletion:

- current volume count = 46;
- current volume set SHA256 = `918671f58a589f5edfd47ecce0e5a7cde9f2b104a99e5b72bd79b4b20cee9999`;
- exact candidate exists with the same anonymous-volume metadata;
- no containers exist;
- candidate has no current container references;
- DynSec / Broker config / snapshots / networks / guard remain at the frozen baseline.

Authorized mutation, if separately approved, is limited to:

```text
docker volume rm a16dba0851cd3fee17660cf65029622951c7b7d99cbe066b9d177605b62db2e7
```

PASS after deletion requires:

```text
DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
CONTAINER_COUNT=0
HOST_MQTT_LISTENERS=0
DYNSEC_BASELINE_EXACT=true
BROKER_CONFIG_BASELINE_EXACT=true
PROJECT_NETWORKS_EMPTY=true
GUARD_ACTIVE=true
GUARD_ENABLED=true
PRODUCTION_SECRET_DESTINATION_PRESENT=false
TRANSACTION_DIRECTORY_PRESENT=false
```

No production Broker/Manager/Home Assistant start, no R5 apply, no board access, and no PR merge are authorized by this closure.
