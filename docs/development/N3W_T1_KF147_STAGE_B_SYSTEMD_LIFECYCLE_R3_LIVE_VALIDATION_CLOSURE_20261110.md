# N3W T1 KF-147 Stage B systemd lifecycle R3 live validation closure

Date: 2026-11-10  
PR: #800  
Status: CLOSED_PASS

## Authority

```text
EXECUTED_HEAD=675871a0567aca858c8af34f9eecf0a2e79ba063
SEAL_MANIFEST_COMMIT=21fae19f2ca89cbc6f47a8eae98281a6a9e6931f
SEAL_TEST_COMMIT=8637e3ecc8ab0a345831300673b7e44aa7529465
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_STAGE_B_SYSTEMD_LIFECYCLE_REVALIDATION_R3_20261110_01
RESULT=PASS
```

## Why R3 existed

The first Stage B R2 live attempt consumed its one-shot authorization but stopped after the seven-file host-source mutation because the execution contract stopped `n3w-t1-ha-ota.service` while `n3wfc4-services-activation.service` had a reverse `Requires=` dependency on that unit. systemd therefore stopped the services owner, which stopped Manager and Home Assistant. The original executor restarted only the host daemon, so post-validation and rollback validation both observed the services owner inactive.

Read-only forensic proved the seven-file rollback itself restored predecessor source state, U1 remained intact, Broker remained running, and the later bounded services recovery restored Manager and Home Assistant with the original container identities. R2 remained consumed and non-replayable.

The source repair changed both execute and rollback lifecycle ordering to:

```text
stop services owner
stop host daemon
apply or restore host source/state
start host daemon
start services owner
validate
```

R3 used a fresh gate, confirmation phrase, remote staging directory and durable state root. It did not reuse R2 state.

## Physical T1 R3 result

```text
STATUS=PASS
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

HOST_SOURCE_MUTATION=true
HOST_DAEMON_STOPPED=true
HOST_DAEMON_RESTART=true
SERVICES_OWNER_STOPPED=true
SERVICES_OWNER_RESTART=true

MANAGER_IPC_V3_SUPPORT=true
CAPACITY_SNAPSHOT_PRESENT=true
PREPARE_CANDIDATE_PRESERVED=true
U1_TRANSACTION_PRESERVED=true

ROLLBACK_REQUIRED=false
ROLLBACK=null
REMOTE_RETURNCODE=0
SSH_MASTER_CLEANUP=true

MANAGER_MUTATION=false
HOMEASSISTANT_MUTATION=false
BROKER_MUTATION=false
USB_MUTATION=false
U2_PLUS=false
MERGE=false
```

The PASS path proves the repaired systemd lifecycle ordering works on the physical T1, the exact seven-file host source/policy delta is active, Manager IPC V3 capacity publication is available, the existing U1 transaction and Extreme USB candidate remain continuous, and no USB write or U2+ transition occurred.

## Authorization seal

After the physical PASS, the R3 manifest was sealed fail-closed:

```text
LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
```

R3 must never be replayed.

## Remaining boundary

Stage B is CLOSED_PASS. The next product boundary is the mandatory-USB confirmation / U2+ progression. That is a separate destructive live boundary and is not authorized by this closure. No USB erase/write, U2+, board access, merge or deployment beyond the validated Stage B host-source apply is implied here.
