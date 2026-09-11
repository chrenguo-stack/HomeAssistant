# N3-W / P5 ESP32-C6 post-flash startup incident and M04/M05 closure archive

Date: 2026-08-10

Status: `SANITIZED_INCIDENT_ARCHIVE_M05_PASS`

## Purpose

This document preserves a public, sanitized engineering incident observed during
N3-W / P5 / M04 physical replacement work on two independent ESP32-C6 devices,
including a later recurrence on the Child successor, the subsequent M04 closure,
and the M05 reordered-fragment live validation.

It records the operational distinction between a post-write hard reset and a true
cold power-on without exposing private device identities, raw live traces, or
replayable authorization material.

This archive is documentation only. It does not authorize board access, serial
access, reset, power changes, Flash or erase operations, MQTT publication, PATH,
RESEND, or REORDER commands, service mutation, or M06 entry.

## Archival baseline

This draft remains bound to the exact public repository baseline:

- repository: `chrenguo-stack/HomeAssistant`;
- `main`: `9ff26629146fe2c1056f52e269c044a135306772`;
- tree: `5cbe98c4e5838fb64378093691997423e3b65149`;
- PR #301: merged into that `main`;
- PR #302: remains an older Draft pause archive and is not the current M04/M05 state source.

The baseline above is an archival binding only. A future mutation must stop and be
freshly rebound if `main` or the Draft PR state changes before that mutation.

## Original incident observations

The same post-write startup failure class was first observed on two independent
ESP32-C6 devices serving different P5 roles.

For those two original occurrences:

1. the frozen full-image write completed successfully;
2. independent image verification completed successfully;
3. a hard reset was issued after the verified write;
4. expected application/network liveness did not recover after that hard reset;
5. no new image was written and no erase operation was performed during recovery;
6. exactly one complete USB power removal followed by cold power-on restored
   liveness.

The first occurrence was on the Relay role. After its bounded cold power cycle, the
Relay resumed application output and the isolated environment again showed stable
sessions for both devices.

The second occurrence was on the Child role. After its bounded cold power cycle, new
Child telemetry resumed and the isolated environment again showed stable sessions
for both devices.

## Later Child successor recurrence

After the initial archive draft, the same startup class recurred on the Child
successor.

A separately bounded exactly-one application-start reset had already been consumed
without recovering Child network presence. A later Child-only recovery action then
performed one complete USB power removal and kept the Child fully unpowered for the
required interval. The Relay remained untouched. No reset, serial access,
Flash/erase, MQTT publication, PATH, RESEND, or service mutation was performed during
that recovery action.

The physical execution gate itself remains permanently recorded as
`CONSUMED_FAILED_EXECUTION_BOUNDARY_VIOLATION`. Its executor did not capture the
required reconnect confirmation before terminal closure, so the gate is not and must
not be retroactively reclassified as PASS. The executor therefore does not prove the
reconnect count or same-port condition.

That execution terminal is separate from the later runtime fact. The operator later
reported that the Child was physically connected. A host-only read-only forensic
capture then observed all of the following:

- Child network presence was visible;
- a Child-to-Broker TCP session was visible;
- multiple valid Direct Child telemetry messages were observed;
- canonical state progressed within the current live session;
- the active path remained Direct with no candidate path;
- the Relay remained present and unchanged;
- Manager, Broker, and Home Assistant remained stable without restart.

This post-terminal evidence therefore records the separate forensic fact
`CHILD_COLD_POWER_RECOVERY_CONFIRMED` while leaving the consumed execution gate
unchanged.

Raw sequence/revision values, endpoint identities, device identities, credentials,
and private evidence digests are intentionally omitted. Recovery is described by
within-session progression rather than by comparing a new boot/session sequence
number to a historical sequence baseline.

## M04 closure

After the Child successor had recovered onto a stable Direct path, a fresh read-only
field rebaseline confirmed continued natural Direct telemetry, current-session
canonical progression, stable Child and Relay network presence, stable Manager,
Broker, and Home Assistant services, and preserved production-network isolation.

A new separately authorized exactly-one RESEND observation was then performed. That
authorization was claimed once, consumed once, and is permanently non-replayable.
The live observation established the following sanitized facts:

- exactly one RESEND command attempt was made;
- the Relay/Gateway path emitted exactly one cached Relay-form frame matching the
  Direct tuple selected immediately before the RESEND;
- no unexpected different Gateway tuple was observed in that bounded observation;
- newer Direct telemetry continued after the cached replay;
- the active path remained Direct and no candidate path appeared;
- the duplicate Relay replay did not switch path ownership or regress canonical
  state;
- Child and Relay network presence remained stable;
- Manager, Broker, and Home Assistant remained stable;
- production-network isolation remained preserved.

The unique PASS terminal from that live observation was subsequently frozen into
private immutable evidence and verified by readback before filesystem write
protection. The public archive intentionally does not reproduce the private evidence
digest, raw tuple values, raw sequence/revision values, device identities, endpoint
identity, credentials, keys, or live traces.

The resulting M04 terminal state is:

`M04_ACCEPTED=true`

`M04_TERMINAL=PASS`

The exactly-one M04 RESEND is consumed and must not be repeated.

## M05 reordered-fragment closure

After M04 closure, a separate M05 preexecution read-only rebaseline confirmed that
the current Child/Relay field state was still stable, the active path was Direct with
no candidate path, production isolation remained intact, and the current cached
Relay-form frame was large enough to require multiple ESP-NOW fragments. No Gateway
frame was present during that preexecution observation.

A separately authorized exactly-one REORDER live observation was then claimed once
and consumed once. The REORDER contract was source-bound to retransmitting the most
recent cached Relay-form datagrams in reverse fragment order without allocating a new
canonical telemetry tuple or changing the requested path.

The bounded M05 observation established the following sanitized facts:

- exactly one REORDER command attempt was made;
- the selected cached Relay-form frame consisted of multiple fragments, so reversed
  ordering was a meaningful test rather than a single-fragment no-op;
- the Relay successfully reassembled the reversed fragment delivery into the same
  cached Relay-form frame and emitted exactly one matching Gateway ingress frame;
- no unexpected different Gateway tuple was observed in the bounded observation;
- newer Direct telemetry continued after the reordered replay;
- the active path remained Direct and no candidate path appeared;
- the duplicate Relay replay did not switch path ownership or regress canonical
  state;
- Child and Relay network presence remained stable;
- Manager, Broker, and Home Assistant remained stable;
- production-network isolation remained preserved.

This is a source-bound reverse-order reassembly validation. It does not claim an
independent radio sniffer capture of the over-the-air fragment arrival sequence.

The unique M05 PASS terminal was subsequently frozen into separate private immutable
evidence. The freeze verified exact readback, content-address binding, read-only file
modes, and non-overwrite semantics without issuing any additional MQTT publication,
REORDER, RESEND, PATH, board, USB, serial, reset, power, Flash, service, Relay
hardware, or GitHub mutation.

The public archive intentionally omits the private evidence digest and path, raw live
tuple values, raw sequence/revision values, boot/session identity, device identity,
endpoint identity, credentials, PMK/LMK/application keys, and other private material.

The resulting M05 terminal state is:

`M05_ACCEPTED=true`

`M05_TERMINAL=PASS`

The exactly-one M05 REORDER is consumed and permanently non-replayable.

## Engineering conclusion

The accumulated P5 observations retain the operational rule:

`hard reset issued != application boot proven`

A successful image write, successful verification, and issuance of a hard reset are
not sufficient by themselves to prove that the application has reached an accepted
live state.

For this workflow, the safer physical replacement sequence remains:

`write -> verify -> no-reset -> separate startup/liveness gate`

Startup/liveness must be proved independently. A cold power cycle, if ever needed,
must remain separately authorized and bounded, and its execution terminal must not be
rewritten after consumption.

M04 additionally confirms the repaired Direct/Relay cache contract: successful
Direct publication can prime the Relay-form resend cache transactionally, and a
separately authorized cached replay can be recognized as the same canonical tuple
without switching the active Direct path.

M05 additionally confirms the bounded multi-fragment reorder contract: the cached
Relay-form datagrams can be delivered in reverse fragment order, reassembled by the
Relay into the same frame, and rejected as a duplicate at the canonical/path layer
without displacing the active Direct path.

## What this incident does and does not establish

The repeated behavior across two independent devices, with a later recurrence on the
Child successor and recovery without changing Flash contents, makes a bad image
write, a false verification result, a single-board hardware defect, or a role-only
application defect poor primary explanations for these observations.

The incident does **not** establish a specific ESP32-C6 silicon, ESP-IDF, USB
Serial/JTAG, reset-domain, power-domain, Wi-Fi, or radio-runtime root cause. Those
remain investigation areas rather than proven causes.

The later recurrence also does not prove that every hard reset will fail or that
every cold power-on will recover the device. It establishes only the repeated
non-equivalence observed in this bounded P5 work.

The M05 result does not establish an independent over-the-air capture of fragment
ordering; it establishes the source-bound REORDER behavior together with successful
multi-fragment Relay reassembly and the resulting end-to-end state invariants.

## Process change retained from the incident

Future P5 physical replacement and live-validation work should preserve these
invariants:

- write success is recorded separately from application startup success;
- image verification is recorded separately from application startup success;
- a hard reset event is not accepted as proof of boot or network liveness;
- startup/liveness is a separate gate with its own observation window and terminal
  outcome;
- cold power cycling, if ever required, is separately authorized and bounded;
- consumed physical gates are never replayed or retroactively reclassified;
- execution-gate terminal state and later forensic runtime facts are recorded
  separately;
- cross-boot recovery is judged from current-session evidence rather than historical
  sequence-number magnitude alone;
- exactly-one live mutation authorizations remain non-replayable after claim;
- REORDER validation must use a genuinely multi-fragment cached frame when the goal
  is to test out-of-order fragment reassembly;
- live recovery and validation evidence remains private and is not reproduced in the
  public archive.

## Public/private boundary

This archive intentionally excludes:

- raw board MAC addresses or other private device identifiers;
- local serial device paths;
- private image or execution-package digests;
- private terminal or evidence digests;
- private immutable-evidence filesystem paths;
- raw serial or network traces;
- raw live sequence/revision, boot/session, or tuple values;
- credentials, PMK, LMK, application keys, other keys, session material, or private
  endpoint identity;
- replayable physical or live authorization/READY text.

Private immutable records remain the authoritative source for exact device identity,
execution binding, and live evidence.

## M04/M05 state boundary

M04 and M05 are now closed successfully:

- `M04_ACCEPTED=true`;
- `M04_TERMINAL=PASS`;
- `M05_ACCEPTED=true`;
- `M05_TERMINAL=PASS`;
- the current Child runtime remained on the Direct path through both closures;
- the Relay remained running and physically untouched during the M04 RESEND and M05
  REORDER validations;
- the Child's earlier exactly-one RESET remains consumed and must not be repeated;
- the later Child cold-power execution gate remains
  `CONSUMED_FAILED_EXECUTION_BOUNDARY_VIOLATION` and is non-replayable;
- the post-terminal forensic fact remains `CHILD_COLD_POWER_RECOVERY_CONFIRMED`;
- the M04 exactly-one RESEND is consumed PASS and must not be repeated;
- the M05 exactly-one REORDER is consumed PASS and must not be repeated;
- both M04 and M05 unique live PASS terminals are frozen in private immutable
  evidence;
- PATH, RESEND, and REORDER are not authorized by this archive;
- M06 has not been authorized.

Any M06 action requires a new, separate decision and authorization. This archive does
not authorize that action.
