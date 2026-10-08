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


## 15. P2 R3 explicit-T1 SSH read-only successor — operator authorization

The operator explicitly approved P2 R3 under the following bounded scope,
distinct from consumed P2 initial and P2 R2 SSH grants.

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P2_R3_EXPLICIT_T1_SSH_READONLY_SUCCESSOR
P2_R3_EXPLICIT_T1_AUTHORIZATION_GRANTED=true
P2_R3_AUTHORIZATION_CLAIMED=false
P2_R3_AUTHORIZATION_CONSUMED=false
P2_INITIAL_AUTHORIZATION_CONSUMED=true
P2_R2_AUTHORIZATION_CONSUMED=true
P2_PREDECESSOR_AUTHORIZATION_REPLAY=false

STEP1=ONE_BOUNDED_EXPLICIT_ROOT_T1_SSH_CONNECTIVITY_PROBE
AFTER_STEP1_PASS=CONTINUE_P2_MANAGER_BROKER_READONLY_BASELINE_AND_PREBOOT_IDENTITY_SNAPSHOT
ANY_FAILURE=STOP_NO_RETRY

TARGET_AUTHORITY=OPERATOR_PROVEN_EXPLICIT_ROOT_PRIVATE_IPV4
DO_NOT_USE=ssh_t1_alias
SSH_STRICT_HOST_KEY_VERIFICATION=true
OPERATOR_INTERACTIVE_AUTH_IF_REQUIRED=true
AUTO_RETRY=false

BOARD_ACCESS=false
BOARD_WRITE=false
BROKER_RESTART=false
MANAGER_RESTART=false
T1_CONFIGURATION_MUTATION=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
AUTO_P3=false
MERGE=false
```

Preclaim guard must verify an explicit root@private IPv4 target, effective
SSH `HostName` equals that exact operator-supplied private IPv4 (with no
proxy), SSH user root, port 22, and private Mac evidence directory absent.
Target comparison with the stale `ssh t1` alias is not an authority.

First actual SSH connection claims and consumes R3. Do not classify an
interactive password prompt as failure: the operator's proven manual SSH
session may depend on interactive authentication. Use one bounded SSH
command with StrictHostKeyChecking=yes, ConnectTimeout, no multiplexing,
and at most one prompt; keep raw diagnostics private. No password is ever
captured by the script and no SSH target/address is printed publicly.

Successful proof is a remote sentinel under exit code 0. Only then
continue the **same R3 authorization** with P2 read-only Broker/Manager
snapshots; one consumed grant is not replayable upon failure.
```text
P2_R3_PROGRESS=AUTHORIZED_AWAITING_SSH_PROBE
NEXT_ACTION=P2_R3_EXPLICIT_T1_SSH_MINIMAL_PROBE
STOP=true
```


## 16. P2 R3 host-only target-config preclaim STOP — authorization intact

The first P2 R3 script stopped **before SSH access** on its local `ssh -G`
effective-configuration predicate. The operator returned only a sanitized
result, so no single failed predicate has yet been proven.

```text
STAGE=P2_R3_EXPLICIT_T1_SSH_CONNECTIVITY
P2_R3_HOST_ONLY_PRECLAIM_RESULT=SSH_TARGET_CONFIG_MISMATCH
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
PREDECESSOR_AUTHORIZATION_REPLAY=false
SSH_TARGET_PREFLIGHT_PASS=false
SSH_CONNECTION_ATTEMPTED=false
SSH_CONNECTION_PASS=false

P2_R3_TYPED_TARGET_SHA256=2b149655aab07a3941fa76d0fd03e6b632e628077d5cddcf4eafa0e2c9e313fd

BOARD_ACCESS=false
BOARD_WRITE=false
BROKER_RESTART=false
MANAGER_RESTART=false
MANAGER_DB_WRITE=false
AUTO_RETRY=false
AUTO_P3=false
STOP=true
```

Likely harness-side compatibility issue to check: OpenSSH `ssh -G` may
normalize the effective value of `StrictHostKeyChecking=yes` to `true`.
The R3 guard compared it to the literal string `yes`. This explanation
is **hypothesis only** until each guard's Boolean result is independently
reported.

Next stage must be purely Mac local: rerun `ssh -G` for the operator-proven
explicit root target, compare one Boolean for each guard and only emit
sanitized classifications. This is permitted without another remote
authorization because R3 remains unclaimed and unconsumed. Do not manually
change global SSH configuration or weaken host-key validation to satisfy
an incorrect harness check.


## 17. P2 R3 SSH target guard defect proven — authorization preserved

A final Mac-only `ssh -G` examination of the **same explicit T1 root target**
proved that the preclaim STOP was caused solely by OpenSSH boolean value
normalization. The script had required a literal `yes`; the same effective
`StrictHostKeyChecking=yes` setting is reported by OpenSSH as `true`.

```text
STAGE=P2_R3_SSH_LOCAL_GUARD_DIAGNOSIS
TARGET_MATCHES_PREVIOUS_INPUT=true
SSH_CONFIG_RC=0
HOSTNAME_MATCH=true
SSH_USER_ROOT=true
SSH_PORT_22=true
PROXYCOMMAND_NONE=true
PROXYJUMP_NONE=true
REMOTE_COMMAND_NONE=true
STRICT_HOST_KEY_EFFECTIVE=true
STRICT_CHECK_OLD_SCRIPT_PASS=false
STRICT_CHECK_CORRECTED_PASS=true

P2_R3_STRICT_CHECK_NORMALIZATION_ROOT_CAUSE=PROVEN
FAILURE_CLASS=EXECUTOR_PRECLAIM_FALSE_NEGATIVE
T1_NETWORK_ACCESS=false
P2_R3_AUTHORIZATION_CLAIMED=false
P2_R3_AUTHORIZATION_CONSUMED=false
```

The corrected preclaim must accept both `true` and `yes` as strict
host-key-checking **enabled**, and reject all disabled/permissive values
(`false`, `no`, `ask`, `accept-new`). Preserve the exact successful
operator-proven explicit-root private T1 target, one bounded SSH attempt,
private diagnostic evidence, and STOP on any failure. This is not a request
to modify local SSH configuration.

```text
P2_R3_NEXT_ACTION=CORRECTED_ONE_TIME_SSH_PROBE
P2_R3_AUTHORIZATION_REPLAY=false
BOARD_ACCESS=false
BOARD_WRITE=false
MANAGER_RESTART=false
BROKER_RESTART=false
MANAGER_DB_WRITE=false
AUTO_RETRY=false
AUTO_P3=false
STOP=true
```


## 18. Corrected P2 R3 explicit-target SSH physical probe PASSED

The operator ran the **corrected** one-time SSH probe against the
operator-confirmed explicit-root T1 target. The effective target guard passed,
SSH returned exit code 0, and the expected remote sentinel was observed.
This is fresh direct evidence of a working authenticated T1 SSH command
transport using the corrected target and options.

```text
STAGE=P2_R3_CORRECTED_EXPLICIT_T1_SSH
P2_R3_CORRECTED_EXPLICIT_T1_SSH_CONNECTION_PASS=true
SSH_TARGET_PREFLIGHT_PASS=true
SSH_CONNECTION_ATTEMPTED=true
SSH_CONNECTION_PASS=true
SSH_RETURN_CODE=0
SSH_STDERR_SHA256=262df7d6c4418978ef7cf3787b4cbb1bcc74daa93fcecf611190765a40d16b50

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
PREDECESSOR_AUTHORIZATION_REPLAY=false
READY_FOR_P2_READONLY_BASELINE=true

BOARD_ACCESS=false
BOARD_WRITE=false
MANAGER_RESTART=false
BROKER_RESTART=false
MANAGER_DB_WRITE=false
AUTO_RETRY=false
AUTO_P3=false
```

The P2 R3 grant is **consumed for the SSH connectivity probe**, but the
explicit operator scope permits continuing to read the current Broker/
Manager runtime and generate the Manager preboot identity snapshot **within
this same successful R3 workflow**. It does not permit retrying failed
remote steps, entering P3, or flashing the clean candidate board.

The SSH proof is **not** itself proof that Broker A TLS, current Manager
configuration, all SQLite history, or preboot identity snapshot has passed.
Those remain the next strictly read-only gate.

```text
P2_R3_NEXT_ACTION=T1_MANAGER_BROKER_READONLY_BASELINE_AND_PREBOOT_IDENTITY_SNAPSHOT
P2_R3_BASELINE_COMPLETED=false
P2_R3_PREBOOT_IDENTITY_SNAPSHOT_CREATED=false
P2_R3_DISCOVERY_AUTO_SOURCE_A=NOT_PROVEN
P2_R3_AUTO_RETRY=false
STOP=true
```


## 19. P2 R3 read-only baseline stopped at Docker inspect

After the corrected SSH transport PASS, the authorized R3 read-only baseline
entered T1 and stopped on the first generic Docker-inspect failure emitted by
the executor.

```text
STAGE=P2_R3_T1_MANAGER_BROKER_PREBOOT_READONLY
P2_R3_BASELINE_RESULT=DOCKER_INSPECT_FAILED
T1_ACCESSED=true
SSH_PREVIOUS_PROBE_BOUND=true
SSH_RETURN_CODE=2
P2_READONLY_BASELINE_PASS=false
MANAGER_PREBOOT_SNAPSHOT_CREATED=false
READY_FOR_P2_DISCOVERY_PROBE=false

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
PREDECESSOR_AUTHORIZATION_REPLAY=false
AUTO_RETRY=false

BOARD_ACCESS=false
BOARD_WRITE=false
BROKER_RESTART=false
MANAGER_RESTART=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
AUTO_P3=false
STOP=true
```

The remaining public result fields stayed at their initial false defaults because
the executor stopped before those checks. They are therefore **not negative
runtime evidence** for Manager, Broker, TLS, listeners, or identity state.

The R3 executor used a generic `DOCKER_INSPECT_FAILED` error for both:
`docker inspect --type container greenhouse-manager` and
`docker inspect --type container mosquitto`. The saved public result does
not prove which inspect failed, nor whether Docker CLI/daemon access itself
failed.

Fresh source review shows:
- the exact runtime identity snapshot authority defaults Manager container to
  `greenhouse-manager` (blob
  `ad4d70266c8628d138170a0e86b62e1e891a01c7`);
- the current Broker production preflight source inspects `mosquitto`
  (blob `f8b604221b28e6b717a7f5919feafdcaa8e15ca3`).

Thus the executor names match current source assumptions, but live-T1 name
binding and Docker availability remain unproven.

```text
P2_R3_AUTHORIZATION_REPLAY=false
P2_R4_AUTHORIZATION_GRANTED=false
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P2_R4_DOCKER_RUNTIME_IDENTITY_READONLY_DIAGNOSIS
R4_REQUIRED_SCOPE=one bounded explicit-T1 SSH read-only Docker runtime diagnosis
R4_AUTO_RETRY=false
R4_SERVICE_MUTATION=false
R4_DATABASE_MUTATION=false
R4_BOARD_ACCESS=false
R4_AUTO_P3=false
```


## 20. P2 R4 Docker runtime identity read-only diagnosis — operator authorization

The operator explicitly approved a new successor gate after the consumed R3
baseline stopped at a generic Docker inspect failure.

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P2_R4_DOCKER_RUNTIME_IDENTITY_READONLY_DIAGNOSIS
P2_R4_AUTHORIZATION_GRANTED=true
P2_R4_AUTHORIZATION_CLAIMED=false
P2_R4_AUTHORIZATION_CONSUMED=false

P2_R3_AUTHORIZATION_CONSUMED=true
P2_R3_AUTHORIZATION_REPLAY=false

ALLOWED=one bounded explicit-root T1 SSH connection
ALLOWED=read-only Docker CLI/daemon health check
ALLOWED=read-only running-container inventory and classification
ALLOWED=private evidence on operator Mac only

DO_NOT_RUN=full P2 baseline
DO_NOT_RUN=identity snapshot
DO_NOT_RUN=Manager discovery probe
DO_NOT_RESTART=Manager
DO_NOT_RESTART=Broker
DO_NOT_MUTATE=database
DO_NOT_ACCESS=board
DO_NOT_ENTER=P3
FAILURE_POLICY=STOP_IMMEDIATELY_NO_RETRY
AUTO_RETRY=false
MERGE=false
```

The R4 executor must not assume the live container names. It may enumerate
running containers read-only, inspect their names/images/Compose labels in
memory, and emit only sanitized classifications publicly. Raw container
inventory and raw container IDs remain private evidence.

The R4 result must distinguish:
1. Docker CLI unavailable;
2. Docker daemon inaccessible;
3. expected Manager name present/absent;
4. expected Broker name present/absent;
5. uniquely classifiable Manager/Broker candidates by image/Compose labels;
6. ambiguous/no candidate.

```text
P2_R4_NEXT_ACTION=ONE_BOUNDED_DOCKER_RUNTIME_READONLY_DIAGNOSIS
STOP=true
```
