# N3-W T1 S20 transaction Broker log-volume leak source repair closure

Date: 2026-10-11

Status: CLOSED_PASS

PR: #541 OPEN DRAFT

## 1. Scope

This closure covers only the R4 transaction-Broker Docker anonymous-volume recurrence caused by the exact Mosquitto image declaring `/mosquitto/log` while the executor did not explicitly override that path.

It does not repair or authorize the separate R4 admin-readiness transport mismatch. R5 is not entered by this closure.

## 2. Live recovery baseline

The already-authorized bounded R4 recovery completed before this source closure:

```text
RECOVERY_RESULT=PASS
R4_VOLUME_DRIFT_RECOVERED=true
CANDIDATE_PRESENT=false
CONTAINER_COUNT=0
VOLUME_COUNT=45
VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
BROKER_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
PROJECT_NETWORKS_EMPTY=true
GUARD_ACTIVE=true
GUARD_ENABLED=true
HOST_MQTT_LISTENERS=0
```

Authority:
`docs/development/N3W_T1_S20_R4_BOUNDED_EXTRA_VOLUME_RECOVERY_CLOSURE_20261011.md`.

## 3. Source repair

The transaction Broker command now explicitly uses:

```text
--tmpfs /mosquitto/log
```

Source:
`host/greenhouse-manager/src/greenhouse_manager/ops/t1_s20_real_service_handoff.py`

The existing host bind for `/mosquitto/data` remains unchanged.

Source repair commit:

```text
ffec7df78ffff3f7505ca6580bda7a51f886c4a2
```

Focused regression test commit:

```text
2b161171693b89ad2e76bf6ff2e56be3a7cf3112
```

Corrected Docker lifecycle workflow commit:

```text
47337faa8da0b359af5631d7f9d3cec6fdd47505
```

## 4. CI authority

Workflow:

```text
N3W T1 S20 real service handoff CI
RUN_ID=38101584262
```

Both jobs completed successfully.

### Source job

```text
JOB=source
RESULT=success
RUFF=PASS
PYTEST=70 passed in 0.52s
```

The focused source suite includes the S20 transaction Broker source contract and the existing credential/DynSec focused tests.

### Docker lifecycle job

```text
JOB=volume-lifecycle
RESULT=success
EXACT_SOURCE_TAG=m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine
EXACT_INDEX_DIGEST=sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408
DATA_MOUNT=bind /mosquitto/data
LOG_TMPFS={"/mosquitto/log":""}
TRANSACTION_BROKER_VOLUME_SET_UNCHANGED=true
```

The lifecycle proof records the Docker volume-name set before the isolated transaction container, starts the exact Mosquitto image with the repaired `/mosquitto/log` tmpfs contract, destroys the container, then compares the complete volume-name set after. The before/after sets were identical.

The earlier failed fixture is not product evidence: it looked for tmpfs in Docker `.Mounts`; the corrected fixture reads `.HostConfig.Tmpfs`, where Docker records the `--tmpfs` contract. The corrected run above is the closure authority.

## 5. Source drift review

The corrected CI tested source/workflow head:

```text
47337faa8da0b359af5631d7f9d3cec6fdd47505
```

At the CI review point, PR #541 head was:

```text
b56b588583bda4b4a8e72360254f98753177af9c
```

The exact compare was:

```text
AHEAD_BY=4
BEHIND_BY=0
```

and every delta after the tested head was documentation only:

```text
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/N3W_T1_S20_TRANSACTION_BROKER_LOG_VOLUME_LEAK_SOURCE_REPAIR_PROGRESS_20261011.md
```

Therefore the tested source and workflow remained exact at the review point.

## 6. Closure result

```text
N3W_T1_S20_TRANSACTION_BROKER_LOG_VOLUME_LEAK_SOURCE_REPAIR=PASS
R4_ORPHAN_VOLUME_LIVE_RECOVERY=PASS
ANONYMOUS_LOG_VOLUME_RECURRENCE_PREVENTED=true
TRANSACTION_BROKER_LOG_BACKING=tmpfs
DOCKER_VOLUME_SET_LIFECYCLE_REGRESSION=PASS
SOURCE_FOCUSED_TESTS=PASS
LIVE_T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

## 7. Known-failure numbering correction

The current repository already uses `KF-102` for the S19 isolated DynSec MQTT acceptance harness identity mistake. That authority must not be overwritten.

The later R4 temporary-Broker readiness/rollback issue had been provisionally referred to as `KF-102` in newer handoff/progress notes. Current authority corrects that numbering collision:

```text
KF-102=S19 isolated DynSec MQTT acceptance harness identity mistake
KF-103=S20 R4 temporary Broker readiness/rollback transaction harness
```

Within KF-103:

```text
ANONYMOUS_LOG_VOLUME_SUBISSUE=GUARDED
ADMIN_READINESS_TLS_TRANSPORT_SUBISSUE=OPEN
```

## 8. Stop before R5

The remaining R4 blocker is the separate admin-readiness transport mismatch: the executor client config still targets plaintext `127.0.0.1:1883`, while the exact Broker config exposes TLS listener `8883`.

This closure does not modify that transport contract.

```text
R5_APPLY=false
AUTO_ENTER_R5=false
NEXT_STAGE_REQUIRES_EXPLICIT_USER_DIRECTION=true
STOP_BEFORE_R5=true
```
