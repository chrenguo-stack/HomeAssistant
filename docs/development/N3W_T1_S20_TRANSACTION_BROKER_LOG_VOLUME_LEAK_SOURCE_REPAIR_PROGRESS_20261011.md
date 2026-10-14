# N3-W T1 S20 transaction Broker log-volume leak source repair progress

Date: 2026-10-11

Status: SOURCE_REPAIR_IMPLEMENTED / CI_PENDING

PR: #541 OPEN DRAFT

## 1. Live recovery is closed

The bounded R4 orphan-volume recovery completed successfully.

```text
AUTHORIZATION=N3W_T1_S20_R4_BOUNDED_EXTRA_VOLUME_RECOVERY_20261011_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
DELETE_RC=0
RECOVERY_RESULT=PASS
R4_VOLUME_DRIFT_RECOVERED=true
CANDIDATE_PRESENT=false
CONTAINER_COUNT=0
VOLUME_COUNT=45
VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
SECOND_ATTEMPT_AUTHORIZED=false
```

DynSec, Broker config, retained snapshots, project networks, ingress guard, and MQTT host-listener baseline remained unchanged.

Authority:
`docs/development/N3W_T1_S20_R4_BOUNDED_EXTRA_VOLUME_RECOVERY_CLOSURE_20261011.md`.

## 2. Recurrence root cause

The exact Mosquitto image declares both:

```text
/mosquitto/data
/mosquitto/log
```

The S20 transaction Broker already overrides `/mosquitto/data` with the frozen host DynSec bind, but previously did not override `/mosquitto/log`.

R4 Docker events proved that Docker therefore created an anonymous volume for `/mosquitto/log`, mounted it into the transaction container, and left the volume behind after the container was destroyed.

Deleting that one orphan restored the live baseline but did not by itself prevent recurrence.

## 3. Source repair

The transaction Broker now explicitly overrides the image-declared log volume with container-lifetime tmpfs:

```text
docker run ...
  --network none
  --tmpfs /mosquitto/log
  ...
```

Source:

`host/greenhouse-manager/src/greenhouse_manager/ops/t1_s20_real_service_handoff.py`

New contract:

```text
BROKER_LOG_TARGET=/mosquitto/log
BROKER_LOG_BACKING=tmpfs
DOCKER_NAMED_OR_ANONYMOUS_LOG_VOLUME=false
PERSIST_AFTER_CONTAINER_DESTROY=false
```

The existing persistent DynSec bind at `/mosquitto/data` is unchanged. TLS/config/transaction mounts are unchanged. No readiness/TLS transport repair is included in this gate.

Source commit:

```text
ffec7df78ffff3f7505ca6580bda7a51f886c4a2
```

## 4. Source regression test

The focused S20 test now requires:

- the transaction Broker command contains exactly an explicit tmpfs target for `/mosquitto/log`;
- `/mosquitto/log` is not passed as a `-v` Docker volume/bind contract;
- the exact verified local Broker image ID remains the runtime image authority.

Test commit:

```text
2b161171693b89ad2e76bf6ff2e56be3a7cf3112
```

The pre-existing S20 focused source CI on the first repair head completed successfully.

## 5. Docker-isolated lifecycle proof

The existing workflow:

`.github/workflows/n3w-t1-s20-real-service-handoff-ci.yml`

now includes a `volume-lifecycle` job using the exact Mosquitto source tag and frozen OCI index digest.

The job:

1. captures Docker volume names before;
2. starts an isolated container with host bind at `/mosquitto/data` and tmpfs at `/mosquitto/log`;
3. verifies the data bind and Docker HostConfig tmpfs contract;
4. destroys the container;
5. compares the complete before/after Docker volume-name sets.

The first version of this CI check failed only because the fixture tried to find tmpfs in Docker `.Mounts`. Runtime output showed the data bind, while Docker records `--tmpfs` under `.HostConfig.Tmpfs`. No product/source defect was inferred from that fixture failure.

The CI fixture was corrected to read `.HostConfig.Tmpfs`.

Current workflow-fix HEAD:

```text
47337faa8da0b359af5631d7f9d3cec6fdd47505
```

Current S20 workflow run:

```text
RUN_ID=38101584262
STATUS=QUEUED_AT_LAST_ALLOWED_POLL
```

Run URL:

`https://github.com/chrenguo-stack/HomeAssistant/actions/runs/38101584262`

Per CI polling policy, no more polling is performed in this turn.

## 6. Current gate

```text
NEXT_ONE_GATE=N3W_T1_S20_TRANSACTION_BROKER_LOG_VOLUME_LEAK_SOURCE_REPAIR_CI_REVIEW
SOURCE_REPAIR_IMPLEMENTED=true
DOCKER_ISOLATED_PROOF_PENDING=true
LIVE_T1_MUTATION=false
PRODUCTION_SERVICE_START=false
R5_APPLY=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

Do not enter R5 until the corrected Docker-isolated lifecycle job and relevant source CI are reviewed and this source-repair gate is closed.
