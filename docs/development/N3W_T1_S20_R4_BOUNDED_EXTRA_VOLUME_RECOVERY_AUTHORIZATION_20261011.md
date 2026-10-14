# N3-W T1 S20 R4 bounded extra-volume recovery authorization

Date: 2026-10-11

Status: AUTHORIZED / NOT YET CLAIMED / NOT YET CONSUMED

Repository: `chrenguo-stack/HomeAssistant`

PR: #541, OPEN DRAFT

## Authorization

```text
AUTHORIZATION=N3W_T1_S20_R4_BOUNDED_EXTRA_VOLUME_RECOVERY_20261011_01
GRANTED=true
CLAIMED=false
CONSUMED=false
SECOND_ATTEMPT_ALLOWED=false
```

User explicitly granted this authorization in chat on 2026-10-11.

## Exact mutation scope

Only the following proven R4 orphan volume may be deleted:

```text
VOLUME=a16dba0851cd3fee17660cf65029622951c7b7d99cbe066b9d177605b62db2e7
R4_TRANSACTION_PROVENANCE=true
DESTINATION=/mosquitto/log
CURRENT_CONTAINER_REFERENCE_COUNT=0
```

No other Docker volume, container, network, file, service, credential, firewall rule, board state, or repository merge is authorized for mutation.

## Mandatory pre-delete gate

Immediately before deletion, execution must prove all of the following:

```text
CONTAINER_COUNT=0
CURRENT_VOLUME_COUNT=46
CURRENT_VOLUME_SET_SHA256=918671f58a589f5edfd47ecce0e5a7cde9f2b104a99e5b72bd79b4b20cee9999
CANDIDATE_PRESENT=true
CANDIDATE_CREATED_AT=2026-10-11T00:15:12+08:00
CANDIDATE_LABELS={"com.docker.volume.anonymous":""}
CANDIDATE_CURRENT_CONTAINER_REFERENCE_COUNT=0
DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
BROKER_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
PROJECT_PRIVATE_NETWORK_CONTAINERS=0
PROJECT_SERVICES_NETWORK_CONTAINERS=0
GUARD_ACTIVE=active
GUARD_ENABLED=enabled
HOST_TCP1883_LISTENER_COUNT=0
HOST_TCP8883_LISTENER_COUNT=0
HOST_TCP18883_LISTENER_COUNT=0
PRODUCTION_SECRET_DESTINATION_PRESENT=false
TRANSACTION_DIRECTORY_PRESENT=false
```

The four frozen R1-R4 DynSec snapshots must also still equal the frozen DynSec baseline and remain owner/mode `0:0:600`.

If any precondition differs, stop without claiming or consuming this authorization.

## Authorized command

After all preconditions pass, the sole authorized mutation is:

```text
docker volume rm a16dba0851cd3fee17660cf65029622951c7b7d99cbe066b9d177605b62db2e7
```

Invocation consumes the authorization whether it succeeds or fails. No automatic or manual second deletion attempt is authorized by this grant.

## Mandatory postcheck

PASS requires:

```text
CANDIDATE_PRESENT=false
CONTAINER_COUNT=0
DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
DYNSEC_BASELINE_EXACT=true
BROKER_CONFIG_BASELINE_EXACT=true
PROJECT_NETWORKS_EMPTY=true
GUARD_ACTIVE=true
GUARD_ENABLED=true
HOST_MQTT_LISTENERS=0
PRODUCTION_SECRET_DESTINATION_PRESENT=false
TRANSACTION_DIRECTORY_PRESENT=false
```

## Explicitly forbidden

```text
docker volume prune
docker system prune
deleting any second volume
starting or restarting production Broker/Manager/Home Assistant
R1/R2/R3/R4 authorization replay
R5 apply
board/USB/serial/flash/NVS/RF access
PR #541 merge
```

Source attribution authority:
`docs/development/N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_CLOSURE_20261011.md`.
