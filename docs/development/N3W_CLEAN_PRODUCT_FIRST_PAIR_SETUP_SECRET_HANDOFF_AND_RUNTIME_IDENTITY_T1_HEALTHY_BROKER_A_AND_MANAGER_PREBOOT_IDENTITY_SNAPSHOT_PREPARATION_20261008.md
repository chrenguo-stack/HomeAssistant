# N3-W Clean Product First-Pair / Runtime Identity
# P2 T1 Healthy Broker-A and Manager Preboot Identity Snapshot Preparation — 2026-10-08

```text
STATUS=AUTHORIZED_NOT_EXECUTED
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_STATE=OPEN_DRAFT
MERGE=false
```

## 1. Entry authority

```text
P1_R2_CLEAN_BOARD_ELIGIBILITY=CLOSED_PASS
P1_R2_CLOSURE_AUTHORITY=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_R2_CLOSURE_20261008.md

SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
ARTIFACT_ID=11469977052

PRODUCT_HARDWARE_ID_SHA256=DEFERRED
BOARD_WRITE=false
FLASH_ERASE=false
FLASH_WRITE=false
```

## 2. Operator authorization

The operator explicitly authorized P2 read-only preparation.

```text
AUTHORIZATION=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_T1_HEALTHY_BROKER_A_AND_MANAGER_PREBOOT_IDENTITY_SNAPSHOT_PREPARATION_20261007_01
AUTHORIZATION_CLASS=T1_BROKER_MANAGER_READONLY_PREPARATION
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

BOARD_WRITE=false
BROKER_RESTART=false
MANAGER_RESTART=false
BROKER_MUTATION=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
```

## 3. Required fresh proof

P2 must freshly prove:

```text
PAIRING_ADVERTISED_HOST_MODE=auto
REAL_T1_ADDRESS=A
NODE_CREDENTIAL_BROKER_HOST=A
BROKER_TCP_TLS_A_8883=PASS
MANAGER_DISCOVERY_AUTO_SOURCE=A

MANAGER_CONTAINER_RUNNING=true
BROKER_CONTAINER_RUNNING=true

MANAGER_CONTAINER_ID=<private/raw not public>
MANAGER_STARTED_AT=<public-safe runtime metadata>
MANAGER_RESTART_COUNT=<integer>
BROKER_CONTAINER_ID=<private/raw not public>
BROKER_STARTED_AT=<public-safe runtime metadata>
BROKER_RESTART_COUNT=<integer>

MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SCHEMA=n3w.kf050.runtime-identity-snapshot/1
MANAGER_PREBOOT_IDENTITY_SNAPSHOT=<private hashed set>
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256=<public-safe digest>
```

Raw T1 LAN address A and raw Manager hardware identities remain private evidence.

## 4. Exact snapshot source authority

The exact product source contains the read-only snapshot implementation:

```text
SOURCE_PATH=tools/execution_packages/n3w/auto_safe_fallback/clean_board_eligibility_readonly_preflight/runtime_identity_binding_readonly.py
SOURCE_BLOB=ad4d70266c8628d138170a0e86b62e1e891a01c7
SNAPSHOT_SCHEMA=n3w.kf050.runtime-identity-snapshot/1
SQLITE_MODE=mode=ro
SQLITE_QUERY_ONLY=true
MANAGER_MUTATION=false
MANAGER_REPLAY_MUTATION=false
```

The companion Manager-history reader remains:

```text
SOURCE_PATH=tools/execution_packages/n3w/auto_safe_fallback/clean_board_eligibility_readonly_preflight/manager_history_readonly.py
SOURCE_BLOB=2a2a9e4b6adfe9cceabecad9e8ced6a1eac3bb84
```

P2 must preserve those read-only semantics.

## 5. Staged execution

```text
P2_STEP_1=T1_MANAGER_BROKER_RUNTIME_AND_PREBOOT_IDENTITY_SNAPSHOT
P2_STEP_2=EXTERNAL_MANAGER_DISCOVERY_AUTO_SOURCE_A_PROBE
P2_STEP_3=P2_CLOSURE_REVIEW
```

Step 1 may inspect Docker runtime metadata, Manager environment, host network
addresses, TLS endpoint, Manager database mounts and SQLite state in read-only
mode. It may create private evidence on the operator Mac only.

Step 2 must use a bounded read-only network probe from outside T1 to prove that
Manager auto discovery returns the route-selected current T1 address A.

No stage may restart/recreate Manager or Broker, alter firewall/network
configuration, write Manager databases, clear replay/high-water, or access/write
the candidate board.

## 6. Stop conditions

```text
MANAGER_NOT_RUNNING=STOP
BROKER_NOT_RUNNING=STOP
PAIRING_ADVERTISED_HOST_NOT_AUTO=STOP
NODE_BROKER_HOST_NOT_CURRENT_T1_ADDRESS=STOP
TLS_8883_FAIL=STOP
IDENTITY_SNAPSHOT_AMBIGUOUS=STOP
DISCOVERY_AUTO_SOURCE_NOT_PROVEN=STOP

AUTO_REPAIR=false
AUTO_RESTART=false
AUTO_P3=false
```

## 7. Current stop point

```text
P2_AUTHORIZATION_GRANTED=true
P2_AUTHORIZATION_CLAIMED=false
P2_AUTHORIZATION_CONSUMED=false
P2_EXECUTION_NOT_STARTED=true

NEXT_ACTION=P2_STEP_1_T1_MANAGER_BROKER_RUNTIME_AND_PREBOOT_IDENTITY_SNAPSHOT
STOP=true
```


## 8. First P2 Step-1 execution result

The first authorized P2 Step-1 attempt crossed the T1 SSH access boundary but
failed before any successful remote probe result was returned.

```text
P2_STEP1_RESULT=INVALID_SSH_TRANSPORT_FAILURE_RC255
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

T1_ACCESSED=true
SSH_RETURN_CODE=255
READY_FOR_P2_STEP2=false
STOP=true

BOARD_ACCESS=false
BOARD_WRITE=false
BROKER_RESTART=false
MANAGER_RESTART=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
```

No successful remote JSON was produced, so none of the required T1/Broker/
Manager readiness predicates or the preboot identity snapshot are proven by
this attempt.

The exact SSH failure class is not yet proven from the public-safe output.
Do not replay the consumed P2 authorization. The next action is a host-only
classification of the already-saved private `remote.stderr.txt`; that action
must not open a new SSH connection.

```text
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
P2_AUTHORIZATION_REPLAY=false
NEXT_ACTION=HOST_ONLY_CLASSIFY_SAVED_SSH_STDERR
```


## 9. Host-only classification of consumed P2 Step-1 SSH failure

The already-saved Mac-side `remote.stderr.txt` was classified without opening
a new SSH connection.

```text
STAGE=P2_SSH_FAILURE_HOST_ONLY_CLASSIFICATION
PRIVATE_STDERR_PRESENT=true
SSH_FAILURE_CLASS=CONNECTION_RESET
T1_NETWORK_ACCESS=false
AUTHORIZATION_REPLAY=false
STOP=true
```

This narrows the failure from generic SSH rc=255 to a connection-reset class,
but does not yet prove whether the reset occurred before SSH authentication,
during key exchange, or after session establishment.

```text
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
P2_SUCCESSOR_T1_ACCESS_NOT_YET_AUTHORIZED=true
```

Before requesting successor T1 access, perform a host-only SSH configuration and
saved-stderr refinement check. It may inspect `ssh -G t1`, local key-file
existence/permissions, and the already-saved stderr, but must not initiate a
network connection.
