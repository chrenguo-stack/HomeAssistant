# N3-W T1 S20 R4 readiness failure and rollback volume drift progress alignment

Date: 2026-10-11

Status: R4_APPLY_FAIL / PRODUCT_STATE_RESTORED_EXCEPT_DOCKER_VOLUME_SET / READINESS_ROOT_CAUSE_CONFIRMED / MANUAL_RECOVERY_GATE_REQUIRED

Repository: `chrenguo-stack/HomeAssistant`

PR: #541, OPEN DRAFT

Merge: FORBIDDEN

Board access: false

## 1. R4 transaction result

```text
AUTHORIZATION_ID=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R4_20261010_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY=false

S20_APPLY_R4=FAIL
EXECUTOR_RESULT=rollback_incomplete_manual_recovery_required
```

The authorization is permanently consumed. It must never be replayed.

## 2. What R4 fixed successfully

R4 repaired the previous Broker-startup path mismatch.

Fresh Docker event evidence proves the temporary Broker:

```text
create
start
<remained alive while readiness probes executed>
kill
die exitCode=137
destroy
```

Unlike R1/R2/R3, the Broker did not fail immediately during startup.

Therefore:

```text
R4_TEMP_BROKER_STARTUP=PASS
R3_TLS_TARGET_PATH_BLOCKER=CLOSED
```

The container lifetime was approximately 21 seconds, covering the readiness retry window.

## 3. Exact R4 failure point

Every in-container execution event before rollback was the same command shape:

```text
mosquitto_rr
-o /run/n3w-s20/admin.conf
-q 1
-W 3
-t $CONTROL/dynamic-security/v1
-e $CONTROL/dynamic-security/v1/response
-s
```

Every such execution returned:

```text
exitCode=1
```

No `createRole`, `createClient`, service positive-authentication, wrong-client-ID, or anonymous-test command was reached.

The executor's generated client config freezes:

```text
-h 127.0.0.1
-p 1883
-V 5
```

The exact live Broker config authority is:

```text
/etc/n3wfc4/mosquitto.conf
SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
```

and contains only:

```text
listener 8883 0.0.0.0
cafile /mosquitto/config/n3w-ca.pem
certfile /mosquitto/config/n3w-server.pem
keyfile /mosquitto/config/n3w-server.key
tls_version tlsv1.2
```

It does not expose listener 1883.

Therefore the R4 readiness probe is deterministically aimed at a nonexistent plain MQTT listener.

Classification:

```text
R4_ROOT_CLASS=S20_EXECUTOR_ADMIN_READINESS_TRANSPORT_CONTRACT_DRIFT
R4_ROOT_CAUSE=ADMIN_CLIENT_CONFIG_HARDCODES_PLAINTEXT_127_0_0_1_1883_WHILE_EXACT_TEMP_BROKER_CONFIG_EXPOSES_TLS_8883_ONLY
R4_ROOT_CAUSE_STATUS=CONFIRMED
SERVICE_DYNSEC_MUTATION_REACHED=false
```

Future repair must derive or explicitly bind the admin readiness transport to the exact live Broker config, including TLS/CA/server-name semantics where required. It must not add an unproven plaintext 1883 listener merely to make the harness pass.

## 4. R4 rollback external forensic

Independent read-only evidence after executor returned rollback incomplete:

```text
DOCKER_CONTAINER_COUNT=0
TRANSACTION_CONTAINER_PRESENT=false

HOST_TCP1883_LISTENER_COUNT=0
HOST_TCP8883_LISTENER_COUNT=0
HOST_TCP18883_LISTENER_COUNT=0

REAL_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
REAL_DYNSEC_BASELINE_EXACT=true
REAL_DYNSEC_STAT=1883:1883:600

ROLLBACK_TMP_PRESENT=false

R1_SNAPSHOT_BASELINE_EXACT=true
R2_SNAPSHOT_BASELINE_EXACT=true
R3_SNAPSHOT_BASELINE_EXACT=true
R4_SNAPSHOT_BASELINE_EXACT=true
R1_R2_R3_R4_SNAPSHOT_MODE=0:0:600

BROKER_CONFIG_BASELINE_EXACT=true
S18_BACKUP_BASELINE_EXACT=true

PRODUCTION_SECRET_DESTINATION_PRESENT=false
PRODUCTION_SECRET_PARENT_PRESENT=false
TRANSACTION_DIRECTORY_PRESENT=false

DYNSEC_CLIENT_COUNT=1
DYNSEC_ROLE_COUNT=1
DYNSEC_ADMIN_ONLY=true
TARGET_SERVICE_CLIENTS_PRESENT_COUNT=0
TARGET_SERVICE_ROLES_PRESENT_COUNT=0
NODE_CLIENTS_PRESENT=false

NETWORK_n3wfc4-private_CONTAINER_COUNT=0
NETWORK_n3wfc4-services_CONTAINER_COUNT=0

GUARD_ACTIVE=active
GUARD_ENABLED=enabled
```

Thus the product/security state targeted by the transaction has returned to the exact pre-R4 baseline.

## 5. Why executor classified rollback incomplete

The one remaining mismatch is Docker volume inventory:

Pre-R4 frozen baseline:

```text
DOCKER_VOLUME_COUNT=45
DOCKER_VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
```

Post-R4 external forensic:

```text
DOCKER_VOLUME_COUNT=46
DOCKER_VOLUME_SET_SHA256=918671f58a589f5edfd47ecce0e5a7cde9f2b104a99e5b72bd79b4b20cee9999
DOCKER_VOLUME_SET_BASELINE_EXACT=false
```

The rollback implementation checks container inventory first, then Docker volume count/set before later guards. Because container count was already zero and the volume count/set had drifted, the exact rollback failure point is:

```text
rollback_postcheck_volume_set_drift
```

Therefore:

```text
R4_DYNSEC_ROLLBACK=PASS
R4_SECRET_CLEANUP=PASS
R4_CONTAINER_CLEANUP=PASS
R4_LISTENER_CLEANUP=PASS
R4_NETWORK_CLEANUP=PASS
R4_DOCKER_VOLUME_SET_RESTORE=FAIL

S20_APPLY_R4_ROLLBACK=CLOSED_PARTIAL
MANUAL_RECOVERY_REQUIRED=true
```

Do not call this a full rollback CLOSED_PASS until the extra volume is identified, proven transaction-created, removed under a new bounded authorization if necessary, and the exact 45-volume baseline is re-established.

## 6. Current live safety status

Current directly proven host state:

```text
PRODUCTION_BROKER_STARTED=false
PRODUCTION_MANAGER_STARTED=false
PRODUCTION_HOMEASSISTANT_STARTED=false

TEMP_TRANSACTION_CONTAINER_PRESENT=false
MQTT_HOST_LISTENERS_PRESENT=false

REAL_DYNSEC_BASELINE_EXACT=true
PRODUCTION_SERVICE_CLIENTS_PRESENT=false
PRODUCTION_SERVICE_ROLES_PRESENT=false
NODE_CLIENTS_PRESENT=false

PRODUCTION_SECRET_DESTINATION_PRESENT=false
PRODUCTION_SECRET_PARENT_PRESENT=false
TRANSACTION_DIRECTORY_PRESENT=false

PROJECT_NETWORKS_EMPTY=true
INGRESS_GUARD_ACTIVE=true
INGRESS_GUARD_ENABLED=true

DOCKER_VOLUME_COUNT=46
DOCKER_VOLUME_BASELINE_EXACT=false

BOARD_ACCESS=false
```

No production runtime may be started while the Docker-volume baseline remains unresolved.

## 7. Authorization ledger

```text
AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_20261010_01
CLAIMED=true
CONSUMED=true
RESULT=FAIL_ROLLED_BACK
REPLAY_PERMITTED=false

AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R2_20261010_01
CLAIMED=true
CONSUMED=true
RESULT=FAIL_ROLLED_BACK
REPLAY_PERMITTED=false

AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R3_20261010_01
CLAIMED=true
CONSUMED=true
RESULT=FAIL_ROLLED_BACK
REPLAY_PERMITTED=false

AUTHORIZATION=N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_R4_20261010_01
CLAIMED=true
CONSUMED=true
RESULT=FAIL_ROLLBACK_INCOMPLETE_VOLUME_SET_DRIFT
REPLAY_PERMITTED=false
```

No R5 live authorization exists.

## 8. Current source authority

Last source/CI authority before R4 apply:

```text
PR541_SOURCE_HEAD=d28129967eafacdab257c3dd00ecf3dc8910f52e
PR541_STATE=OPEN_DRAFT

R4_EXECUTOR_BLOB_SHA1=69aa03770883960e6b2656fe9be88fb8fc9b96e6
R4_EXECUTOR_SHA256=cc14d78b5771930bb66a3dd8e3527fb0f0e871fcb7c86b786d005752ae42a293

PUBLIC_REPOSITORY_SAFETY_CI=PASS:38065513470
N3W_T1_S20_REAL_SERVICE_HANDOFF_CI=PASS:38065513507
GREENHOUSE_MANAGER_CI=PASS:38065513519
```

Repository main remains:

```text
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR541_AHEAD_OF_MAIN=216
PR541_BEHIND_MAIN=0
```

PR #541 must remain OPEN DRAFT and unmerged.

## 9. New known failure / regression guard

```text
KF-102=S20_TEMP_BROKER_READINESS_AND_DOCKER_VOLUME_LIFECYCLE
```

Required future guard:

- temporary Broker readiness must use the exact listener/TLS contract of the bound Broker config;
- no hard-coded plaintext port may silently diverge from that config;
- all temporary Docker artifacts, including anonymous volumes, must be inventoried before and after transaction;
- rollback closure must identify exact unexpected volume names/IDs, not only report count/hash mismatch;
- an apply authorization that has been claimed is never replayable;
- after any rollback inventory mismatch, no production service start or successor live attempt until recovery is explicitly closed.

## 10. Next one gate

```text
NEXT_ONE_GATE=N3W_T1_S20_R4_EXTRA_DOCKER_VOLUME_READONLY_ATTRIBUTION_20261011_01
```

This gate is strictly read-only.

Purpose:

1. enumerate all current Docker volumes with name, driver, labels, mountpoint metadata and creation time where available;
2. correlate the extra volume with the R4 transaction timestamp and Mosquitto image/container lifecycle;
3. prove exactly one candidate is R4-created or return ambiguity;
4. do not delete any volume;
5. return a bounded recovery design only after identity is proven.

PASS means one exact extra-volume identity is proven and a minimal deletion authorization can be designed.

FAIL/STOP means the extra volume cannot be uniquely attributed; no deletion and no R5 work.

## 11. Hard stop

```text
LIVE_MUTATION=false
VOLUME_DELETE=false
PRODUCTION_SERVICE_START=false
R4_REPLAY=false
R5_APPLY=false
BOARD_ACCESS=false
PR_MERGE=false
STOP=true
```
