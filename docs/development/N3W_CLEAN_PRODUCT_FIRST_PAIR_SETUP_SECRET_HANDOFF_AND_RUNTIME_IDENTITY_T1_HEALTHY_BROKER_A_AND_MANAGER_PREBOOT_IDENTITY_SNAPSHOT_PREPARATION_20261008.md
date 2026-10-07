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


## 10. Corrected SSH transport classification: early KEX connection closed

A further host-only refinement examined the saved stderr alongside the local
OpenSSH effective configuration without contacting T1.

```text
STAGE=P2_SSH_HOST_ONLY_REFINEMENT
T1_NETWORK_ACCESS=false
AUTHORIZATION_REPLAY=false
SAVED_STDERR_SHA256=626faaaadb4524a710d54414338a51055982e5abb53a770851b3bfcd32e3cac6

SSH_CONFIG_RC=0
SSH_CONFIG_PARSED=true
SSH_PORT=22
SSH_TARGET_HOST_SHA256=628b49d96dcde97a430dd4f597705899e09a968f793491e4b704cae33a40dc02
PROXYCOMMAND_CONFIGURED=false
PROXYJUMP_CONFIGURED=false
IDENTITYFILE_DECLARED_COUNT=7
IDENTITYFILE_EXISTING_COUNT=1
SSH_AGENT_STATE=NO_KEYS

KEX_EXCHANGE_IDENTIFICATION_PRESENT=true
CONNECTION_CLOSED_TEXT=true
RESET_BY_PEER_TEXT=false
BANNER_EXCHANGE_PRESENT=false
PERMISSION_DENIED_TEXT=false
HOST_KEY_FAILURE_TEXT=false

P2_SSH_FAILURE_REFINED_CLASS=EARLY_KEX_CONNECTION_CLOSED
SSH_AUTHENTICATION_REACHED=NOT_PROVEN
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=NOT_PROVEN
```

**Correction to the preliminary Section 9 label:** the saved stderr contains
`Connection closed` and a `kex_exchange_identification` marker, but **does
not contain `Connection reset`**. The earlier `CONNECTION_RESET` label
was an over-broad classifier result and is superseded by the refined
`EARLY_KEX_CONNECTION_CLOSED` label. This identifies a pre-authentication
SSH transport failure symptom rather than proving an SSH daemon, host,
network, Manager, or Broker root cause.

The empty SSH agent alone is not a demonstrated authentication defect: an
identity file exists, and the observed failure precedes proof of
authentication. The effective SSH host is only represented here by its hash;
it has **not** been fresh-verified as the intended current T1 endpoint.

```text
P2_STEP1_RESULT=INVALID_SSH_TRANSPORT_FAILURE_RC255
P2_AUTHORIZATION_CLAIMED=true
P2_AUTHORIZATION_CONSUMED=true
P2_AUTHORIZATION_REPLAY=false
P2_SUCCESSOR_AUTHORIZATION_GRANTED=false
P2_MANAGER_PREBOOT_SNAPSHOT_CREATED=false
READY_FOR_P2_STEP2=false
NEXT_ACTION=REQUEST_P2_SUCCESSOR_MINIMAL_SSH_READONLY_AUTHORIZATION
BOARD_ACCESS=false
BOARD_WRITE=false
MANAGER_RESTART=false
BROKER_RESTART=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
AUTO_RETRY=false
STOP=true
```

Under a **new, explicit** successor authorization only, the next probe should
perform one bounded SSH connection with private `-vv` evidence and a harmless
read-only remote `true` command. First verify the intended current T1 SSH
locator rather than treating `ssh -G t1` as destination authority. Do not
automatically replay the failed multi-step snapshot, contact the board, restart
services, or attempt P3.


## 11. P2 R2 successor SSH and read-only preparation authorization

The operator explicitly granted a **new successor authorization**, distinct
from the consumed first P2 attempt:

```text
SUCCESSOR_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_T1_HEALTHY_BROKER_A_AND_MANAGER_PREBOOT_IDENTITY_SNAPSHOT_PREPARATION_R2_20261008_01
P2_R2_SUCCESSOR_SSH_READONLY_AUTHORIZATION_GRANTED=true
P2_R2_AUTHORIZATION_CLAIMED=false
P2_R2_AUTHORIZATION_CONSUMED=false
PREDECESSOR_P2_AUTHORIZATION_CONSUMED=true
PREDECESSOR_P2_AUTHORIZATION_REPLAY=false

ALLOWED=host-only SSH target verification
ALLOWED=one bounded SSH connectivity check
ALLOWED_AFTER_SSH_PASS=P2 read-only T1/Broker-A/Manager baseline and identity snapshot
FAILURE_POLICY=STOP_IMMEDIATELY_NO_RETRY
BOARD_ACCESS=false
BOARD_WRITE=false
MANAGER_RESTART=false
BROKER_RESTART=false
BROKER_MUTATION=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
AUTO_P3=false
MERGE=false
```

First perform a host-only effective SSH config check. Compare its hostname
SHA-256 with the prior frozen SSH alias target hash
`628b49d96dcde97a430dd4f597705899e09a968f793491e4b704cae33a40dc02`,
and require port 22 and no ProxyJump/ProxyCommand. A matching hash proves
only alias consistency with the previous attempt; it does **not** independently
prove that the resolved address is the intended live T1. That further binding
requires strict trusted SSH host-key verification and, later, an exact
read-only Docker/Manager/Broker authority check.

Only after those local checks PASS, claim/consume the successor authorization
immediately before the first actual SSH network connection. Run one bounded
SSH probe with BatchMode, StrictHostKeyChecking=yes, connection attempts=1,
disabled connection multiplexing, and private verbose diagnostics. On any
failure STOP without a second connection, without retrying the previous P2
snapshot, and without any service or board mutation.

```text
P2_R2_NEXT_ONE_ACTION=LOCAL_SSH_TARGET_GUARD_THEN_ONE_BOUNDED_SSH_PROBE
AUTO_CONTINUE_AFTER_FAILURE=false
STOP=true
```


## 12. P2 R2 successor minimal SSH probe failed

The authorized single bounded SSH connectivity probe was attempted from Mac
after local configuration verification. It returned exit code 255 and did not
produce the expected remote sentinel. No Manager/Broker/DB read-only baseline
was executed in this successor attempt.

```text
STAGE=P2_R2_SSH_TARGET_AND_CONNECTIVITY
P2_R2_SSH_PROBE_RESULT=FAILED_RC255
SSH_CONFIG_PASS=true
SSH_TARGET_HASH_MATCH=true
SSH_TARGET_HOST_SHA256=628b49d96dcde97a430dd4f597705899e09a968f793491e4b704cae33a40dc02
SSH_PORT=22
SSH_PROXY_COMMAND_NONE=true
SSH_PROXY_JUMP_NONE=true
SSH_IDENTITYFILE_EXISTING_COUNT=1
SSH_CONNECTION_ATTEMPTED=true
SSH_CONNECTION_PASS=false
SSH_RETURN_CODE=255
SSH_STDERR_SHA256=27e0e401451462d210c9884a6092dd719afd4a2483d6511576c59473d5dc0714

P2_R2_AUTHORIZATION_CLAIMED=true
P2_R2_AUTHORIZATION_CONSUMED=true
PREDECESSOR_AUTHORIZATION_REPLAY=false
AUTO_RETRY=false
READY_FOR_P2_READONLY_BASELINE=false

BOARD_ACCESS=false
BOARD_WRITE=false
BROKER_RESTART=false
MANAGER_RESTART=false
MANAGER_DB_WRITE=false
AUTO_P3=false
STOP=true
```

The SSH config hash is a consistency check against the prior local alias,
**not proof that the live target is T1**. The RC255 alone cannot prove the
specific SSH failure phase this time. Do not assume the previous
`EARLY_KEX_CONNECTION_CLOSED` classification is reproduced until the newly
saved `probe.stderr.txt` is locally classified. Remote service health is
not proved or disproved.

```text
P2_R2_SSH_ERROR_DOMAIN=SSH_TRANSPORT_OR_ENDPOINT_UNDETERMINED
EXACT_ROOT_CAUSE=TBD
P2_R2_REMOTE_RUNTIME_EVIDENCE=NOT_COLLECTED
P2_MANAGER_PREBOOT_SNAPSHOT_CREATED=false
P2_R2_AUTHORIZATION_REPLAY=false
NEXT_ACTION=HOST_ONLY_CLASSIFY_SAVED_R2_VERBOSE_SSH_LOG
SUCCESSOR_REMOTE_AUTHORIZATION_REQUIRED_FOR_FURTHER_SSH=true
```

The next action must read only the private Mac evidence and emit sanitized
phase booleans. Do not paste the verbose SSH log, SSH target, private key
paths, remote identifiers, or host-key material into public project records.


## 13. Operator-confirmed direct T1 SSH login — alias authority mismatch investigation

After the two `ssh t1` failures, the operator independently reported a
successful interactive SSH login using an explicit `root@<private T1 IPv4>`
target, reaching the expected `root@armbian` shell.

```text
EXPLICIT_T1_SSH_LOGIN_OBSERVED=true
EXPLICIT_T1_SSH_LOGIN_ACCOUNT=root
EXPLICIT_T1_SSH_LOGIN_PROMPT=root@armbian
DIRECT_T1_SSH_TRANSPORT_SUCCESS=true

FAILED_EXECUTOR_SSH_TARGET=t1
FAILED_EXECUTOR_SSH_TARGET_EQUALS_SUCCESSFUL_EXPLICIT_TARGET=NOT_PROVEN
SSH_ALIAS_TARGET_MISMATCH=HYPOTHESIS_NOT_PROVEN
T1_SSH_SERVICE_UNAVAILABLE=false
T1_BROKER_MANAGER_RUNTIME_HEALTH=NOT_TESTED
P2_MANAGER_PREBOOT_SNAPSHOT_CREATED=false

P2_R2_AUTHORIZATION_CONSUMED=true
AUTO_RETRY=false
BOARD_ACCESS=false
BOARD_WRITE=false
MANAGER_RESTART=false
BROKER_RESTART=false
MANAGER_DB_WRITE=false
STOP=true
```

Correction: the previous repeated `ssh t1` failures establish only a failure
of that alias-based route under the executor's options. They do **not** establish
general unreachability of T1. A fresh successful explicit-root login proves
that the operator's SSH transport to the expected T1 shell works, but it does
not prove the alias points to that destination. Root cause remains unproven.

Next perform a **host-only** effective SSH configuration comparison between
`ssh -G t1` and the operator's successfully used explicit SSH target. Compare
resolved HostName, User, Port, and relevant connection settings without logging
the raw IP or credentials. No new T1 connection is necessary for this comparison.
Do not replay the two consumed authorizations. Any further automated T1 access
requires a new explicitly scoped successor authorization with the successful
T1 target bound first.


## 14. Local SSH effective-target comparison: confirmed configuration discrepancy

The operator executed an additional host-only `ssh -G` comparison between
the failed scripted alias `t1` and the successfully used explicit-root
T1 login target. This **did not open a T1 connection**.

```text
STAGE=P2_SSH_ALIAS_LOCAL_COMPARISON
ALIAS_CONFIG_PASS=true
DIRECT_CONFIG_PASS=true
HOSTNAME_CONFIG_EQUAL=false
SSH_USER_EQUAL=false
SSH_PORT_EQUAL=true
T1_NETWORK_ACCESS=false
STOP=true

P2_R2_SSH_ALIAS_CONFIGURATION_COMPARISON=DIFFERENT_HOST_AND_USER
P2_R2_ALIAS_EQUALS_SUCCESSFUL_LOGIN_CONFIGURATION=false
P2_R2_FAILURE_CAUSED_BY_ALIAS_DIFFERENCE=LIKELY_NOT_YET_PROVEN
P2_R2_AUTHORIZATION_CONSUMED=true
P2_R2_AUTHORIZATION_REPLAY=false

P2_MANAGER_PREBOOT_SNAPSHOT_CREATED=false
READY_FOR_P2_READONLY_BASELINE=false
BOARD_ACCESS=false
BOARD_WRITE=false
BROKER_RESTART=false
MANAGER_RESTART=false
MANAGER_DB_WRITE=false
AUTO_RETRY=false
STOP=true
```

This proves that the repeated `ssh t1` tests did not reproduce the
operator's successful SSH target/user configuration. The two hostnames
might still resolve to the same endpoint, but the effective SSH user is
definitely different. No further remote diagnostic work should focus on
Manager, Broker, or the ESP32-C6 board before the executor target is corrected.

For the **next separate authorized successor**, bind SSH to the
operator-confirmed explicit T1 root target (kept private), with strict
host-key checking, a single bounded connection attempt and fail-closed
behavior. A passed SSH probe may then proceed within that successor grant
to the P2 read-only runtime checks and a fresh preboot identity snapshot,
and must not repeat the expired prior grant. A local-only comparison
does not itself authorize another SSH attempt.

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P2_R3_EXPLICIT_T1_SSH_READONLY_SUCCESSOR
P2_R3_AUTHORIZATION_GRANTED=false
P2_R3_BOARD_ACCESS=false
P2_R3_SERVICE_MUTATION=false
P2_R3_DATABASE_MUTATION=false
P2_R3_AUTO_P3=false
```
