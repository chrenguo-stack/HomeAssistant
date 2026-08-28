# N3-W / FC4 S2R2 Runtime Recovery Archive V1.0

Date: 2026-08-26

## Purpose

Archive the S2R1/F7/F7R1/F7R2 through S2R2-R1M recovery chain that preceded the final Spare-T1 current-main convergence transaction. This is a public-safe engineering record: live usernames, client IDs, host addresses, secret paths, credential fingerprints, Dynamic Security object fingerprints, and private rollback paths are intentionally omitted.

## Source and image authority

- Repository exact-main remained unchanged throughout this recovery branch: `1f80d54ff5f84056e0559a7d8cc80427c5e0bb14`.
- Exact tree: `f3b8095c62e8a4838eb1b614f05c932f54f5226d`.
- No source change was required by this investigation.
- No product image rebuild was required by the final diagnosis.
- The already-materialized current-main ARM64 candidate remained the accepted image authority.

## Recovery chronology

### 1. Pairing-service ownership and state handoff

The first handoff attempt exposed that presence of the pairing TCP/UDP ports was not sufficient evidence that the expected Manager owned them. Exact PID/cgroup/container correlation showed that a separate preserved `fc4-manager` service owned the pairing ports.

Subsequent state review proved that the registration, replay, relay authorization, relay key, peer-trust, credential-lifecycle and node-CA roles could be reused directly from existing persistent host objects. No state copy, merge or migration was required.

### 2. Manager MQTT authentication blocker

The current-main candidate reached the Broker TLS endpoint but was rejected by MQTT authorization. Read-only follow-up proved:

- Broker TLS chain and identity verification were valid.
- The intended Manager Dynamic Security object existed, was enabled and had the expected role binding.
- The active Dynamic Security file path had initially been inferred from stale material and was later corrected by resolving the path from the running Broker.
- The active Manager object used the current `encoded_password` representation; a classifier that checked only legacy password fields falsely reported a passwordless client.

### 3. F7 probe invalidated

The first bounded authentication proof used a handcrafted MQTT v5 CONNECT packet. A later read-only implementation audit proved the packet invalid because the MQTT v5 CONNECT properties encoding was malformed. Therefore that probe was invalid as authentication evidence and did not prove a Broker, credential or product defect.

### 4. F7R1 stopped before claim

A host-side Paho MQTTv5 proof was attempted only through preclaim. The host Python environment did not contain Paho and the local hostname-resolution assumption did not match the intended target. The gate stopped before authorization claim and before any MQTT connection attempt.

No package installation, host repair or DNS mutation was performed.

### 5. F7R2 produced the decisive authentication evidence

A one-shot ephemeral container based on the exact current-main candidate image was used as the Paho MQTTv5 execution environment. It performed a single TLS MQTT v5 CONNECT-only proof with no subscribe, publish, will or Dynamic Security control command.

The Broker returned a valid MQTT v5 `Not authorized` CONNACK. Because TLS, Manager object existence, role, enabled-state, username/client-ID binding and password-file binding had already been independently proven, the remaining failure class was frozen as **Manager credential authority drift**: the existing Manager password material did not authenticate against the Broker's current active credential state.

This did **not** prove a source MQTT implementation defect or a product-runtime implementation defect.

## S2R2 preclaim and successor contract correction

The first S2R2 live transaction stopped before claim because the old S1 successor was stale relative to the now-proven current runtime contract. Exact-diff review found missing or stale bindings in these semantic areas:

- Manager MQTT identity and password-file binding;
- N3-W runtime and product-pairing enablement;
- pairing manager identity / bind / advertised endpoint / ports;
- provisioning identity and password-file binding;
- node-Broker TLS endpoint binding;
- explicit shared-state role bindings.

The old successor was not deployed.

## Registration host-object resolution

A conservative intermediate classifier marked registration state as unresolved because the old successor did not explicitly bind the current-main default registration path. A focused host-object check proved that the currently preserved registration DB is a persistent, safe host object and can be mounted directly to the current-main registration path.

Final state conclusion:

```text
SHARED_STATE_DIRECT_REUSE=PASS
STATE_COPY_REQUIRED=false
STATE_MIGRATION_REQUIRED=false
```

## New successor materialization

A new successor was materialized outside the repository as private runtime material. Public archive policy intentionally records only the non-secret content fingerprint:

```text
NEW_SUCCESSOR_SHA256=235a3711b5a99ae401bb743a21259a8f53177a7c5c2894fe412ffdd00698b2c7
```

Validation closure:

```text
EXACT_CANDIDATE_IMAGE_BINDING=PASS
S1_CA_REPAIR_PRESERVED=PASS
MANAGER_IDENTITY_BINDING=PASS
MANAGER_PASSWORD_FILE_BINDING=PASS
PRODUCT_RUNTIME_BINDING=PASS
PROVISIONING_BINDING=PASS
NODE_BROKER_TLS_BINDING=PASS
REGISTRATION_DIRECT_REUSE=PASS
REPLAY_DIRECT_REUSE=PASS
RELAY_AUTH_DIRECT_REUSE=PASS
RELAY_KEYS_DIRECT_REUSE=PASS
PEER_TRUST_DIRECT_REUSE=PASS
CREDENTIAL_LIFECYCLE_DIRECT_REUSE=PASS
SHARED_STATE_DIRECT_REUSE=PASS
PAIRING_SOCKET_BINDING=PASS
SUCCESSOR_DIFF_SCOPE=PASS
STATE_COPY_REQUIRED=false
STATE_MIGRATION_REQUIRED=false
SOURCE_CHANGE_REQUIRED=false
IMAGE_CHANGE_REQUIRED=false
NEW_SUCCESSOR_READY_FOR_LIVE_PRECLAIM=true
```

## Credential reconciliation contract for the next live transaction

The next live S2R2 transaction must not generate a new password or recreate the Manager client/role. It must reconcile the existing Manager password material into the existing Manager Dynamic Security client, prove one Paho MQTTv5 CONNECT, hand pairing ownership from the preserved `fc4-manager` service to the exact current-main Manager, and observe a bounded stability window.

If any failure occurs after the Dynamic Security mutation, rollback must use a fresh prechange Dynamic Security backup and the transaction's exact prechange runtime snapshot. A Broker stop/start is permitted only on the rollback path; successful normal-path convergence must not restart the Broker.

## Scope closure

```text
THIS_ARCHIVE_SOURCE_CODE_CHANGED=false
THIS_ARCHIVE_PRIVATE_SUCCESSOR_COMMITTED=false
MANAGER_CREDENTIAL_RECONCILIATION_REQUIRED=true
CREDENTIAL_ROTATION_REQUIRED=false
STATE_MIGRATION_REQUIRED=false
SPARE_T1_CURRENT_MAIN_CONVERGENCE_PENDING=true
FC4_THREE_BOARD_FINAL_PHYSICAL_ACCEPTANCE_STARTED=false
```
