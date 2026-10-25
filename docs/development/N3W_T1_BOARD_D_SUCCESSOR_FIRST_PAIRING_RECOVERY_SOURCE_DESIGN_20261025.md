# N3W T1 Board D successor first-pairing recovery source design — 2026-10-25

## 1. Scope

This design follows the failed Board D first secure pairing attempt recorded in Issue #670 and the container-ID round-trip repair merged by PR #672.

It does not authorize any live T1 or Board mutation by itself.

Current live facts are:

- the original onboarding authorization was consumed and is not replayable;
- the original pairing window was manually closed and the exposure was proven closed;
- Broker, Manager, and Home Assistant remained running with restart_count=0;
- Setup Secret import never occurred;
- node_id allocation never occurred;
- credential, application-key, and peer-trust state all remain zero;
- the Manager registration database contains one never-approved registration;
- five pairing sessions exist for one hardware identity;
- four sessions are terminal expired;
- the current fifth session is still stored as pending but is already expired by clock;
- no node_id lease exists.

The recovery goal is to make a later fresh first-pair authorization possible without deleting replay history, clearing Board NVS, flashing firmware, or restarting Broker/Manager/Home Assistant.

## 2. Existing product authority

The existing product recovery semantics are retained:

- `RegistrationRegistry.abandon_expired_first_registration()` is the authority for releasing only an expired, never-approved first-registration current pointer.
- The old pairing session remains an immutable replay tombstone.
- The recovery action is recorded as a separate `expired_first_registration_abandoned` event with reason `expired_first_pairing_recovery`.
- Existing node assignment history, node leases, retirement state, or credential history make the recovery ineligible.
- ADR-0008 remains authoritative: a retry uses a fresh device-generated random pairing ID, while terminal pairing IDs remain replay tombstones.

The historical FC4 executor required stopping Manager before mutating the database externally. That execution wrapper is not reused for the current production architecture because normal pairing and recovery must preserve Broker/Manager/Home Assistant continuity.

## 3. New recovery architecture

The successor recovery is split from the later pairing attempt.

### Gate A — successor recovery

A new one-shot recovery authorization is required.

Before claim, the executor must prove:

- source/tool binding is exact;
- the predecessor onboarding transaction exists;
- predecessor authorization_claimed=true;
- predecessor authorization_consumed=true;
- predecessor replay_allowed=false;
- predecessor deadline is elapsed;
- Manager-owned pairing window is CLOSED;
- UDP/47111 and TCP/47112 are closed;
- pairing.sock is absent;
- Broker/Manager/Home Assistant identities and restart counts still match the predecessor baseline;
- exactly one current registration exists;
- current registration has no node_id or logical location;
- the current pairing session belongs to that registration;
- the current session is either already expired or pending with expires_at earlier than current time;
- every pairing session belongs to the same hardware identity;
- no pairing session is approved;
- node_id_leases=0;
- credential assignments=0;
- active application-key nodes=0;
- application-key epochs=0;
- peer-trust records=0.

After durable claim of the new recovery authorization, Manager performs the recovery in-process through the existing local pairing-control socket.

The Manager operation must:

1. require the dynamic pairing window to be CLOSED;
2. bind the target using hardware-ID SHA256 and pairing-ID SHA256;
3. if the exact current session is pending but expired by clock, transition only that exact session to expired and record the normal expiry audit event;
4. call the existing `abandon_expired_first_registration()` product method;
5. preserve the expired session and all earlier sessions/events;
6. return only sanitized hashes and booleans.

After Manager recovery succeeds, the T1 onboarding executor must prove:

- registrations=0;
- node_id_leases=0;
- the exact predecessor pairing session remains state=expired reason=expired;
- `expired_first_registration_abandoned / expired_first_pairing_recovery` is present;
- all four security-state counts remain zero;
- Broker/Manager/Home Assistant identities and restart counts are unchanged;
- pairing window remains CLOSED;
- 47111/47112 remain closed;
- pairing.sock remains absent.

Only then may the predecessor onboarding transaction be moved byte-for-byte into a private archive path. It must not be rewritten as success or made replayable.

The recovery authorization then closes PASS. It does not open a pairing window.

### Gate B — fresh first-pair attempt

Gate B requires a separate new first-pair authorization.

The normal onboarding tool may admit preserved recovery history only when:

- no current registration exists;
- no node_id lease exists;
- all pairing sessions are terminal tombstones;
- no event contains an assigned node_id;
- the successor recovery record is CLOSED_PASS and binds the preserved predecessor transaction;
- all security-state counts remain zero.

The new onboarding transaction must be independent from the predecessor authorization.

When the new dynamic pairing window opens, Board D may first present its old current pairing ID. Manager must reject that tombstoned identity as terminal replay/expiry. Existing firmware then generates and durably persists a fresh random pairing ID before retrying. No Board NVS reset is required.

## 4. Manager implementation boundary

The running Manager already owns the persistent `RegistrationRegistry` used by normal N3-W runtime. The dynamic pairing controller must receive this same registry instance.

The pairing-control socket gains one local-only recovery operation. It must not accept raw Setup Secret material and must not expose raw hardware ID or pairing ID in its response.

The recovery operation must not:

- recreate or restart Manager;
- stop Broker or Home Assistant;
- delete pairing_sessions;
- delete registration_events;
- modify credential assignments;
- rotate MQTT credentials;
- modify application keys;
- modify peer trust;
- open the pairing window.

## 5. Onboarding transaction boundary

The predecessor onboarding transaction remains immutable forensic evidence.

The successor recovery uses a separate private recovery record so the new recovery authorization is durably claimed before any state mutation.

After recovery PASS:

- predecessor transaction is archived byte-for-byte;
- recovery record remains durable and non-replayable;
- no new pairing transaction exists yet.

A later Gate B authorization creates a new onboarding transaction.

## 6. Required regression coverage

Tests must cover:

- exact pending session can be expired individually only after its deadline;
- non-expired pending session is rejected;
- approved/rejected/non-current identity is rejected;
- expired first registration can be abandoned without deleting tombstones;
- credential history or prior node assignment blocks recovery;
- recovery control request is accepted only while window=CLOSED;
- recovery control request uses SHA256 identity binding and never returns raw IDs;
- running Manager stays alive through recovery;
- Broker/Manager/Home Assistant restart semantics are unchanged;
- onboarding successor recovery claims before mutation;
- predecessor transaction remains non-replayable;
- predecessor transaction archive is byte-identical;
- partial recovery failure never opens a pairing window;
- historical tombstones are accepted for a later fresh first-pair gate only after recovery CLOSED_PASS;
- any security-state residue blocks fresh first-pair admission.

## 7. Live boundary

No live recovery is authorized by this source design.

Before any future live mutation, exact source must be reviewed, CI must pass, a fresh read-only T1 snapshot must reproduce the eligibility state, and a new explicit successor-recovery authorization must be granted.

After recovery PASS, a second explicit authorization is still required for the next Board D first-pair window.
