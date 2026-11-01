# T1 Manager retained recovery evidence v1

## 1. Problem statement

The manager production probe previously required an INFO log matching a fresh
`Accepted telemetry node=<node_id>` event. The bound N1 node normally publishes
once every 60 seconds, so version 0.4.75 increased the passive window to 90
seconds. The real T1 V58 transaction still timed out and rolled back safely.

The manager also subscribes to retained canonical telemetry at every startup.
When the retained document is valid, the manager restores the node state and
publishes the exact Home Assistant Discovery document. That startup recovery is
a valid continuity path even when no new node packet arrives during the
transaction window.

## 2. Accepted canonical evidence

After the authenticated candidate container start time, the production probe
may accept either of these exact, node-bound paths:

1. fresh ingress evidence: `Accepted telemetry node=<node_id> ...`;
2. retained recovery evidence: `Published Home Assistant discovery
   node=<node_id> topic=<exact discovery topic>`.

Either path must be followed by a read-only fetch of the exact canonical
telemetry retained topic, whose JSON `node_id` must equal the bound node.
Unrelated nodes or Discovery topics do not satisfy the gate.

## 3. Availability continuity

Availability is a node lifecycle state, not a manager health state. The exact
retained availability document must always contain the bound `node_id`.

- After fresh ingress evidence, the exact availability state must be `online`,
  because accepting fresh telemetry publishes online availability in the same
  processing transaction.
- After retained recovery evidence, `online` is valid when the restored
  canonical timestamp is still within the manager stale window.
- After retained recovery evidence, `unavailable` is valid only after the
  authenticated candidate emits the exact post-start log
  `Published unavailable state topic=<exact availability topic>` and a second
  read confirms the retained document remains bound to the same node and state.
- Any other state, wrong node, wrong topic, missing log, malformed JSON, or
  timeout fails closed.

This distinction prevents an offline or stale node from blocking manager
identity migration while still proving that the candidate restored and
maintained the exact node lifecycle path. It does not reinterpret an offline
node as online.

## 4. Safety properties

- The probe does not publish synthetic telemetry or availability.
- The 90-second passive window remains as a bounded fallback.
- The candidate must already have passed authenticated identity, password mount,
  stable MQTT socket, and ingress subscription checks.
- The later Discovery retained-state and entity-continuity checks remain
  mandatory.
- Any missing, mismatched, or timed-out evidence fails closed and triggers the
  existing mandatory manager rollback.
- Mosquitto, Home Assistant, nodes, anonymous compatibility, and node credential
  state remain outside the mutation scope.

## 5. Version

The canonical recovery evidence model was introduced in greenhouse-manager
0.4.76 following the verified V58 rollback and V59 read-only audit.

The availability-continuity extension is introduced in greenhouse-manager
0.4.77 following the verified V64 rollback and V65 read-only audit, which
localized the next gate failure to `availability_publication` while confirming
that canonical retained recovery had already passed.
