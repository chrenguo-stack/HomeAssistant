# N3-W T1 S20 R5 admin-readiness TLS transport source repair closure

Date: 2026-10-11

Status: CLOSED_PASS / LIVE_APPLY_NOT_AUTHORIZED

PR: #541 OPEN DRAFT

## 1. Scope

This closure covers only:

```text
N3W_T1_S20_R5_ADMIN_READINESS_TLS_TRANSPORT_SOURCE_REPAIR
```

It does not authorize a live R5 transaction.

## 2. Frozen R4 blocker

R4 proved the temporary Broker itself could start, but admin readiness never reached Dynamic Security mutation because the generated client config used plaintext loopback port 1883 while the exact frozen Broker config exposes TLS port 8883.

```text
R4_TEMP_BROKER_STARTUP=PASS
R4_ADMIN_READINESS=FAIL
R4_SERVICE_DYNSEC_MUTATION_REACHED=false
ROOT_CAUSE=ADMIN_CLIENT_CONFIG_HARDCODES_PLAINTEXT_127_0_0_1_1883_WHILE_EXACT_TEMP_BROKER_CONFIG_EXPOSES_TLS_8883_ONLY
```

## 3. R5 repaired transport

R5 transaction client configs now use:

```text
-h armbian
-p 8883
--cafile /mosquitto/config/n3w-ca.pem
-V 5
```

The transaction Broker keeps:

```text
--network none
--add-host armbian:127.0.0.1
--tmpfs /mosquitto/log
```

Therefore:

```text
TCP_DESTINATION=transaction-container-loopback
TLS_SERVER_NAME=armbian
CA_TRUST=exact-mounted-N3W-CA
PLAINTEXT_1883_LISTENER_ADDED=false
TLS_INSECURE=false
LAN_IP_DEPENDENCY=false
```

The anonymous negative probe now uses the same TLS transport so transport failure cannot be misclassified as anonymous-auth rejection.

## 4. Preclaim hardening

The source now verifies before any future claim:

- exact frozen Broker config SHA;
- exact TLS CA/cert/key paths;
- exactly one Broker listener and it is 8883;
- no plaintext 1883 listener;
- TLS file metadata;
- server certificate hostname matches `armbian`;
- exact frozen 45-volume set;
- zero containers and zero MQTT host listeners;
- empty project networks;
- ingress guard active/enabled;
- exact DynSec baseline;
- retained R1/R2/R3/R4 snapshots;
- R5 rollback snapshot absent.

## 5. Attempt isolation

```text
R1_AUTHORIZATION=CONSUMED_NO_REPLAY
R2_AUTHORIZATION=CONSUMED_NO_REPLAY
R3_AUTHORIZATION=CONSUMED_NO_REPLAY
R4_AUTHORIZATION=CONSUMED_NO_REPLAY

R4_RETAINED_SNAPSHOT=
/etc/n3wfc4/private/dynsec-s20-r4-pre-three-service.json

R5_PROSPECTIVE_AUTHORIZATION=
N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R5_20261011_01

R5_AUTHORIZATION_GRANTED=false
R5_AUTHORIZATION_CLAIMED=false
R5_AUTHORIZATION_CONSUMED=false

R5_ROLLBACK_SNAPSHOT=
/etc/n3wfc4/private/dynsec-s20-r5-pre-three-service.json
```

No R5 snapshot has been created by this source stage.

## 6. CI closure authority

Corrected workflow:

```text
WORKFLOW=N3W T1 S20 real service handoff CI
RUN_ID=38102338780
TRIGGER_HEAD=1ecc12ded60c7ea53e0af94722a05f3b4f0e4654
```

All three jobs passed.

### Source

```text
JOB=source
RESULT=success
RUFF=PASS
PYTEST=74 passed in 0.48s
```

### Docker volume lifecycle

```text
JOB=volume-lifecycle
RESULT=success
DATA_MOUNT=bind /mosquitto/data
LOG_TMPFS={"/mosquitto/log":""}
TRANSACTION_BROKER_VOLUME_SET_UNCHANGED=true
```

### TLS readiness

The isolated job used the exact Mosquitto source tag/index, throwaway DynSec admin state, a throwaway CA/server certificate whose SAN is `armbian`, and the R5 network/TLS shape.

```text
JOB=tls-readiness
RESULT=success
DYNSEC_LIST_CLIENTS_RESPONSE=admin
CONTAINER_HOST_ALIAS=127.0.0.1 armbian
R5_ADMIN_READINESS_TLS_TRANSPORT=PASS
TLS_SERVER_NAME_VERIFICATION=PASS
TRANSACTION_BROKER_VOLUME_SET_UNCHANGED=true
```

The job also required a connection configured as host `127.0.0.1` with the same CA to fail, proving hostname verification was not bypassed.

## 7. First fixture failure classification

The first TLS job failed before Broker start because the CI fixture changed `server.key` ownership to UID/GID 1883 and then attempted an unprivileged chmod.

That fixture was corrected to `sudo chmod 600`.

```text
FIRST_TLS_CI_FAILURE=FIXTURE_ONLY
PRODUCT_SOURCE_FAILURE_PROVEN=false
BROKER_STARTED_IN_FAILED_JOB=false
TLS_READINESS_REACHED_IN_FAILED_JOB=false
```

The corrected run above is closure authority.

## 8. Source drift review

The CI source/workflow trigger head is:

```text
1ecc12ded60c7ea53e0af94722a05f3b4f0e4654
```

At review, PR #541 head was:

```text
321f2906749e873bf94cfd948ac9a2dd1d0ed474
```

Exact compare:

```text
AHEAD_BY=5
BEHIND_BY=0
```

All post-CI deltas were documentation only:

```text
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/N3W_T1_S20_R5_ADMIN_READINESS_TLS_TRANSPORT_SOURCE_REPAIR_PROGRESS_20261011.md
```

Therefore there is no tested source/workflow drift.

## 9. Closure

```text
N3W_T1_S20_R5_ADMIN_READINESS_TLS_TRANSPORT_SOURCE_REPAIR=PASS
R5_SOURCE_TESTS=PASS_74
R5_VOLUME_LIFECYCLE=PASS
R5_ADMIN_READINESS_TLS_TRANSPORT=PASS
TLS_SERVER_NAME_VERIFICATION=PASS
PLAINTEXT_1883_LISTENER_ADDED=false
TLS_INSECURE=false
R4_VOLUME_GUARD_PRESERVED=true

LIVE_T1_MUTATION=false
R5_LIVE_APPLY=false
R5_AUTHORIZATION_GRANTED=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

## 10. Next gate

The next gate is a fresh read-only T1 preclaim using the exact CI-bound R5 executor.

```text
NEXT_ONE_GATE=N3W_T1_S20_R5_FRESH_T1_READONLY_PRECLAIM_20261011_01
AUTHORIZATION=NOT_REQUIRED_READONLY
LIVE_RUNTIME_MUTATION=false
AUTO_APPLY_AFTER_PRECLAIM=false
```

Only if that preclaim passes may the high-level model request a new explicit one-shot live mutation authorization for:

```text
N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R5_20261011_01
```
