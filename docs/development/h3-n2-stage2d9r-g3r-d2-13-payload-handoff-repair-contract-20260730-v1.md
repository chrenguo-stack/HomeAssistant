# H3/N2 Stage 2D-9R G3R D2-13 payload handoff repair contract

## Approved decision

`D1-H3N2-STAGE2D9R-G3R-D2-13-PAYLOAD-HANDOFF-REPAIR-20260730-01`

## Purpose

D2-12 terminated before authorization claim and before any board, USB, serial,
esptool, Flash, Broker, PREPARE or VERIFY operation. The private outer runner
invoked the public inner entrypoint without the two payload TAR arguments required
by the inherited parser. The parser returned code 2 before a physical result file
could be written.

D2-12 is permanently non-replayable. This successor creates a new unauthorized
D2-13 request and package identity. It does not reuse the D2-12 request, private
package, authorization, physical decision, closure or package.

## Repair

The official shell launcher:

1. disables Python bytecode before the first Python process;
2. resolves its own directory with physical-path semantics (`pwd -P`);
3. exports that directory as `GH_D2_13_LAUNCHER_PACKAGE_ROOT`;
4. is invoked through `/bin/sh` while remaining mode `0600` inside the frozen execution package, matching the inherited executor contract;
5. invokes only the D2-13 Python wrapper.

The host-only `handoff-check` command exercises the same shell-to-Python binding without authorization or physical access.

Before the inherited parser runs, the Python wrapper:

1. obtains and normalizes `--package-root`;
2. independently normalizes the launcher-provided package root;
3. requires both roots to be identical;
4. binds the immutable and locked-recovery TAR files to fixed basenames inside
   that package root;
5. injects missing `--immutable-payload-tar` and `--recovery-payload-tar`
   arguments;
6. rejects duplicate, conflicting, symlinked or missing payload paths.

This removes the private outer runner's responsibility for forwarding public
payload paths while keeping the public package as the only source of payload
identity.

## macOS path normalization

All path comparisons use expanded, resolved physical paths. A package reached
through a Finder-style path containing spaces or through a symlink alias resolves
to the same physical package root. A conflicting payload outside that root is
rejected before authorization claim.

## Preclaim evidence

A handoff failure detected before the inherited parser writes a result is required
to emit a stable preclaim result whenever `--result-output` is recoverable from
the command line. When an authorization record already exists, the failure is
fail-closed as `CONSUMED_FAILED_PRECLAIM`, with authorization claimed false and
all physical-operation flags false. A matching marker is written when a state
root is available.

## D2-12 terminal disposition

The public review records only redacted facts:

- status: `CONSUMED_FAILED_OR_STOPPED`;
- failure: `OUTER_TO_INNER_PAYLOAD_HANDOFF_ARGUMENTS_MISSING`;
- return code: 2;
- no physical result file;
- no authorization marker;
- authorization claimed and consumed: false;
- board/USB/serial/esptool/Flash/network operations: false;
- no private paths or secret values.

## D2-13 request state

The generated request is intentionally unauthorized:

- `authorized=false`;
- `authorization_created=false`;
- `authorization_claimed=false`;
- `authorization_consumed=false`;
- one shot and no automatic retry;
- ACTIVATE, CLEANUP and production operation unauthorized.

## Validation requirements

The dedicated CI must verify:

- exact stacking on PR #210 HEAD `ad64fcca8ddeeb06bec2d3c379fc3c2c6b669af2`;
- PR #210 and its load-bearing Artifact are unchanged and current;
- deterministic review generation in two lanes;
- real shell integration with payload arguments omitted by the caller;
- macOS-style spaces and symlink normalization;
- conflicting payload paths fail closed;
- authorization-created, claim-before failure evidence is stable;
- D2-12 is permanently non-replayable;
- no authorization JSON, private path, secret, symlink or Python bytecode enters
  the public Artifact.

## Out of scope

This decision does not authorize private package creation, physical authorization,
board connection, USB enumeration, serial access, esptool, Flash/NVS, Broker,
PREPARE, VERIFY, recovery, ACTIVATE, CLEANUP, Ready, merge, release, tag or
deployment.
