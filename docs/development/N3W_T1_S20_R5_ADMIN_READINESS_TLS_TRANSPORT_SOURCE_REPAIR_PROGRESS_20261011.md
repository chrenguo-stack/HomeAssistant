# N3-W T1 S20 R5 admin-readiness TLS transport source repair progress

Date: 2026-10-11

Status: SOURCE_REPAIR_IMPLEMENTED / CI_RUNNING / LIVE_APPLY_NOT_AUTHORIZED

PR: #541 OPEN DRAFT

## 1. Entry authority

The user explicitly approved entering:

```text
N3W_T1_S20_R5_ADMIN_READINESS_TLS_TRANSPORT_SOURCE_REPAIR
```

This approval authorizes source/design/test work only.

It does **not** authorize any T1 live transaction, production Broker/Manager/Home Assistant start, DynSec mutation, service-secret generation, board access, or PR merge.

```text
R5_SOURCE_REPAIR_AUTHORIZED=true
R5_LIVE_APPLY_AUTHORIZED=false
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

## 2. Frozen root cause

R4 proved that the temporary Broker itself can start with the exact production config/TLS file mounts.

The remaining failure was admin readiness:

```text
R4_TEMP_BROKER_STARTUP=PASS
R4_ADMIN_READINESS=FAIL
R4_SERVICE_DYNSEC_MUTATION_REACHED=false
```

The R4 executor-generated client configs used:

```text
-h 127.0.0.1
-p 1883
```

while the exact frozen Broker config exposes the TLS listener on port 8883 only.

The production Broker certificate lifecycle authority also freezes the TLS server name as:

```text
armbian
```

Therefore the source repair must not add a plaintext listener and must not disable hostname verification.

## 3. R5 transport design

R5 client configs now use:

```text
-h armbian
-p 8883
--cafile /mosquitto/config/n3w-ca.pem
-V 5
```

The temporary Broker container continues to use:

```text
--network none
```

and adds the deterministic loopback-only name binding:

```text
--add-host armbian:127.0.0.1
```

This means:

```text
client connect host = armbian
TCP destination = transaction container loopback
TLS server-name verification = armbian
CA trust = exact mounted N3W CA
plaintext listener = not added
--insecure = forbidden/not used
host/LAN dependency = none
```

The existing R4 anonymous-volume recurrence repair remains unchanged:

```text
--tmpfs /mosquitto/log
```

## 4. Preclaim hardening

The R5 source now checks all of the following before a future claim:

- exact frozen Broker config SHA;
- exact TLS file paths in Broker config;
- exactly one Broker listener and it is port 8883;
- no plaintext 1883 listener in the frozen Broker config;
- TLS CA/certificate/key metadata contract;
- server certificate hostname contract for `armbian`;
- exact 45-volume baseline;
- zero containers / zero MQTT host listeners;
- empty project networks and active/enabled ingress guard;
- exact DynSec baseline;
- retained R1/R2/R3/R4 snapshots.

## 5. Attempt / rollback isolation

R1-R4 live authorizations remain consumed and non-replayable.

R5 source now defines a new prospective authorization id:

```text
R5_AUTHORIZATION_ID=
N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R5_20261011_01

R5_AUTHORIZATION_GRANTED=false
R5_AUTHORIZATION_CLAIMED=false
R5_AUTHORIZATION_CONSUMED=false
```

The R4 snapshot becomes retained immutable evidence:

```text
R4_EVIDENCE_SNAPSHOT=
/etc/n3wfc4/private/dynsec-s20-r4-pre-three-service.json
```

and a future R5 apply would create a distinct create-new-only rollback snapshot:

```text
R5_ROLLBACK_SNAPSHOT=
/etc/n3wfc4/private/dynsec-s20-r5-pre-three-service.json
```

No R5 snapshot has been created by this source-repair stage.

## 6. Negative authentication repair

The anonymous negative probe previously still used plaintext `127.0.0.1:1883`. That could produce a false PASS because transport failure is not proof that anonymous authentication is rejected.

R5 repairs that probe to use the same TLS transport contract:

```text
host=armbian
port=8883
cafile=/mosquitto/config/n3w-ca.pem
protocol=MQTT5
```

so a future anonymous rejection is an authentication/authorization result on the real transport path rather than an unrelated connection failure.

## 7. Source commits

```text
R5_TLS_SOURCE_REPAIR=
9b4cca92f4c7d003a3689f2ae0f1d2ced4ac3140

R5_TLS_SOURCE_TESTS=
dc5730f603e990211427df71ea4fdda5d1c2a015

R5_ROLLBACK_NAMING_ALIGNMENT=
67d794f517ccc8072997d8ad24b61c489efbdf46

R5_TLS_DOCKER_ISOLATED_CI=
97243608e1d66ad362d5dc7a59ff2050457d5aa9
```

## 8. Regression coverage

Focused source tests now guard:

- generated client config uses `armbian:8883` + exact CA;
- generated client config contains no `127.0.0.1:1883`;
- generated client config does not use `--insecure`;
- transaction Broker command contains `--add-host armbian:127.0.0.1`;
- R5 authorization and R1-R5 snapshot paths are attempt-scoped;
- Broker config rejects an additional plaintext 1883 listener;
- server-name preclaim verifies `armbian`;
- anonymous negative probe uses the same TLS transport.

The existing S20 workflow now also has an isolated `tls-readiness` job that uses the exact Mosquitto source tag/index, a throwaway CA/server certificate with SAN `armbian`, throwaway DynSec admin state, `--network none`, and `--add-host armbian:127.0.0.1`. It performs a real `mosquitto_rr listClients` over TLS and additionally proves that connecting as `127.0.0.1` with hostname verification fails.

## 9. CI

Current S20 workflow run:

```text
RUN_ID=38102267167
WORKFLOW=N3W T1 S20 real service handoff CI
SOURCE=RUNNING_AT_LAST_POLL
VOLUME_LIFECYCLE=RUNNING_AT_LAST_POLL
TLS_READINESS=QUEUED_AT_LAST_POLL
```

Run URL:

`https://github.com/chrenguo-stack/HomeAssistant/actions/runs/38102267167`

## 10. Current gate

```text
CURRENT_GATE=N3W_T1_S20_R5_ADMIN_READINESS_TLS_TRANSPORT_SOURCE_REPAIR
SOURCE_REPAIR_IMPLEMENTED=true
SOURCE_REVIEW_PENDING_CI=true
LIVE_T1_MUTATION=false
R5_LIVE_APPLY=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

The next transition after CI is source/CI review only. A future R5 live apply requires a separate fresh T1 read-only preclaim and a new explicit one-shot live mutation authorization.
