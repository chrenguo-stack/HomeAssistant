# N3-W P2 Executor Authority and Runtime Binding Incident — 2026-10-08

```text
INCIDENT=N3W_P2_EXECUTOR_AUTHORITY_AND_RUNTIME_BINDING_20261008
STATUS=CLOSED_WITH_GUARDS
PRODUCT_DEFECT=false
T1_DEFECT=false
MANAGER_DEFECT=false
BROKER_DEFECT=false
BOARD_DEFECT=false
P2_FINAL_STATUS=CLOSED_PASS
```

## 1. Why this incident is recorded

P2 eventually passed without any T1, Manager, Broker, database, or board
mutation, but multiple executor assumptions caused unnecessary stop/re-authorize
cycles and consumed substantial operator time. These failures must remain
durable project knowledge rather than chat-only history.

## 2. Failure chain

### A. Wrong SSH target authority

Initial executors used `ssh t1`. The operator's known-good login used an
explicit `root@<private T1 IPv4>` target. Host-only `ssh -G` comparison
proved both effective HostName and User differed.

```text
FAILED_EXECUTOR_TARGET=ssh t1
OPERATOR_PROVEN_TARGET=explicit root@private-T1-IPv4
HOSTNAME_CONFIG_EQUAL=false
SSH_USER_EQUAL=false
T1_DIRECT_INTERACTIVE_LOGIN=PASS
PRODUCT_DEFECT=false
```

Guard: never treat a convenient SSH alias as target authority. Bind the exact
operator-proven target privately before consuming a remote authorization.

### B. OpenSSH normalized boolean false negative

The first explicit-target R3 preclaim incorrectly required
`StrictHostKeyChecking == "yes"`. On the operator Mac, `ssh -G` normalized
the same effective enabled setting to `true`.

```text
STRICT_HOST_KEY_EFFECTIVE=true
OLD_EXECUTOR_EXPECTED_LITERAL=yes
OLD_EXECUTOR_RESULT=FALSE_NEGATIVE
CORRECT_ACCEPTED_ENABLED_VALUES=yes|true
```

Guard: normalize CLI semantic values before comparison. Never require a
presentation spelling when multiple equivalent canonical forms exist.

### C. Broker container name hard-coded incorrectly

R3 used `docker inspect mosquitto`. Fresh live Docker inventory proved:

```text
DOCKER_CLI_PRESENT=true
DOCKER_DAEMON_ACCESSIBLE=true
MANAGER_CONTAINER_NAME=greenhouse-manager
BROKER_CONTAINER_NAME=n3wfc4-broker-1
BROKER_COMPOSE_PROJECT=n3wfc4
BROKER_COMPOSE_SERVICE=broker
BROKER_BINDING_UNIQUE=true
```

Current project source already contains the stronger Broker selector: unique
Docker Compose project `n3wfc4` plus service `broker`.

Guard: runtime role identity is selected by authoritative labels/contract, not
a guessed generated container name.

### D. Early-stop default false values were misleading

The failed R3 baseline initialized many result fields to `false` and then
stopped at Docker inspect. Those false values were not observations.

Guard: unexecuted predicates must serialize as `UNKNOWN` / `NOT_PROVEN`,
not `false`. A default value must never masquerade as negative runtime
evidence.

### E. Diagnosis was split too finely

After explicit T1 SSH had been proven, several host-only and remote micro-gates
were used where one consolidated read-only collector could have resolved the
remaining runtime identity, TLS, DB snapshot and external discovery evidence.

Guard: after target authority and mutation boundaries are proven, prefer one
bounded read-only evidence collector with a single STOP point over repeated
single-fact remote probes.

## 3. Final corrected P2 authority

Final R5 completed in one consolidated read-only execution:

```text
P2_R5_PASS=true
PAIRING_ADVERTISED_HOST_MODE_AUTO=true
REAL_T1_ADDRESS_MATCH=true
NODE_CREDENTIAL_BROKER_HOST_MATCH=true
BROKER_TCP_TLS_A_8883=true
MANAGER_DISCOVERY_AUTO_SOURCE_A=true
MANAGER_PREBOOT_SNAPSHOT_CREATED=true
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c
MANAGER_RESTART_COUNT=0
BROKER_RESTART_COUNT=0
```

No failure above proved a product defect.

## 4. Fixed executor regression rules

For all future Mac -> T1 physical executors:

```text
SSH_ALIAS_IS_AUTHORITY=false
EXPLICIT_TARGET_BINDING_REQUIRED=true
SSH_G_EFFECTIVE_VALUE_NORMALIZATION_REQUIRED=true
BROKER_EXACT_CONTAINER_NAME_REQUIRED=false
BROKER_UNIQUE_COMPOSE_LABEL_BINDING_REQUIRED=true
UNEXECUTED_BOOLEAN_DEFAULT=false
UNKNOWN_PROPAGATION_REQUIRED=true
CONSOLIDATE_READONLY_PROBES_AFTER_TARGET_BINDING=true
CLAIM_ONLY_IMMEDIATELY_BEFORE_FIRST_AUTHORIZED_REMOTE_OR_MUTATING_ACTION=true
```

For Broker selection, require exactly one running container matching:

```text
com.docker.compose.project=n3wfc4
com.docker.compose.service=broker
```

For Manager selection, current P2 authority remains exact running container
`greenhouse-manager`, with its runtime/image identity frozen separately.

## 5. Disposition

```text
INCIDENT_STATUS=CLOSED_WITH_GUARDS
P2_STATUS=CLOSED_PASS
READY_FOR_P3=true
P3_REQUIRES_EXPLICIT_BOARD_MUTATION_AUTHORIZATION=true
```
