# N3-W R2A Board A Runtime Namespace Recovery Closeout — 2026-09-03

## Scope

This document closes the Board A branch of the N3-W three-board regression/retest after the Board A runtime-liveness failure was isolated, recovered, and physically revalidated.

This is a secret-safe public archive. Raw NODE_ID, SYSTEM_ID, MQTT client ID, hardware ID, pairing ID, Setup Secret, USB serial, MAC address, T1 locator, socket endpoint, private paths and raw Broker/Manager logs are intentionally excluded.

## Frozen authorities

- Repository main at investigation start: `9a8592a5b17205f2995324f5eeb9e0687c7225e5`
- Frozen deployed product Manager source: `8fbedc7e0778ce91d146cd5f0772bebdd20ad13a`
- Frozen Board firmware source: `739d9af2bac78a3a59f92a4ae345d8f1b1dc15ab`
- Exact historical Board application image SHA-256: `748078a81138383f6b8d609bf5c6692820d5634ce0cd57b6b0fdc6052aa90c60`
- Exact image size: `1108896` bytes
- Historical readback window: `1109232` bytes; the extra `336` bytes were verified as `0xFF` padding and are not part of the exact application image.

## Failure symptom

Board A retained its stable node identity and could establish transport/authentication, but QoS1 telemetry was published under a predecessor system namespace. The active Broker/DynSec authority correctly allowed only the current system namespace, so those telemetry publishes were rejected.

The proved failure classification was:

```text
BOARD_A_ROOT_CAUSE=STALE_PREVIOUS_SYSTEM_NAMESPACE_PERSISTED_IN_BOARD_RUNTIME_STATE
BOARD_A_NODE_IDENTITY=CORRECT
BOARD_A_SYSTEM_NAMESPACE=STALE_PREVIOUS_SYSTEM
BROKER_CURRENT_DYNSEC_ROLE=CURRENT_SYSTEM_CORRECT
RESULT=QOS1_PUBLISH_NOT_AUTHORIZED
```

This proves stale predecessor namespace lineage in Board runtime state. It does **not** prove that exact NVS bytes were unchanged across historical flash operations, and it does not prove a firmware/product regression.

## Recovery

The recovery intentionally did not widen Broker ACLs and did not change the Manager system identity.

The bounded recovery sequence was:

1. preserve a pre-mutation NVS backup and bind the exact product application artifact;
2. invalidate only the scoped Board runtime peer/broker state required to leave the stale namespace lineage;
3. restore and verify the exact product application;
4. allow the normal product fresh-pairing bootstrap to produce a fresh private pairing handoff;
5. use the product existing-identity credential-recovery path to preserve the stable NODE_ID while advancing the MQTT credential generation;
6. verify the recovered runtime through the normal Board → Broker → Manager → canonical output path.

The live recovery completed with pairing epoch `8` and credential generation `8`; the stable node identity remained unchanged. Previously consumed authorizations are non-replayable.

## Physical validation evidence

### Broker-side current-namespace proof

The bounded Broker observability window proved:

- target-node QoS1 telemetry: `9`
- current-system QoS1 telemetry: `9`
- stale-system QoS1 telemetry: `0`
- other-system QoS1 telemetry: `0`
- current-system PUBACK success: `9`
- current-system PUBACK Not Authorized: `0`
- missing PUBACK: `0`

The temporary Broker debug configuration was restored exactly after the observation window:

- Broker config SHA-256 before: `a55c2479df1e9ff1d5547edf487f38e7a2edca0b57ccf5dfb7a590dd331a4848`
- Broker config SHA-256 after: `a55c2479df1e9ff1d5547edf487f38e7a2edca0b57ccf5dfb7a590dd331a4848`
- DynSec changeIndex before/after: `35 / 35`
- Broker restart count before/after: `0 / 0`

### Broker → Manager and Manager accepted-pipeline proof

Read-only follow-up proved:

- retained Board current-system QoS1 publishes: `9`
- Broker → Manager current-system QoS1 deliveries: `9`
- current Manager subscribe ACL: allowed at highest priority
- current Manager receive ACL: allowed at highest priority
- stale Manager system-ACL lineage: absent

A later fresh window proved the exact Manager → Broker MQTT socket stable in all `8/8` samples, with no Manager or Broker restart and no DynSec/config drift.

The retained bounded Broker debug evidence then proved the accepted application pipeline independently of the missing INFO log oracle:

- Board current-system Direct QoS1 cycles: `9`
- Board PUBACK success: `9`
- Manager canonical telemetry publishes: `9`
- Manager canonical telemetry QoS1 publishes: `9`
- Manager canonical retained publishes: `9`
- Manager availability publishes: `9`
- Manager availability QoS1 publishes: `9`
- Manager availability retained publishes: `9`
- Direct → canonical correlated cycles: `9`
- maximum observed Direct → canonical correlation latency: `87 ms`

Therefore:

```text
BOARD_A_CURRENT_SYSTEM_NAMESPACE_RECOVERY_PROVEN=true
BROKER_TO_MANAGER_DIRECT_DELIVERY_PROVEN=true
MANAGER_ACCEPTED_PIPELINE_PROVEN=true
BOARD_A_POST_RECOVERY_RUNTIME_LIVENESS=PASS
R2_BOARD_A_RUNTIME_LIVENESS=PASS
BOARD_A_R2_ADJUDICATION=PASS_AFTER_SCOPED_RUNTIME_NAMESPACE_RECOVERY
PRODUCT_REGRESSION_PROVEN=false
```

## Oracle and executor lessons

Several failures during the recovery chain were harness/oracle defects rather than product failures:

- Manager SQLite paths obtained from Manager environment variables are container-path authorities; host-side SQLite access must not assume those paths exist on the T1 host. Query inside the Manager container or explicitly translate through mounts.
- Current Broker selection must be derived from the live Manager MQTT endpoint and Docker network/listener binding, not from container/image-name heuristics.
- A flash readback window length must not be substituted for exact ESP image length; trailing erased padding is a separate oracle.
- Network/socket observations must be made from the correct network namespace. Broker-netns peer inference produced a false negative; Manager-netns matching against the Manager-resolved Broker endpoint produced the authoritative result.
- Absence of the `Accepted simplified N3-W telemetry` INFO line was a false-negative logging oracle. Canonical/replay state and Manager canonical/availability publishes proved the accepted path actually executed.

## KNOWN_FAILURES disposition

This closeout accompanies the following KNOWN_FAILURES changes:

- add `KF-083`: Board runtime stale predecessor-system namespace residue — `SECURITY`, `RESOLVED`;
- add `KF-084`: exact firmware rebuild byte non-reproducibility — `INFRASTRUCTURE`, `OPEN`, root cause `TBD`;
- extend `KF-010` with the Board A accepted-log false-negative oracle case;
- extend `KF-045` with the Manager container-path vs host-path SQLite authority recurrence;
- extend `KF-057` with exact-image-size vs readback-window separation;
- extend `KF-058` with network-namespace socket authority;
- extend `KF-071` with current Broker endpoint authority binding.

## Route closure

Board A is closed PASS. This document does not authorize an automatic Board B switch. The next board remains behind a separate sequential gate.
