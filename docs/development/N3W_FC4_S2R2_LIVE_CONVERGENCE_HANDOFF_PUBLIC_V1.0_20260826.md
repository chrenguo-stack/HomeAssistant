# N3-W / FC4 S2R2 Live Convergence Handoff — Public V1.0

Date: 2026-08-26

## Current stage

```text
FC4 Final Physical Acceptance
└─ Spare T1 current-main convergence
   └─ S2R2 live convergence preclaim  <- current boundary
```

Three-board physical acceptance has not started.

## Frozen source authority

```text
EXACT_MAIN=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
EXACT_TREE=f3b8095c62e8a4838eb1b614f05c932f54f5226d
```

No source or image modification is required by the currently proven recovery result.

## New successor authority

The old S1 successor is retired for future live cutover because its runtime contract is stale.

The replacement successor is private runtime material and is intentionally not committed to the public repository. Its frozen fingerprint is:

```text
SUCCESSOR_SHA256=235a3711b5a99ae401bb743a21259a8f53177a7c5c2894fe412ffdd00698b2c7
NEW_SUCCESSOR_READY_FOR_LIVE_PRECLAIM=true
```

The replacement successor has passed exact candidate image, Manager binding, provisioning binding, node-Broker TLS, shared-state direct-reuse, pairing-socket and diff-scope validation.

## Proven authentication result

A one-shot Paho MQTTv5 probe executed inside the exact current-main candidate image received a valid Broker `Not authorized` CONNACK while TLS and the intended Manager Dynamic Security object/role/enable-state were already proven correct.

Frozen classification:

```text
MANAGER_CREDENTIAL_AUTHORITY_DRIFT=PROVEN
SOURCE_MQTT_BINDING_IMPLEMENTATION_DEFECT_PROVEN=false
SOURCE_PRODUCT_RUNTIME_DEFECT_PROVEN=false
```

The next transaction must reconcile the existing Manager password material into the existing Dynamic Security Manager client. It must not generate a new password, increment a credential generation, recreate the client, or recreate the role.

## Shared-state conclusion

All required state roles have been proven directly reusable from existing persistent host objects:

```text
SHARED_STATE_DIRECT_REUSE=PASS
STATE_COPY_REQUIRED=false
STATE_MIGRATION_REQUIRED=false
```

The registration role was explicitly rechecked because its effective path differed from the preserved service's container path. Host-object identity proved direct rebinding is possible.

## Provisioning conclusion

The existing provisioning Dynamic Security identity and its existing secret mount authority have been proven present and safe. No provisioning credential recovery or rotation is part of the next transaction.

## Required next read-only preclaim

Before any new live authorization is claimed, revalidate:

1. exact replacement-successor fingerprint;
2. exact candidate image binding;
3. Manager / preserved pairing service / Broker / Home Assistant baseline;
4. exact pairing TCP/UDP owner identity;
5. active Dynamic Security path and target Manager object;
6. provisioning control identity and secret binding;
7. shared-state direct reuse;
8. a fresh prechange runtime snapshot and fresh Dynamic Security rollback copy.

Historical snapshots are evidence only and must not be used as rollback authority for a new live transaction.

## Required live transaction shape

If the read-only preclaim passes, a new authorization must be explicitly bound to the replacement successor SHA. The atomic transaction is:

```text
fresh rollback snapshot
-> fresh active Dynamic Security backup
-> authenticate with existing provisioning authority
-> exactly one Manager password reconciliation
-> exactly one Paho MQTTv5 Manager CONNECT proof
-> stop preserved pairing service
-> prove pairing TCP/UDP ports released
-> deploy exact replacement successor
-> verify Manager MQTT + N3-W product runtime + pairing ownership/socket
-> observe bounded stability window
-> commit
```

Normal-path Broker restart is forbidden.

If any post-credential-mutation gate fails, rollback must restore the fresh prechange Dynamic Security state and may perform exactly one Broker stop/start on the rollback path, then restore the prechange Manager and the same preserved pairing-service container. No second live attempt is allowed under the consumed authorization.

## Execution model

Continue the project execution model:

```text
High-order model:
architecture / gate / authorization / rollback / result classification

Codex:
low-order exact executor only
```

Codex must not self-expand scope, self-repair, retry a consumed authorization, or enter the next phase without a new high-order decision.

## Physical boundary

Until Spare-T1 current-main convergence passes:

```text
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_ERASE=false
```

After Spare-T1 convergence passes, return directly to the FC4 three-board final physical acceptance mainline rather than opening additional Manager/MQTT RCA branches without new contradictory evidence.
