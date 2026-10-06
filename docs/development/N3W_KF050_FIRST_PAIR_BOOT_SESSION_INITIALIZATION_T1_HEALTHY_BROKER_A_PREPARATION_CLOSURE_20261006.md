# N3-W KF-050 First-Pair Boot-Session Initialization — T1 Healthy Broker A Preparation Closure — 2026-10-06

```text
TASK=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_T1_HEALTHY_BROKER_A_PREPARATION_20261006_01
STATUS=CLOSED_PASS
T1_HEALTHY_BROKER_A_PREPARATION=PASS
BOARD_ACCESS=false
BOARD_WRITE=false
BROKER_RESTART=false
BROKER_MUTATION=false
SERVICE_IDENTITIES_ENV_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MERGE=false
```

## 1. Entry authority

Stage P1 clean-board eligibility was already CLOSED_PASS. The candidate board remained untouched during this gate.

The live T1 preflight proved that the network, Broker, TLS, ingress guard, and dynamic pairing discovery were healthy, while the Broker host used for newly provisioned node credentials was stale.

```text
PAIRING_ADVERTISED_HOST_MODE=auto
BROKER_8883_WILDCARD_PUBLICATION=true
BROKER_RUNNING=true
BROKER_RESTART_COUNT=0
BROKER_TLS_CURRENT_ETH0_PASS=true
BROKER_TLS_LOOPBACK_PASS=true
BROKER_GUARD_ACTIVE=active
BROKER_GUARD_ENABLED=enabled
DOCKER_USER_8883_ANCHOR_COUNT=1
INPUT_8883_ANCHOR_COUNT=1
MANAGER_DISCOVERY_AUTO_SOURCE_A=true
NODE_BROKER_HOST_UPDATE_REQUIRED=true
```

The private LAN address A is not published. Public evidence binds it only by SHA-256:

```text
REAL_T1_ADDRESS_SHA256=6257bd5c713a053e9efa4c9b036119a068dba2ddb8145e8288e89ad470822338
```

## 2. Configuration-authority drift found during preparation

The first mutation attempt stopped safely before any transaction because a stronger-than-valid assumption treated the running Manager Broker host as if it were identical to the on-disk `manager.env` value.

Follow-up read-only evidence proved three distinct states:

```text
RUNNING_MANAGER_NODE_BROKER_HOST=historical address X
MANAGER_ENV_NODE_BROKER_HOST=historical address Y
SERVICE_IDENTITIES_NODE_BROKER_HOST=historical address Y
CURRENT_REAL_T1_ADDRESS=A
```

Public-safe hashes:

```text
RUNTIME_NODE_BROKER_HOST_SHA256=fd81bc85606fef9be0fef1ebeda6c00dcab38fe80440939ec413442894216534
MANAGER_ENV_NODE_BROKER_HOST_SHA256=8203b89b390ddffc683cc6fdff253aafff7419eec085a4945670cf6b495590f2
REAL_T1_ADDRESS_SHA256=6257bd5c713a053e9efa4c9b036119a068dba2ddb8145e8288e89ad470822338
```

The failed attempt reported:

```text
STATUS=STOP
ERROR=old Broker host drift
ROLLBACK_STATUS=NOT_NEEDED
```

No mutation had begun and no rollback action was required.

A final read-only Compose authority check then proved:

```text
COMPOSE_SHA256=2c9c28c582a9c01e18a2e54a4c0b2bbddc75192ed377a701ed2f661f15cd5a8a
MANAGER_SERVICE_REFERENCES_MANAGER_ENV=true
MANAGER_SERVICE_REFERENCES_SERVICE_IDENTITIES_ENV=false
WHOLE_COMPOSE_REFERENCES_MANAGER_ENV=true
WHOLE_COMPOSE_REFERENCES_SERVICE_IDENTITIES_ENV=false
```

Therefore `manager.env` is the current live Manager configuration input for this key. `service-identities.env` remains an unreferenced historical/sidecar file for this live deployment and was intentionally not mutated in this gate.

## 3. Controlled repair

The repair scope was limited to the current live Manager Broker-host authority.

Before replacement, the executor:

1. rebound the exact current T1 address A;
2. rebound the expected `manager.env` hash and non-target hash;
3. rebound the current Manager identity and its stale runtime Broker host;
4. rebound the current Broker identity and restart count;
5. rebound the ingress firewall fingerprint;
6. re-proved TCP/8883 TLS and `auto` discovery on A;
7. created a stopped shadow Manager from the current live Manager runtime contract;
8. required the shadow to preserve image, mounts, non-target environment, runtime/security settings, host networking, and pairing mode while substituting only the node Broker host with A.

Only after the shadow contract passed did the transaction begin.

The durable mutation was exactly:

```text
/opt/greenhouse-fc4-95c42fa5/runtime/manager/manager.env
GH_N3W_NODE_BROKER_HOST: historical address Y -> current real T1 address A
```

The Manager was then recreated from the live runtime contract so the runtime value also became A.

No Broker Compose command was issued. No firewall change, replay-state mutation, high-water clear, board access, or board write occurred.

## 4. Final poststate

```text
STATUS=PASS
T1_HEALTHY_BROKER_A_PREPARATION=PASS
PAIRING_ADVERTISED_HOST_MODE=auto
MANAGER_ENV_NODE_BROKER_HOST_IS_A=true
MANAGER_RUNTIME_NODE_BROKER_HOST_IS_A=true
NODE_CREDENTIAL_BROKER_HOST_IS_A=true
BROKER_TLS_A_8883=PASS
MANAGER_DISCOVERY_AUTO_SOURCE_A=PASS
MANAGER_RECREATED=true
MANAGER_RESTART_COUNT=0
BROKER_CONTAINER_ID_UNCHANGED=true
BROKER_RESTART_COUNT=0
FIREWALL_UNCHANGED=true
MANAGER_ENV_EXCLUDING_NODE_BROKER_HOST_UNCHANGED=true
SERVICE_IDENTITIES_ENV_MUTATION=false
BOARD_ACCESS=false
BOARD_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
```

New Manager public-safe runtime binding:

```text
MANAGER_CONTAINER_ID_SHA256=7b3c2a4de642e8a57da9d3f1652c9c35a27533c16f056736ecc89e289463bccc
MANAGER_STARTED_AT=2026-10-06T15:08:36.478286093Z
MANAGER_RESTART_COUNT=0
```

The Broker remained the same running container throughout the successful repair and retained restart count zero.

## 5. Gate decision

All Stage P2 requirements from the clean-board physical acceptance preexecution are satisfied:

```text
PAIRING_ADVERTISED_HOST_MODE=auto
REAL_T1_ADDRESS=A
NODE_CREDENTIAL_BROKER_HOST=A
BROKER_TCP_TLS_A_8883=PASS
MANAGER_DISCOVERY_AUTO_SOURCE=A
T1_HEALTHY_BROKER_A_PREPARATION=PASS
```

The formal clean-product baseline may now advance to Stage P3. No board write is authorized by this closure itself.

```text
NEXT_ONE_GATE=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_CLEAN_FULL_PRODUCT_FLASH_20261006_01
BOARD_WRITE_REQUIRES_SEPARATE_AUTHORIZATION=true
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MERGE=false
```
