# N3-W / P5 / M04 ESP32-C6 post-flash startup incident archive

Date: 2026-08-10

Status: `SANITIZED_INCIDENT_ARCHIVE_M04_NOT_ACCEPTED`

## Purpose

This document preserves a public, sanitized engineering incident observed during
N3-W / P5 / M04 physical replacement work on two independent ESP32-C6 devices.
It records the operational distinction between a post-write hard reset and a true
cold power-on without exposing private device identities or live evidence.

This archive is documentation only. It does not authorize board access, serial
access, reset, power changes, Flash or erase operations, MQTT publication, PATH or
RESEND commands, service mutation, M04 acceptance, or M05 entry.

## Archival baseline

This draft was prepared against exact public repository baseline:

- repository: `chrenguo-stack/HomeAssistant`;
- `main`: `9ff26629146fe2c1056f52e269c044a135306772`;
- tree: `5cbe98c4e5838fb64378093691997423e3b65149`;
- PR #301: merged into that `main`;
- PR #302: remains an older Draft pause archive and is not the current M04 state source.

The baseline above is an archival binding only. If `main` changes before the
separately authorized documentation commit, the mutation must stop and be freshly
rebound.

## Incident summary

The same post-write startup failure class was observed on two independent ESP32-C6
devices serving different P5 roles.

For each occurrence:

1. the frozen full-image write completed successfully;
2. independent image verification completed successfully;
3. a hard reset was issued after the verified write;
4. expected application/network liveness did not recover after that hard reset;
5. no new image was written and no erase operation was performed during recovery;
6. exactly one complete USB power removal followed by cold power-on restored
   liveness.

The first occurrence was on the Relay role. After the single cold power cycle, the
Relay resumed application output and the isolated environment again showed stable
sessions for both devices.

The second occurrence was on the Child role. After the single cold power cycle, new
Child telemetry resumed and the isolated environment again showed stable sessions
for both devices.

## Engineering conclusion

The observed P5 replacement sequence establishes the following operational rule:

`hard reset issued != application boot proven`

A successful image write, successful verification, and issuance of a hard reset are
not sufficient by themselves to prove the application has reached an accepted live
state.

For this workflow, the safer physical replacement sequence is:

`write -> verify -> no-reset -> separate startup/liveness gate`

The startup/liveness gate must independently prove the expected application and
network behavior before the replacement is accepted.

## What this incident does and does not establish

The repeated recovery on two independent devices, without changing Flash contents,
makes a bad image write, a false verification result, a single-board hardware defect,
or a role-specific application defect poor primary explanations for these two
observations.

The incident does **not** establish a specific ESP32-C6 silicon, ESP-IDF, USB
Serial/JTAG, reset-domain, power-domain, Wi-Fi, or radio-runtime root cause. Those
remain possible investigation areas rather than proven causes.

## Process change retained from the incident

Future P5 physical replacement work should preserve these invariants:

- write success is recorded separately from application startup success;
- image verification is recorded separately from application startup success;
- a hard reset event is not accepted as proof of boot or network liveness;
- startup/liveness is a separate gate with its own observation window and terminal
  outcome;
- cold power cycling, if ever required, is separately authorized and bounded;
- consumed physical gates are never replayed to obtain a different result;
- live recovery evidence remains private and is not reproduced in the public archive.

## Public/private boundary

This archive intentionally excludes:

- raw board MAC addresses or other private device identifiers;
- local serial device paths;
- private image or execution-package digests;
- private terminal or evidence digests;
- raw serial or network traces;
- credentials, keys, session material, or private endpoint identity;
- replayable physical authorization or READY text.

Private immutable records remain the authoritative source for exact device identity,
execution binding, and live evidence.

## M04 state boundary

This documentation archive does not close M04.

At the time of this draft:

- `M04_ACCEPTED=false`;
- the Relay is to remain untouched in its current running state;
- the Child's previously authorized exactly-one RESET is consumed and must not be
  repeated;
- PATH and RESEND are not authorized;
- M05 remains prohibited.

After this archive is committed under a separate documentation-only authorization,
the next live action, if separately approved after a fresh no-drift rebaseline, is a
Child-only exactly-one USB full power cycle with read-only recovery observation. It
must not include a RESET, serial access, Flash/erase, active MQTT publication, PATH,
RESEND, service restart, or any Relay power/action change.
