# N3-W / P5 / M04 development pause handoff

Date: 2026-08-09

Status: `DEVELOPMENT_PAUSED_PR301_DRAFT_CI_PASS_M04_NOT_ACCEPTED`

## Purpose

This document freezes a public, sanitized, recoverable development checkpoint for
N3-W / P5 / M04. Development is intentionally paused after the host-only repair in
PR #301 reached a green exact-head CI result.

This archive is documentation only. It is not authorization to mark PR #301 Ready,
merge it, build or claim an execution package, access either board, send a RESEND or
path-control command, perform a live check, or enter M05.

## Exact GitHub checkpoint

| Item | Frozen value | State |
| --- | --- | --- |
| `main` | `ae4a323af49aa1f6aec8b1582d865a01898d26d7` | PR #300 integrated |
| PR #301 | `b724dc6f4b07cd62e02d2650e60110c128328025` | open / Draft / not merged / mergeable |
| PR #301 base | `ae4a323af49aa1f6aec8b1582d865a01898d26d7` | exact `main` binding |
| PR #301 CI | run `31321846342` | completed / success |

PR #301 is titled `Fix N3-W P5 M04 direct relay datagram cache priming`. Its
exact scope is four files:

- `.github/workflows/n3w-p5-m04-direct-relay-datagram-cache-priming-hostonly-repair-ci.yml`;
- `firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.cpp`;
- `firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.h`;
- `tests/n3w_p5/test_n3w_p5_liveness_contract.py`.

The pause archive is deliberately kept out of PR #301 so its exact-scope gate and
reviewable implementation diff remain unchanged.

## Development outcome retained in Git

PR #300, now present in the frozen `main`, repaired two prerequisites for cached
ESP-NOW resend:

1. ESP-NOW reuses the already connected Wi-Fi station radio state rather than
   attempting an invalid channel mutation;
2. send-callback observability is deferred out of the Wi-Fi callback and processed
   in normal component context.

The subsequent M04 attempt established a second root cause: after a board restart,
the volatile cached Relay datagram list is empty, while successful Direct telemetry
previously did not repopulate it. A RESEND therefore stopped at the empty-cache guard
before the repaired radio-readiness and send-observability paths could be exercised.

PR #301 implements the host-only repair:

1. Direct telemetry constructs the Relay-form authenticated frame and fragments for
   the exact same canonical tuple;
2. those pending datagrams are committed to `last_datagrams_` only after the Direct
   MQTT publish reports success;
3. an MQTT publish failure preserves the previously successful resend cache;
4. Direct cache priming performs no ESP-NOW send and does not enqueue the normal
   Relay retry cache;
5. the Relay path reuses the same frame-building helper and commits
   `last_datagrams_` only after retry-cache enqueue succeeds.

The transactional ordering is important: RESEND must never expose a tuple as the
last successfully published Direct tuple unless that tuple was actually accepted by
the Direct MQTT publish call.

## Validation checkpoint

At exact PR #301 head `b724dc6f4b07cd62e02d2650e60110c128328025`:

- 18 focused host-only preparation and liveness contract tests passed;
- Ruff lint and formatting checks passed;
- Child ESP32-C6 configuration and compile-only validation passed;
- Relay ESP32-C6 configuration and compile-only validation passed;
- dedicated GitHub Actions run `31321846342` completed successfully;
- general public repository, Manager, and isolated CI checks associated with the
  exact head also completed successfully where applicable.

These results prove the checked-in contracts and compile targets only. They do not
constitute M04 live acceptance or physical-board validation of the PR #301 code.

## Live and physical terminal state

- M03 remains terminal PASS and is historical input to M04.
- M04 is **not accepted**.
- The latest M04 successor execution authorization is `CONSUMED_FAILED` and is not
  replayable.
- Exactly one authorized RESEND was consumed in that failed attempt. It must not be
  repeated under the same authorization.
- PR #301 has not been merged and its code has not been installed on the boards.
- The last operator report kept both boards on their unchanged Mac USB-only power
  arrangement, with the Relay independent supply disconnected.
- No board, cable, power, serial, Flash, MQTT publish, path-control, RESEND, or live
  service action occurred during PR #301 host-only development or this archive.

The operator-reported physical state is historical and was not re-probed by this
archive. It must be freshly rebaselined before any later physical or live action.

## Public/private boundary

This public archive intentionally contains no credentials, application keys, session
material, production network address, board MAC address, Factory-image digest,
private execution-package digest, private evidence digest, raw live trace, private
filesystem path, or replayable authorization string.

All private Factory, package, terminal, device-identity, and live-evidence bindings
remain in the private evidence boundary and must be verified there before any future
package preparation or execution. They must not be reconstructed from this public
document.

## Resume sequence

Resume work in the following order:

1. perform a fresh read-only drift review of `main`, PR #301 exact head and base,
   PR state, and the exact-head CI result;
2. re-review the PR #301 transactional cache-commit implementation and its four-file
   exact scope;
3. obtain separate authorization before any PR status update, Ready transition, or
   merge;
4. after an authorized merge, rebaseline the new exact `main` and determine the
   required Factory/package replacement from private bindings;
5. obtain separate authorization for package preparation and separate authorization
   for each physical firmware action;
6. only after both boards run the exact repaired build may a new M04 package and a
   new exactly-one-RESEND execution authorization be prepared;
7. close M04 from new live evidence before considering M05.

## Stop conditions and prohibited actions

Stop immediately on any Git, PR, CI, private-binding, device-identity, power-state,
or service-state drift. Do not infer authorization from this handoff.

While this checkpoint remains paused:

- do not Ready or merge PR #301;
- do not delete its branch;
- do not generate, claim, or execute a live package;
- do not replay the consumed RESEND;
- do not access boards or serial ports, Flash, erase, reset, or change power;
- do not publish MQTT or send PATH commands;
- do not restart or modify Manager, Broker, or Home Assistant;
- do not enter M05.

The next valid action is a read-only drift rebaseline under a new, explicit scope.
