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

## 3. Safety properties

- The probe does not publish synthetic telemetry.
- The 90-second passive window remains as a bounded fallback.
- The candidate must already have passed authenticated identity, password mount,
  stable MQTT socket, and ingress subscription checks.
- The later Discovery retained-state and entity-continuity checks remain
  mandatory.
- Any missing, mismatched, or timed-out evidence fails closed and triggers the
  existing mandatory manager rollback.
- Mosquitto, Home Assistant, nodes, anonymous compatibility, and node credential
  state remain outside the mutation scope.

## 4. Version

This evidence model is introduced in greenhouse-manager 0.4.76 following the
verified V58 rollback and V59 read-only audit.
