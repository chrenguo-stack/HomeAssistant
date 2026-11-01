# N3-W P5 M03 live acceptance status and M04 entry baseline

Date: 2026-08-09

Status: `N3W_P5_M03_PASS_M04_PENDING_PROHIBITED`

## Scope

This sanitized public status records the completed M03 Relay-to-Direct acceptance and defines the entry baseline for M04 duplicate handling.

It is limited to a Draft PR based on exact main `ec45cdf249b34b7982aa68cb668805d351046ed6`. It is not M04 package, claim, execution, Ready, merge, deployment, release, or tag authorization.

## M03 acceptance result

M03 reached terminal PASS under its separate, exact private execution and closure controls:

- exactly one path-control publish changed the active path from Relay to Direct;
- the active Relay gateway was cleared after the switch;
- boot identity remained continuous;
- accepted canonical sequence remained monotonic;
- accepted tuples remained unique;
- no canonical rollback was observed;
- post-switch Direct canonical continuity was observed;
- no Relay-gateway frame was observed after the path-control publish;
- the final old-path observation stayed within the configured five-second grace window;
- no AEAD failure was observed;
- Manager, Broker, and Home Assistant restart counts remained zero;
- the confirmed physical state was preserved.

Private terminal, package, evidence, device-identity, and raw-trace values remain private and are not reproduced here.

## N3-W phase status

The matrix is complete through M03 only. N3-W phase exit is not ready.

- M03: `terminal_pass`;
- M04: `pending_prohibited`;
- M05–M14: `pending_prohibited`;
- next required matrix: M04.

M03 evidence does not satisfy or authorize M04 or any later matrix.

## M04 duplicate-handling entry baseline

The intended M04 candidate is the last saved Relay tuple while Direct remains the active path.

The acceptance rule is tuple-specific:

1. the resent Relay tuple may be observed at gateway ingress;
2. it must not create a second canonical record for the same tuple;
3. the active path must remain Direct;
4. unrelated new Direct telemetry may continue to advance the global canonical sequence.

Therefore, M04 must not interpret a normally advancing global sequence as duplicate failure. The controlling invariant is that the resent tuple is not canonicalized twice.

Current M04 state:

- no M04 package has been generated;
- no M04 package has been claimed;
- no M04 execution has started;
- no RESEND has been sent;
- M04 remains prohibited until a separate exact authorization.

## Public safety boundary

This status contains no credential, device identifier, private evidence hash, Factory-image hash, private package or terminal hash, raw live trace, or replayable authorization.

Its preparation performs no live-environment access, MQTT publish, path command, RESEND, board access, USB or serial access, Flash/erase/OTA, power change, service restart or mutation, production-network access, lab-init, deployment, release, or tag action.

## Next gate

Review this Draft PR at its exact head and review its CI result. Any Ready transition or merge requires a separate authorization.

M04 package preparation and M04 execution each require their own future exact authorization.
