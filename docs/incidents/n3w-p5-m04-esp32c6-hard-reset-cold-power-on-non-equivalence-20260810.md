# N3-W / P5 / M04 ESP32-C6 post-flash startup incident archive

Date: 2026-08-10

Status: `SANITIZED_INCIDENT_ARCHIVE_M04_NOT_ACCEPTED`

## Purpose

This document preserves a public, sanitized engineering incident observed during
N3-W / P5 / M04 physical replacement work on two independent ESP32-C6 devices,
including a later recurrence on the Child successor.

It records the operational distinction between a post-write hard reset and a true
cold power-on without exposing private device identities, raw live traces, or
replayable authorization material.

This archive is documentation only. It does not authorize board access, serial
access, reset, power changes, Flash or erase operations, MQTT publication, PATH or
RESEND commands, service mutation, M04 acceptance, or M05 entry.

## Archival baseline

This draft remains bound to the exact public repository baseline:

- repository: `chrenguo-stack/HomeAssistant`;
- `main`: `9ff26629146fe2c1056f52e269c044a135306772`;
- tree: `5cbe98c4e5838fb64378093691997423e3b65149`;
- PR #301: merged into that `main`;
- PR #302: remains an older Draft pause archive and is not the current M04 state source.

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

## Process change retained from the incident

Future P5 physical replacement work should preserve these invariants:

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
- live recovery evidence remains private and is not reproduced in the public archive.

## Public/private boundary

This archive intentionally excludes:

- raw board MAC addresses or other private device identifiers;
- local serial device paths;
- private image or execution-package digests;
- private terminal or evidence digests;
- raw serial or network traces;
- raw live sequence/revision values;
- credentials, keys, session material, or private endpoint identity;
- replayable physical authorization or READY text.

Private immutable records remain the authoritative source for exact device identity,
execution binding, and live evidence.

## M04 state boundary

This documentation archive does not close M04.

At the time of this update:

- `M04_ACCEPTED=false`;
- the current Child runtime is separately observed as recovered on the Direct path;
- the Relay remains running and must remain untouched;
- the Child's earlier exactly-one RESET remains consumed and must not be repeated;
- the later Child cold-power execution gate remains
  `CONSUMED_FAILED_EXECUTION_BOUNDARY_VIOLATION` and is non-replayable;
- the post-terminal forensic fact is `CHILD_COLD_POWER_RECOVERY_CONFIRMED`;
- PATH and RESEND are not authorized by this archive;
- M05 remains prohibited.

After this archive update and a fresh no-drift rebaseline, the next live decision may
consider a new, separately authorized exactly-one RESEND observation. This archive
does not authorize that action.
