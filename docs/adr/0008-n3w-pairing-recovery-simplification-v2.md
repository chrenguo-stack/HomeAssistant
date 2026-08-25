# ADR-0008: N3-W pairing and recovery simplification V2

- Status: accepted / architecture contract freeze
- Date: 2026-08-25
- Scope: N3-W product pairing, recovery and local Setup Secret intake
- Supersedes: pairing-epoch and successor-helper recovery authority added after ADR-0007

## Decision

Pairing/session recovery is a transaction lifecycle. It is not an MQTT
credential rotation, N3-W application-key rotation, or system-trust rotation.

```text
PAIRING / SESSION RECOVERY
    != MQTT CREDENTIAL ROTATION
    != N3W APPLICATION-KEY ROTATION
    != SYSTEM TRUST ROTATION
```

The device durable `pairing_epoch` and pairing epoch as an anti-replay or
correctness authority are product deletion targets. A Manager may retain a
`pairing_attempt_no` solely as audit metadata. It is not sent to the device and
does not enter the crypto transcript, pairing ID, anti-replay decisions,
credential generation, application-key epoch, or recovery correctness.

Each fresh pairing transaction uses a device-generated CSPRNG `pairing_id` with
at least 128 random bits. A pending intent containing that ID and the Setup
Secret may be durable only until pairing commits, so a reboot can continue the
same QR transaction. A retry terminates or expires the old transaction and
creates a fresh random transaction; it does not increment a distributed epoch.
Terminal pairing IDs remain replay tombstones and can never become active again.

## Independent security lifecycles

The first MQTT credential generation is 1. Normal pairing retries and ordinary
repair pairing reuse a safe active credential and do not stage or rotate one.
Only compromise, unrecoverable credential loss, explicit operator security
rotation, retirement, or revocation enters the MQTT credential lifecycle.

The N3-W application-key lifecycle is independently versioned. Pairing and
MQTT generations neither select nor advance its epoch. Only its explicit key
rotation contract advances it.

`SYSTEM_PEER_KEY` and `PEER_TRUST_GENERATION` retain ADR-0007 semantics. Reboot,
Wi-Fi loss, Relay switching, pairing retry, adding a node, and ordinary
non-compromise retirement do not rotate them. A real compromise or explicit
security event may rotate them.

## Transaction and commit boundary

The product pairing path is:

```text
UNPAIRED
-> PAIRING_PENDING
-> secure Setup Secret proof-of-possession
-> BUNDLE_DELIVERED
-> node durable persistence
-> one final delivery digest receipt
-> Manager COMMIT
-> PROVISIONED
```

The HMAC proof remains bound to hardware ID, random pairing ID, Manager
identity, and both nonces. HKDF and encrypted credential delivery remain. A
failure before the final receipt must not leave partially active credentials.
The receipt is the one transactional acknowledgement; additional timing floors,
successor generations, and physical recovery states are not product authority.

## Product Setup Secret interface

The filesystem Setup Secret inbox is `LAB_ONLY` compatibility code and is not
enabled by the default product composition. The product interface is a
Manager-owned local Unix domain socket, normally:

```text
/run/greenhouse-manager/pairing.sock
```

The Manager creates, owns, permissions, and removes the socket. A bounded local
request supports only `import_setup_secret` and contains exactly `schema`,
`hardware_id`, `pairing_id`, and `setup_secret`. The Manager synchronously
accepts or rejects through the existing coordinator. The secret is not logged,
written to a staging file, or persisted by the IPC layer. The path is absolute,
local-only and rejected on symlink ambiguity. CLI/UI clients call this IPC and
never write SQLite directly.

## Identity, replay and retirement

`HARDWARE_ID` remains stable. An active node keeps its stable automatically
assigned `NODE_ID` during an ordinary repair. Retired or revoked hardware and
cross-node identity mismatches remain fail-closed. Pairing replay tombstones are
separate from telemetry replay protection: durable monotonic `BOOT_ID`, `SEQ`,
and the Manager canonical high-water remain unchanged.

## Legacy recovery classification

Pairing-epoch successor helpers and helper-to-product app swaps are
`LEGACY_MIGRATION_ONLY`, `ENGINEERING_MIGRATION_ONLY`, or `BOARD_LAB_ONLY`.
They may remain quarantined for historical compatibility evidence, but normal
product code and Final Product Acceptance must not import or execute them.
Epoch 6 -> 7 -> 8 is not a product recovery roadmap.

Legacy Board B migration is a non-blocking compatibility test. FC4 Final
Product Acceptance proceeds from clean product state and does not depend on a
legacy Board B migration or helper flow.

## Protected physical execution governance

Any later protected physical executor follows:

```text
PRECHECK -> READY -> CLAIM -> EXECUTE -> VERIFY -> TERMINAL
```

Exact source/tree/artifact binding, Python and imports, serial availability,
SSH round trip, read-only Manager snapshot, Docker, permissions, restore
artifacts/commands, and any board binding execute before `CLAIM`. A precheck
failure means `CLAIM=false`, `MUTATION=false`, and `SESSION_CONSUMED=false` and
does not create a new pairing epoch, successor identity, or physical state.

## Retained security properties

Stable hardware/NODE identity, per-node MQTT credentials and Broker ACLs,
Setup Secret PoP, HMAC, HKDF, encrypted delivery, final receipt, SYSTEM_ID,
long-lived system peer trust, pair-specific LMKs, authenticated ESP-NOW,
BOOT_ID/SEQ high-water replay protection, latest-valid-wins, explicit security
rotation, retirement/revocation rejection, redaction, private-source handling,
and fail-closed behavior are retained.

Ordinary telemetry and Relay architecture are unchanged: one authenticated
frame, one send attempt, loss accepted, next sample advances state, and
multi-ingress `NODE_ID + BOOT_ID + SEQ` latest-valid-wins. Transport path remains
diagnostic metadata and never becomes ownership authority.
